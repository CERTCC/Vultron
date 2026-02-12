"""
Provides handler functions for specific activities in the Vultron API v2 backend.
"""

from functools import wraps
from typing import Protocol

from vultron.api.v2.errors import (
    VultronApiHandlerMissingSemanticError,
    VultronApiHandlerSemanticMismatchError,
)
from vultron.behavior_dispatcher import DispatchActivity
import logging

from vultron.enums import MessageSemantics
from vultron.semantic_map import find_matching_semantics

logger = logging.getLogger(__name__)


class BehaviorHandler(Protocol):
    """
    Protocol for behavior handler functions.
    """

    def __call__(self, dispatchable: DispatchActivity) -> None: ...


def verify_semantics(expected_semantic_type: MessageSemantics):
    def decorator(func):
        @wraps(func)
        def wrapper(dispatchable: DispatchActivity):
            if not dispatchable.semantic_type:
                logger.error(
                    "Dispatchable activity %s is missing semantic_type",
                    dispatchable,
                )
                raise VultronApiHandlerMissingSemanticError()

            computed = find_matching_semantics(dispatchable.payload)

            if computed != expected_semantic_type:
                logger.error(
                    "Dispatchable activity %s claims semantic_type %s that does not match its payload (%s)",
                    dispatchable,
                    expected_semantic_type,
                    computed,
                )
                raise VultronApiHandlerSemanticMismatchError(
                    expected=expected_semantic_type, actual=computed
                )

            return func(dispatchable)


@verify_semantics(MessageSemantics.CREATE_REPORT)
def create_report(dispatchable: DispatchActivity) -> None:
    logger.debug("create_report handler called: %s", dispatchable)

    return None


@verify_semantics(MessageSemantics.SUBMIT_REPORT)
def submit_report(dispatchable: DispatchActivity) -> None:
    logger.debug("submit_report handler called: %s", dispatchable)
    return None


@verify_semantics(MessageSemantics.VALIDATE_REPORT)
def validate_report(dispatchable: DispatchActivity) -> None:
    logger.debug("validate_report handler called: %s", dispatchable)
    return None


@verify_semantics(MessageSemantics.INVALIDATE_REPORT)
def invalidate_report(dispatchable: DispatchActivity) -> None:
    logger.debug("invalidate_report handler called: %s", dispatchable)
    return None


@verify_semantics(MessageSemantics.ACK_REPORT)
def ack_report(dispatchable: DispatchActivity) -> None:
    logger.debug("ack_report handler called: %s", dispatchable)
    return None


@verify_semantics(MessageSemantics.CLOSE_REPORT)
def close_report(dispatchable: DispatchActivity) -> None:
    logger.debug("close_report handler called: %s", dispatchable)
    return None


@verify_semantics(MessageSemantics.CREATE_CASE)
def create_case(dispatchable: DispatchActivity) -> None:
    logger.debug("create_case handler called: %s", dispatchable)
    return None


@verify_semantics(MessageSemantics.ADD_REPORT_TO_CASE)
def add_report_to_case(dispatchable: DispatchActivity) -> None:
    logger.debug("add_report_to_case handler called: %s", dispatchable)
    return None


@verify_semantics(MessageSemantics.SUGGEST_ACTOR_TO_CASE)
def suggest_actor_to_case(dispatchable: DispatchActivity) -> None:
    logger.debug("suggest_actor_to_case handler called: %s", dispatchable)
    return None


@verify_semantics(MessageSemantics.ACCEPT_SUGGEST_ACTOR_TO_CASE)
def accept_suggest_actor_to_case(dispatchable: DispatchActivity) -> None:
    logger.debug(
        "accept_suggest_actor_to_case handler called: %s", dispatchable
    )
    return None


@verify_semantics(MessageSemantics.REJECT_SUGGEST_ACTOR_TO_CASE)
def reject_suggest_actor_to_case(dispatchable: DispatchActivity) -> None:
    logger.debug(
        "reject_suggest_actor_to_case handler called: %s", dispatchable
    )
    return None


@verify_semantics(MessageSemantics.OFFER_CASE_OWNERSHIP_TRANSFER)
def offer_case_ownership_transfer(dispatchable: DispatchActivity) -> None:
    logger.debug(
        "offer_case_ownership_transfer handler called: %s", dispatchable
    )
    return None


@verify_semantics(MessageSemantics.ACCEPT_CASE_OWNERSHIP_TRANSFER)
def accept_case_ownership_transfer(dispatchable: DispatchActivity) -> None:
    logger.debug(
        "accept_case_ownership_transfer handler called: %s", dispatchable
    )
    return None


@verify_semantics(MessageSemantics.REJECT_CASE_OWNERSHIP_TRANSFER)
def reject_case_ownership_transfer(dispatchable: DispatchActivity) -> None:
    logger.debug(
        "reject_case_ownership_transfer handler called: %s", dispatchable
    )
    return None


@verify_semantics(MessageSemantics.INVITE_ACTOR_TO_CASE)
def invite_actor_to_case(dispatchable: DispatchActivity) -> None:
    logger.debug("invite_actor_to_case handler called: %s", dispatchable)
    return None


@verify_semantics(MessageSemantics.ACCEPT_INVITE_ACTOR_TO_CASE)
def accept_invite_actor_to_case(dispatchable: DispatchActivity) -> None:
    logger.debug(
        "accept_invite_actor_to_case handler called: %s", dispatchable
    )
    return None


