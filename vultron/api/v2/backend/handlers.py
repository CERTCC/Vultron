"""
Provides handler functions for specific activities in the Vultron API v2 backend.
"""

from typing import Protocol

from vultron.behavior_dispatcher import DispatchActivity
import logging

logger = logging.getLogger(__name__)


class BehaviorHandler(Protocol):
    """
    Protocol for behavior handler functions.
    """

    def __call__(self, dispatchable: DispatchActivity) -> None: ...


def create_report(dispatchable: DispatchActivity) -> None:
    logger.debug("create_report handler called: %s", dispatchable)
    return None


def submit_report(dispatchable: DispatchActivity) -> None:
    logger.debug("submit_report handler called: %s", dispatchable)
    return None


def validate_report(dispatchable: DispatchActivity) -> None:
    logger.debug("validate_report handler called: %s", dispatchable)
    return None


def invalidate_report(dispatchable: DispatchActivity) -> None:
    logger.debug("invalidate_report handler called: %s", dispatchable)
    return None


def ack_report(dispatchable: DispatchActivity) -> None:
    logger.debug("ack_report handler called: %s", dispatchable)
    return None


def close_report(dispatchable: DispatchActivity) -> None:
    logger.debug("close_report handler called: %s", dispatchable)
    return None


def create_case(dispatchable: DispatchActivity) -> None:
    logger.debug("create_case handler called: %s", dispatchable)
    return None


def add_report_to_case(dispatchable: DispatchActivity) -> None:
    logger.debug("add_report_to_case handler called: %s", dispatchable)
    return None


def suggest_actor_to_case(dispatchable: DispatchActivity) -> None:
    logger.debug("suggest_actor_to_case handler called: %s", dispatchable)
    return None


def accept_suggest_actor_to_case(dispatchable: DispatchActivity) -> None:
    logger.debug(
        "accept_suggest_actor_to_case handler called: %s", dispatchable
    )
    return None


def reject_suggest_actor_to_case(dispatchable: DispatchActivity) -> None:
    logger.debug(
        "reject_suggest_actor_to_case handler called: %s", dispatchable
    )
    return None


def offer_case_ownership_transfer(dispatchable: DispatchActivity) -> None:
    logger.debug(
        "offer_case_ownership_transfer handler called: %s", dispatchable
    )
    return None


def accept_case_ownership_transfer(dispatchable: DispatchActivity) -> None:
    logger.debug(
        "accept_case_ownership_transfer handler called: %s", dispatchable
    )
    return None


def reject_case_ownership_transfer(dispatchable: DispatchActivity) -> None:
    logger.debug(
        "reject_case_ownership_transfer handler called: %s", dispatchable
    )
    return None


def invite_actor_to_case(dispatchable: DispatchActivity) -> None:
    logger.debug("invite_actor_to_case handler called: %s", dispatchable)
    return None


def accept_invite_actor_to_case(dispatchable: DispatchActivity) -> None:
    logger.debug(
        "accept_invite_actor_to_case handler called: %s", dispatchable
    )
    return None


def reject_invite_actor_to_case(dispatchable: DispatchActivity) -> None:
    logger.debug(
        "reject_invite_actor_to_case handler called: %s", dispatchable
    )
    return None


def create_embargo_event(dispatchable: DispatchActivity) -> None:
    logger.debug("create_embargo_event handler called: %s", dispatchable)
    return None


def add_embargo_event_to_case(dispatchable: DispatchActivity) -> None:
    logger.debug("add_embargo_event_to_case handler called: %s", dispatchable)
    return None


def remove_embargo_event_from_case(dispatchable: DispatchActivity) -> None:
    logger.debug(
        "remove_embargo_event_from_case handler called: %s", dispatchable
    )
    return None


def announce_embargo_event_to_case(dispatchable: DispatchActivity) -> None:
    logger.debug(
        "announce_embargo_event_to_case handler called: %s", dispatchable
    )
    return None


def invite_to_embargo_on_case(dispatchable: DispatchActivity) -> None:
    logger.debug("invite_to_embargo_on_case handler called: %s", dispatchable)
    return None


def accept_invite_to_embargo_on_case(dispatchable: DispatchActivity) -> None:
    logger.debug(
        "accept_invite_to_embargo_on_case handler called: %s", dispatchable
    )
    return None


def reject_invite_to_embargo_on_case(dispatchable: DispatchActivity) -> None:
    logger.debug(
        "reject_invite_to_embargo_on_case handler called: %s", dispatchable
    )
    return None


def close_case(dispatchable: DispatchActivity) -> None:
    logger.debug("close_case handler called: %s", dispatchable)
    return None


def create_case_participant(dispatchable: DispatchActivity) -> None:
    logger.debug("create_case_participant handler called: %s", dispatchable)
    return None


def add_case_participant_to_case(dispatchable: DispatchActivity) -> None:
    logger.debug(
        "add_case_participant_to_case handler called: %s", dispatchable
    )
    return None


def remove_case_participant_from_case(dispatchable: DispatchActivity) -> None:
    logger.debug(
        "remove_case_participant_from_case handler called: %s", dispatchable
    )
    return None


def create_note(dispatchable: DispatchActivity) -> None:
    logger.debug("create_note handler called: %s", dispatchable)
    return None


def add_note_to_case(dispatchable: DispatchActivity) -> None:
    logger.debug("add_note_to_case handler called: %s", dispatchable)
    return None


def remove_note_from_case(dispatchable: DispatchActivity) -> None:
    logger.debug("remove_note_from_case handler called: %s", dispatchable)
    return None


def create_case_status(dispatchable: DispatchActivity) -> None:
    logger.debug("create_case_status handler called: %s", dispatchable)
    return None


def add_case_status_to_case(dispatchable: DispatchActivity) -> None:
    logger.debug("add_case_status_to_case handler called: %s", dispatchable)
    return None


def create_participant_status(dispatchable: DispatchActivity) -> None:
    logger.debug("create_participant_status handler called: %s", dispatchable)
    return None


def add_participant_status_to_participant(
    dispatchable: DispatchActivity,
) -> None:
    logger.debug(
        "add_participant_status_to_participant handler called: %s",
        dispatchable,
    )
    return None


def unknown(dispatchable: DispatchActivity) -> None:
    logger.warning("unknown handler called for dispatchable: %s", dispatchable)
    return None
