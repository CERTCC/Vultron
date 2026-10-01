#!/usr/bin/env python
#
#  Copyright (c) 2026 Carnegie Mellon University and Contributors.
#  - see Contributors.md for a full list of Contributors
#  - see ContributionInstructions.md for information on how you can Contribute to this project
#  Vultron Multiparty Coordinated Vulnerability Disclosure Protocol Prototype is
#  licensed under a MIT (SEI)-style license, please see LICENSE.md distributed
#  with this Software or contact permission@sei.cmu.edu for full terms.
#  Created, in part, with funding and support from the United States Government
#  (see Acknowledgments file). This program may include and/or can make use of
#  certain third party source code, object code, documentation and other files
#  ("Third Party Software"). See LICENSE.md for more details.
#  Carnegie Mellon®, CERT® and CERT Coordination Center® are registered in the
#  U.S. Patent and Trademark Office by Carnegie Mellon University
"""Action nodes for SYNC log-replication replay.

Replay is catch-up for one peer that has fallen behind, driven by an inbound
``Reject(CaseLedgerEntry)``.  The fan-out nodes that used to live here — the
distribution of a single entry to every recipient — now sit in ``fanout.py``
alongside their RM.CLOSED-filtered variants (BTND-07-004), and the genesis
pre-seed ``AnnounceCaseOnGenesisRejectNode`` sits in ``genesis_announce.py``
(CS-18-001).
"""

from __future__ import annotations

import logging
from typing import Any, cast

import py_trees
from py_trees.common import Status
from py_trees.ports import NoDataAvailable

from vultron.core.behaviors.helpers import (
    DataLayerActionWithPorts,
    PortInformation,
)
from vultron.core.behaviors.sync.nodes.embargo_pause import (
    clear_embargo_pause,
    peer_is_withheld,
    record_embargo_pause,
    send_ledger_suffix,
    sorted_case_ledger_entries,
)
from vultron.core.behaviors.sync.nodes.replay_guard import (
    record_replay,
    replay_from_hash,
    should_replay,
)
from vultron.core.models.case_ledger_entry import (
    CaseLedgerEntry,
)
from vultron.core.participants.authority import resolve_case_manager_id
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.ports.sync_activity import SyncActivityPort
from vultron.errors import (
    VultronError,
    VultronWiringError,
)

logger = logging.getLogger(__name__)


def _require_rejected_entry(activity: Any, node_name: str) -> CaseLedgerEntry:
    entry = getattr(activity, "rejected_entry", None)
    if entry is None:
        entry = getattr(activity, "object_", None)
    if isinstance(entry, CaseLedgerEntry):
        return entry
    raise VultronError(
        f"{node_name}: activity did not carry a rejected CaseLedgerEntry"
    )


class FindCaseActorNode(DataLayerActionWithPorts):
    """Resolve the authority's address, and publish the case id for later gates.

    The address is the ``CVDRole.CASE_MANAGER`` role-holder's, resolved through
    the single neutral resolver (ADR-0088, ARCH-24-001). It used to come from a
    module-local ``_find_case_actor`` that scanned for a ``Service`` whose
    ``context`` was the case id — a hosting-location signal ARCH-24-004 forbids,
    and one that answered ``None`` during the bootstrap window before any
    ``Service`` carries ``context`` (CM-02-012). Worse, that helper fell back to
    *the first arbitrary* ``Service`` in the store when nothing matched, so a
    miss produced a plausible-looking wrong address rather than a failure.

    This node resolves an *address*; it does not decide authority. The genesis
    pre-seed's authority gate is the separate ``CheckIsCaseManagerNode`` in
    ``create_reject_log_entry_tree`` (ARCH-24-005).

    ``case_id`` is an output because ``CheckIsCaseManagerNode`` reads it from the
    blackboard (CLP-09). Without it the role gate on the genesis pre-seed could
    not resolve a case, returned FAILURE, and the guard's selector silently took
    its skip branch — so the announce never fired for *anyone*, case manager or
    not. This node already derives the value from the rejected entry, so it is
    the right place to publish it. It also means this node cannot be moved after
    the pre-seed arm: that arm does not read ``case_actor_id``, but it does need
    the ``case_id`` published here.

    Failing is deliberate, and is not the regression it resembles. A FAILURE here
    stops the sequence, so neither the pre-seed nor the replay runs. The retired
    fallback did let both proceed — but as *the wrong actor*, since it answered
    with an arbitrary ``Service``, and a replay emitted under a foreign identity
    is worse than one that did not happen. Both remaining failure modes mean the
    executing actor cannot legitimately answer for this log: it does not hold the
    case, or the case names no CASE_MANAGER. Neither is routine for an actor
    fielding a ``Reject`` about a log it owns.
    """

    INPUT_PORTS: dict[str, PortInformation] = {
        **DataLayerActionWithPorts.INPUT_PORTS,
        "activity": PortInformation(data_type=object, required=True),
    }

    # See the class docstring: the role gate downstream needs this.
    OUTPUT_PORTS: dict[str, PortInformation] = {
        "case_actor_id": PortInformation(data_type=str, required=True),
        "case_id": PortInformation(data_type=str, required=True),
    }

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {
            "activity": "/activity",
            "case_actor_id": "/case_actor_id",
            "case_id": "/case_id",
        }

    def initialise(self) -> None:
        super().initialise()
        self.activity = self.get_input("activity")

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None
        entry = _require_rejected_entry(self.activity, self.name)
        self._set_output("case_id", entry.case_id)

        # Regime 1 (ADR-0087): a peer is asking us to replay this case's log,
        # so the case must be here — its absence is an anomaly, not a branch.
        case, failure = self._require_case(entry.case_id)
        if failure is not None:
            return failure

        case_actor_id = resolve_case_manager_id(case, self.datalayer)
        if case_actor_id is None:
            self.logger.warning(
                "%s: no CASE_MANAGER participant for case '%s'",
                self.name,
                entry.case_id,
            )
            return Status.FAILURE

        self._set_output("case_actor_id", case_actor_id)
        return Status.SUCCESS


