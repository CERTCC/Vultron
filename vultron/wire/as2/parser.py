"""AS2 wire layer parser for the Vultron Protocol.

Converts raw request bodies (dicts) into typed as_Activity objects.
This is stage 2 of the inbound pipeline: raw dict → typed AS2 activity.
Raises domain errors; driving adapters are responsible for mapping these
to transport-level error responses (e.g., HTTP status codes).
"""

import json
import logging
from typing import Any, cast

from vultron.wire.as2.errors import (
    VultronParseError,
    VultronParseMissingPublishedError,
    VultronParseMissingTypeError,
    VultronParseUnknownTypeError,
    VultronParseValidationError,
)
from vultron.wire.as2.unknown_keys import (
    OPAQUE_PAYLOAD_KEYS,
    SetAsideKey,
    partition_unknown_keys,
    resolve_inline_class,
)
from vultron.wire.as2.vocab.base.base import as_Base
from vultron.wire.as2.vocab.base.objects.activities.base import as_Activity
from vultron.wire.as2.vocab.base.registry import find_in_vocabulary
from vultron.wire.as2.vocab.base.utils import is_blank

logger = logging.getLogger(__name__)


#: Marks every ``model_validate`` call in this module as reading inbound data,
#: which is what tells ``as_Base`` to read an absent clock-defaulted timestamp as
#: ``None`` rather than stamping the receiver's clock (ISSUE-3257, CLP-15-007).
#: Parsing is the only place this belongs: a caller *authoring* an object wants
#: the default, and passing this context for one would silently drop its time.
_INBOUND_CONTEXT = {as_Base.INBOUND_CONTEXT_KEY: True}


def _expand_inline_value(value: object, path: str = "") -> object:
    """Recursively pre-expand inline AS2 dicts to typed vocabulary instances.

    Generic field annotations such as ``as_Object`` or ``as_ObjectRef`` can
    silently erase subtype information when Pydantic validates nested inline
    dicts. Recursively coercing any typed dict to its vocabulary class preserves
    the actor/activity/case subtype information needed for semantic matching of
    nested invite/accept/reject flows.

    Args:
        value: The inline value to expand.
        path: Dotted field path of *value* within the activity body, used only
            to locate a refusal for the sender. Recursion appends each field
            name and list index, so a nested fault reports e.g.
            ``object.target[0]`` rather than naming only its own type.
    """
    if isinstance(value, list):
        return [
            _expand_inline_value(item, f"{path}[{index}]")
            for index, item in enumerate(value)
        ]
    if not isinstance(value, dict):
        return value

    expanded = {
        key: (
            item
            if key in OPAQUE_PAYLOAD_KEYS
            else _expand_inline_value(item, f"{path}.{key}" if path else key)
        )
        for key, item in value.items()
    }
    inline_cls = resolve_inline_class(expanded)
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
        return inline_cls.model_validate(expanded, context=_INBOUND_CONTEXT)
    except Exception as exc:
        where = f" at {path!r}" if path else ""
        raise VultronParseValidationError(
            f"Inline {inline_cls.__name__} object{where} is malformed: {exc}"
        ) from exc


