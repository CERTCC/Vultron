from vultron.errors import VultronError

# Re-export from dispatcher_errors to maintain backward compatibility
# This error is used by the core behavior_dispatcher and needs to be
# available without triggering api.v2 module initialization
from vultron.dispatcher_errors import (  # noqa: F401
    VultronApiHandlerNotFoundError,
)


class VultronApiError(VultronError):
    """Base class for all Vultron API v2 errors."""


class VultronApiValidationError(VultronApiError, ValueError):
    """Raised when there is a validation error in the API request."""


class VultronApiDispatchError(VultronApiError, RuntimeError):
    """Raised when there is an error dispatching an activity to its handler."""


class VultronApiHandlerMissingSemanticError(VultronApiError, ValueError):
    """Raised when a dispatchable activity is missing a semantic_type."""

    def __init__(self):
        super().__init__("Dispatchable activity is missing semantic_type")


class VultronApiHandlerSemanticMismatchError(VultronApiError, ValueError):
    """Raised when the semantics of an activity do not match the expected semantics for its handler."""

    def __init__(self, expected: str, actual: str):
        self.expected = expected
        self.actual = actual
        super().__init__(
            f"Semantic mismatch: expected '{expected}', got '{actual}'"
        )
