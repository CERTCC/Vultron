"""
Backward-compatibility shim for vultron.api.v2.backend.handlers.

As of P75-4 all use cases are class-based (``XxxUseCase(dl).execute(event)``).

This module re-exports:
- ``verify_semantics`` — as a no-op shim (semantic checking happens at
  dispatcher routing-table level)
- All use-case callables under their original handler function names so that
  existing call sites (tests and legacy code) continue to work unchanged.

New code should call the use-case classes directly.
"""

from vultron.api.v2.backend.handlers._shim import (
    verify_semantics,
)  # noqa: F401
from vultron.core.models.events import VultronEvent
from vultron.types import DispatchEvent

# ---- use case modules ---------------------------------------------------
import vultron.core.use_cases.report as _uc_report
import vultron.core.use_cases.case as _uc_case
import vultron.core.use_cases.case_participant as _uc_participant
import vultron.core.use_cases.actor as _uc_actor
import vultron.core.use_cases.embargo as _uc_embargo
import vultron.core.use_cases.note as _uc_note
import vultron.core.use_cases.status as _uc_status
import vultron.core.use_cases.unknown as _uc_unknown


def _unwrap(dispatchable):
    """Extract a VultronEvent from a DispatchEvent wrapper or pass through."""
    if isinstance(dispatchable, DispatchEvent):
        return dispatchable.payload
    return dispatchable


# ---- report handlers -------------------------------------------------------


def create_report(dispatchable, dl=None):
    return _uc_report.CreateReportReceivedUseCase(
        dl, _unwrap(dispatchable)
    ).execute()


def submit_report(dispatchable, dl=None):
    return _uc_report.SubmitReportReceivedUseCase(
        dl, _unwrap(dispatchable)
    ).execute()


def validate_report(dispatchable, dl=None):
    return _uc_report.ValidateReportReceivedUseCase(
        dl, _unwrap(dispatchable)
    ).execute()


def invalidate_report(dispatchable, dl=None):
    return _uc_report.InvalidateReportReceivedUseCase(
        dl, _unwrap(dispatchable)
    ).execute()


def ack_report(dispatchable, dl=None):
    return _uc_report.AckReportReceivedUseCase(
        dl, _unwrap(dispatchable)
    ).execute()


def close_report(dispatchable, dl=None):
    return _uc_report.CloseReportReceivedUseCase(
        dl, _unwrap(dispatchable)
    ).execute()


# ---- case handlers ---------------------------------------------------------


def create_case(dispatchable, dl=None):
    return _uc_case.CreateCaseReceivedUseCase(
        dl, _unwrap(dispatchable)
    ).execute()


def engage_case(dispatchable, dl=None):
    return _uc_case.EngageCaseReceivedUseCase(
        dl, _unwrap(dispatchable)
    ).execute()


def defer_case(dispatchable, dl=None):
    return _uc_case.DeferCaseReceivedUseCase(
        dl, _unwrap(dispatchable)
    ).execute()


def add_report_to_case(dispatchable, dl=None):
    return _uc_case.AddReportToCaseReceivedUseCase(
        dl, _unwrap(dispatchable)
    ).execute()


def close_case(dispatchable, dl=None):
    return _uc_case.CloseCaseReceivedUseCase(
        dl, _unwrap(dispatchable)
    ).execute()


def update_case(dispatchable, dl=None):
    return _uc_case.UpdateCaseReceivedUseCase(
        dl, _unwrap(dispatchable)
    ).execute()


# ---- case participant handlers ---------------------------------------------


def create_case_participant(dispatchable, dl=None):
    return _uc_participant.CreateCaseParticipantReceivedUseCase(
        dl, _unwrap(dispatchable)
    ).execute()


def add_case_participant_to_case(dispatchable, dl=None):
    return _uc_participant.AddCaseParticipantToCaseReceivedUseCase(
        dl, _unwrap(dispatchable)
    ).execute()


def remove_case_participant_from_case(dispatchable, dl=None):
    return _uc_participant.RemoveCaseParticipantFromCaseReceivedUseCase(
        dl, _unwrap(dispatchable)
    ).execute()


# ---- actor handlers --------------------------------------------------------


def suggest_actor_to_case(dispatchable, dl=None):
    return _uc_actor.SuggestActorToCaseReceivedUseCase(
        dl, _unwrap(dispatchable)
    ).execute()


def accept_suggest_actor_to_case(dispatchable, dl=None):
    return _uc_actor.AcceptSuggestActorToCaseReceivedUseCase(
        dl, _unwrap(dispatchable)
    ).execute()


def reject_suggest_actor_to_case(dispatchable, dl=None):
    return _uc_actor.RejectSuggestActorToCaseReceivedUseCase(
        dl, _unwrap(dispatchable)
    ).execute()


def offer_case_ownership_transfer(dispatchable, dl=None):
    return _uc_actor.OfferCaseOwnershipTransferReceivedUseCase(
        dl, _unwrap(dispatchable)
    ).execute()


def accept_case_ownership_transfer(dispatchable, dl=None):
    return _uc_actor.AcceptCaseOwnershipTransferReceivedUseCase(
        dl, _unwrap(dispatchable)
    ).execute()


