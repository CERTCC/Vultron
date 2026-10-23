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
"""Semantic-type matcher condition nodes for SYNC log-replication.

Each ``Is*EventNode`` matches the ``semantic_type`` of one kind of entry on
the blackboard ``activity.log_entry``.  Usually that is one semantic type; the
note-attachment node matches the two entries that attach a note.  They are
used as preconditions in the ``AnnounceLogEntryReceivedBT`` Selector branches
(BTND-08-001/002).  The embargo negotiation's matchers live in
``embargo_event_conditions`` and the shared bases in
``_event_condition_base``; both are re-exported here.
"""

from __future__ import annotations

from vultron.core.behaviors.sync.nodes._event_condition_base import (
    _ActivityEventNode,
    _SemanticTypeSetNode,
    _SingleSemanticTypeNode,
)
from vultron.core.behaviors.sync.nodes.embargo_event_conditions import (
    IsAcceptEmbargoInviteEventNode,
    IsEmbargoAbandonmentEventNode,
    IsEmbargoInviteRelayEventNode,
    IsEmbargoProposalEventNode,
    IsRejectEmbargoInviteEventNode,
    IsUndoEmbargoInviteEventNode,
    is_relayed_embargo_invite,
    sent_by_case_manager,
)
from vultron.core.models.events.base import MessageSemantics
from vultron.core.models.participant_semantic_types import (
    CREATE_CASE_PARTICIPANT_SEMANTIC_TYPE,
    UPDATE_CASE_OWNER_SEMANTIC_TYPE,
)

_REMOVE_EMBARGO_EVENT = MessageSemantics.REMOVE_EMBARGO_EVENT_FROM_CASE.value
_CREATE_EMBARGO_EVENT = MessageSemantics.CREATE_EMBARGO_EVENT.value
_ADD_PARTICIPANT_STATUS_EVENT = (
    MessageSemantics.ADD_PARTICIPANT_STATUS_TO_PARTICIPANT.value
)
_ACCEPT_INVITE_ACTOR_TO_CASE_EVENT = (
    MessageSemantics.ACCEPT_INVITE_ACTOR_TO_CASE.value
)
_REJECT_INVITE_ACTOR_TO_CASE_EVENT = (
    MessageSemantics.REJECT_INVITE_ACTOR_TO_CASE.value
)
_ADD_NOTE_TO_CASE_EVENT = MessageSemantics.ADD_NOTE_TO_CASE.value
_REMOVE_NOTE_FROM_CASE_EVENT = MessageSemantics.REMOVE_NOTE_FROM_CASE.value
_ADD_REPORT_TO_CASE_EVENT = MessageSemantics.ADD_REPORT_TO_CASE.value


class IsRemoveEmbargoEventNode(_SingleSemanticTypeNode):
    """Precondition: return SUCCESS when this log entry IS a remove-embargo event.

    Used as the precondition in the ``EmbargoTeardownEffects`` slot of
    ``AnnounceLogEntryReceivedBT`` (built by ``_event_effect_slot``)::

        Selector(EmbargoTeardownEffects)
          Sequence
            IsRemoveEmbargoEventNode   ← SUCCESS iff semantic_type matches
            ApplyEmbargoTeardownNode
          Inverter(IsRemoveEmbargoEventNode)  ← SUCCESS iff wrong semantic type

    The relay slots beside it (proposal, relayed Invite, Accept and Reject
    of an Invite, and the abandonment of a proposal) follow the same shape.

    The Inverter fires SUCCESS only when the condition does NOT match (routing
    no-op for the wrong semantic type).  When the condition matches but
    ApplyEmbargoTeardownNode fails, both branches of the Selector fail and
    the FAILURE propagates to block PersistReceivedLogEntry (SYNC-12-001).

    Per BTND-08-001, BTND-08-002, BT-06-001, SYNC-12-001.
    """

    matched_semantic_type = _REMOVE_EMBARGO_EVENT


