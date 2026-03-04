"""
Handler functions for Vultron API v2 backend activities.

Re-exports all handler functions and the verify_semantics decorator from
submodules for backward compatibility.
"""

from vultron.api.v2.backend.handlers._base import verify_semantics
from vultron.api.v2.backend.handlers.actor import (
    accept_case_ownership_transfer,
    accept_invite_actor_to_case,
    accept_suggest_actor_to_case,
    invite_actor_to_case,
    offer_case_ownership_transfer,
    reject_case_ownership_transfer,
    reject_invite_actor_to_case,
    reject_suggest_actor_to_case,
    suggest_actor_to_case,
)
from vultron.api.v2.backend.handlers.case import (
    add_report_to_case,
    close_case,
    create_case,
    defer_case,
    engage_case,
    update_case,
)
from vultron.api.v2.backend.handlers.embargo import (
    accept_invite_to_embargo_on_case,
    add_embargo_event_to_case,
    announce_embargo_event_to_case,
    create_embargo_event,
    invite_to_embargo_on_case,
    reject_invite_to_embargo_on_case,
    remove_embargo_event_from_case,
)
from vultron.api.v2.backend.handlers.note import (
    add_note_to_case,
    create_note,
    remove_note_from_case,
)
from vultron.api.v2.backend.handlers.participant import (
    add_case_participant_to_case,
    create_case_participant,
    remove_case_participant_from_case,
)
from vultron.api.v2.backend.handlers.report import (
    ack_report,
    close_report,
    create_report,
    invalidate_report,
    submit_report,
    validate_report,
)
from vultron.api.v2.backend.handlers.status import (
    add_case_status_to_case,
    add_participant_status_to_participant,
    create_case_status,
    create_participant_status,
)
from vultron.api.v2.backend.handlers.unknown import unknown

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
    # actor / invite / ownership
    "suggest_actor_to_case",
    "accept_suggest_actor_to_case",
    "reject_suggest_actor_to_case",
    "offer_case_ownership_transfer",
    "accept_case_ownership_transfer",
    "reject_case_ownership_transfer",
    "invite_actor_to_case",
    "accept_invite_actor_to_case",
    "reject_invite_actor_to_case",
    # participant
    "create_case_participant",
    "add_case_participant_to_case",
    "remove_case_participant_from_case",
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