def reject_case_ownership_transfer(dispatchable, dl=None):
    return _uc_actor.RejectCaseOwnershipTransferReceivedUseCase(
        dl, _unwrap(dispatchable)
    ).execute()


def invite_actor_to_case(dispatchable, dl=None):
    return _uc_actor.InviteActorToCaseReceivedUseCase(
        dl, _unwrap(dispatchable)
    ).execute()


def accept_invite_actor_to_case(dispatchable, dl=None):
    return _uc_actor.AcceptInviteActorToCaseReceivedUseCase(
        dl, _unwrap(dispatchable)
    ).execute()


def reject_invite_actor_to_case(dispatchable, dl=None):
    return _uc_actor.RejectInviteActorToCaseReceivedUseCase(
        dl, _unwrap(dispatchable)
    ).execute()


# ---- embargo handlers ------------------------------------------------------


def create_embargo_event(dispatchable, dl=None):
    return _uc_embargo.CreateEmbargoEventReceivedUseCase(
        dl, _unwrap(dispatchable)
    ).execute()


def add_embargo_event_to_case(dispatchable, dl=None):
    return _uc_embargo.AddEmbargoEventToCaseReceivedUseCase(
        dl, _unwrap(dispatchable)
    ).execute()


def remove_embargo_event_from_case(dispatchable, dl=None):
    return _uc_embargo.RemoveEmbargoEventFromCaseReceivedUseCase(
        dl, _unwrap(dispatchable)
    ).execute()


def announce_embargo_event_to_case(dispatchable, dl=None):
    return _uc_embargo.AnnounceEmbargoEventToCaseReceivedUseCase(
        dl, _unwrap(dispatchable)
    ).execute()


def invite_to_embargo_on_case(dispatchable, dl=None):
    return _uc_embargo.InviteToEmbargoOnCaseReceivedUseCase(
        dl, _unwrap(dispatchable)
    ).execute()


def accept_invite_to_embargo_on_case(dispatchable, dl=None):
    return _uc_embargo.AcceptInviteToEmbargoOnCaseReceivedUseCase(
        dl, _unwrap(dispatchable)
    ).execute()


def reject_invite_to_embargo_on_case(dispatchable, dl=None):
    return _uc_embargo.RejectInviteToEmbargoOnCaseReceivedUseCase(
        dl, _unwrap(dispatchable)
    ).execute()


# ---- note handlers ---------------------------------------------------------


def create_note(dispatchable, dl=None):
    return _uc_note.CreateNoteReceivedUseCase(
        dl, _unwrap(dispatchable)
    ).execute()


def add_note_to_case(dispatchable, dl=None):
    return _uc_note.AddNoteToCaseReceivedUseCase(
        dl, _unwrap(dispatchable)
    ).execute()


def remove_note_from_case(dispatchable, dl=None):
    return _uc_note.RemoveNoteFromCaseReceivedUseCase(
        dl, _unwrap(dispatchable)
    ).execute()


# ---- status handlers -------------------------------------------------------


def create_case_status(dispatchable, dl=None):
    return _uc_status.CreateCaseStatusReceivedUseCase(
        dl, _unwrap(dispatchable)
    ).execute()


def add_case_status_to_case(dispatchable, dl=None):
    return _uc_status.AddCaseStatusToCaseReceivedUseCase(
        dl, _unwrap(dispatchable)
    ).execute()


def create_participant_status(dispatchable, dl=None):
    return _uc_status.CreateParticipantStatusReceivedUseCase(
        dl, _unwrap(dispatchable)
    ).execute()


def add_participant_status_to_participant(dispatchable, dl=None):
    return _uc_status.AddParticipantStatusToParticipantReceivedUseCase(
        dl, _unwrap(dispatchable)
    ).execute()


# ---- unknown handler -------------------------------------------------------


def unknown(dispatchable, dl=None):
    return _uc_unknown.UnknownUseCase(dl, _unwrap(dispatchable)).execute()


__all__ = [
    "verify_semantics",
    # report
    "create_report",
    "submit_report",
    "validate_report",
    "invalidate_report",
    "ack_report",
    "close_report",
    # case
    "create_case",
    "engage_case",
    "defer_case",
    "add_report_to_case",
    "close_case",
    "update_case",
    # case participant
    "create_case_participant",
    "add_case_participant_to_case",
    "remove_case_participant_from_case",
    # actor
    "suggest_actor_to_case",
    "accept_suggest_actor_to_case",
    "reject_suggest_actor_to_case",
    "offer_case_ownership_transfer",
    "accept_case_ownership_transfer",
    "reject_case_ownership_transfer",
    "invite_actor_to_case",
    "accept_invite_actor_to_case",
    "reject_invite_actor_to_case",
    # embargo
    "create_embargo_event",
    "add_embargo_event_to_case",
    "remove_embargo_event_from_case",
    "announce_embargo_event_to_case",
    "invite_to_embargo_on_case",
    "accept_invite_to_embargo_on_case",
    "reject_invite_to_embargo_on_case",
    # note
    "create_note",
    "add_note_to_case",
    "remove_note_from_case",
    # status
    "create_case_status",
    "add_case_status_to_case",
    "create_participant_status",
    "add_participant_status_to_participant",
    # unknown
    "unknown",
]
