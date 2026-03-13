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

    .. deprecated::
        ``DispatchEvent`` is retained for backward compatibility.  The
        dispatcher now accepts ``VultronEvent`` directly (P75-2c).  New code
        should use ``VultronEvent`` and pass ``DataLayer`` as a separate
        argument to ``dispatch()``.
    """

    semantic_type: MessageSemantics
    activity_id: str
    payload: VultronEvent


# Backward-compat alias — retained for test compatibility.
DispatchActivity = DispatchEvent


class BehaviorHandler(Protocol):
    """Protocol for use-case callable functions.

    Use-case functions accept a ``VultronEvent`` subclass and a ``DataLayer``
    instance.  The ``dispatchable`` parameter name is retained for backward
    compatibility with any code that passes it as a keyword argument.
    """

    def __call__(self, event: VultronEvent, dl: "DataLayer") -> None: ...
