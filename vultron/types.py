from __future__ import annotations

from typing import Protocol, TYPE_CHECKING

from vultron.core.models.events import VultronEvent

if TYPE_CHECKING:
    from vultron.core.ports.datalayer import DataLayer


class BehaviorHandler(Protocol):
    """Protocol for use-case callable functions.

    Use-case functions accept a ``VultronEvent`` subclass and a ``DataLayer``
    instance.  The ``dispatchable`` parameter name is retained for backward
    compatibility with any code that passes it as a keyword argument.
    """

    def __call__(self, event: VultronEvent, dl: "DataLayer") -> None: ...