class IsParticipantStatusEventNode(_SingleSemanticTypeNode):
    """Precondition: return SUCCESS when this log entry IS a participant-status event.

    Used as the precondition in the ``ParticipantStatusEffects`` Selector's
    inner Sequence in ``AnnounceLogEntryReceivedBT``::

        Selector(ParticipantStatusEffects)
          Sequence
            IsParticipantStatusEventNode   ← SUCCESS iff semantic_type matches
            ApplyParticipantStatusFromLedgerNode
          Inverter(IsParticipantStatusEventNode)  ← SUCCESS iff wrong semantic type

    The Inverter fires SUCCESS only when the condition does NOT match (routing
    no-op for the wrong semantic type).  When the condition matches but
    ApplyParticipantStatusFromLedgerNode fails, both branches of the Selector
    fail and the FAILURE propagates to block PersistReceivedLogEntry (SYNC-12-001).

    Per BTND-08-001, BTND-08-002, DEMOMA-07-003 step 3, SYNC-12-001.
    """

    matched_semantic_type = _ADD_PARTICIPANT_STATUS_EVENT


class IsAddNoteEventNode(_SingleSemanticTypeNode):
    """Precondition: SUCCESS when this log entry attaches a note to the case.

    One entry attaches a note: ``add_note_to_case``, a received
    ``Add(Note, target=Case)`` carrying the note inline.  The activity states
    the attachment itself, so its entry is the change's entry (CLP-07-013);
    no other entry attaches a note (RSH-08-004, VAM-01-011).

    Used as the precondition in the ``NoteEffects`` Selector's inner
    Sequence in ``AnnounceLogEntryReceivedBT``::

        Selector(NoteEffects)
          Sequence
            IsAddNoteEventNode   ← SUCCESS iff semantic_type matches
            ApplyNoteFromLedgerNode
          Inverter(IsAddNoteEventNode)  ← SUCCESS iff wrong semantic type

    The Inverter fires SUCCESS only when the condition does NOT match (routing
    no-op for the wrong semantic type).  When the condition matches but
    ApplyNoteFromLedgerNode fails, both branches of the Selector fail and
    the FAILURE propagates to block PersistReceivedLogEntry (SYNC-12-001).

    Per BTND-08-001, BTND-08-002, SYNC-02-002, SYNC-12-001.
    """

    matched_semantic_type = _ADD_NOTE_TO_CASE_EVENT


class IsRemoveNoteEventNode(_SingleSemanticTypeNode):
    """Precondition: SUCCESS when this log entry IS a remove-note event.

    Precondition of the ``RemoveNoteEffects`` slot, in the same
    ``Selector(Seq(Is, Apply), Inverter(Is))`` shape as the add-note slot.

    Per BTND-08-001, BTND-08-002, SYNC-02-002, SYNC-12-001, RSH-08-004.
    """

    matched_semantic_type = _REMOVE_NOTE_FROM_CASE_EVENT


class IsCreateEmbargoEventNode(_SingleSemanticTypeNode):
    """Precondition: SUCCESS when this log entry IS a ``create_embargo_event``.

    The CASE_MANAGER commits it right after a case's genesis entry, one per
    embargo the creation wrote, carrying the embargo in full (CLP-07-013).

    Per BTND-08-001, SYNC-12-001.
    """

    matched_semantic_type = _CREATE_EMBARGO_EVENT


class IsCreateCaseParticipantEventNode(_SingleSemanticTypeNode):
    """Precondition: SUCCESS when this log entry IS a ``create_case_participant``.

    Precondition of the ``CreateCaseParticipant`` slot, in the same
    ``Selector(Seq(Is, Apply), Inverter(Is))`` shape as the other slots.  The
    CASE_MANAGER commits it when it creates a participant record, for instance
    the inert record of a stub Invite's invitee (CM-11-006).

    Per BTND-08-001, BTND-08-002, CM-11-006, SYNC-12-001, RSH-08-004.
    """

    matched_semantic_type = CREATE_CASE_PARTICIPANT_SEMANTIC_TYPE


class IsInviteAcceptEventNode(_SingleSemanticTypeNode):
    """Precondition: SUCCESS when this log entry IS the invitee's stub Accept.

    Precondition of the ``InviteAccept`` slot: the entry is the invitee's
    ``Accept(Invite(stub))`` message itself, which is the entry for the consent
    it signs and its ``joined`` mark (ADR-0114, CM-31-012).

    Per BTND-08-001, BTND-08-002, SYNC-12-001, RSH-08-004.
    """

    matched_semantic_type = _ACCEPT_INVITE_ACTOR_TO_CASE_EVENT


class IsInviteRejectEventNode(_SingleSemanticTypeNode):
    """Precondition: SUCCESS when this log entry IS the invitee's stub Reject.

    Precondition of the ``InviteReject`` slot: the entry is the invitee's
    ``Reject(Invite(stub))`` message itself, which is the entry for the consent
    ``DECLINED`` (ADR-0114, CM-11-007).

    Per BTND-08-001, BTND-08-002, SYNC-12-001, RSH-08-004.
    """

    matched_semantic_type = _REJECT_INVITE_ACTOR_TO_CASE_EVENT


