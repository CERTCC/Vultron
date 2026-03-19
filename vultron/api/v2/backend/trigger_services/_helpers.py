#!/usr/bin/env python

#  Copyright (c) 2026 Carnegie Mellon University and Contributors.
#  - see Contributors.md for a full list of Contributors
#  - see ContributionInstructions.md for information on how you can Contribute to this project
#  Vultron Multiparty Coordinated Vulnerability Disclosure Protocol Prototype is
#  licensed under a MIT (SEI)-style license, please see LICENSE.md distributed
#  with this Software or contact permission@sei.cmu.edu for full terms.
#  Created, in part, with funding and support from the United States Government
#  (see Acknowledgments file). This program may include and/or can make use of
#  certain third party source code, object code, documentation and other files
#  ("Third Party Software"). See LICENSE.md for more details.
#  Carnegie Mellon®, CERT® and CERT Coordination Center® are registered in the
#  U.S. Patent and Trademark Office by Carnegie Mellon University

"""
HTTP error translation utilities for trigger service adapter layer.

Translates domain exceptions from ``vultron.core.use_cases.triggers`` into
FastAPI ``HTTPException`` responses.
"""

from contextlib import contextmanager
from typing import Generator

from fastapi import HTTPException, status
from pydantic import ValidationError as PydanticValidationError

from vultron.errors import (
    VultronConflictError,
    VultronError,
    VultronNotFoundError,
    VultronValidationError,
)


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


# Re-export helpers that routers and tests may still import from this module.
# These are now thin pass-throughs to core equivalents.
from vultron.core.use_cases.triggers._helpers import (  # noqa: E402, F401
    add_activity_to_outbox,
    find_embargo_proposal,
    outbox_ids,
    resolve_actor,
    resolve_case,
    update_participant_rm_state,
)
