"""AS2 wire layer parser for the Vultron Protocol.

Converts raw request bodies (dicts) into typed as_Activity objects.
This is stage 2 of the inbound pipeline: raw dict → typed AS2 activity.
Raises domain errors; driving adapters are responsible for mapping these
to transport-level error responses (e.g., HTTP status codes).
"""

import logging

from vultron.wire.as2.vocab import VOCABULARY
from vultron.wire.as2.vocab.type_helpers import AsActivityType
from vultron.wire.as2.errors import (
    VultronParseMissingTypeError,
    VultronParseUnknownTypeError,
    VultronParseValidationError,
)

logger = logging.getLogger(__name__)


def parse_activity(body: dict) -> AsActivityType:
    """Parse a raw dict into a typed as_Activity object.

    This is stage 2 of the inbound pipeline. It validates the `type` field,
    looks up the corresponding class in the AS2 vocabulary, and runs Pydantic
    validation.

    Args:
        body: The raw request body as a dictionary.

    Returns:
        A typed as_Activity subclass instance.

    Raises:
        VultronParseMissingTypeError: If the `type` field is absent.
        VultronParseUnknownTypeError: If the `type` value is not in the vocabulary.
        VultronParseValidationError: If Pydantic validation fails.
    """
    logger.info("Parsing activity from body (type=%r)", body.get("type"))

    as_type = body.get("type")
    if as_type is None:
        raise VultronParseMissingTypeError(
            "Missing 'type' field in activity body."
        )

    cls = VOCABULARY.activities.get(as_type)
    if cls is None:
        raise VultronParseUnknownTypeError(
            f"Unrecognized activity type: {as_type!r}."
        )

    try:
        return cls.model_validate(body)
    except Exception as exc:
        raise VultronParseValidationError(str(exc)) from exc
