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
"""The CASE_MANAGER's re-seed of a peer with a fresh case copy (SYNC-16-003).

A re-seed is ``Announce(VulnerabilityCase)`` of the CASE_MANAGER's current
case, sent to one peer.  The copy names the case's ledger position
(SYNC-16-005), so the peer can replace its case file and backfill whatever
its chain lacks (SYNC-16-006, SYNC-16-007).

:class:`ReseedPeerNode` is the one re-seed send.  It is rate-bounded per peer
(:func:`should_reseed`, SYNC-16-004): the time and position of the last
re-seed are kept in the peer's persisted replication state
(:func:`record_reseed`, SYNC-04-002), and a re-seed asked for inside the
cooldown sends nothing.  The cooldown is a rate limit, never a suppression:
once it has passed the next request re-seeds, so a lost copy cannot strand a
peer (the choice SYNC-15-003 makes for replay).

:class:`ReportRepeatDivergenceNode` reads the same record: a divergence
fault for an entry the last re-seed's copy already reflected is logged at
ERROR when the peer has acknowledged that copy's position, since the
CASE_MANAGER's case then disagrees with its own ledger, and at WARNING
otherwise, since the copy may be lost or in flight (SYNC-16-008).

Neither node commits a ledger entry: a re-seed is replication signalling,
like the replay it resembles (SYNC-16-002).
"""

from __future__ import annotations

from typing import cast

from py_trees.common import Status

from vultron.core.behaviors.helpers import (
    DataLayerActionWithPorts,
    _EmitSingleActivityBase,
)
from vultron.core.behaviors.sync.nodes.embargo_pause import peer_is_withheld
from vultron.core.behaviors.sync.nodes.replay_guard import (
    _read_state,
    cooldown_elapsed,
    update_replication_state,
)
from vultron.core.models._helpers import _as_id, now_utc
from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.models.ledger_position import LedgerPosition
from vultron.core.models.replication_state import VultronReplicationState
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.ports.trigger_activity import TriggerActivityPort
from vultron.core.sync_helpers import sorted_case_ledger_entries
from vultron.errors import (
    VultronBTInternalError,
    VultronError,
    VultronNotFoundError,
)
from vultron.primitives import same_actor_id

__all__ = [
    "RESEED_COOLDOWN_SECONDS",
    "ReportRepeatDivergenceNode",
    "ReseedPeerNode",
    "announce_case_to_peer",
    "announced_ledger_entry",
    "record_reseed",
    "should_reseed",
]

#: Minimum interval between two re-seeds of one peer.  A diverged replica
#: faults once per entry it refuses, so without a bound every replayed entry
#: would earn another full case copy (SYNC-16-004).
RESEED_COOLDOWN_SECONDS: float = 30.0


def should_reseed(
    datalayer: CasePersistence, *, case_id: str, peer_id: str
) -> bool:
    """True unless *peer_id* was re-seeded within the cooldown.

    Read-only: :func:`record_reseed` records a re-seed once it is queued.

    Spec: SYNC-16-004.
    """
    state = _read_state(datalayer, case_id=case_id, peer_id=peer_id)
    return cooldown_elapsed(
        None if state is None else state.last_reseeded_at,
        RESEED_COOLDOWN_SECONDS,
    )


def record_reseed(
    datalayer: CasePersistence,
    *,
    case_id: str,
    peer_id: str,
    position: LedgerPosition,
) -> None:
    """Record that *peer_id* was just re-seeded with a copy at *position*.

    Kept in the peer's persisted replication state, beside its replay
    record, so the bound survives a restart (SYNC-04-002, SYNC-16-004).
    """
    now = now_utc()

    def _record(state: VultronReplicationState) -> None:
        state.last_reseeded_at = now
        state.last_reseed_position = position

    update_replication_state(
        datalayer, case_id=case_id, peer_id=peer_id, change=_record
    )


def announce_case_to_peer(
    factory: TriggerActivityPort, *, actor_id: str, case_id: str, peer_id: str
) -> str:
    """Build and store *actor_id*'s ``Announce(VulnerabilityCase)`` of
    *case_id* to *peer_id* alone; return its id.

    The one case-copy send the genesis pre-seed (SYNC-15-002) and the
    re-seed (SYNC-16-003) share.  The copy names the case's ledger position
    (SYNC-16-005).  Queueing it is the caller's.
    """
    return factory.announce_vulnerability_case(
        case_id=case_id, actor=actor_id, context_id=case_id, to=[peer_id]
    )


