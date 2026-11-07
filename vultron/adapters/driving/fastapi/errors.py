from collections.abc import Generator
from contextlib import contextmanager

from fastapi import HTTPException, status
from pydantic import ValidationError as PydanticValidationError

from vultron.errors import (
    VultronError,
    VultronInvalidStateTransitionError,
    VultronNotFoundError,
    VultronProofVerificationError,
    VultronValidationError,
)


@contextmanager
def domain_error_translation() -> Generator[None, None, None]:
    """Context manager that translates domain exceptions to HTTPExceptions."""
    try:
        yield
    except (VultronError, PydanticValidationError) as e:
        raise translate_domain_errors(e)  # noqa: B904  # ruff-baseline #3353


def _error_http_exception(
    status_code: int,
    error: str,
    message: str,
    *,
    activity_id: str | None = None,
    details: list[dict[str, object]] | None = None,
) -> HTTPException:
    """An HTTPException carrying the structured EH-05-001 error body.

    ``status`` mirrors *status_code*, and ``details`` (EH-05-002) is added only
    when given.
    """
    detail: dict[str, object] = {
        "status": status_code,
        "error": error,
        "message": message,
        "activity_id": activity_id,
    }
    if details:
        detail["details"] = details
    return HTTPException(status_code=status_code, detail=detail)


def conflict_http_exception(
    message: str, *, activity_id: str | None = None
) -> HTTPException:
    """A 409 carrying the structured EH-05-001 body every conflict uses."""
    return _error_http_exception(
        status.HTTP_409_CONFLICT,
        "Conflict",
        message,
        activity_id=activity_id,
    )


def unsignable_http_exception(message: str) -> HTTPException:
    """A 422 for a body the outbox's signer refuses (EH-05-001).

    For the outbox POST only: the client must change the content, and the
    server is not at fault.  Ingress answers an uncanonicalizable body as
    #5386 decides, so :func:`translate_domain_errors` does not map it.
    """
    return _error_http_exception(
        status.HTTP_422_UNPROCESSABLE_CONTENT, "ValidationError", message
    )


def translate_domain_errors(exc: Exception) -> HTTPException:
    """Convert a domain exception to an appropriate HTTPException."""
    if isinstance(exc, VultronNotFoundError):
        return _error_http_exception(
            status.HTTP_404_NOT_FOUND, "NotFound", str(exc)
        )
    if isinstance(exc, VultronInvalidStateTransitionError):
        return conflict_http_exception(
            str(exc), activity_id=getattr(exc, "activity_id", None)
        )
    if isinstance(exc, VultronProofVerificationError):
        # EH-03-005: a missing or failing proof is answered 422, like content
        # that fails validation, under its own error name so a sender can tell
        # it from a field error.  No ``activity_id``: an unverified document's
        # id is the forger's claim.
        return _error_http_exception(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "ProofVerificationError",
            str(exc),
        )
    if isinstance(exc, (VultronValidationError, PydanticValidationError)):
        # EH-05-002: when the boundary recognised more than one violation,
        # surface them as structured entries so callers are not forced to parse
        # `message` — a fragility ISSUE-2112 named, since a change to internal
        # check order silently alters which error a text parser picks up.
        # `message` still renders the whole set, so text-only consumers are no
        # worse off.
        violations = getattr(exc, "violations", ())
        return _error_http_exception(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "ValidationError",
            str(exc),
            activity_id=getattr(exc, "activity_id", None),
            details=[
                {
                    "message": violation.message,
                    "classification": violation.classification,
                    "dimensions": list(violation.dimensions),
                }
                for violation in violations
            ],
        )
    raise exc


class VultronApiError(VultronError):
    """Base class for all Vultron API v2 errors."""


class VultronApiValidationError(VultronApiError, ValueError):
    """Raised when there is a validation error in the API request."""


class VultronApiDispatchError(VultronApiError, RuntimeError):
    """Raised when there is an error dispatching an activity to its handler."""


class VultronApiHandlerSemanticMismatchError(VultronApiError, ValueError):
    """Raised when the semantics of an activity do not match the expected semantics for its handler."""

    def __init__(self, expected: str, actual: str):
        self.expected = expected
        self.actual = actual
        super().__init__(
            f"Semantic mismatch: expected '{expected}', got '{actual}'"
        )
