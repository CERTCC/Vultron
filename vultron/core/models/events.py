"""Domain event vocabulary for the Vultron Protocol.

Defines the authoritative vocabulary of semantic intents that can occur
in the system, as understood by the domain layer.
"""

from enum import auto, StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict


class MessageSemantics(StrEnum):
    """Defines high-level semantics for certain activity patterns that may be relevant for behavior dispatching."""

    CREATE_REPORT = auto()
    SUBMIT_REPORT = auto()
    VALIDATE_REPORT = auto()
    INVALIDATE_REPORT = auto()
    ACK_REPORT = auto()
    CLOSE_REPORT = auto()

    CREATE_CASE = auto()
    UPDATE_CASE = auto()
    ENGAGE_CASE = auto()
    DEFER_CASE = auto()
    ADD_REPORT_TO_CASE = auto()

    SUGGEST_ACTOR_TO_CASE = auto()
    ACCEPT_SUGGEST_ACTOR_TO_CASE = auto()
    REJECT_SUGGEST_ACTOR_TO_CASE = auto()
    OFFER_CASE_OWNERSHIP_TRANSFER = auto()
    ACCEPT_CASE_OWNERSHIP_TRANSFER = auto()
    REJECT_CASE_OWNERSHIP_TRANSFER = auto()

    INVITE_ACTOR_TO_CASE = auto()
    ACCEPT_INVITE_ACTOR_TO_CASE = auto()
    REJECT_INVITE_ACTOR_TO_CASE = auto()

    CREATE_EMBARGO_EVENT = auto()
    ADD_EMBARGO_EVENT_TO_CASE = auto()
    REMOVE_EMBARGO_EVENT_FROM_CASE = auto()
    ANNOUNCE_EMBARGO_EVENT_TO_CASE = auto()
    INVITE_TO_EMBARGO_ON_CASE = auto()
    ACCEPT_INVITE_TO_EMBARGO_ON_CASE = auto()
    REJECT_INVITE_TO_EMBARGO_ON_CASE = auto()

    CLOSE_CASE = auto()

    CREATE_CASE_PARTICIPANT = auto()
    ADD_CASE_PARTICIPANT_TO_CASE = auto()
    REMOVE_CASE_PARTICIPANT_FROM_CASE = auto()

    CREATE_NOTE = auto()
    ADD_NOTE_TO_CASE = auto()
    REMOVE_NOTE_FROM_CASE = auto()

    CREATE_CASE_STATUS = auto()
    ADD_CASE_STATUS_TO_CASE = auto()

    CREATE_PARTICIPANT_STATUS = auto()
    ADD_PARTICIPANT_STATUS_TO_PARTICIPANT = auto()

    # reserved for activities that don't fit any of the above semantics, but we want to be able to dispatch on them anyway
    UNKNOWN = auto()


class InboundPayload(BaseModel):
    """Domain-level wrapper around an inbound wire-format activity.

    Produced by the extractor before dispatch. The `raw_activity` field carries
    the original wire-format object; core logic MUST NOT inspect its AS2 types.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    activity_id: str
    actor_id: str
    object_type: str | None = None
    object_id: str | None = None
    raw_activity: Any  # the original as_Activity; opaque to core logic