def announced_ledger_entry(
    datalayer: CasePersistence, announce_id: str, announcer_id: str
) -> CaseLedgerEntry:
    """The ``CaseLedgerEntry`` *announcer_id*'s ``Announce`` *announce_id* carried.

    A fault about a refused ledger entry names the refused
    ``Announce(CaseLedgerEntry)`` by reference and carries no case
    (ASK-07-004, ASK-07-006).  The CASE_MANAGER stored that ``Announce``
    when it sent it, so the entry, and with it the case and its index, is
    read from there.  Only an ``Announce`` *announcer_id* sent counts: one
    this store merely received names nothing *announcer_id* sent the peer.

    Raises:
        VultronNotFoundError: This store holds no ``Announce`` of a
            ``CaseLedgerEntry`` by *announcer_id* under *announce_id*.
    """
    activity = datalayer.read(announce_id)
    sender = _as_id(getattr(activity, "actor", None))
    if (
        getattr(activity, "type_", None) != "Announce"
        or not isinstance(sender, str)
        or not same_actor_id(sender, announcer_id)
    ):
        raise VultronNotFoundError("Announce(CaseLedgerEntry)", announce_id)
    entry: object = getattr(activity, "object_", None)
    if isinstance(entry, str):
        entry = datalayer.read(entry)
    if not isinstance(entry, CaseLedgerEntry):
        raise VultronNotFoundError("Announce(CaseLedgerEntry)", announce_id)
    return entry


