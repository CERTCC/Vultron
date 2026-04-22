"""AS2 wire layer parser for the Vultron Protocol.

Converts raw request bodies (dicts) into typed as_Activity objects.
This is stage 2 of the inbound pipeline: raw dict → typed AS2 activity.
Raises domain errors; driving adapters are responsible for mapping these
to transport-level error responses (e.g., HTTP status codes).
"""

import logging
from typing import Any, cast

from pydantic import BaseModel

from vultron.wire.as2.vocab.base.objects.activities.base import as_Activity
from vultron.wire.as2.vocab.base.registry import find_in_vocabulary
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    VulnerabilityCaseStub,
)
from vultron.wire.as2.errors import (
    VultronParseMissingTypeError,
    VultronParseUnknownTypeError,
    VultronParseValidationError,
)

logger = logging.getLogger(__name__)


_VULNERABILITY_CASE_STUB_KEYS = frozenset(
    {"@context", "id", "type", "summary"}
)


def _inline_vocab_class(value: dict[str, Any]) -> type[BaseModel] | None:
    """Return the most specific vocabulary class for an inline dict, if known."""
    obj_type = value.get("type")
    if not isinstance(obj_type, str):
        return None

    if (
        obj_type == "VulnerabilityCase"
        and value.keys() <= _VULNERABILITY_CASE_STUB_KEYS
    ):
        return VulnerabilityCaseStub

    try:
        return find_in_vocabulary(obj_type)
    except KeyError:
        return None


def _expand_inline_value(value: object) -> object:
    """Recursively pre-expand inline AS2 dicts to typed vocabulary instances.

    Generic field annotations such as ``as_Object`` or ``as_ObjectRef`` can
    silently erase subtype information when Pydantic validates nested inline
    dicts. Recursively coercing any typed dict to its vocabulary class preserves
    the actor/activity/case subtype information needed for semantic matching of
    nested invite/accept/reject flows.
    """
    if isinstance(value, list):
        return [_expand_inline_value(item) for item in value]
    if not isinstance(value, dict):
        return value

    expanded = {key: _expand_inline_value(item) for key, item in value.items()}
    inline_cls = _inline_vocab_class(expanded)
    if inline_cls is None:
        return expanded

    try:
        return inline_cls.model_validate(expanded)
    except Exception:
        return expanded


def _expand_inline_object(body: dict[str, Any]) -> dict[str, Any]:
    """Recursively expand nested inline dicts while leaving the outer body raw."""
    return {key: _expand_inline_value(value) for key, value in body.items()}


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
