from vultron.errors import VultronError


class VultronApiError(VultronError):
    """Base class for all Vultron API v2 errors."""


class VultronApiValidationError(VultronApiError, ValueError):
    """Raised when there is a validation error in the API request."""


class VultronApiHandlerNotFoundError(VultronApiError, KeyError):
    """Raised when no handler is found for a given activity type."""


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
