"""
Maps Message Semantics to their appropriate handlers.

Backward-compatibility shim. Use vultron.api.v2.backend.handler_map directly.
"""

from vultron.api.v2.backend.handler_map import SEMANTICS_HANDLERS


def get_semantics_handlers() -> dict:
    return SEMANTICS_HANDLERS
