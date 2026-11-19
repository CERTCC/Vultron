"""AS2 wire layer parser for the Vultron Protocol.

Converts raw request bodies (dicts) into typed as_Activity objects.
This is stage 2 of the inbound pipeline: raw dict → typed AS2 activity.
Raises domain errors; driving adapters are responsible for mapping these
to transport-level error responses (e.g., HTTP status codes).
"""

import json
import logging
from typing import Any, cast

from pydantic import BaseModel, ValidationError

from vultron.core.models._helpers import MissingClaimedTimeError
from vultron.core.models.preview_object import PreviewObject, PreviewValue
from vultron.core.models.sender_sequence import is_sender_sequence
from vultron.wire.as2.case_proposal_envelope import (
    refuse_malformed_case_proposal_envelope,
)
from vultron.wire.as2.case_reference_placement import refuse_misplaced_forms
from vultron.wire.as2.context_agreement import refuse_context_disagreement
from vultron.wire.as2.errors import (
    VultronParseError,
    VultronParseMissingPublishedError,
    VultronParseMissingTypeError,
    VultronParseUnknownTypeError,
    VultronParseValidationError,
)
from vultron.wire.as2.typed_reference import as_TypedReference
from vultron.wire.as2.unknown_keys import (
    OPAQUE_PAYLOAD_KEYS,
    declared_slot_class,
    partition_unknown_keys,
    report_set_aside,
    resolve_inline_class,
    slot_classes,
)
from vultron.wire.as2.vocab.base.base import as_Base
from vultron.wire.as2.vocab.base.objects.activities.base import as_Activity
from vultron.wire.as2.vocab.base.registry import (
    resolve_received_type,
    resolve_wire_type,
)
from vultron.wire.as2.vocab.base.utils import is_blank

logger = logging.getLogger(__name__)


#: Marks every ``model_validate`` call in this module as reading inbound data,
#: which is what tells a class to refuse a whole object with no ``published``
#: (CLP-15-011) and to read any other absent time as ``None``, the sender
#: claiming none (ISSUE-3257, CLP-15-007).  It belongs
#: only where a peer's body is read (here, and the fetch edge): a caller
#: *authoring* an object states the act's instant (ADR-0176), and passing this
#: context for one would hide its omission.
_INBOUND_CONTEXT = {as_Base.INBOUND_CONTEXT_KEY: True}

#: The wire name of an activity's sender sequence (SYNC-21-001).
_SENDER_SEQUENCE_KEY = "senderSequence"


def _is_preview_form(cls: type[BaseModel] | None) -> bool:
    """Whether *cls* is a preview or a loose form a preview holds (ADR-0217)."""
    return cls is not None and issubclass(cls, (PreviewObject, PreviewValue))


def _inline_class(
    value: dict[str, Any], path: str, slots: tuple[type[BaseModel], ...]
) -> type[BaseModel] | None:
    """The class that validates the inline dict *value*.

    Its ``type`` names a wire class (:func:`resolve_inline_class`), except
    inside a preview, whose fields declare loose forms (*slots*): what a
    preview shows is read as its sender sent it, so a nested object of a
    type a slot declares a loose form for is read in that form, and a dict
    with no ``type`` in a slot that declares one loose form takes it
    (ADR-0217).  The unknown-key partition reads the same slot class
    (:func:`declared_slot_class`), so one class decides the object's keys and
    validates it.
    """
    resolved = resolve_inline_class(value, path)
    loose = tuple(cls for cls in slots if _is_preview_form(cls))
    if not loose:
        return resolved
    if "type" not in value:
        return loose[0] if len(loose) == 1 else resolved
    declared = declared_slot_class(value, loose, resolved)
    return declared if declared is not None else resolved


