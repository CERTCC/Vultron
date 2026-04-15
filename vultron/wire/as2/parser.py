"""AS2 wire layer parser for the Vultron Protocol.

Converts raw request bodies (dicts) into typed as_Activity objects.
This is stage 2 of the inbound pipeline: raw dict → typed AS2 activity.
Raises domain errors; driving adapters are responsible for mapping these
to transport-level error responses (e.g., HTTP status codes).
"""

import logging
from typing import Any, cast

from vultron.wire.as2.vocab.base.objects.activities.base import as_Activity
from vultron.wire.as2.vocab.base.registry import find_in_vocabulary
from vultron.wire.as2.errors import (
    VultronParseMissingTypeError,
    VultronParseUnknownTypeError,
    VultronParseValidationError,
)

logger = logging.getLogger(__name__)


def _expand_inline_object(body: dict[str, Any]) -> dict[str, Any]:
    """Pre-expand an inline object dict to a typed vocabulary instance.

    When an activity body contains an inline object as a plain dict (e.g., a
    ``CaseLogEntry`` dict embedded in an ``Announce`` body), Pydantic would
    normally parse it using the *base* field type of ``object_`` (``as_Object``
    with ``extra="ignore"``), silently dropping any subtype-specific fields.

    This helper detects inline objects with a known ``type`` key, looks up the
    concrete vocabulary class, and validates the dict into that class *before*
    the outer activity is validated — preserving all fields.

    If the object is already a string (URI reference), a non-dict, or has an
    unknown type, the body is returned unchanged.

    Spec: SYNC-02-004 (CaseLogEntry must be fully inlined).
    """
    obj = body.get("object")
    if not isinstance(obj, dict):
        return body
    obj_type = obj.get("type")
    if obj_type is None:
        return body
    try:
        obj_cls = find_in_vocabulary(obj_type)
    except KeyError:
        return body
    try:
        expanded = body.copy()
        expanded["object"] = obj_cls.model_validate(obj)
        return expanded
    except Exception:
        return body


def parse_activity(body: dict[str, Any]) -> as_Activity:
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

    type_ = body.get("type")
    if type_ is None:
        raise VultronParseMissingTypeError(
            "Missing 'type' field in activity body."
        )

    try:
        cls = find_in_vocabulary(type_)
    except KeyError:
        raise VultronParseUnknownTypeError(
            f"Unrecognized activity type: {type_!r}."
        )

    if not issubclass(cls, as_Activity):
        raise VultronParseUnknownTypeError(
            f"Type {type_!r} is not an activity type."
        )

    try:
        return cast(
            as_Activity, cls.model_validate(_expand_inline_object(body))
        )
    except Exception as exc:
        raise VultronParseValidationError(str(exc)) from exc
