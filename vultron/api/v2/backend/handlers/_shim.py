"""
Backward-compat stub for verify_semantics.

The ``@verify_semantics`` decorator has been removed from the handler layer
(P75-2c).  Semantic type validation is now enforced by the dispatcher routing
table — the dispatcher looks up use-case callables by ``event.semantic_type``,
so a mismatch cannot occur.

This no-op shim is retained so that any code or test that still imports
``verify_semantics`` continues to work.  Remove it when no callers remain.
"""

import logging
from functools import wraps

logger = logging.getLogger(__name__)


def verify_semantics(expected_semantic_type):
    """No-op backward-compat decorator (P75-2c: handler shims removed)."""

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)

        return wrapper

    return decorator
