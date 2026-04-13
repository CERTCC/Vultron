#!/usr/bin/env python

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

"""Routing table mapping ``MessageSemantics`` to core use-case classes.

``USE_CASE_MAP`` is the authoritative routing table.
"""

from vultron.core.models.events import MessageSemantics
import vultron.core.use_cases.received.actor as _actor
import vultron.core.use_cases.received.case as _case
import vultron.core.use_cases.received.case_participant as _case_participant
import vultron.core.use_cases.received.embargo as _embargo
import vultron.core.use_cases.received.note as _note
import vultron.core.use_cases.received.report as _report
import vultron.core.use_cases.received.status as _status
import vultron.core.use_cases.received.sync as _sync
import vultron.core.use_cases.received.unknown as _unknown

USE_CASE_MAP: dict[MessageSemantics, type] = {
    MessageSemantics.CREATE_REPORT: _report.CreateReportReceivedUseCase,
    MessageSemantics.SUBMIT_REPORT: _report.SubmitReportReceivedUseCase,
    MessageSemantics.VALIDATE_REPORT: _report.ValidateReportReceivedUseCase,
    MessageSemantics.INVALIDATE_REPORT: _report.InvalidateReportReceivedUseCase,
    MessageSemantics.ACK_REPORT: _report.AckReportReceivedUseCase,
    MessageSemantics.CLOSE_REPORT: _report.CloseReportReceivedUseCase,
    MessageSemantics.CREATE_CASE: _case.CreateCaseReceivedUseCase,
    MessageSemantics.UPDATE_CASE: _case.UpdateCaseReceivedUseCase,
    MessageSemantics.ENGAGE_CASE: _case.EngageCaseReceivedUseCase,
    MessageSemantics.DEFER_CASE: _case.DeferCaseReceivedUseCase,
    MessageSemantics.ADD_REPORT_TO_CASE: _case.AddReportToCaseReceivedUseCase,
    MessageSemantics.CLOSE_CASE: _case.CloseCaseReceivedUseCase,
    MessageSemantics.ANNOUNCE_CASE_LOG_ENTRY: _sync.AnnounceLogEntryReceivedUseCase,
    MessageSemantics.REJECT_CASE_LOG_ENTRY: _sync.RejectLogEntryReceivedUseCase,
    MessageSemantics.SUGGEST_ACTOR_TO_CASE: _actor.SuggestActorToCaseReceivedUseCase,
    MessageSemantics.ACCEPT_SUGGEST_ACTOR_TO_CASE: _actor.AcceptSuggestActorToCaseReceivedUseCase,
    MessageSemantics.REJECT_SUGGEST_ACTOR_TO_CASE: _actor.RejectSuggestActorToCaseReceivedUseCase,
    MessageSemantics.OFFER_CASE_OWNERSHIP_TRANSFER: _actor.OfferCaseOwnershipTransferReceivedUseCase,
    MessageSemantics.ACCEPT_CASE_OWNERSHIP_TRANSFER: _actor.AcceptCaseOwnershipTransferReceivedUseCase,
    MessageSemantics.REJECT_CASE_OWNERSHIP_TRANSFER: _actor.RejectCaseOwnershipTransferReceivedUseCase,
    MessageSemantics.INVITE_ACTOR_TO_CASE: _actor.InviteActorToCaseReceivedUseCase,
    MessageSemantics.ACCEPT_INVITE_ACTOR_TO_CASE: _actor.AcceptInviteActorToCaseReceivedUseCase,
    MessageSemantics.REJECT_INVITE_ACTOR_TO_CASE: _actor.RejectInviteActorToCaseReceivedUseCase,
    MessageSemantics.CREATE_EMBARGO_EVENT: _embargo.CreateEmbargoEventReceivedUseCase,
    MessageSemantics.ADD_EMBARGO_EVENT_TO_CASE: _embargo.AddEmbargoEventToCaseReceivedUseCase,
    MessageSemantics.REMOVE_EMBARGO_EVENT_FROM_CASE: _embargo.RemoveEmbargoEventFromCaseReceivedUseCase,
    MessageSemantics.ANNOUNCE_EMBARGO_EVENT_TO_CASE: _embargo.AnnounceEmbargoEventToCaseReceivedUseCase,
    MessageSemantics.INVITE_TO_EMBARGO_ON_CASE: _embargo.InviteToEmbargoOnCaseReceivedUseCase,
    MessageSemantics.ACCEPT_INVITE_TO_EMBARGO_ON_CASE: _embargo.AcceptInviteToEmbargoOnCaseReceivedUseCase,
    MessageSemantics.REJECT_INVITE_TO_EMBARGO_ON_CASE: _embargo.RejectInviteToEmbargoOnCaseReceivedUseCase,
    MessageSemantics.CREATE_CASE_PARTICIPANT: _case_participant.CreateCaseParticipantReceivedUseCase,
    MessageSemantics.ADD_CASE_PARTICIPANT_TO_CASE: _case_participant.AddCaseParticipantToCaseReceivedUseCase,
    MessageSemantics.REMOVE_CASE_PARTICIPANT_FROM_CASE: _case_participant.RemoveCaseParticipantFromCaseReceivedUseCase,
    MessageSemantics.CREATE_NOTE: _note.CreateNoteReceivedUseCase,
    MessageSemantics.ADD_NOTE_TO_CASE: _note.AddNoteToCaseReceivedUseCase,
    MessageSemantics.REMOVE_NOTE_FROM_CASE: _note.RemoveNoteFromCaseReceivedUseCase,
    MessageSemantics.CREATE_CASE_STATUS: _status.CreateCaseStatusReceivedUseCase,
    MessageSemantics.ADD_CASE_STATUS_TO_CASE: _status.AddCaseStatusToCaseReceivedUseCase,
    MessageSemantics.CREATE_PARTICIPANT_STATUS: _status.CreateParticipantStatusReceivedUseCase,
    MessageSemantics.ADD_PARTICIPANT_STATUS_TO_PARTICIPANT: _status.AddParticipantStatusToParticipantReceivedUseCase,
    MessageSemantics.UNKNOWN: _unknown.UnknownUseCase,
}