def _expand_inline_object(body: dict[str, Any]) -> dict[str, Any]:
    """Recursively expand nested inline dicts while leaving the outer body raw."""
    return {
        key: _expand_inline_value(value, key) for key, value in body.items()
    }


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
            when a recognised inline object fails its own class's validation,
            or if the body cannot be re-serialized as strict JSON to seal it
            as received evidence (VM-08-002).
    """
    logger.debug("Parsing activity from body (type=%r)", body.get("type"))

    # Blank is absence, not an unknown type: the inbox adapter maps
    # ``VultronParseMissingTypeError`` to HTTP 400 and every other parse error
    # to 422, so letting ``"type": ""`` fall through to the vocabulary lookup
    # answered two spellings of the same omission with two status codes
    # (ISSUE-3217).
    type_ = body.get("type")
    if is_blank(type_):
        raise VultronParseMissingTypeError(
            "Missing 'type' field in activity body."
        )

    # A non-string ``type`` is deliberately not a ``MissingType`` 400: the
    # sender did name a type, it is just not one we can look up, so it belongs
    # in the ``UnknownType`` 422.  It must be rejected *here* rather than left
    # to the lookup below, because ``find_in_vocabulary`` tests dict membership
    # and an unhashable value (``[]``, ``{}``) raises ``TypeError`` — not the
    # ``KeyError`` that except clause catches — which escaped ``parse_activity``
    # entirely and drew a 500 from the inbox adapter (ISSUE-3217).
    if not isinstance(type_, str):
        raise VultronParseUnknownTypeError(
            f"Unrecognized activity type: {type_!r}."
        )

    # Wire-only lookup (VM-06-008): a core-only name is an unknown type here,
    # not a core class to validate a sender's activity against.
    try:
        cls = find_in_vocabulary(type_)
    except KeyError:
        raise VultronParseUnknownTypeError(  # noqa: B904  # ruff-baseline #3353
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
    # ``published`` and may be bare ID strings.  Their absence is kept as
    # absence by ``as_Base.carry_absent_times_on_inbound`` instead, which the
    # ``_INBOUND_CONTEXT`` below switches on (ISSUE-3257).
    #
    # A present-but-blank value carries no claimed time either, so it is refused
    # the same way.  Asking only whether the *key* was absent let ``""`` reach
    # ``model_validate``, which reported it as a schema fault and replaced this
    # explanation with a Pydantic isoformat dump (ISSUE-3217).
    #
    # Deliberately narrower than ``not body.get("published")``, which is what
    # ``723ff08eb`` on main used and what this resolution supersedes.  A falsy
    # test also absorbs ``0``, ``[]``, ``{}`` and ``false``; those are malformed
    # values, not omitted ones, and reporting them as a missing field tells the
    # sender to resend a field they already sent (ADR-0090 rejects that as
    # option 1; MV-03-002).
    if is_blank(body.get("published")):
        raise VultronParseMissingPublishedError(
            f"Missing 'published' field on {type_!r} activity. An activity "
            "must carry the time its sender claims the event occurred; "
            "without it the receiver cannot tell a claimed time from its own "
            "clock (CLP-15-004)."
        )

    # Taken before anything expands or validates the body: this text is the
    # received artifact VM-08-002 governs, and nothing downstream can alter it.
    evidence_json = _received_evidence_json(body)

    # Decided once, here, for every object at every depth (MV-11-001): a near
    # miss refuses, a foreign key is set aside and reported.  Nothing below
    # sees a set-aside key, so a core class's ``extra="forbid"`` is never the
    # rule that decides a peer's property (MV-11-004).
    declared_body, set_aside = partition_unknown_keys(body, cls)
    _report_set_aside(body, set_aside)

    try:
        activity = cast(
            as_Activity,
            cls.model_validate(
                _expand_inline_object(declared_body),
                context=_INBOUND_CONTEXT,
            ),
        )
    except VultronParseError:
        # A malformed inline object already carries its own diagnosis, naming
        # the nested type that failed; re-wrapping would bury it.
        raise
    except Exception as exc:
        raise VultronParseValidationError(str(exc)) from exc

    activity.seal_received_evidence(evidence_json)
    return activity


def _report_set_aside(
    body: dict[str, Any], set_aside: list[SetAsideKey]
) -> None:
    """Log one INFO record per set-aside key (MV-11-003, SL-02-001/002).

    INFO, not WARNING: a property this receiver does not read is a normal
    protocol event — usually a peer's extension — not an anomaly (SL-03-001).
    The key survives only in the received evidence (VM-08-002).
    """
    if not set_aside:
        return
    activity_id = body.get("id")
    actor = body.get("actor")
    actor_id = actor.get("id") if isinstance(actor, dict) else actor
    for entry in set_aside:
        logger.info(
            "Set aside unknown key %r at %s; it is not read by this receiver"
            " (MV-11-003) [activity_id=%s actor_id=%s]",
            entry.key,
            entry.location,
            activity_id,
            actor_id,
        )


def _received_evidence_json(body: dict[str, Any]) -> str:
    """Serialize *body* as the received evidence, refusing non-JSON content.

    Why a class config cannot hold VM-08-002 any more: ``frozen=True`` covers
    only the class that declares it, and since ADR-0099 detail 3 a parsed
    activity nests *core* classes, which are mutable by design because they are
    also the domain objects (ISSUE-3584).  Pydantic has no per-instance
    freezing, so the guarantee moves from the object graph to a value copy taken
    here.  Serialized text rather than a deep-copied ``dict``: a ``str`` cannot
    be mutated in place by anyone, so no reader has to be trusted.

    A body that cannot be re-serialized is refused rather than coerced into a
    string form.  That covers a ``dict`` built in process with a non-JSON value,
    and a JSON number such as ``1e400`` that decodes to ``inf``, which strict
    JSON cannot carry back out.  ``json.dumps`` would also quietly rewrite some
    in-process values it *can* serialize (a non-string key becomes a string, a
    tuple a list), so the text is decoded again and must equal *body*; otherwise
    the evidence would describe a body that never arrived.

    Raises:
        VultronParseValidationError: If *body* holds a non-JSON value, or one
            that does not survive a JSON round trip unchanged.
    """
    try:
        evidence_json = json.dumps(body, ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise VultronParseValidationError(
            f"Activity body is not JSON-serializable: {exc}"
        ) from exc
    if json.loads(evidence_json) != body:
        raise VultronParseValidationError(
            "Activity body does not survive a JSON round trip unchanged "
            "(a non-string key or a tuple value?); it is not a JSON body."
        )
    return evidence_json