class IsSubmitReportEventNode(_SingleSemanticTypeNode):
    """Precondition: return SUCCESS when this log entry IS an add_report_to_case event.

    Used as the precondition in the ``OfferReportEffects`` Selector's inner
    Sequence in ``AnnounceLogEntryReceivedBT``::

        Selector(OfferReportEffects)
          Sequence
            IsSubmitReportEventNode   ← SUCCESS iff semantic_type matches
            ApplyOfferReportFromLedgerNode
          Inverter(IsSubmitReportEventNode)  ← SUCCESS iff wrong semantic type

    The Inverter fires SUCCESS only when the condition does NOT match (routing
    no-op for the wrong semantic type).  When the condition matches but
    ApplyOfferReportFromLedgerNode fails, both branches of the Selector fail
    and the FAILURE propagates to block PersistReceivedLogEntry (SYNC-12-001).

    Per BTND-08-001, BTND-08-002, SYNC-02-002, ISSUE-2134.
    """

    matched_semantic_type = _ADD_REPORT_TO_CASE_EVENT


class IsOwnershipTransferEventNode(_SingleSemanticTypeNode):
    """Precondition: return SUCCESS when this log entry names a new Case Owner.

    The ``update_case_owner`` entry the CASE_MANAGER commits after the
    ``Accept`` of an ownership transfer, carrying the case with its new
    ``attributed_to`` (CM-21-002, CLP-07-013).  The ``Accept`` entry itself
    moves nothing on a replica: each change it causes is its own entry.

    Used as the precondition in the ``OwnershipTransferEffects`` Selector's
    inner Sequence in ``AnnounceLogEntryReceivedBT``::

        Selector(OwnershipTransferEffects)
          Sequence
            IsOwnershipTransferEventNode   ← SUCCESS iff semantic_type matches
            ApplyOwnershipTransferFromLedgerNode
          Inverter(IsOwnershipTransferEventNode)  ← SUCCESS iff wrong semantic type

    The Inverter fires SUCCESS only when the condition does NOT match (routing
    no-op for the wrong semantic type).  When the condition matches but
    ApplyOwnershipTransferFromLedgerNode fails, both branches of the Selector
    fail and the FAILURE propagates to block PersistReceivedLogEntry
    (SYNC-12-001).

    Per BTND-08-001, BTND-08-002, CM-21-007, SYNC-02-002, SYNC-12-001.
    """

    matched_semantic_type = UPDATE_CASE_OWNER_SEMANTIC_TYPE


class IsWithdrawFromEmbargoEventNode(_SingleSemanticTypeNode):
    """Precondition: this entry is a ``withdraw_from_embargo_on_case`` event.

    A signatory's ``Leave(EmbargoEvent)`` the CASE_MANAGER committed
    (MSM-07-010).  Used in the ``EmbargoWithdrawalEffects`` slot of
    ``AnnounceLogEntryReceivedBT``.

    Per EP-09-007, RSH-08-004, BTND-08-001, SYNC-12-001.
    """

    matched_semantic_type = (
        MessageSemantics.WITHDRAW_FROM_EMBARGO_ON_CASE.value
    )


__all__ = [
    "IsAcceptEmbargoInviteEventNode",
    "IsAddNoteEventNode",
    "IsCreateCaseParticipantEventNode",
    "IsCreateEmbargoEventNode",
    "IsEmbargoAbandonmentEventNode",
    "IsEmbargoInviteRelayEventNode",
    "IsEmbargoProposalEventNode",
    "IsInviteAcceptEventNode",
    "IsInviteRejectEventNode",
    "IsOwnershipTransferEventNode",
    "IsParticipantStatusEventNode",
    "IsRejectEmbargoInviteEventNode",
    "IsRemoveEmbargoEventNode",
    "IsRemoveNoteEventNode",
    "IsSubmitReportEventNode",
    "IsUndoEmbargoInviteEventNode",
    "IsWithdrawFromEmbargoEventNode",
    "_ActivityEventNode",
    "_SemanticTypeSetNode",
    "_SingleSemanticTypeNode",
    "is_relayed_embargo_invite",
    "sent_by_case_manager",
]