def _expand_inline_value(
    value: object,
    path: str = "",
    slots: tuple[type[BaseModel], ...] = (),
) -> object:
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
        slots: The model classes the field holding *value* declares, passed
            down only from a preview or a loose form, whose fields declare
            the loose forms its contents are read in (:func:`_inline_class`).
    """
    if isinstance(value, list):
        return [
            _expand_inline_value(item, f"{path}[{index}]", slots)
            for index, item in enumerate(value)
        ]
    if not isinstance(value, dict):
        return value

    inline_cls = _inline_class(value, path, slots)
    reads_loose = _is_preview_form(inline_cls)
    expanded = {
        key: (
            item
            if key in OPAQUE_PAYLOAD_KEYS
            else _expand_inline_value(
                item,
                f"{path}.{key}" if path else key,
                slot_classes(inline_cls, key)
                if reads_loose and inline_cls is not None
                else (),
            )
        )
        for key, item in value.items()
    }
    if inline_cls is None:
        return expanded
    # The class holds one ``type``: a list is read as the term it resolved
    # to, which a core class's own validation could not do (ADR-0196).  Only
    # the ``type`` the class was resolved from is narrowed.
    if "type" in expanded:
        _, expanded = resolve_received_type(expanded)

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
        refuse_missing_claimed_time(exc, path)
        where = f" at {path!r}" if path else ""
        raise VultronParseValidationError(
            f"Inline {inline_cls.__name__} object{where} is malformed:"
            f" {_reference_hint(exc, path)}{exc}"
        ) from exc


def _expand_inline_object(body: dict[str, Any]) -> dict[str, Any]:
    """Recursively expand nested inline dicts while leaving the outer body raw."""
    return {
        key: _expand_inline_value(value, key) for key, value in body.items()
    }


def refuse_missing_claimed_time(
    exc: Exception, path: str, prefix: str = ""
) -> None:
    """Re-raise a nested object's missing ``published`` as that refusal.

    A received whole object must carry its author's time at any depth
    (CLP-15-011), and its class's inbound validator says so with
    :class:`MissingClaimedTimeError`.  Pydantic buries that cause in a
    ``ValidationError``; finding it here lets the sender read the same
    refusal CLP-15-008 gives a top-level activity, with the position of every
    untimed object.  The fetch edge reads a fetched body's the same way.  Any
    other fault in the same error is named too, so the sender learns of every
    violation at once (EH-07-001).  Returns when *exc* holds no such cause,
    leaving the caller's schema-fault refusal to run.

    Args:
        exc: The exception validation raised.
        path: Dotted position of the object that was being validated, or
            ``""`` for the activity itself.
        prefix: Leading text naming the activity, as :func:`_named` gives.

    Raises:
        VultronParseMissingPublishedError: When *exc* carries the cause.
    """
    if not isinstance(exc, ValidationError):
        return
    missing: list[str] = []
    rule = ""
    others: list[str] = []
    for error in exc.errors():
        where = _join_location(path, error["loc"])
        cause = error.get("ctx", {}).get("error")
        if isinstance(cause, MissingClaimedTimeError):
            missing.append(where)
            rule = str(cause)
        elif not _is_union_alternative(error):
            others.append(f"{where or 'the activity'}: {error['msg']}")
    if not missing:
        return
    # Each union member a value failed reports the same position; name it once.
    named = [repr(where) for where in dict.fromkeys(missing) if where]
    location = f" at {', '.join(named)}" if named else ""
    also = f"; also refused: {'; '.join(others)}" if others else ""
    raise VultronParseMissingPublishedError(
        f"{prefix}Missing 'published'{location}: {rule}{also}"
    ) from exc


def _reference_hint(exc: Exception, path: str) -> str:
    """A lead naming each slot a typed reference cannot fill, or ``""``.

    A typed reference names an object and is never the object (MV-10-011), so
    a slot that admits only a whole object refuses it, and a slot that admits
    only a URI wants the reference's ``id``.  Pydantic says only that the
    value is not the slot's type; this says why.
    """
    if not isinstance(exc, ValidationError):
        return ""
    whole: set[str] = set()
    uri: set[str] = set()
    for error in exc.errors():
        if not isinstance(error.get("input"), as_TypedReference):
            continue
        slot = _join_location(path, error["loc"])
        (uri if error["type"] == "string_type" else whole).add(slot)
    leads = []
    if whole:
        leads.append(
            f"a typed reference at {_slots(whole)} names an object, but the"
            " slot needs the whole object (MV-10-011); "
        )
    if uri:
        leads.append(
            f"a typed reference at {_slots(uri)} names an object, but the"
            " slot takes only a URI: send the reference's 'id' (MV-10-011); "
        )
    return "".join(leads)


def _slots(slots: set[str]) -> str:
    """*slots* as a sorted, quoted, comma-separated list."""
    return ", ".join(repr(slot) for slot in sorted(slots))


def _is_union_alternative(error: Any) -> bool:
    """Whether *error* only says a value is not one member of a union.

    Pydantic reports each union member a value failed, so a status in a
    ``CaseStatus | str`` slot also fails as "not a valid string".  Such an
    error ends on the member's schema tag; it restates the real fault rather
    than adding one.
    """
    loc = error["loc"]
    return (
        error["type"].endswith("_type")
        and bool(loc)
        and isinstance(loc[-1], str)
        and ("[" in loc[-1] or "(" in loc[-1])
    )


def _join_location(path: str, loc: tuple[int | str, ...]) -> str:
    """*path* extended by a pydantic error ``loc``, in :func:`_expand_inline_value` form.

    An index becomes ``[n]``.  A step holding ``[`` or ``(`` is a schema tag
    pydantic adds for a validator-wrapped member (``function-after[...]``),
    not a position in the body, so it is left out.
    """
    where = path
    for step in loc:
        if isinstance(step, int):
            where += f"[{step}]"
        elif "[" not in step and "(" not in step:
            where = f"{where}.{step}" if where else step
    return where


def _named(body: dict[str, Any]) -> str:
    """``"activity '<id>': "`` for a body that names its id, else ``""``."""
    activity_id = body.get("id")
    if isinstance(activity_id, str) and activity_id.strip():
        return f"activity {activity_id!r}: "
    return ""


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
            or blank, or a whole object anywhere in the activity carries none,
            other than an actor profile or a collection (CLP-15-011).
        VultronParseUnknownTypeError: If the `type` value is not in the
            vocabulary: a string it does not hold, a list naming no type it
            holds or two unrelated ones (VM-03-006), or any other value.
        VultronParseValidationError: If Pydantic validation fails, including
            when a recognised inline object fails its own class's validation,
            if a ``Create(CaseProposal)`` does not carry its proposer's inline
            actor profile (CP-01-010), if a case reference sits anywhere but
            the object of a ``Join``, ``Ignore``, ``Leave`` or ``Offer``
            (AKM-03-004), if a case preview sits anywhere but the
            ``preview`` of the case reference that is an Invite's ``object``
            (MV-10-002), if the activity's ``context`` and that of an
            object down its ``object`` chain name different cases
            (HP-08-015),
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

    # Wire-only lookup (VM-06-008): a core-only name is an unknown type here,
    # not a core class to validate a sender's activity against.  The shared
    # resolver reads a string or an AS2 type list (ADR-0196) and answers any
    # other value with a ``KeyError``.  A ``type`` it cannot resolve is
    # deliberately not a ``MissingType`` 400: the sender did name a type, it is
    # just not one we can look up, so it is the ``UnknownType`` 422.  An
    # unhashable value (``{}``) once raised ``TypeError`` from a bare dict
    # lookup, which escaped ``parse_activity`` and drew a 500 (ISSUE-3217).
    try:
        cls = resolve_wire_type(type_)
    except KeyError as exc:
        raise VultronParseUnknownTypeError(
            f"Unrecognized activity type: {type_!r} ({exc.args[0]})."
        ) from exc

    if not issubclass(cls, as_Activity):
        raise VultronParseUnknownTypeError(
            f"Type {type_!r} is not an activity type."
        )

    # Ordered after type resolution — "is this a type we recognise" is a
    # routing question and answering it first keeps the existing error
    # precedence — but before ``model_validate``, because inbound validation
    # reads an absent ``published`` as ``None`` at every depth.  When the
    # field had a clock default, an absent timestamp became the *receiver's*
    # clock, read downstream as the sender's claim, which is what made
    # CLP-14-007 and CLP-14-008 compare the receiver's clock against itself
    # (ISSUE-3149).  Absence is a
    # message-validity failure, not something to correct downstream
    # (ADR-0032: validate at the edge).
    #
    # Scoped to the top-level activity: a nested whole object's absent
    # ``published`` is refused by its class's inbound validator, which the
    # ``_INBOUND_CONTEXT`` below switches on, and is named by its position
    # (CLP-15-011).  A nested reference, URI or ``Link`` carries no time.
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
    # sender to resend a field they already sent.  MV-03-002 reports a present,
    # non-blank but unparseable value as a schema fault instead (ADR-0090).
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
    actor = body.get("actor")
    report_set_aside(
        set_aside,
        {
            "activity_id": body.get("id"),
            "actor_id": actor.get("id") if isinstance(actor, dict) else actor,
        },
    )
    declared_body = _without_malformed_sender_sequence(declared_body)

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
        refuse_missing_claimed_time(exc, "", _named(body))
        # Named, so a refusal of a field such as ``ledgerPosition`` says which
        # activity it refused (SYNC-18-015).
        raise VultronParseValidationError(f"{_named(body)}{exc}") from exc

    # A schema-valid envelope can still be one this receiver cannot act on;
    # the Create(CaseProposal) checks are the CP-01-010 refusals.
    refuse_malformed_case_proposal_envelope(activity)
    # A case reference names the case only where an act may (AKM-03-004), a
    # case preview stands for the case only in a stub Invite (MV-10-002), and
    # a marker withholds a value only in a preview's field (MV-12-002).
    refuse_misplaced_forms(activity)
    # An activity and the objects it carries name one case (HP-08-015).
    refuse_context_disagreement(activity)

    activity.seal_received_evidence(evidence_json)
    return activity


def parse_received_body(received_body: str) -> as_Activity:
    """Parse a received body a receiver holds, as the inbox parsed it.

    *received_body* is the evidence an earlier parse sealed (VM-08-002): the
    text an archive or a deferred record keeps (ADR-0149).  Parsing it again
    seals the same text, so the result carries exactly the held body.

    Raises:
        VultronParseError: When the held text no longer parses.
    """
    return parse_activity(json.loads(received_body))


def _without_malformed_sender_sequence(body: dict[str, Any]) -> dict[str, Any]:
    """*body* without a ``senderSequence`` that is not a positive integer.

    A malformed number is the CASE_MANAGER's to refuse, with a notice naming
    the number it expects, after its door and sender guards admit the
    activity (SYNC-21-017, SYNC-21-023).  Refusing it here would refuse it
    with no notice, and before the guards, so the value is set aside: the
    activity parses as one that carries no number, and the received
    evidence keeps the value as it arrived (VM-08-002).  A receiver that is
    not the case's CASE_MANAGER reads no number, so it loses nothing.
    """
    value = body.get(_SENDER_SEQUENCE_KEY)
    if value is None or is_sender_sequence(value):
        return body
    logger.info(
        "Set aside %s %r, which is not a positive integer; the activity"
        " carries no number (SYNC-21-017) [activity_id=%s]",
        _SENDER_SEQUENCE_KEY,
        value,
        body.get("id"),
    )
    return {k: v for k, v in body.items() if k != _SENDER_SEQUENCE_KEY}


def _received_evidence_json(body: dict[str, Any]) -> str:
    """Serialize *body* as the received evidence, refusing non-JSON content.

    Why a class config cannot hold VM-08-002 any more: ``frozen=True`` covers
    only the class that declares it, and since ARCH-25-003 (ADR-0099) a parsed
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
