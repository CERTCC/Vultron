"""Base domain event types for the Vultron Protocol.

Defines the core vocabulary of semantic intents (MessageSemantics) and the
VultronEvent base class that all per-semantic inbound domain event types
inherit from.
"""

from enum import StrEnum, auto

from pydantic import BaseModel

from vultron.core.models.activity import VultronActivity
from vultron.core.models.base import NonEmptyString, VultronObject


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

    ANNOUNCE_CASE_LOG_ENTRY = auto()
    REJECT_CASE_LOG_ENTRY = auto()

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
    # object_ URI could not be resolved after rehydration; activity is dead-lettered
    UNKNOWN_UNRESOLVABLE_OBJECT = auto()


class VultronEvent(BaseModel):
    """Base domain event produced from an inbound wire-format activity.

    ``VultronEvent`` is the semantic event type used for dispatching within
    core. It is distinct from ``VultronActivity``, which is the domain model
    for the AS2 activity object itself (used for DataLayer storage).

    A ``VultronEvent`` carries full domain objects extracted from the wire-format
    activity, mirroring the richness of an AS2 Activity without importing any
    wire-layer types.  ``object_`` uses a trailing underscore because ``object``
    is a Python built-in; all other field names are natural English identifiers.

    Produced by ``extract_intent()`` in the wire layer before dispatch.
    All fields are plain domain types (strings or ``VultronObject`` subclasses);
    no AS2 wire types are present.

    Concrete per-semantic subclasses set ``semantic_type`` as a ``Literal``
    to enable type-safe handler dispatch and Pydantic discriminated-union
    reconstruction. Subclasses that always carry an activity MUST narrow the
    optional ``activity`` field to required by redeclaring it without a default.

    ID/type string properties are derived from the rich object fields to maintain
    backward compatibility with code that accesses ``event.object_id``, etc.
    """

    semantic_type: MessageSemantics
    activity_id: NonEmptyString
    activity_type: NonEmptyString | None = None
    actor_id: NonEmptyString

    # Rich domain objects — parallel to AS2 Activity fields.
    # ``object_`` uses a trailing underscore because ``object`` is a Python built-in.
    object_: VultronObject | None = None
    target: VultronObject | None = None
    context: VultronObject | None = None
    origin: VultronObject | None = None

    # Nested fields: activity.object.object, .target, .context
    inner_object: VultronObject | None = None
    inner_target: VultronObject | None = None
    inner_context: VultronObject | None = None

    in_reply_to: NonEmptyString | None = None

    # Optional at the base level; subclasses that always carry an activity
    # MUST narrow this to required by redeclaring without a default.
    activity: VultronActivity | None = None

    # Dispatch-context annotation: the canonical ID of the actor whose inbox
    # is being processed.  Set by the inbox adapter (not extracted from wire
    # format) so that use cases can compare it against activity.to/cc without
    # inspecting AS2 types.  None when dispatched outside the inbox path (CLI,
    # triggers, tests that don't set it).
    receiving_actor_id: str | None = None

    @property
    def id_(self) -> str:
        return self.activity_id

    # Derived ID/type properties — backward compatibility for use-case code.

    @property
    def object_id(self) -> str | None:
        return self.object_.id_ if self.object_ is not None else None

    @property
    def object_type(self) -> str | None:
        return self.object_.type_ if self.object_ is not None else None

    @property
    def target_id(self) -> str | None:
        return self.target.id_ if self.target is not None else None

    @property
    def target_type(self) -> str | None:
        return self.target.type_ if self.target is not None else None

    @property
    def context_id(self) -> str | None:
        return self.context.id_ if self.context is not None else None

    @property
    def context_type(self) -> str | None:
        return self.context.type_ if self.context is not None else None

    @property
    def origin_id(self) -> str | None:
        return self.origin.id_ if self.origin is not None else None

    @property
    def origin_type(self) -> str | None:
        return self.origin.type_ if self.origin is not None else None

    @property
    def inner_object_id(self) -> str | None:
        return self.inner_object.id_ if self.inner_object is not None else None

    @property
    def inner_object_type(self) -> str | None:
        return (
            self.inner_object.type_ if self.inner_object is not None else None
        )

    @property
    def inner_target_id(self) -> str | None:
        return self.inner_target.id_ if self.inner_target is not None else None

    @property
    def inner_target_type(self) -> str | None:
        return (
            self.inner_target.type_ if self.inner_target is not None else None
        )

    @property
    def inner_context_id(self) -> str | None:
        return (
            self.inner_context.id_ if self.inner_context is not None else None
        )

    @property
    def inner_context_type(self) -> str | None:
        return (
            self.inner_context.type_
            if self.inner_context is not None
            else None
        )
