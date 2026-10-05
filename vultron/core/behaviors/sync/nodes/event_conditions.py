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
"""Event-type matcher condition nodes for SYNC log-replication.

Each ``Is*EventNode`` matches exactly one ``event_type`` string on the
blackboard ``activity.log_entry``.  They are used as preconditions in the
``AnnounceLogEntryReceivedBT`` Selector branches (BTND-08-001/002).
"""

from __future__ import annotations

from typing import Any

from py_trees.common import Status
from py_trees.ports import NoDataAvailable, PortInformation

from vultron.core.behaviors.helpers import DataLayerConditionWithPorts
from vultron.core.behaviors.sync.nodes._helpers import _extract_id_from_field
from vultron.core.behaviors.sync.nodes.conditions import _require_log_entry
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.events.base import MessageSemantics
from vultron.core.models.rsvp_deadline import (
    INVITE_EXPIRED_EVENT_TYPE,
    INVITE_EXPIRED_NOOP_EVENT_TYPE,
)
from vultron.core.models.wire_keys import wire_key
from vultron.core.participants.authority import resolve_case_manager_id
from vultron.core.ports.case_persistence import CasePersistence
from vultron.errors import VultronWiringError

_REMOVE_EMBARGO_EVENT = "remove_embargo_event_from_case"
_ADD_PARTICIPANT_STATUS_EVENT = "add_participant_status_to_participant"
_ADD_NOTE_TO_CASE_EVENT = "add_note_to_case"
_ACCEPT_INVITE_ACTOR_TO_CASE_EVENT = "accept_invite_actor_to_case"
_CLOSE_CASE_EVENT = "close_case"
_ADD_REPORT_TO_CASE_EVENT = "add_report_to_case"
_ACCEPT_CASE_OWNERSHIP_TRANSFER_EVENT = "accept_case_ownership_transfer"
# The revision relay's event types (EP-09-007, ADR-0113).  The proposal and
# each relayed Invite share one event type and are told apart by authorship:
# see :func:`is_relayed_embargo_invite`.
_ATTRIBUTED_TO = wire_key("attributed_to")
_EMBARGO_INVITE_EVENT = MessageSemantics.INVITE_TO_EMBARGO_ON_CASE.value
_ACCEPT_EMBARGO_INVITE_EVENT = (
    MessageSemantics.ACCEPT_INVITE_TO_EMBARGO_ON_CASE.value
)
_REJECT_EMBARGO_INVITE_EVENT = (
    MessageSemantics.REJECT_INVITE_TO_EMBARGO_ON_CASE.value
)
#: Ledger ``event_type`` of the CASE_MANAGER's abandonment of an open embargo
#: proposal once P/X/A is set (EMB-16-001).  The snapshot is the ER the wire
#: carries, ``Reject(Invite(EmbargoEvent))`` (MSM-02-006), but it is the
#: manager's decision rather than its consent answer, so it has an event type
#: of its own: replayed as a reject, a manager that is not the case owner
#: would decide nothing (#4131).
EMBARGO_ABANDONMENT_EVENT_TYPE = (
    f"{MessageSemantics.REJECT_INVITE_TO_EMBARGO_ON_CASE.value}_abandoned"
)


class _ActivityEventNode(DataLayerConditionWithPorts):
    """Common base for Is*EventNode classes that read activity from a port."""

    INPUT_PORTS: dict[str, PortInformation] = {
        **DataLayerConditionWithPorts.INPUT_PORTS,
        "activity": PortInformation(data_type=object, required=True),
    }

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {"activity": "/activity"}

    def initialise(self) -> None:
        super().initialise()
        try:
            self.activity = self.get_input("activity")
        except (NoDataAvailable, NotImplementedError):
            self.activity = None


class IsRemoveEmbargoEventNode(_ActivityEventNode):
    """Precondition: return SUCCESS when this log entry IS a remove-embargo event.

    Used as the precondition in the ``EmbargoTeardownEffects`` slot of
    ``AnnounceLogEntryReceivedBT`` (built by ``_event_effect_slot``)::

        Selector(EmbargoTeardownEffects)
          Sequence
            IsRemoveEmbargoEventNode   ← SUCCESS iff event_type matches
            ApplyEmbargoTeardownNode
          Inverter(IsRemoveEmbargoEventNode)  ← SUCCESS iff wrong event type

    The relay slots beside it (proposal, relayed Invite, Accept and Reject
    of an Invite, and the abandonment of a proposal) follow the same shape.

    The Inverter fires SUCCESS only when the condition does NOT match (routing
    no-op for the wrong event type).  When the condition matches but
    ApplyEmbargoTeardownNode fails, both branches of the Selector fail and
    the FAILURE propagates to block PersistReceivedLogEntry (SYNC-12-001).

    Per BTND-08-001, BTND-08-002, BT-06-001, SYNC-12-001.
    """

    def update(self) -> Status:
        entry = _require_log_entry(self.activity, self.name)
        if entry.event_type == _REMOVE_EMBARGO_EVENT:
            return Status.SUCCESS
        return Status.FAILURE


