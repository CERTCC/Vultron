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
``Reject(CaseLedgerEntry)`` or by the position a ``Read(CaseLedgerEntry)``
states (SYNC-03-002, SYNC-17-004).  The fan-out nodes that used to live here — the
distribution of a single entry to every recipient — now sit in ``fanout.py``
alongside their RM.CLOSED-filtered variants (BTND-07-004), and the genesis
pre-seed ``AnnounceCaseOnGenesisRejectNode`` sits in ``genesis_announce.py``
(CS-18-001).
"""

from __future__ import annotations

import logging
from typing import cast

import py_trees
from py_trees.common import Status
from py_trees.ports import NoDataAvailable

from vultron.core.behaviors.helpers import (
    DataLayerActionWithPorts,
    PortInformation,
)
from vultron.core.behaviors.sync.nodes.embargo_pause import (
    LedgerSuffixSend,
    clear_embargo_pause,
    closed_peer_cutoff,
    peer_is_inactive_joined,
    peer_is_withheld,
    record_embargo_pause,
    send_ledger_suffix,
    sorted_case_ledger_entries,
)
from vultron.core.behaviors.sync.nodes.replay_case import (
    CaseNamedReplayNode,
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


class FindCaseActorNode(CaseNamedReplayNode):
    """Resolve the authority's address, and publish the case id for later gates.

    The address is the ``CVDRole.CASE_MANAGER`` role-holder's, resolved through
    the single neutral resolver (ADR-0088, ARCH-24-001), never a ``Service``
    whose ``context`` is the case (ARCH-24-004).  This node resolves an
    *address*; it does not decide authority, which is the CASE_MANAGER gate
    the factory wraps around the effects (ARCH-24-005).  The case is
    *case_id* when the tree names it, else the activity's ``replay_case_id``.

    ``case_id`` is an output so a later node can read the case from the
    blackboard (CLP-09); ``CheckIsCaseManagerNode`` falls back to it when it
    is built without a case id.

    Failing is deliberate: a FAILURE stops the sequence, so no replay runs
    under a guessed identity.  It means the executing actor cannot answer for
    this log: it does not hold the case, or the case names no CASE_MANAGER.
    """

    INPUT_PORTS: dict[str, PortInformation] = {
        **DataLayerActionWithPorts.INPUT_PORTS,
        "activity": PortInformation(data_type=object, required=True),
    }

    # See the class docstring: ``case_id`` is published for later nodes.
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
        case_id = self.replay_case(self.activity)
        self._set_output("case_id", case_id)

        # Regime 1 (ADR-0087): a peer is asking us to replay this case's log,
        # so the case must be here — its absence is an anomaly, not a branch.
        case, failure = self._require_case(case_id)
        if failure is not None:
            return failure

        case_actor_id = resolve_case_manager_id(case, self.datalayer)
        if case_actor_id is None:
            self.logger.warning(
                "%s: no CASE_MANAGER participant for case '%s'",
                self.name,
                case_id,
            )
            return Status.FAILURE

        self._set_output("case_actor_id", case_actor_id)
        return Status.SUCCESS


class CollectAndSortCaseLedgerEntriesNode(CaseNamedReplayNode):
    """Publish the case's sorted ledger and the peer (the activity's sender).

    The case is *case_id* when given, else the activity's ``replay_case_id``.
    """

    INPUT_PORTS: dict[str, PortInformation] = {
        **DataLayerActionWithPorts.INPUT_PORTS,
        "activity": PortInformation(data_type=object, required=True),
    }

    OUTPUT_PORTS: dict[str, PortInformation] = {
        "replay_case_id": PortInformation(data_type=str, required=True),
        "replay_peer_id": PortInformation(data_type=str, required=True),
        "replay_case_ledger_entries": PortInformation(
            data_type=object, required=True
        ),
    }

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {
            "activity": "/activity",
            "replay_case_id": "/replay_case_id",
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
        case_id = self.replay_case(activity)
        peer_id = activity.actor_id
        if not peer_id:
            raise VultronError(
                f"{self.name}: replay request missing peer actor_id"
            )

        entries = sorted_case_ledger_entries(
            cast(CasePersistence, self.datalayer), case_id
        )

        self._set_output("replay_case_id", case_id)
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
    """Replay the ledger suffix a peer's ``Reject`` or ``Read`` leaves it short of.

    A ``Reject(CaseLedgerEntry)`` asks for it (SYNC-03-002); a
    ``Read(CaseLedgerEntry)`` states a position behind the tail (SYNC-17-004).

    A peer that is not an active participant (CM-10-004) is sent nothing.
    When it is a joined participant that is not active (the active embargo
    withholds it, or it was removed, CM-31-001), its stream is paused from
    the first entry it asked for, and the backfill that admits it starts there
    (CM-10-005, CM-10-006). An admitted peer's
    replay clears any recorded pause: it resends everything past the
    contiguous prefix the peer reports holding (SYNC-10-004), so nothing
    withheld is left to backfill.

    The replay stops at the first entry whose hash does not verify
    (SYNC-03-009): the entries before it are queued, it and every later one
    are not, and the node returns ``FAILURE`` (BT-14-001).  The cooldown
    still records a replay that queued at least one entry (SYNC-15-011), and
    a recorded pause stays, since the suffix was not all sent.
    """

    def __init__(self, name: str | None = None) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self._sync_port: SyncActivityPort | None = None

    INPUT_PORTS: dict[str, PortInformation] = {
        **DataLayerActionWithPorts.INPUT_PORTS,
        "case_actor_id": PortInformation(data_type=str, required=True),
        "replay_case_id": PortInformation(data_type=str, required=True),
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
            "replay_case_id": "/replay_case_id",
            "replay_peer_id": "/replay_peer_id",
            "replay_case_ledger_entries": "/replay_case_ledger_entries",
            "replay_from_index": "/replay_from_index",
            "sync_port": "/sync_port",
        }

    def initialise(self) -> None:
        super().initialise()
        self.case_actor_id_bb: str = self.get_input("case_actor_id")
        self.replay_case_id: str = self.get_input("replay_case_id")
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

        case_id = self.replay_case_id
        peer_id = cast(str, self.replay_peer_id)
        entries = cast(list[CaseLedgerEntry], self.replay_case_ledger_entries)
        from_index = cast(int, self.replay_from_index)
        datalayer = cast(CasePersistence, self.datalayer)

        # CM-10-005: replay is case content too. A peer that is not an active
        # participant gets nothing — not even the gap it asked for — and when
        # it is joined but not active (embargo-withheld or removed), its
        # pause starts at that gap.
        try:
            withheld = peer_is_withheld(
                datalayer, case_id=case_id, peer_id=peer_id
            )
            paused = withheld and peer_is_inactive_joined(
                datalayer, case_id=case_id, peer_id=peer_id
            )
            # CM-23-004: a peer at RM.CLOSED is owed the entries that record
            # its own closure and nothing after them, so its replay stops at
            # the last of those, as its fan-out did.
            cutoff = (
                None
                if withheld
                else closed_peer_cutoff(
                    datalayer,
                    case_id=case_id,
                    peer_id=peer_id,
                    entries=entries,
                )
            )
        except VultronError as exc:
            self.feedback_message = str(exc)
            self.logger.exception("%s: embargo gate undecidable", self.name)
            return Status.FAILURE
        if withheld:
            if paused:
                record_embargo_pause(
                    datalayer,
                    case_id=case_id,
                    peer_id=peer_id,
                    from_index=from_index + 1,
                )
            self.logger.info(
                "%s: peer '%s' is not an active participant of case"
                " '%s'; replay withheld (CM-10-004, CM-10-005)",
                self.name,
                peer_id,
                case_id,
            )
            return Status.SUCCESS
        if cutoff is not None and cutoff <= from_index:
            self.logger.info(
                "%s: peer '%s' is at RM.CLOSED in case '%s' and holds every"
                " entry recording its own closure; nothing replayed"
                " (CM-23-004)",
                self.name,
                peer_id,
                case_id,
            )
            return Status.SUCCESS

        # SYNC-15-003: rate-limit no-progress replays.  A peer that cannot
        # anchor its hash chain re-Rejects every entry we replay; replaying the
        # full ledger again on each Reject is a self-sustaining amplification
        # loop that starves the actor.
        from_hash = replay_from_hash(entries, from_index)
        if not should_replay(
            cast(CasePersistence, self.datalayer),
            case_id=case_id,
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
        sent = send_ledger_suffix(
            self._sync_port,
            entries,
            after_index=from_index,
            actor_id=self.case_actor_id_bb,
            peer_id=peer_id,
            through_index=cutoff,
        )
        return self._record_replay_outcome(
            sent, case_id=case_id, peer_id=peer_id, from_hash=from_hash
        )

    def _record_replay_outcome(
        self,
        sent: LedgerSuffixSend,
        *,
        case_id: str,
        peer_id: str,
        from_hash: str,
    ) -> Status:
        """Update the pause and the cooldown for a replay, and report it."""
        datalayer = cast(CasePersistence, self.datalayer)
        # An admitted peer's replay ends any pause. A suffix past the paused
        # index needs no resend either: the Reject reports a contiguous prefix
        # through from_index (SYNC-10-004), so the replica already holds every
        # entry withheld below it.  A replay held back at a broken entry
        # (SYNC-03-009) has not sent the suffix, so the pause stays, as it
        # does for a held-back admission backfill.
        if sent.held_back is None:
            clear_embargo_pause(datalayer, case_id=case_id, peer_id=peer_id)

        # Record the position only when entries actually went out; a
        # zero-entry replay must not start a cooldown (SYNC-15-003).
        if sent.sent:
            record_replay(
                datalayer,
                case_id=case_id,
                peer_id=peer_id,
                from_hash=from_hash,
            )

        self.logger.info(
            "%s: replayed %d entries to peer '%s' for case '%s'"
            " (%d already pending in outbox, not re-queued — SYNC-15-012)",
            self.name,
            sent.sent,
            peer_id,
            case_id,
            sent.already_pending,
        )
        if sent.held_back is not None:
            # SYNC-03-009, BT-14-001: the replay stopped at an entry that
            # does not verify, so it is not reported as delivered.
            # send_ledger_suffix already logged the hold-back at ERROR.
            self.feedback_message = str(sent.held_back)
            return Status.FAILURE
        return Status.SUCCESS


class ReplayMissingEntriesNode(py_trees.composites.Sequence):
    """Replay the entries after the sender's stated position (SYNC-03-002).

    The case is *case_id* when given, else the activity's ``replay_case_id``.
    """

    def __init__(
        self, name: str | None = None, *, case_id: str | None = None
    ) -> None:
        super().__init__(
            name=name or self.__class__.__name__,
            memory=False,
            children=[
                CollectAndSortCaseLedgerEntriesNode(
                    name="CollectAndSortCaseLedgerEntries", case_id=case_id
                ),
                FindDivergenceIndexNode(name="FindDivergenceIndex"),
                SendMissingEntriesNode(name="SendMissingEntries"),
            ],
        )