class CollectAndSortCaseLedgerEntriesNode(DataLayerActionWithPorts):
    INPUT_PORTS: dict[str, PortInformation] = {
        **DataLayerActionWithPorts.INPUT_PORTS,
        "activity": PortInformation(data_type=object, required=True),
    }

    OUTPUT_PORTS: dict[str, PortInformation] = {
        "replay_entry": PortInformation(
            data_type=CaseLedgerEntry, required=True
        ),
        "replay_peer_id": PortInformation(data_type=str, required=True),
        "replay_case_ledger_entries": PortInformation(
            data_type=object, required=True
        ),
    }

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {
            "activity": "/activity",
            "replay_entry": "/replay_entry",
            "replay_peer_id": "/replay_peer_id",
            "replay_case_ledger_entries": "/replay_case_ledger_entries",
        }

    def initialise(self) -> None:
        super().initialise()
        self.activity = self.get_input("activity")

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None
        activity = self.activity
        entry = _require_rejected_entry(activity, self.name)
        peer_id = activity.actor_id
        if not peer_id:
            raise VultronError(
                f"{self.name}: Reject(CaseLedgerEntry) missing peer actor_id"
            )

        entries = sorted_case_ledger_entries(
            cast(CasePersistence, self.datalayer), entry.case_id
        )

        self._set_output("replay_entry", entry)
        self._set_output("replay_peer_id", peer_id)
        self._set_output("replay_case_ledger_entries", entries)
        return Status.SUCCESS


class FindDivergenceIndexNode(DataLayerActionWithPorts):
    INPUT_PORTS: dict[str, PortInformation] = {
        **DataLayerActionWithPorts.INPUT_PORTS,
        "activity": PortInformation(data_type=object, required=True),
        "replay_case_ledger_entries": PortInformation(
            data_type=object, required=True
        ),
    }

    OUTPUT_PORTS: dict[str, PortInformation] = {
        "replay_from_index": PortInformation(data_type=int, required=True),
    }

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {
            "activity": "/activity",
            "replay_case_ledger_entries": "/replay_case_ledger_entries",
            "replay_from_index": "/replay_from_index",
        }

    def initialise(self) -> None:
        super().initialise()
        self.activity = self.get_input("activity")
        self.replay_case_ledger_entries = self.get_input(
            "replay_case_ledger_entries"
        )

    def update(self) -> Status:
        entries = cast(list[CaseLedgerEntry], self.replay_case_ledger_entries)
        from_hash = self.activity.last_accepted_hash
        from_index = -1
        for log_entry in entries:
            if log_entry.entry_hash == from_hash:
                from_index = log_entry.log_index
                break

        self._set_output("replay_from_index", from_index)
        return Status.SUCCESS


