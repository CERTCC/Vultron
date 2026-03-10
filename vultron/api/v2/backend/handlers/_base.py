"""
Shared utilities for handler functions.
"""

import logging
from functools import wraps
from typing import TYPE_CHECKING

from vultron.api.v2.errors import (
    VultronApiHandlerMissingSemanticError,
    VultronApiHandlerSemanticMismatchError,
)
from vultron.core.models.events import MessageSemantics
from vultron.types import DispatchActivity

if TYPE_CHECKING:
    from vultron.api.v2.datalayer.abc import DataLayer

logger = logging.getLogger(__name__)


def verify_semantics(expected_semantic_type: MessageSemantics):
    def decorator(func):
        @wraps(func)
        def wrapper(dispatchable: DispatchActivity, dl: "DataLayer"):
            if not dispatchable.semantic_type:
                logger.error(
                    "Dispatchable activity %s is missing semantic_type",
                    dispatchable,
                )
                raise VultronApiHandlerMissingSemanticError()

            if dispatchable.semantic_type != expected_semantic_type:
                logger.error(
                    "Dispatchable activity %s has semantic_type %s but handler expects %s",
                    dispatchable,
                    dispatchable.semantic_type,
                    expected_semantic_type,
                )
                raise VultronApiHandlerSemanticMismatchError(
                    expected=expected_semantic_type,
                    actual=dispatchable.semantic_type,
                )

            return func(dispatchable, dl)

        return wrapper

    return decorator
