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
ERROR when the peer has acknowledged that copy's position and claims a
time for the fault after that acknowledgement's, since the CASE_MANAGER's
case then disagrees with its own ledger, and at WARNING otherwise, since the
copy may be lost or in flight, or the fault a delayed one from before the
copy arrived (SYNC-16-008).

Neither node commits a ledger entry: a re-seed is replication signalling,
like the replay it resembles (SYNC-16-002).
"""

from __future__ import annotations

from datetime import datetime
from typing import cast

from py_trees.common import Status

from vultron.core.behaviors.act_key_ports import (
    act_key_ports,
    act_key_remappings,
    act_value,
    optional_act_value,
)
from vultron.core.behaviors.act_keys import (
    CASE_ID,
    FAULT_PUBLISHED,
    REFUSED_ENTRY,
    SENDER_ID,
)
from vultron.core.behaviors.helpers import (
    DataLayerActionWithPorts,
    PortInformation,
)
from vultron.core.behaviors.helpers.emit import _EmitSingleActivityBase
from vultron.core.behaviors.idempotency import DeclaredRefusalMixin
from vultron.core.behaviors.sync.nodes.embargo_pause import peer_is_withheld
from vultron.core.behaviors.sync.nodes.replay_guard import (
    cooldown_elapsed,
    read_replication_state,
    update_replication_state,
)
from vultron.core.models._helpers import as_utc
from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.models.ledger_position import LedgerPosition
from vultron.core.models.replication_state import VultronReplicationState
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.ports.trigger_activity import TriggerActivityPort
from vultron.core.sync_helpers import sorted_case_ledger_entries
from vultron.errors import (
    VultronBTInternalError,
    VultronError,
)

__all__ = [
    "RESEED_COOLDOWN_SECONDS",
    "ReportRepeatDivergenceNode",
    "ReseedPeerNode",
    "announce_case_to_peer",
    "record_reseed",
    "should_reseed",
]

#: Minimum interval between two re-seeds of one peer.  A diverged replica
#: faults once per entry it refuses, so without a bound every replayed entry
#: would earn another full case copy (SYNC-16-004).
RESEED_COOLDOWN_SECONDS: float = 30.0


def should_reseed(
    datalayer: CasePersistence, *, case_id: str, peer_id: str, at: datetime
) -> bool:
    """True unless *peer_id* was re-seeded within the cooldown before *at*,
    the act's instant.

    Read-only: :func:`record_reseed` records a re-seed once it is queued.

    Spec: SYNC-16-004.
    """
    state = read_replication_state(datalayer, case_id=case_id, peer_id=peer_id)
    return cooldown_elapsed(
        None if state is None else state.last_reseeded_at,
        RESEED_COOLDOWN_SECONDS,
        at=at,
    )


def record_reseed(
    datalayer: CasePersistence,
    *,
    case_id: str,
    peer_id: str,
    position: LedgerPosition,
    at: datetime,
) -> None:
    """Record that *peer_id* was re-seeded at *at* with a copy at *position*.

    Kept in the peer's persisted replication state, beside its replay
    record, so the bound survives a restart (SYNC-04-002, SYNC-16-004).
    *at* is the act's instant (ADR-0176).
    """

    def _record(state: VultronReplicationState) -> None:
        state.last_reseeded_at = at
        state.last_reseed_position = position

    update_replication_state(
        datalayer, case_id=case_id, peer_id=peer_id, change=_record, at=at
    )


def announce_case_to_peer(
    factory: TriggerActivityPort,
    *,
    actor_id: str,
    case_id: str,
    peer_id: str,
    at: datetime,
) -> str:
    """Build and store *actor_id*'s ``Announce(VulnerabilityCase)`` of
    *case_id* to *peer_id* alone; return its id.

    The one case-copy send the genesis pre-seed (SYNC-15-015) and the
    re-seed (SYNC-16-003) share.  The copy names the case's ledger position
    (SYNC-16-005).  Queueing it is the caller's.
    """
    return factory.announce_vulnerability_case(
        case_id=case_id,
        actor=actor_id,
        context_id=case_id,
        to=[peer_id],
        at=at,
    )


class ReseedPeerNode(DeclaredRefusalMixin, _EmitSingleActivityBase):
    """Send the peer ``Announce(VulnerabilityCase)`` of its case, rate-bounded.

    The case is ``/case_id`` and the peer is ``/sender_id``, the sender of
    the received activity the re-seed answers (BTND-01-008).

    Returns SUCCESS whether or not it sends, and says which it was:
    ``withheld`` when the peer is not an active participant, so it is sent
    no case content (CM-10-004), unless *refuses_withheld_peer* makes that a
    declared refusal (below); ``rate_limited`` when the peer was
    re-seeded within the cooldown (SYNC-16-004); ``reseeded`` when this run
    queued a copy.  The copy, its outbox entry and the record of its ledger
    position (:func:`record_reseed`) are written in one transaction, so a
    copy is never queued unrecorded nor recorded unqueued.

    Returns FAILURE when the gate cannot be decided because this store holds
    no such case.  A copy the trigger-activity port cannot build is this
    actor's own fault, never the peer's, so it raises
    :class:`~vultron.errors.VultronBTInternalError` with nothing written
    (BT-14-001).

    A tree whose re-seed is the whole answer to the sender's request (the
    case-diverged fault, SYNC-16-003) passes *refuses_withheld_peer*: a
    withheld peer then fails the node with a declared refusal naming the
    case (CM-10-004), so the verdict is the node's, never a reader's
    (ADR-0195).  A re-seed that is one part of a larger answer (the stale
    ledger-position answer) leaves it off and keeps ``withheld`` a success.

    Authored as the executing actor; it belongs inside a CASE_MANAGER gate
    (BT-17-008).

    Spec: SYNC-16-003, SYNC-16-004, PCR-02-001.
    """

    INPUT_PORTS: dict[str, PortInformation] = {
        **_EmitSingleActivityBase.INPUT_PORTS,
        **act_key_ports(CASE_ID, SENDER_ID),
    }

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {
            **super()._domain_port_remappings(),
            **act_key_remappings(CASE_ID, SENDER_ID),
        }

    def __init__(
        self,
        name: str | None = None,
        *,
        refuses_withheld_peer: bool = False,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.refuses_withheld_peer = refuses_withheld_peer
        """Whether a withheld peer is a declared refusal, not a success."""
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
        self.case_id = act_value(self, CASE_ID, str)
        self.peer_id = act_value(self, SENDER_ID, str)
        datalayer = cast(CasePersistence, self.datalayer)
        at = self._require_act_instant()
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
            if self.refuses_withheld_peer:
                return self._refuse(
                    f"the sender is not an active participant of case"
                    f" '{self.case_id}'; no case copy sent (CM-10-004)"
                )
            return Status.SUCCESS
        if not should_reseed(
            datalayer, case_id=self.case_id, peer_id=self.peer_id, at=at
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
                    at=self._require_act_instant(),
                )
                self._emit_through_seam(activity_id, "")
                record_reseed(
                    datalayer,
                    case_id=self.case_id,
                    peer_id=self.peer_id,
                    position=position,
                    at=at,
                )
        except (VultronError, ValueError) as exc:
            # ValueError: a model's own validation (a pydantic
            # ValidationError) refused the record; this actor's fault too.
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

    The case is ``/case_id``, the peer is ``/sender_id`` (the fault's
    sender), and *refused_entry*, read from ``/refused_entry``, is the entry
    the peer's divergence fault reports refusing; *fault_published* is read
    from ``/fault_published``, which a fault that claims no time leaves
    unset (BTND-01-008).  When the peer's last re-seed named a ledger position at or after it, the copy the
    peer was sent already reflected that entry.

    - If the peer's acknowledged position (``last_acknowledged_hash``) is at
      or past the re-seed's position, the peer applied that copy.  When
      *fault_published*, the time the peer claims for the fault, is at or
      before the time it claimed for that acknowledgement
      (``last_acknowledged_published``), the fault is a stale repeat sent
      before the copy arrived and delivered late: ordinary recovery, logged
      at WARNING (``stale``).  A tie counts as stale because a peer may
      claim whole seconds, so the two can share a second (CS-13-007 binds
      only what this node writes).  Both times
      are the peer's own clock, so no skew between machines enters the
      comparison.
    - Otherwise, when the fault's time is after that acknowledgement's, the
      CASE_MANAGER's case disagrees with its own ledger: a defect, logged at
      ERROR (``repeated``).  A missing time on either side shows no order,
      so it keeps the ERROR.
    - Without that acknowledgement the copy may have been lost, or the entry
      replayed before the copy arrived: ordinary recovery, logged at WARNING
      (``unconfirmed``) and left to the rate-bounded re-seed (SYNC-16-004).

    Writes nothing and always returns SUCCESS; the re-seed that follows stays
    under its own rate bound.

    Spec: SYNC-16-008.
    """

    INPUT_PORTS: dict[str, PortInformation] = {
        **DataLayerActionWithPorts.INPUT_PORTS,
        **act_key_ports(CASE_ID, SENDER_ID, REFUSED_ENTRY, FAULT_PUBLISHED),
    }

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return act_key_remappings(
            CASE_ID, SENDER_ID, REFUSED_ENTRY, FAULT_PUBLISHED
        )

    def __init__(self, *, name: str | None = None) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.fault_published: datetime | None = None
        """The ``published`` time the peer claims for its fault, if any."""
        self.repeated = False
        """True when the peer acknowledged the copy that reflected the entry
        and claims a time for the fault after that acknowledgement's."""
        self.stale = False
        """True when the peer acknowledged that copy at or after the time it
        claims for the fault."""
        self.unconfirmed = False
        """True when the copy reflected the entry but no acknowledgement shows
        the peer applied it."""

    def update(self) -> Status:
        self.repeated = self.stale = self.unconfirmed = False
        if (f := self._require_datalayer()) is not None:
            return f
        self.case_id = act_value(self, CASE_ID, str)
        self.peer_id = act_value(self, SENDER_ID, str)
        self.refused_entry = act_value(self, REFUSED_ENTRY, CaseLedgerEntry)
        self.fault_published = as_utc(
            optional_act_value(self, FAULT_PUBLISHED, datetime)
        )
        datalayer = cast(CasePersistence, self.datalayer)
        state = read_replication_state(
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
            acknowledged_at = state.last_acknowledged_published
            if _sent_by(self.fault_published, acknowledged_at):
                self.stale = True
                self.logger.warning(
                    "%s: peer '%s' reports case '%s' diverged at ledger entry"
                    " '%s' (log_index %d) in a fault it sent at %s, at or before it"
                    " acknowledged position %d at %s: a stale repeat from"
                    " before its re-seed copy (position %d) arrived, so the"
                    " re-seed bound decides (SYNC-16-008, SYNC-16-004)",
                    self.name,
                    self.peer_id,
                    self.case_id,
                    self.refused_entry.id_,
                    self.refused_entry.log_index,
                    self.fault_published,
                    acknowledged,
                    acknowledged_at,
                    position.log_index,
                )
                return Status.SUCCESS
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


def _sent_by(
    fault_published: datetime | None, acknowledged_at: datetime | None
) -> bool:
    """True when the fault's claimed time is at or before the acknowledgement's.

    Both are times the same peer claimed, so they share its clock.  A tie is
    not after: a peer may claim ``published`` at whole seconds, so a fault
    and the acknowledgement that followed it can share a second.  A time missing on
    either side shows no order, so it is never "at or before".
    """
    acknowledged = as_utc(acknowledged_at)
    if fault_published is None or acknowledged is None:
        return False
    return fault_published <= acknowledged


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