class SendMissingEntriesNode(DataLayerActionWithPorts):
    """Replay the ledger suffix a peer's ``Reject(CaseLedgerEntry)`` asks for.

    A peer the CM-10-004 embargo gate withholds content from is sent nothing:
    its stream is paused from the first entry it asked for, and the backfill
    that admits it starts there (CM-10-005, CM-10-006). An admitted peer's
    replay clears any recorded pause: it resends everything past the
    contiguous prefix the peer reports holding (SYNC-10-004), so nothing
    withheld is left to backfill.
    """

    def __init__(self, name: str | None = None) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self._sync_port: SyncActivityPort | None = None

    INPUT_PORTS: dict[str, PortInformation] = {
        **DataLayerActionWithPorts.INPUT_PORTS,
        "case_actor_id": PortInformation(data_type=str, required=True),
        "replay_entry": PortInformation(
            data_type=CaseLedgerEntry, required=True
        ),
        "replay_peer_id": PortInformation(data_type=str, required=True),
        "replay_case_ledger_entries": PortInformation(
            data_type=object, required=True
        ),
        "replay_from_index": PortInformation(data_type=int, required=True),
        "sync_port": PortInformation(data_type=object, required=False),
    }

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {
            "case_actor_id": "/case_actor_id",
            "replay_entry": "/replay_entry",
            "replay_peer_id": "/replay_peer_id",
            "replay_case_ledger_entries": "/replay_case_ledger_entries",
            "replay_from_index": "/replay_from_index",
            "sync_port": "/sync_port",
        }

    def initialise(self) -> None:
        super().initialise()
        self.case_actor_id_bb: str = self.get_input("case_actor_id")
        self.replay_entry = self.get_input("replay_entry")
        self.replay_peer_id: str = self.get_input("replay_peer_id")
        self.replay_case_ledger_entries = self.get_input(
            "replay_case_ledger_entries"
        )
        self.replay_from_index: int = self.get_input("replay_from_index")
        try:
            self._sync_port = cast(
                SyncActivityPort, self.get_input("sync_port")
            )
        except (NoDataAvailable, NotImplementedError):
            self._sync_port = None

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None
        if self._sync_port is None:
            raise VultronWiringError(
                f"{self.name}: sync_port must be injected to replay entries"
            )

        entry = cast(CaseLedgerEntry, self.replay_entry)
        peer_id = cast(str, self.replay_peer_id)
        entries = cast(list[CaseLedgerEntry], self.replay_case_ledger_entries)
        from_index = cast(int, self.replay_from_index)
        datalayer = cast(CasePersistence, self.datalayer)

        # CM-10-005: replay is case content too. A withheld peer gets nothing
        # — not even the gap it asked for — and its pause starts at that gap.
        try:
            withheld = peer_is_withheld(
                datalayer, case_id=entry.case_id, peer_id=peer_id
            )
        except VultronError as exc:
            self.feedback_message = str(exc)
            self.logger.exception("%s: embargo gate undecidable", self.name)
            return Status.FAILURE
        if withheld:
            record_embargo_pause(
                datalayer,
                case_id=entry.case_id,
                peer_id=peer_id,
                from_index=from_index + 1,
            )
            self.logger.info(
                "%s: peer '%s' has not accepted the active embargo on case"
                " '%s'; replay withheld (CM-10-005)",
                self.name,
                peer_id,
                entry.case_id,
            )
            return Status.SUCCESS

        # SYNC-15-003: rate-limit no-progress replays.  A peer that cannot
        # anchor its hash chain re-Rejects every entry we replay; replaying the
        # full ledger again on each Reject is a self-sustaining amplification
        # loop that starves the actor.
        from_hash = replay_from_hash(entries, from_index)
        if not should_replay(
            cast(CasePersistence, self.datalayer),
            case_id=entry.case_id,
            peer_id=peer_id,
            from_hash=from_hash,
            log=self.logger,
            node_name=self.name,
        ):
            return Status.SUCCESS

        # SYNC-15-012: a Reject that arrives after the peer's gap already
        # drained still replays (its position advanced), but the suffix it
        # asks for may already sit in the outbox from the previous replay.
        # The sync port declines to queue a row it already holds for this
        # peer and says so, so only rows actually queued count as sent
        # (SYNC-15-011, #3602).
        replayed, skipped = send_ledger_suffix(
            self._sync_port,
            entries,
            after_index=from_index,
            actor_id=self.case_actor_id_bb,
            peer_id=peer_id,
        )
        # An admitted peer's replay ends any pause. A suffix past the paused
        # index needs no resend either: the Reject reports a contiguous prefix
        # through from_index (SYNC-10-004), so the replica already holds every
        # entry withheld below it.
        clear_embargo_pause(datalayer, case_id=entry.case_id, peer_id=peer_id)

        # Record the position only when entries actually went out; a
        # zero-entry replay must not start a cooldown (SYNC-15-003).
        if replayed:
            record_replay(
                cast(CasePersistence, self.datalayer),
                case_id=entry.case_id,
                peer_id=peer_id,
                from_hash=from_hash,
            )

        self.logger.info(
            "%s: replayed %d entries to peer '%s' for case '%s'"
            " (%d already pending in outbox, not re-queued — SYNC-15-012)",
            self.name,
            replayed,
            peer_id,
            entry.case_id,
            skipped,
        )
        return Status.SUCCESS


class ReplayMissingEntriesNode(py_trees.composites.Sequence):
    def __init__(self, name: str | None = None) -> None:
        super().__init__(
            name=name or self.__class__.__name__,
            memory=False,
            children=[
                CollectAndSortCaseLedgerEntriesNode(
                    name="CollectAndSortCaseLedgerEntries"
                ),
                FindDivergenceIndexNode(name="FindDivergenceIndex"),
                SendMissingEntriesNode(name="SendMissingEntries"),
            ],
        )
