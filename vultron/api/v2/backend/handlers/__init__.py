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
    return _uc_report.CreateReportReceivedUseCase(dl).execute(
        _unwrap(dispatchable)
    )


def submit_report(dispatchable, dl=None):
    return _uc_report.SubmitReportReceivedUseCase(dl).execute(
        _unwrap(dispatchable)
    )


def validate_report(dispatchable, dl=None):
    return _uc_report.ValidateReportReceivedUseCase(dl).execute(
        _unwrap(dispatchable)
    )


def invalidate_report(dispatchable, dl=None):
    return _uc_report.InvalidateReportReceivedUseCase(dl).execute(
        _unwrap(dispatchable)
    )


def ack_report(dispatchable, dl=None):
    return _uc_report.AckReportReceivedUseCase(dl).execute(
        _unwrap(dispatchable)
    )


def close_report(dispatchable, dl=None):
    return _uc_report.CloseReportReceivedUseCase(dl).execute(
        _unwrap(dispatchable)
    )


# ---- case handlers ---------------------------------------------------------


def create_case(dispatchable, dl=None):
    return _uc_case.CreateCaseReceivedUseCase(dl).execute(
        _unwrap(dispatchable)
    )


def engage_case(dispatchable, dl=None):
    return _uc_case.EngageCaseReceivedUseCase(dl).execute(
        _unwrap(dispatchable)
    )


def defer_case(dispatchable, dl=None):
    return _uc_case.DeferCaseReceivedUseCase(dl).execute(_unwrap(dispatchable))


def add_report_to_case(dispatchable, dl=None):
    return _uc_case.AddReportToCaseReceivedUseCase(dl).execute(
        _unwrap(dispatchable)
    )


def close_case(dispatchable, dl=None):
    return _uc_case.CloseCaseReceivedUseCase(dl).execute(_unwrap(dispatchable))


def update_case(dispatchable, dl=None):
    return _uc_case.UpdateCaseReceivedUseCase(dl).execute(
        _unwrap(dispatchable)
    )


# ---- case participant handlers ---------------------------------------------


def create_case_participant(dispatchable, dl=None):
    return _uc_participant.CreateCaseParticipantReceivedUseCase(dl).execute(
        _unwrap(dispatchable)
    )


def add_case_participant_to_case(dispatchable, dl=None):
    return _uc_participant.AddCaseParticipantToCaseReceivedUseCase(dl).execute(
        _unwrap(dispatchable)
    )


def remove_case_participant_from_case(dispatchable, dl=None):
    return _uc_participant.RemoveCaseParticipantFromCaseReceivedUseCase(
        dl
    ).execute(_unwrap(dispatchable))


# ---- actor handlers --------------------------------------------------------


def suggest_actor_to_case(dispatchable, dl=None):
    return _uc_actor.SuggestActorToCaseReceivedUseCase(dl).execute(
        _unwrap(dispatchable)
    )


def accept_suggest_actor_to_case(dispatchable, dl=None):
    return _uc_actor.AcceptSuggestActorToCaseReceivedUseCase(dl).execute(
        _unwrap(dispatchable)
    )


def reject_suggest_actor_to_case(dispatchable, dl=None):
    return _uc_actor.RejectSuggestActorToCaseReceivedUseCase(dl).execute(
        _unwrap(dispatchable)
    )


def offer_case_ownership_transfer(dispatchable, dl=None):
    return _uc_actor.OfferCaseOwnershipTransferReceivedUseCase(dl).execute(
        _unwrap(dispatchable)
    )


def accept_case_ownership_transfer(dispatchable, dl=None):
    return _uc_actor.AcceptCaseOwnershipTransferReceivedUseCase(dl).execute(
        _unwrap(dispatchable)
    )


def reject_case_ownership_transfer(dispatchable, dl=None):
    return _uc_actor.RejectCaseOwnershipTransferReceivedUseCase(dl).execute(
        _unwrap(dispatchable)
    )


def invite_actor_to_case(dispatchable, dl=None):
    return _uc_actor.InviteActorToCaseReceivedUseCase(dl).execute(
        _unwrap(dispatchable)
    )


def accept_invite_actor_to_case(dispatchable, dl=None):
    return _uc_actor.AcceptInviteActorToCaseReceivedUseCase(dl).execute(
        _unwrap(dispatchable)
    )


def reject_invite_actor_to_case(dispatchable, dl=None):
    return _uc_actor.RejectInviteActorToCaseReceivedUseCase(dl).execute(
        _unwrap(dispatchable)
    )


# ---- embargo handlers ------------------------------------------------------


def create_embargo_event(dispatchable, dl=None):
    return _uc_embargo.CreateEmbargoEventReceivedUseCase(dl).execute(
        _unwrap(dispatchable)
    )


def add_embargo_event_to_case(dispatchable, dl=None):
    return _uc_embargo.AddEmbargoEventToCaseReceivedUseCase(dl).execute(
        _unwrap(dispatchable)
    )


def remove_embargo_event_from_case(dispatchable, dl=None):
    return _uc_embargo.RemoveEmbargoEventFromCaseReceivedUseCase(dl).execute(
        _unwrap(dispatchable)
    )


def announce_embargo_event_to_case(dispatchable, dl=None):
    return _uc_embargo.AnnounceEmbargoEventToCaseReceivedUseCase(dl).execute(
        _unwrap(dispatchable)
    )


def invite_to_embargo_on_case(dispatchable, dl=None):
    return _uc_embargo.InviteToEmbargoOnCaseReceivedUseCase(dl).execute(
        _unwrap(dispatchable)
    )


def accept_invite_to_embargo_on_case(dispatchable, dl=None):
    return _uc_embargo.AcceptInviteToEmbargoOnCaseReceivedUseCase(dl).execute(
        _unwrap(dispatchable)
    )


def reject_invite_to_embargo_on_case(dispatchable, dl=None):
    return _uc_embargo.RejectInviteToEmbargoOnCaseReceivedUseCase(dl).execute(
        _unwrap(dispatchable)
    )


# ---- note handlers ---------------------------------------------------------


def create_note(dispatchable, dl=None):
    return _uc_note.CreateNoteReceivedUseCase(dl).execute(
        _unwrap(dispatchable)
    )


def add_note_to_case(dispatchable, dl=None):
    return _uc_note.AddNoteToCaseReceivedUseCase(dl).execute(
        _unwrap(dispatchable)
    )


def remove_note_from_case(dispatchable, dl=None):
    return _uc_note.RemoveNoteFromCaseReceivedUseCase(dl).execute(
        _unwrap(dispatchable)
    )


# ---- status handlers -------------------------------------------------------


def create_case_status(dispatchable, dl=None):
    return _uc_status.CreateCaseStatusReceivedUseCase(dl).execute(
        _unwrap(dispatchable)
    )


def add_case_status_to_case(dispatchable, dl=None):
    return _uc_status.AddCaseStatusToCaseReceivedUseCase(dl).execute(
        _unwrap(dispatchable)
    )


def create_participant_status(dispatchable, dl=None):
    return _uc_status.CreateParticipantStatusReceivedUseCase(dl).execute(
        _unwrap(dispatchable)
    )


def add_participant_status_to_participant(dispatchable, dl=None):
    return _uc_status.AddParticipantStatusToParticipantReceivedUseCase(
        dl
    ).execute(_unwrap(dispatchable))


# ---- unknown handler -------------------------------------------------------


def unknown(dispatchable, dl=None):
    return _uc_unknown.UnknownUseCase(dl).execute(_unwrap(dispatchable))


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
