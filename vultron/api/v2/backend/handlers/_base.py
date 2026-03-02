"""
Shared utilities for handler functions.
"""

import logging
from functools import wraps

from vultron.api.v2.errors import (
    VultronApiHandlerMissingSemanticError,
    VultronApiHandlerSemanticMismatchError,
)
from vultron.enums import MessageSemantics
from vultron.semantic_map import find_matching_semantics
from vultron.types import DispatchActivity

logger = logging.getLogger(__name__)


def verify_semantics(expected_semantic_type: MessageSemantics):
    def decorator(func):
        @wraps(func)
        def wrapper(dispatchable: DispatchActivity):
            if not dispatchable.semantic_type:
                logger.error(
                    "Dispatchable activity %s is missing semantic_type",
                    dispatchable,
                )
                raise VultronApiHandlerMissingSemanticError()

            computed = find_matching_semantics(dispatchable.payload)

            if computed != expected_semantic_type:
                logger.error(
                    "Dispatchable activity %s claims semantic_type %s that does not match its payload (%s)",
                    dispatchable,
                    expected_semantic_type,
                    computed,
                )
                raise VultronApiHandlerSemanticMismatchError(
                    expected=expected_semantic_type, actual=computed
                )

            return func(dispatchable)

        return wrapper

    return decorator