class IsParticipantStatusEventNode(_ActivityEventNode):
    """Precondition: return SUCCESS when this log entry IS a participant-status event.

    Used as the precondition in the ``ParticipantStatusEffects`` Selector's
    inner Sequence in ``AnnounceLogEntryReceivedBT``::

        Selector(ParticipantStatusEffects)
          Sequence
            IsParticipantStatusEventNode   ← SUCCESS iff event_type matches
            ApplyParticipantStatusFromLedgerNode
          Inverter(IsParticipantStatusEventNode)  ← SUCCESS iff wrong event type

    The Inverter fires SUCCESS only when the condition does NOT match (routing
    no-op for the wrong event type).  When the condition matches but
    ApplyParticipantStatusFromLedgerNode fails, both branches of the Selector
    fail and the FAILURE propagates to block PersistReceivedLogEntry (SYNC-12-001).

    Per BTND-08-001, BTND-08-002, DEMOMA-07-003 step 3, SYNC-12-001.
    """

    def update(self) -> Status:
        entry = _require_log_entry(self.activity, self.name)
        if entry.event_type == _ADD_PARTICIPANT_STATUS_EVENT:
            return Status.SUCCESS
        return Status.FAILURE


class IsAddNoteEventNode(_ActivityEventNode):
    """Precondition: return SUCCESS when this log entry IS an add-note event.

    Used as the precondition in the ``NoteEffects`` Selector's inner
    Sequence in ``AnnounceLogEntryReceivedBT``::

        Selector(NoteEffects)
          Sequence
            IsAddNoteEventNode   ← SUCCESS iff event_type matches
            ApplyNoteFromLedgerNode
          Inverter(IsAddNoteEventNode)  ← SUCCESS iff wrong event type

    The Inverter fires SUCCESS only when the condition does NOT match (routing
    no-op for the wrong event type).  When the condition matches but
    ApplyNoteFromLedgerNode fails, both branches of the Selector fail and
    the FAILURE propagates to block PersistReceivedLogEntry (SYNC-12-001).

    Per BTND-08-001, BTND-08-002, SYNC-02-002, SYNC-12-001.
    """

    def update(self) -> Status:
        entry = _require_log_entry(self.activity, self.name)
        if entry.event_type == _ADD_NOTE_TO_CASE_EVENT:
            return Status.SUCCESS
        return Status.FAILURE


class IsInviteAcceptEventNode(_ActivityEventNode):
    """Precondition: return SUCCESS when this log entry IS an accept-invite event.

    Used as the precondition in the ``InviteAcceptEffects`` Selector's inner
    Sequence in ``AnnounceLogEntryReceivedBT``::

        Selector(InviteAcceptEffects)
          Sequence
            IsInviteAcceptEventNode   ← SUCCESS iff event_type matches
            ApplyInviteAcceptFromLedgerNode
          Inverter(IsInviteAcceptEventNode)  ← SUCCESS iff wrong event type

    The Inverter fires SUCCESS only when the condition does NOT match (routing
    no-op for the wrong event type).  When the condition matches but
    ApplyInviteAcceptFromLedgerNode fails, both branches of the Selector fail
    and the FAILURE propagates to block PersistReceivedLogEntry (SYNC-12-001).

    Per BTND-08-001, BTND-08-002, SYNC-02-002, DEMOMA-07-003, SYNC-12-001.
    """

    def update(self) -> Status:
        entry = _require_log_entry(self.activity, self.name)
        if entry.event_type == _ACCEPT_INVITE_ACTOR_TO_CASE_EVENT:
            return Status.SUCCESS
        return Status.FAILURE


class IsCloseCaseEventNode(_ActivityEventNode):
    """Precondition: return SUCCESS when this log entry IS a close-case event.

    Used as the precondition in the ``CloseCaseEffects`` Selector's inner
    Sequence in ``AnnounceLogEntryReceivedBT``::

        Selector(CloseCaseEffects)
          Sequence
            IsCloseCaseEventNode   ← SUCCESS iff event_type matches
            ApplyCloseCaseFromLedgerNode
          Inverter(IsCloseCaseEventNode)  ← SUCCESS iff wrong event type

    The Inverter fires SUCCESS only when the condition does NOT match (routing
    no-op for the wrong event type).  When the condition matches but
    ApplyCloseCaseFromLedgerNode fails, both branches of the Selector fail and
    the FAILURE propagates to block PersistReceivedLogEntry (SYNC-12-001).

    Per BTND-08-001, BTND-08-002, CM-23-003, SYNC-12-001.
    """

    def update(self) -> Status:
        entry = _require_log_entry(self.activity, self.name)
        if entry.event_type == _CLOSE_CASE_EVENT:
            return Status.SUCCESS
        return Status.FAILURE


