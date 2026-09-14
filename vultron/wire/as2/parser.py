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
from vultron.wire.as2.vocab.base.base import as_Base
from vultron.wire.as2.errors import (
    VultronParseError,
    VultronParseMissingPublishedError,
    VultronParseMissingTypeError,
    VultronParseUnknownTypeError,
    VultronParseValidationError,
)

logger = logging.getLogger(__name__)


_VULNERABILITY_CASE_STUB_KEYS = frozenset(
    {"@context", "id", "type", "summary"}
)

# Field names whose values are opaque data blobs (declared ``dict[str, Any]``),
# NOT AS2 object references.  These must not be recursively coerced into typed
# vocabulary instances: a ``CaseLedgerEntry.payload_snapshot`` may itself carry
# an ``{"type": "Announce", "object": {...}}`` snapshot dict, and coercing it to
# an ``as_Announce`` model would make ``CaseLedgerEntry`` validation fail
# (payload_snapshot expects a dict), causing the parser to fall back to the base
# ``as_Object`` type and mis-route the entry (SYNC-13-004).
_OPAQUE_PAYLOAD_KEYS = frozenset({"payloadSnapshot", "payload_snapshot"})


def _is_blank(value: object) -> bool:
    """Return True when *value* carries no content: absent, null, or blank.

    A required field that is present but empty carries nothing, so it is
    absence rather than a malformed value — CS-08-001's "if present, then
    non-empty".  Whitespace-only counts as blank, matching the project's
    canonical predicate (``core.models.base._non_empty``).

    Deliberately narrower than a bare falsy test: ``0``, ``[]`` and ``{}`` are
    *malformed* values for the fields this guards, not omitted ones, and
    reporting them as missing would tell the sender to supply a field they
    already sent (ISSUE-3217).
    """
    return value is None or (isinstance(value, str) and not value.strip())


def _inline_vocab_class(value: dict[str, Any]) -> type[BaseModel] | None:
    """Return the most specific *wire* vocabulary class for an inline dict.

    Returns ``None`` when the type is unregistered or resolves outside the wire
    branch, which leaves the dict unexpanded for the parent field to validate.

    The wire-branch restriction is load-bearing. ``find_in_vocabulary`` falls
    back to ``CORE_TYPE_MAP`` (ARCH-12-003), and a core instance placed inside a
    wire tree is rejected by the wire parent's field type: ``OrderedCollection``
    is registered only in the core map, so an inline actor's ``inbox`` expanded
    to a ``CoreActorCollection`` that ``as_VultronOrganization.inbox`` refused,
    degrading the whole actor to a bare ``as_Link``.  Nested expansion inside a
    wire tree is wire-to-wire (ARCH-22-001), so the mismatch cannot arise
    (ISSUE-3217).
    """
    obj_type = value.get("type")
    if not isinstance(obj_type, str):
        return None

    if (
        obj_type == "VulnerabilityCase"
        and value.keys() <= _VULNERABILITY_CASE_STUB_KEYS
    ):
        return VulnerabilityCaseStub

    try:
        cls = find_in_vocabulary(obj_type)
    except KeyError:
        return None

    return cls if issubclass(cls, as_Base) else None


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

    expanded = {
        key: (
            item if key in _OPAQUE_PAYLOAD_KEYS else _expand_inline_value(item)
        )
        for key, item in value.items()
    }
    inline_cls = _inline_vocab_class(expanded)
    if inline_cls is None:
        return expanded

    # Once the type has resolved to a wire class, failing that class's own
    # validation is a message fault and is refused (ADR-0032: validate at the
    # edge).  Substituting the raw dict was silent data loss: the parent
    # accepted it as a bare ``as_Link``, so the activity parsed *clean* and
    # extracted as ``UNKNOWN`` — an ``Accept(Invite(...))`` with one corrupt
    # inner field lost its case id and drew a 202 for a message the receiver
    # never understood (ISSUE-3217).
    try:
        return inline_cls.model_validate(expanded)
    except Exception as exc:
        raise VultronParseValidationError(
            f"Inline {inline_cls.__name__} object is malformed: {exc}"
        ) from exc


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

    A field that is present but blank is treated as absent (CS-08-001), so each
    "missing field" error below covers the absent, null and blank spellings
    alike.

    Raises:
        VultronParseMissingTypeError: If the `type` field is absent or blank.
        VultronParseMissingPublishedError: If the `published` field is absent
            or blank.
        VultronParseUnknownTypeError: If the `type` value is not in the vocabulary.
        VultronParseValidationError: If Pydantic validation fails, including
            when a recognised inline object fails its own class's validation.
    """
    logger.debug("Parsing activity from body (type=%r)", body.get("type"))

    # Blank is absence, not an unknown type: the inbox adapter maps
    # ``VultronParseMissingTypeError`` to HTTP 400 and every other parse error
    # to 422, so letting ``"type": ""`` fall through to the vocabulary lookup
    # answered two spellings of the same omission with two status codes
    # (ISSUE-3217).
    type_ = body.get("type")
    if _is_blank(type_):
        raise VultronParseMissingTypeError(
            "Missing 'type' field in activity body."
        )

    # ``_is_blank`` rules out ``None``, but a boolean-returning helper cannot
    # narrow the type for the checkers the way an inline ``is None`` did.  A
    # non-string ``type`` is deliberately *not* rejected here: the sender did
    # name a type, it is just not one we can look up, so it belongs in the
    # ``UnknownType`` 422 below rather than the ``MissingType`` 400 above.
    type_ = cast(str, type_)

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

    # Ordered after type resolution — "is this a type we recognise" is a
    # routing question and answering it first keeps the existing error
    # precedence — but before ``model_validate``, because ``as_Base`` declares
    # ``published`` with ``default_factory=now_utc``.  Once validation runs, an
    # absent timestamp is indistinguishable from a sender-supplied one, and the
    # value is the *receiver's* clock.  Downstream that fabricated value is read
    # as the sender's claim, which is what made CLP-14-007 and CLP-14-008
    # compare the receiver's clock against itself (ISSUE-3149).  Absence is a
    # message-validity failure, not something to correct downstream
    # (ADR-0032: validate at the edge).
    #
    # Scoped to the top-level activity: nested objects legitimately omit
    # ``published`` and may be bare ID strings.
    #
    # A present-but-blank value carries no claimed time either, so it is refused
    # the same way.  Asking only whether the *key* was absent let ``""`` reach
    # ``model_validate``, which reported it as a schema fault and replaced this
    # explanation with a Pydantic isoformat dump (ISSUE-3217).
    if _is_blank(body.get("published")):
        raise VultronParseMissingPublishedError(
            f"Missing 'published' field on {type_!r} activity. An activity "
            "must carry the time its sender claims the event occurred; "
            "without it the receiver cannot tell a claimed time from its own "
            "clock (CLP-15-004)."
        )

    try:
        return cast(
            as_Activity, cls.model_validate(_expand_inline_object(body))
        )
    except VultronParseError:
        # A malformed inline object already carries its own diagnosis, naming
        # the nested type that failed; re-wrapping would bury it.
        raise
    except Exception as exc:
        raise VultronParseValidationError(str(exc)) from exc
