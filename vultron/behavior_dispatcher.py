"""
Backward-compatibility shim for vultron.behavior_dispatcher.

All symbols have moved to their canonical locations in the core layer:

- ``ActivityDispatcher`` → ``vultron.core.ports.dispatcher``
- ``DispatcherBase``, ``DirectActivityDispatcher``, ``get_dispatcher``
  → ``vultron.core.dispatcher``
- ``DispatchEvent`` → ``vultron.types``
"""

from vultron.core.dispatcher import (
    DirectActivityDispatcher,
    DispatcherBase,
    get_dispatcher,
)
from vultron.core.ports.dispatcher import ActivityDispatcher
from vultron.types import DispatchEvent

__all__ = [
    "ActivityDispatcher",
    "DirectActivityDispatcher",
    "DispatchEvent",
    "DispatcherBase",
    "get_dispatcher",
]
