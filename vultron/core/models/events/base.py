"""Base domain event types for the Vultron Protocol.

Defines the core vocabulary of semantic intents (MessageSemantics) and the
VultronEvent base class that all per-semantic inbound domain event types
inherit from.
"""

from enum import auto, StrEnum
from typing import Annotated

from pydantic import AfterValidator, BaseModel


def _non_empty(v: str) -> str:
    if not v.strip():
        raise ValueError("must be a non-empty string")
    return v


NonEmptyString = Annotated[str, AfterValidator(_non_empty)]


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


class VultronEvent(BaseModel):
    """Base domain event produced from an inbound wire-format activity.

    Produced by extract_intent() in the wire layer before dispatch.
    All fields are plain domain types (strings); no AS2 wire types are present.

    Concrete per-semantic subclasses set semantic_type as a Literal to enable
    type-safe handler dispatch and Pydantic discriminated-union reconstruction.
    """

    semantic_type: MessageSemantics
    activity_id: NonEmptyString
    activity_type: NonEmptyString | None = None
    actor_id: NonEmptyString

    object_id: NonEmptyString | None = None
    object_type: NonEmptyString | None = None

    target_id: NonEmptyString | None = None
    target_type: NonEmptyString | None = None

    context_id: NonEmptyString | None = None
    context_type: NonEmptyString | None = None

    origin_id: NonEmptyString | None = None
    origin_type: NonEmptyString | None = None

    in_reply_to: NonEmptyString | None = None

    # Nested fields: activity.as_object.as_object, .target, .context
    inner_object_id: NonEmptyString | None = None
    inner_object_type: NonEmptyString | None = None
    inner_target_id: NonEmptyString | None = None
    inner_target_type: NonEmptyString | None = None
    inner_context_id: NonEmptyString | None = None
    inner_context_type: NonEmptyString | None = None

    @property
    def as_id(self) -> str:
        return self.activity_id