class IsSubmitReportEventNode(_ActivityEventNode):
    """Precondition: return SUCCESS when this log entry IS an add_report_to_case event.

    Used as the precondition in the ``OfferReportEffects`` Selector's inner
    Sequence in ``AnnounceLogEntryReceivedBT``::

        Selector(OfferReportEffects)
          Sequence
            IsSubmitReportEventNode   ← SUCCESS iff event_type matches
            ApplyOfferReportFromLedgerNode
          Inverter(IsSubmitReportEventNode)  ← SUCCESS iff wrong event type

    The Inverter fires SUCCESS only when the condition does NOT match (routing
    no-op for the wrong event type).  When the condition matches but
    ApplyOfferReportFromLedgerNode fails, both branches of the Selector fail
    and the FAILURE propagates to block PersistReceivedLogEntry (SYNC-12-001).

    Per BTND-08-001, BTND-08-002, SYNC-02-002, ISSUE-2134.
    """

    def update(self) -> Status:
        entry = _require_log_entry(self.activity, self.name)
        if entry.event_type == _ADD_REPORT_TO_CASE_EVENT:
            return Status.SUCCESS
        return Status.FAILURE


class IsOwnershipTransferEventNode(_ActivityEventNode):
    """Precondition: return SUCCESS when this log entry IS an ownership-transfer event.

    Used as the precondition in the ``OwnershipTransferEffects`` Selector's
    inner Sequence in ``AnnounceLogEntryReceivedBT``::

        Selector(OwnershipTransferEffects)
          Sequence
            IsOwnershipTransferEventNode   ← SUCCESS iff event_type matches
            ApplyOwnershipTransferFromLedgerNode
          Inverter(IsOwnershipTransferEventNode)  ← SUCCESS iff wrong event type

    The Inverter fires SUCCESS only when the condition does NOT match (routing
    no-op for the wrong event type).  When the condition matches but
    ApplyOwnershipTransferFromLedgerNode fails, both branches of the Selector
    fail and the FAILURE propagates to block PersistReceivedLogEntry
    (SYNC-12-001).

    Per BTND-08-001, BTND-08-002, CM-21-007, SYNC-02-002, SYNC-12-001.
    """

    def update(self) -> Status:
        entry = _require_log_entry(self.activity, self.name)
        if entry.event_type == _ACCEPT_CASE_OWNERSHIP_TRANSFER_EVENT:
            return Status.SUCCESS
        return Status.FAILURE


def is_relayed_embargo_invite(
    snapshot: dict[str, Any],
    case: VulnerabilityCase | None,
    dl: CasePersistence,
) -> bool:
    """True when an ``invite_to_embargo_on_case`` snapshot is a relayed Invite.

    The CASE_MANAGER commits the proposal it received and then each Invite it
    relays under the same event type (EP-09-002).  A relay is the manager's own
    emission on the proposer's behalf: ``actor`` is the CASE_MANAGER and
    ``attributedTo`` names somebody else (CM-24).  Anything else is the
    proposal — including a proposal whose sender put a third party in
    ``attributedTo``, which only the CASE_MANAGER may do (PCR-08-010).

    With no case replica the role holder cannot be resolved; the entry is then
    classified on authorship alone, and the apply nodes skip it leniently
    (Regime 2, ADR-0087), so the classification has no effect.
    """
    actor_id = _extract_id_from_field(snapshot.get("actor"))
    attributed_to = _extract_id_from_field(snapshot.get(_ATTRIBUTED_TO))
    if not actor_id or not attributed_to or attributed_to == actor_id:
        return False
    if case is None:
        return True
    return resolve_case_manager_id(case, dl) == actor_id


class _EmbargoInviteEventNode(_ActivityEventNode):
    """Shared match for the two ``invite_to_embargo_on_case`` entry shapes."""

    _match_relay: bool

    def update(self) -> Status:
        entry = _require_log_entry(self.activity, self.name)
        if entry.event_type != _EMBARGO_INVITE_EVENT:
            return Status.FAILURE
        if self.datalayer is None:
            # Telling a proposal from a relayed Invite needs the store; a
            # FAILURE here would read as "not this slot" in both Inverters and
            # leave the entry unreplayed with nothing said (a wiring fault).
            raise VultronWiringError(
                f"{self.name}: no DataLayer to classify the"
                f" '{_EMBARGO_INVITE_EVENT}' entry on case"
                f" '{entry.case_id}'"
            )
        case = self._resolve_case_replica(entry.case_id)
        relayed = is_relayed_embargo_invite(
            entry.payload_snapshot, case, self.datalayer
        )
        return (
            Status.SUCCESS if relayed is self._match_relay else Status.FAILURE
        )


