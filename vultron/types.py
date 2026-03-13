from __future__ import annotations

from typing import Protocol, TYPE_CHECKING

from pydantic import BaseModel

from vultron.core.models.events import MessageSemantics, VultronEvent

if TYPE_CHECKING:
    from vultron.core.ports.datalayer import DataLayer


class DispatchEvent(BaseModel):
    """Data model representing a domain event ready for dispatch.

    Wraps a ``VultronEvent`` payload with routing metadata (semantic type and
    activity ID).  This is a pure domain object — it carries no wire-layer
    (AS2) fields.
    """

    semantic_type: MessageSemantics
    activity_id: str
    payload: VultronEvent


# Backward-compat alias — will be removed once P75-2c flattens the handler layer.
DispatchActivity = DispatchEvent


class BehaviorHandler(Protocol):
    """Protocol for behavior handler functions."""

    def __call__(
        self, dispatchable: DispatchEvent, dl: "DataLayer"
    ) -> None: ...