class ReseedPeerNode(_EmitSingleActivityBase):
    """Send *peer_id* ``Announce(VulnerabilityCase)`` of *case_id*, rate-bounded.

    Returns SUCCESS whether or not it sends, and says which it was:
    ``withheld`` when the peer is not an active participant, so it is sent
    no case content (CM-10-004); ``rate_limited`` when the peer was
    re-seeded within the cooldown (SYNC-16-004); ``reseeded`` when this run
    queued a copy.  The copy, its outbox entry and the record of its ledger
    position (:func:`record_reseed`) are written in one transaction, so a
    copy is never queued unrecorded nor recorded unqueued.

    Returns FAILURE when the gate cannot be decided because this store holds
    no such case.  A copy the trigger-activity port cannot build is this
    actor's own fault, never the peer's, so it raises
    :class:`~vultron.errors.VultronBTInternalError` with nothing written
    (BT-14-001).

    Authored as the executing actor; it belongs inside a CASE_MANAGER gate
    (BT-17-008).

    Spec: SYNC-16-003, SYNC-16-004, PCR-02-001.
    """

    def __init__(
        self, case_id: str, peer_id: str, name: str | None = None
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.case_id = case_id
        self.peer_id = peer_id
        self.reseeded = False
        """True when the last run queued the case copy."""
        self.withheld = False
        """True when the last run found the peer not an active participant."""
        self.rate_limited = False
        """True when the last run found the peer inside the cooldown."""

    def update(self) -> Status:
        self.reseeded = self.withheld = self.rate_limited = False
        if (f := self._require_datalayer_and_actor()) is not None:
            return f
        assert self.actor_id is not None
        datalayer = cast(CasePersistence, self.datalayer)
        try:
            self.withheld = peer_is_withheld(
                datalayer, case_id=self.case_id, peer_id=self.peer_id
            )
        except VultronError as exc:
            self.feedback_message = str(exc)
            self.logger.exception("%s: embargo gate undecidable", self.name)
            return Status.FAILURE
        if self.withheld:
            self.logger.info(
                "%s: peer '%s' is not an active participant of case '%s';"
                " sending it no case copy (CM-10-004)",
                self.name,
                self.peer_id,
                self.case_id,
            )
            return Status.SUCCESS
        if not should_reseed(
            datalayer, case_id=self.case_id, peer_id=self.peer_id
        ):
            self.rate_limited = True
            self.logger.info(
                "%s: peer '%s' was re-seeded with case '%s' less than %.0fs"
                " ago; not re-seeding it again yet (SYNC-16-004)",
                self.name,
                self.peer_id,
                self.case_id,
                RESEED_COOLDOWN_SECONDS,
            )
            return Status.SUCCESS
        case, failure = self._require_case(self.case_id)
        if failure is not None:
            return failure
        factory = self._require_trigger_activity_port()
        position = case.ledger_position
        try:
            with datalayer.transaction():
                activity_id = announce_case_to_peer(
                    factory,
                    actor_id=self.actor_id,
                    case_id=self.case_id,
                    peer_id=self.peer_id,
                )
                self._emit_through_seam(activity_id, "")
                record_reseed(
                    datalayer,
                    case_id=self.case_id,
                    peer_id=self.peer_id,
                    position=position,
                )
        except VultronError as exc:
            raise VultronBTInternalError(
                f"{self.name}: could not re-seed peer '{self.peer_id}' with"
                f" case '{self.case_id}': {exc}"
            ) from exc
        self.reseeded = True
        self.logger.info(
            "%s: re-seeded peer '%s' with Announce(VulnerabilityCase) '%s' of"
            " case '%s' at ledger position %d (SYNC-16-003)",
            self.name,
            self.peer_id,
            activity_id,
            self.case_id,
            position.log_index,
        )
        return Status.SUCCESS


class ReportRepeatDivergenceNode(DataLayerActionWithPorts):
    """Log a divergence the last re-seed's copy already reflected.

    *refused_entry* is the entry the peer's divergence fault reports
    refusing.  When the peer's last re-seed named a ledger position at or
    after it, the copy the peer was sent already reflected that entry.

    - If the peer's acknowledged position (``last_acknowledged_hash``) is at
      or past the re-seed's position, the peer applied that copy, so the
      CASE_MANAGER's case disagrees with its own ledger: a defect, logged at
      ERROR (``repeated``).
    - Otherwise the copy may have been lost, or the entry replayed before
      the copy arrived: ordinary recovery, logged at WARNING
      (``unconfirmed``) and left to the rate-bounded re-seed (SYNC-16-004).

    Writes nothing and always returns SUCCESS; the re-seed that follows stays
    under its own rate bound.

    Spec: SYNC-16-008.
    """

    def __init__(
        self,
        case_id: str,
        peer_id: str,
        refused_entry: CaseLedgerEntry,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.case_id = case_id
        self.peer_id = peer_id
        self.refused_entry = refused_entry
        self.repeated = False
        """True when the peer acknowledged the copy that reflected the entry."""
        self.unconfirmed = False
        """True when the copy reflected the entry but no acknowledgement shows
        the peer applied it."""

    def update(self) -> Status:
        self.repeated = self.unconfirmed = False
        if (f := self._require_datalayer()) is not None:
            return f
        datalayer = cast(CasePersistence, self.datalayer)
        state = _read_state(
            datalayer, case_id=self.case_id, peer_id=self.peer_id
        )
        position = None if state is None else state.last_reseed_position
        if position is None:
            return Status.SUCCESS
        if self.refused_entry.log_index > position.log_index:
            return Status.SUCCESS
        assert state is not None
        acknowledged = _acknowledged_index(
            datalayer, self.case_id, state.last_acknowledged_hash
        )
        if acknowledged is not None and acknowledged >= position.log_index:
            self.repeated = True
            self.logger.error(
                "%s: peer '%s' reports case '%s' diverged at ledger entry '%s'"
                " (log_index %d) after acknowledging position %d, which the"
                " case copy it was re-seeded with (position %d) already"
                " reflected: this CASE_MANAGER's case disagrees with its own"
                " ledger (SYNC-16-008)",
                self.name,
                self.peer_id,
                self.case_id,
                self.refused_entry.id_,
                self.refused_entry.log_index,
                acknowledged,
                position.log_index,
            )
            return Status.SUCCESS
        self.unconfirmed = True
        self.logger.warning(
            "%s: peer '%s' reports case '%s' diverged at ledger entry '%s'"
            " (log_index %d), which its last re-seed copy (position %d)"
            " reflects, but it has not acknowledged that position; the copy"
            " may be lost or still in flight, so the re-seed bound decides"
            " (SYNC-16-008, SYNC-16-004)",
            self.name,
            self.peer_id,
            self.case_id,
            self.refused_entry.id_,
            self.refused_entry.log_index,
            position.log_index,
        )
        return Status.SUCCESS


def _acknowledged_index(
    datalayer: CasePersistence, case_id: str, acknowledged_hash: str
) -> int | None:
    """The ``log_index`` of the entry *acknowledged_hash* names, or ``None``.

    ``None`` for an empty hash (nothing acknowledged) or a hash this ledger
    does not hold: neither is evidence the peer reached any position.
    """
    if not acknowledged_hash:
        return None
    for entry in sorted_case_ledger_entries(datalayer, case_id):
        if entry.entry_hash == acknowledged_hash:
            return entry.log_index
    return None
