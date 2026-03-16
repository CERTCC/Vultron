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

This is domain knowledge — the mapping from a semantic intent to the use case
that handles it belongs in the core layer, not in the adapter layer.

``USE_CASE_MAP`` is the authoritative routing table.
``SEMANTICS_HANDLERS`` is a backward-compat alias used by
``vultron/api/v2/backend/handler_map.py``.
"""

from vultron.core.models.events import MessageSemantics
import vultron.core.use_cases.actor as _actor
import vultron.core.use_cases.case as _case
import vultron.core.use_cases.case_participant as _case_participant
import vultron.core.use_cases.embargo as _embargo
import vultron.core.use_cases.note as _note
import vultron.core.use_cases.report as _report
import vultron.core.use_cases.status as _status
import vultron.core.use_cases.unknown as _unknown

USE_CASE_MAP: dict[MessageSemantics, type] = {
    MessageSemantics.CREATE_REPORT: _report.CreateReportUseCase,
    MessageSemantics.SUBMIT_REPORT: _report.SubmitReportUseCase,
    MessageSemantics.VALIDATE_REPORT: _report.ValidateReportUseCase,
    MessageSemantics.INVALIDATE_REPORT: _report.InvalidateReportUseCase,
    MessageSemantics.ACK_REPORT: _report.AckReportUseCase,
    MessageSemantics.CLOSE_REPORT: _report.CloseReportUseCase,
    MessageSemantics.CREATE_CASE: _case.CreateCaseUseCase,
    MessageSemantics.UPDATE_CASE: _case.UpdateCaseUseCase,
    MessageSemantics.ENGAGE_CASE: _case.EngageCaseUseCase,
    MessageSemantics.DEFER_CASE: _case.DeferCaseUseCase,
    MessageSemantics.ADD_REPORT_TO_CASE: _case.AddReportToCaseUseCase,
    MessageSemantics.CLOSE_CASE: _case.CloseCaseUseCase,
    MessageSemantics.SUGGEST_ACTOR_TO_CASE: _actor.SuggestActorToCaseUseCase,
    MessageSemantics.ACCEPT_SUGGEST_ACTOR_TO_CASE: _actor.AcceptSuggestActorToCaseUseCase,
    MessageSemantics.REJECT_SUGGEST_ACTOR_TO_CASE: _actor.RejectSuggestActorToCaseUseCase,
    MessageSemantics.OFFER_CASE_OWNERSHIP_TRANSFER: _actor.OfferCaseOwnershipTransferUseCase,
    MessageSemantics.ACCEPT_CASE_OWNERSHIP_TRANSFER: _actor.AcceptCaseOwnershipTransferUseCase,
    MessageSemantics.REJECT_CASE_OWNERSHIP_TRANSFER: _actor.RejectCaseOwnershipTransferUseCase,
    MessageSemantics.INVITE_ACTOR_TO_CASE: _actor.InviteActorToCaseUseCase,
    MessageSemantics.ACCEPT_INVITE_ACTOR_TO_CASE: _actor.AcceptInviteActorToCaseUseCase,
    MessageSemantics.REJECT_INVITE_ACTOR_TO_CASE: _actor.RejectInviteActorToCaseUseCase,
    MessageSemantics.CREATE_EMBARGO_EVENT: _embargo.CreateEmbargoEventUseCase,
    MessageSemantics.ADD_EMBARGO_EVENT_TO_CASE: _embargo.AddEmbargoEventToCaseUseCase,
    MessageSemantics.REMOVE_EMBARGO_EVENT_FROM_CASE: _embargo.RemoveEmbargoEventFromCaseUseCase,
    MessageSemantics.ANNOUNCE_EMBARGO_EVENT_TO_CASE: _embargo.AnnounceEmbargoEventToCaseUseCase,
    MessageSemantics.INVITE_TO_EMBARGO_ON_CASE: _embargo.InviteToEmbargoOnCaseUseCase,
    MessageSemantics.ACCEPT_INVITE_TO_EMBARGO_ON_CASE: _embargo.AcceptInviteToEmbargoOnCaseUseCase,
    MessageSemantics.REJECT_INVITE_TO_EMBARGO_ON_CASE: _embargo.RejectInviteToEmbargoOnCaseUseCase,
    MessageSemantics.CREATE_CASE_PARTICIPANT: _case_participant.CreateCaseParticipantUseCase,
    MessageSemantics.ADD_CASE_PARTICIPANT_TO_CASE: _case_participant.AddCaseParticipantToCaseUseCase,
    MessageSemantics.REMOVE_CASE_PARTICIPANT_FROM_CASE: _case_participant.RemoveCaseParticipantFromCaseUseCase,
    MessageSemantics.CREATE_NOTE: _note.CreateNoteUseCase,
    MessageSemantics.ADD_NOTE_TO_CASE: _note.AddNoteToCaseUseCase,
    MessageSemantics.REMOVE_NOTE_FROM_CASE: _note.RemoveNoteFromCaseUseCase,
    MessageSemantics.CREATE_CASE_STATUS: _status.CreateCaseStatusUseCase,
    MessageSemantics.ADD_CASE_STATUS_TO_CASE: _status.AddCaseStatusToCaseUseCase,
    MessageSemantics.CREATE_PARTICIPANT_STATUS: _status.CreateParticipantStatusUseCase,
    MessageSemantics.ADD_PARTICIPANT_STATUS_TO_PARTICIPANT: _status.AddParticipantStatusToParticipantUseCase,
    MessageSemantics.UNKNOWN: _unknown.UnknownUseCase,
}

# Backward-compat alias (adapter layer handler_map.py re-exports this).
SEMANTICS_HANDLERS = USE_CASE_MAP
