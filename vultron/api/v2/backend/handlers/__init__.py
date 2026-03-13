"""
Backward-compatibility shim for vultron.api.v2.backend.handlers.

As of P75-2c the handler-shim layer has been collapsed. The canonical
implementations now live in ``vultron.core.use_cases.*``.

This module re-exports:
- ``verify_semantics`` — as a no-op shim (semantic checking now happens at
  dispatcher routing-table level)
- All use-case callables under their original handler function names so that
  existing call sites (tests and legacy code) continue to work unchanged.

New code should import directly from ``vultron.core.use_cases.*``.
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
    return _uc_report.create_report(_unwrap(dispatchable), dl)


def submit_report(dispatchable, dl=None):
    return _uc_report.submit_report(_unwrap(dispatchable), dl)


def validate_report(dispatchable, dl=None):
    return _uc_report.validate_report(_unwrap(dispatchable), dl)


def invalidate_report(dispatchable, dl=None):
    return _uc_report.invalidate_report(_unwrap(dispatchable), dl)


def ack_report(dispatchable, dl=None):
    return _uc_report.ack_report(_unwrap(dispatchable), dl)


def close_report(dispatchable, dl=None):
    return _uc_report.close_report(_unwrap(dispatchable), dl)


# ---- case handlers ---------------------------------------------------------


def create_case(dispatchable, dl=None):
    return _uc_case.create_case(_unwrap(dispatchable), dl)


def engage_case(dispatchable, dl=None):
    return _uc_case.engage_case(_unwrap(dispatchable), dl)


def defer_case(dispatchable, dl=None):
    return _uc_case.defer_case(_unwrap(dispatchable), dl)


def add_report_to_case(dispatchable, dl=None):
    return _uc_case.add_report_to_case(_unwrap(dispatchable), dl)


def close_case(dispatchable, dl=None):
    return _uc_case.close_case(_unwrap(dispatchable), dl)


def update_case(dispatchable, dl=None):
    return _uc_case.update_case(_unwrap(dispatchable), dl)


# ---- case participant handlers ---------------------------------------------


def create_case_participant(dispatchable, dl=None):
    return _uc_participant.create_case_participant(_unwrap(dispatchable), dl)


def add_case_participant_to_case(dispatchable, dl=None):
    return _uc_participant.add_case_participant_to_case(
        _unwrap(dispatchable), dl
    )


def remove_case_participant_from_case(dispatchable, dl=None):
    return _uc_participant.remove_case_participant_from_case(
        _unwrap(dispatchable), dl
    )


# ---- actor handlers --------------------------------------------------------


def suggest_actor_to_case(dispatchable, dl=None):
    return _uc_actor.suggest_actor_to_case(_unwrap(dispatchable), dl)


def accept_suggest_actor_to_case(dispatchable, dl=None):
    return _uc_actor.accept_suggest_actor_to_case(_unwrap(dispatchable), dl)


def reject_suggest_actor_to_case(dispatchable, dl=None):
    return _uc_actor.reject_suggest_actor_to_case(_unwrap(dispatchable), dl)


def offer_case_ownership_transfer(dispatchable, dl=None):
    return _uc_actor.offer_case_ownership_transfer(_unwrap(dispatchable), dl)


def accept_case_ownership_transfer(dispatchable, dl=None):
    return _uc_actor.accept_case_ownership_transfer(_unwrap(dispatchable), dl)


def reject_case_ownership_transfer(dispatchable, dl=None):
    return _uc_actor.reject_case_ownership_transfer(_unwrap(dispatchable), dl)


def invite_actor_to_case(dispatchable, dl=None):
    return _uc_actor.invite_actor_to_case(_unwrap(dispatchable), dl)


def accept_invite_actor_to_case(dispatchable, dl=None):
    return _uc_actor.accept_invite_actor_to_case(_unwrap(dispatchable), dl)


def reject_invite_actor_to_case(dispatchable, dl=None):
    return _uc_actor.reject_invite_actor_to_case(_unwrap(dispatchable), dl)


# ---- embargo handlers ------------------------------------------------------


def create_embargo_event(dispatchable, dl=None):
    return _uc_embargo.create_embargo_event(_unwrap(dispatchable), dl)


def add_embargo_event_to_case(dispatchable, dl=None):
    return _uc_embargo.add_embargo_event_to_case(_unwrap(dispatchable), dl)


def remove_embargo_event_from_case(dispatchable, dl=None):
    return _uc_embargo.remove_embargo_event_from_case(
        _unwrap(dispatchable), dl
    )


def announce_embargo_event_to_case(dispatchable, dl=None):
    return _uc_embargo.announce_embargo_event_to_case(
        _unwrap(dispatchable), dl
    )


def invite_to_embargo_on_case(dispatchable, dl=None):
    return _uc_embargo.invite_to_embargo_on_case(_unwrap(dispatchable), dl)


def accept_invite_to_embargo_on_case(dispatchable, dl=None):
    return _uc_embargo.accept_invite_to_embargo_on_case(
        _unwrap(dispatchable), dl
    )


def reject_invite_to_embargo_on_case(dispatchable, dl=None):
    return _uc_embargo.reject_invite_to_embargo_on_case(
        _unwrap(dispatchable), dl
    )


# ---- note handlers ---------------------------------------------------------


def create_note(dispatchable, dl=None):
    return _uc_note.create_note(_unwrap(dispatchable), dl)


def add_note_to_case(dispatchable, dl=None):
    return _uc_note.add_note_to_case(_unwrap(dispatchable), dl)


def remove_note_from_case(dispatchable, dl=None):
    return _uc_note.remove_note_from_case(_unwrap(dispatchable), dl)


# ---- status handlers -------------------------------------------------------


def create_case_status(dispatchable, dl=None):
    return _uc_status.create_case_status(_unwrap(dispatchable), dl)


def add_case_status_to_case(dispatchable, dl=None):
    return _uc_status.add_case_status_to_case(_unwrap(dispatchable), dl)


def create_participant_status(dispatchable, dl=None):
    return _uc_status.create_participant_status(_unwrap(dispatchable), dl)


def add_participant_status_to_participant(dispatchable, dl=None):
    return _uc_status.add_participant_status_to_participant(
        _unwrap(dispatchable), dl
    )


# ---- unknown handler -------------------------------------------------------


def unknown(dispatchable, dl=None):
    return _uc_unknown.unknown(_unwrap(dispatchable), dl)


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
