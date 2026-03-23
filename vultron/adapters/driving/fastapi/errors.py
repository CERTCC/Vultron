from contextlib import contextmanager
from typing import Generator

from fastapi import HTTPException, status
from pydantic import ValidationError as PydanticValidationError

from vultron.errors import (
    VultronApiHandlerNotFoundError,
    VultronConflictError,
    VultronError,
    VultronNotFoundError,
    VultronValidationError,
)  # noqa: F401


@contextmanager
def domain_error_translation() -> Generator[None, None, None]:
    """Context manager that translates domain exceptions to HTTPExceptions."""
    try:
        yield
    except (VultronError, PydanticValidationError) as e:
        raise translate_domain_errors(e)


def translate_domain_errors(exc: Exception) -> HTTPException:
    """Convert a domain exception to an appropriate HTTPException."""
    if isinstance(exc, VultronNotFoundError):
        return HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "status": 404,
                "error": "NotFound",
                "message": str(exc),
                "activity_id": None,
            },
        )
    if isinstance(exc, VultronConflictError):
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "status": 409,
                "error": "Conflict",
                "message": str(exc),
                "activity_id": getattr(exc, "activity_id", None),
            },
        )
    if isinstance(exc, (VultronValidationError, PydanticValidationError)):
        return HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={
                "status": 422,
                "error": "ValidationError",
                "message": str(exc),
                "activity_id": getattr(exc, "activity_id", None),
            },
        )
    raise exc


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
