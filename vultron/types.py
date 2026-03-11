from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol

from pydantic import BaseModel, ConfigDict

from vultron.core.models.events import MessageSemantics, VultronEvent

if TYPE_CHECKING:
    from vultron.api.v2.datalayer.abc import DataLayer


class DispatchActivity(BaseModel):
    """
    Data model to represent a dispatchable activity with its associated message semantics as a header.

    The `wire_activity` field carries the original AS2 wire object for adapter-layer
    persistence; core logic MUST NOT inspect its AS2 types.
    The `wire_object` field carries the inline AS2 object from activity.as_object (for
    CREATE-type activities where the object is embedded, not yet in the DataLayer).
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    semantic_type: MessageSemantics
    activity_id: str
    payload: VultronEvent
    wire_activity: Any = (
        None  # opaque AS2 activity for adapter-layer persistence
    )
    wire_object: Any = (
        None  # opaque inline AS2 object (set for CREATE-type activities)
    )


class BehaviorHandler(Protocol):
    """
    Protocol for behavior handler functions.
    """

    def __call__(
        self, dispatchable: DispatchActivity, dl: "DataLayer"
    ) -> None: ...
