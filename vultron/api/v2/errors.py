from vultron.errors import VultronError


class VultronApiError(VultronError):
    """Base class for all Vultron API v2 errors."""


class VultronApiValidationError(VultronApiError, ValueError):
    """Raised when there is a validation error in the API request."""


class VultronApiHandlerNotFoundError(VultronApiError, KeyError):
    """Raised when no handler is found for a given activity type."""


class VultronApiDispatchError(VultronApiError, RuntimeError):
    """Raised when there is an error dispatching an activity to its handler."""