@verify_semantics(MessageSemantics.REJECT_INVITE_ACTOR_TO_CASE)
def reject_invite_actor_to_case(dispatchable: DispatchActivity) -> None:
    logger.debug(
        "reject_invite_actor_to_case handler called: %s", dispatchable
    )
    return None


@verify_semantics(MessageSemantics.CREATE_EMBARGO_EVENT)
def create_embargo_event(dispatchable: DispatchActivity) -> None:
    logger.debug("create_embargo_event handler called: %s", dispatchable)
    return None


@verify_semantics(MessageSemantics.ADD_EMBARGO_EVENT_TO_CASE)
def add_embargo_event_to_case(dispatchable: DispatchActivity) -> None:
    logger.debug("add_embargo_event_to_case handler called: %s", dispatchable)
    return None


@verify_semantics(MessageSemantics.REMOVE_EMBARGO_EVENT_FROM_CASE)
def remove_embargo_event_from_case(dispatchable: DispatchActivity) -> None:
    logger.debug(
        "remove_embargo_event_from_case handler called: %s", dispatchable
    )
    return None


@verify_semantics(MessageSemantics.ANNOUNCE_EMBARGO_EVENT_TO_CASE)
def announce_embargo_event_to_case(dispatchable: DispatchActivity) -> None:
    logger.debug(
        "announce_embargo_event_to_case handler called: %s", dispatchable
    )
    return None


@verify_semantics(MessageSemantics.INVITE_TO_EMBARGO_ON_CASE)
def invite_to_embargo_on_case(dispatchable: DispatchActivity) -> None:
    logger.debug("invite_to_embargo_on_case handler called: %s", dispatchable)
    return None


@verify_semantics(MessageSemantics.ACCEPT_INVITE_TO_EMBARGO_ON_CASE)
def accept_invite_to_embargo_on_case(dispatchable: DispatchActivity) -> None:
    logger.debug(
        "accept_invite_to_embargo_on_case handler called: %s", dispatchable
    )
    return None


@verify_semantics(MessageSemantics.REJECT_INVITE_TO_EMBARGO_ON_CASE)
def reject_invite_to_embargo_on_case(dispatchable: DispatchActivity) -> None:
    logger.debug(
        "reject_invite_to_embargo_on_case handler called: %s", dispatchable
    )
    return None


@verify_semantics(MessageSemantics.CLOSE_CASE)
def close_case(dispatchable: DispatchActivity) -> None:
    logger.debug("close_case handler called: %s", dispatchable)
    return None


@verify_semantics(MessageSemantics.CREATE_CASE_PARTICIPANT)
def create_case_participant(dispatchable: DispatchActivity) -> None:
    logger.debug("create_case_participant handler called: %s", dispatchable)
    return None


@verify_semantics(MessageSemantics.ADD_CASE_PARTICIPANT_TO_CASE)
def add_case_participant_to_case(dispatchable: DispatchActivity) -> None:
    logger.debug(
        "add_case_participant_to_case handler called: %s", dispatchable
    )
    return None


@verify_semantics(MessageSemantics.REMOVE_CASE_PARTICIPANT_FROM_CASE)
def remove_case_participant_from_case(dispatchable: DispatchActivity) -> None:
    logger.debug(
        "remove_case_participant_from_case handler called: %s", dispatchable
    )
    return None


@verify_semantics(MessageSemantics.CREATE_NOTE)
def create_note(dispatchable: DispatchActivity) -> None:
    logger.debug("create_note handler called: %s", dispatchable)
    return None


@verify_semantics(MessageSemantics.ADD_NOTE_TO_CASE)
def add_note_to_case(dispatchable: DispatchActivity) -> None:
    logger.debug("add_note_to_case handler called: %s", dispatchable)
    return None


@verify_semantics(MessageSemantics.REMOVE_NOTE_FROM_CASE)
def remove_note_from_case(dispatchable: DispatchActivity) -> None:
    logger.debug("remove_note_from_case handler called: %s", dispatchable)
    return None


@verify_semantics(MessageSemantics.CREATE_CASE_STATUS)
def create_case_status(dispatchable: DispatchActivity) -> None:
    logger.debug("create_case_status handler called: %s", dispatchable)
    return None


@verify_semantics(MessageSemantics.ADD_CASE_STATUS_TO_CASE)
def add_case_status_to_case(dispatchable: DispatchActivity) -> None:
    logger.debug("add_case_status_to_case handler called: %s", dispatchable)
    return None


@verify_semantics(MessageSemantics.CREATE_PARTICIPANT_STATUS)
def create_participant_status(dispatchable: DispatchActivity) -> None:
    logger.debug("create_participant_status handler called: %s", dispatchable)
    return None


@verify_semantics(MessageSemantics.ADD_PARTICIPANT_STATUS_TO_PARTICIPANT)
def add_participant_status_to_participant(
    dispatchable: DispatchActivity,
) -> None:
    logger.debug(
        "add_participant_status_to_participant handler called: %s",
        dispatchable,
    )
    return None


@verify_semantics(MessageSemantics.UNKNOWN)
def unknown(dispatchable: DispatchActivity) -> None:
    logger.warning("unknown handler called for dispatchable: %s", dispatchable)
    return None