class IsEmbargoProposalEventNode(_EmbargoInviteEventNode):
    """Precondition: this entry is the embargo proposal the CASE_MANAGER received.

    Matches an ``invite_to_embargo_on_case`` entry that is *not* a relayed
    Invite (:func:`is_relayed_embargo_invite`).  Used in the
    ``EmbargoProposalEffects`` slot of ``AnnounceLogEntryReceivedBT``.

    Per EP-09-007, RSH-08-004, BTND-08-001, SYNC-12-001.
    """

    _match_relay = False


class IsEmbargoInviteRelayEventNode(_EmbargoInviteEventNode):
    """Precondition: this entry is an Invite the CASE_MANAGER relayed.

    Matches an ``invite_to_embargo_on_case`` entry whose ``actor`` is the
    CASE_MANAGER and whose ``attributedTo`` is the proposer
    (:func:`is_relayed_embargo_invite`).  Used in the
    ``EmbargoInviteRelayEffects`` slot of ``AnnounceLogEntryReceivedBT``.

    Per EP-09-002, EP-09-007, RSH-08-004, BTND-08-001, SYNC-12-001.
    """

    _match_relay = True


class IsAcceptEmbargoInviteEventNode(_ActivityEventNode):
    """Precondition: this entry is an ``accept_invite_to_embargo_on_case`` event.

    Used in the ``EmbargoAcceptanceEffects`` slot of
    ``AnnounceLogEntryReceivedBT``.

    Per EP-09-007, RSH-08-004, BTND-08-001, SYNC-12-001.
    """

    def update(self) -> Status:
        entry = _require_log_entry(self.activity, self.name)
        if entry.event_type == _ACCEPT_EMBARGO_INVITE_EVENT:
            return Status.SUCCESS
        return Status.FAILURE


class IsRejectEmbargoInviteEventNode(_ActivityEventNode):
    """Precondition: this entry is a ``reject_invite_to_embargo_on_case`` event.

    Used in the ``EmbargoRejectionEffects`` slot of
    ``AnnounceLogEntryReceivedBT``.

    Per EP-09-007, RSH-08-004, BTND-08-001, SYNC-12-001.
    """

    def update(self) -> Status:
        entry = _require_log_entry(self.activity, self.name)
        if entry.event_type == _REJECT_EMBARGO_INVITE_EVENT:
            return Status.SUCCESS
        return Status.FAILURE


class IsEmbargoAbandonmentEventNode(_ActivityEventNode):
    """Precondition: this entry is the CASE_MANAGER's abandonment of a proposal.

    Matches :data:`EMBARGO_ABANDONMENT_EVENT_TYPE`.  Used in the
    ``EmbargoAbandonmentEffects`` slot of ``AnnounceLogEntryReceivedBT``.

    Per EMB-16-001, EP-09-007, RSH-08-004, BTND-08-001, SYNC-12-001.
    """

    def update(self) -> Status:
        entry = _require_log_entry(self.activity, self.name)
        if entry.event_type == EMBARGO_ABANDONMENT_EVENT_TYPE:
            return Status.SUCCESS
        return Status.FAILURE


class IsInviteExpiryEventNode(_ActivityEventNode):
    """Precondition: this entry is the CASE_MANAGER's expiry of an embargo Invite.

    Matches :data:`~vultron.core.models.rsvp_deadline.INVITE_EXPIRED_EVENT_TYPE`.
    Used in the ``InviteExpiryEffects`` slot of ``AnnounceLogEntryReceivedBT``.

    Per CM-28-009, CM-28-014, ADR-0118, BTND-08-001, SYNC-12-001.
    """

    def update(self) -> Status:
        entry = _require_log_entry(self.activity, self.name)
        if entry.event_type == INVITE_EXPIRED_EVENT_TYPE:
            return Status.SUCCESS
        return Status.FAILURE


class IsInviteExpiryNoopEventNode(_ActivityEventNode):
    """Precondition: this entry is the CASE_MANAGER's no-op expiry acknowledgement.

    Matches :data:`~vultron.core.models.rsvp_deadline.INVITE_EXPIRED_NOOP_EVENT_TYPE`.
    Committed when a late ``Accept`` arrives with no current embargo (EM EXITED
    or NONE); the CASE_MANAGER acknowledges it without changing any PEC state
    (EMB-17-004, ADR-0118).  Used in the ``InviteExpiryNoopEffects`` slot of
    ``AnnounceLogEntryReceivedBT``.

    Per EMB-17-004, CM-28-009, ADR-0118, BTND-08-001, SYNC-12-001.
    """

    def update(self) -> Status:
        entry = _require_log_entry(self.activity, self.name)
        if entry.event_type == INVITE_EXPIRED_NOOP_EVENT_TYPE:
            return Status.SUCCESS
        return Status.FAILURE
