"""Tests for vultron.wire.as2.parser."""

import pytest

from vultron.core.models.events import MessageSemantics
from vultron.semantic_registry import extract_event

from vultron.wire.as2.errors import (
    VultronParseMissingPublishedError,
    VultronParseMissingTypeError,
    VultronParseUnknownTypeError,
    VultronParseValidationError,
)
from vultron.wire.as2.parser import parse_activity

#: Every inbound activity must carry a sender-supplied ``published``, so each
#: body below sets one.  Absence is a validity failure, not a field the parser
#: fills in — see ``test_parse_activity_raises_missing_published_when_absent``.
PUBLISHED = "2026-03-04T05:06:07+00:00"

#: Every spelling of "the sender supplied no value".  Whitespace-only counts as
#: blank by the project's canonical predicate (``not v.strip()``, see
#: ``vultron.core.models.base._non_empty``): a guard that catches ``""`` but not
#: ``"   "`` has the same blind spot one character over.
BLANK = ("", " ", "   ", "\t", "\n", " \t\n ")


@pytest.mark.spec("MV-01-001")
def test_parse_activity_raises_missing_type_when_type_absent():
    with pytest.raises(VultronParseMissingTypeError):
        parse_activity({})


@pytest.mark.spec("MV-01-001")
def test_parse_activity_raises_unknown_type_for_unrecognized_type():
    with pytest.raises(VultronParseUnknownTypeError):
        parse_activity({"type": "NoSuchActivityType"})


@pytest.mark.spec("MV-01-001")
@pytest.mark.spec("MV-03-002")
@pytest.mark.spec("CS-08-001")
@pytest.mark.parametrize("blank", BLANK)
def test_parse_activity_reads_blank_type_as_missing_not_unknown(blank: str):
    """A blank ``type`` names no type, so it is absence, not an unknown type.

    The distinction is observable: the inbox adapter maps
    ``VultronParseMissingTypeError`` to HTTP 400 and every other parse error to
    422, so routing a blank ``type`` through ``find_in_vocabulary`` answered a
    sender who omitted the field with two different status codes depending on
    how they spelled the omission (ISSUE-3217).
    """
    with pytest.raises(VultronParseMissingTypeError):
        parse_activity(
            {
                "type": blank,
                "actor": "https://example.org/alice",
                "published": PUBLISHED,
                "object": "https://example.org/notes/1",
            }
        )


@pytest.mark.spec("MV-01-001")
@pytest.mark.spec("CLP-15-004")
def test_parse_activity_raises_missing_published_when_absent():
    """An inbound activity without ``published`` is malformed, not correctable.

    ``as_Base`` declares ``published`` with ``default_factory=now_utc`` so the
    same classes can *author* outbound activities.  On the inbound path that
    default is the receiver's own clock, and once ``model_validate`` has run it
    is indistinguishable from a value the sender actually sent — which is what
    left CLP-14-007 and CLP-14-008 comparing the receiver's clock against
    itself (ISSUE-3149).  The check therefore reads the raw body.
    """
    with pytest.raises(VultronParseMissingPublishedError):
        parse_activity(
            {
                "type": "Create",
                "actor": "https://example.org/alice",
                "object": "https://example.org/notes/1",
            }
        )


@pytest.mark.spec("CLP-15-004")
def test_parse_activity_rejects_explicit_null_published():
    """``"published": null`` is absence spelled out, and refused the same way."""
    with pytest.raises(VultronParseMissingPublishedError):
        parse_activity(
            {
                "type": "Create",
                "actor": "https://example.org/alice",
                "published": None,
                "object": "https://example.org/notes/1",
            }
        )


@pytest.mark.spec("CLP-15-006")
@pytest.mark.spec("MV-03-002")
@pytest.mark.spec("CS-08-001")
@pytest.mark.parametrize("blank", BLANK)
def test_parse_activity_rejects_blank_published(blank: str):
    """A blank ``published`` carries no claimed time, so it is absence.

    CLP-15-006 refuses an inbound activity that "carries no ``published``", and
    a field present but empty carries none — CS-08-001's "if present, then
    non-empty".  Asking only whether the *key* was absent let this reach
    ``model_validate``, which reported it as a schema fault and so replaced the
    CLP-15-006 explanation with a Pydantic isoformat dump (ISSUE-3217).
    """
    with pytest.raises(VultronParseMissingPublishedError):
        parse_activity(
            {
                "type": "Create",
                "actor": "https://example.org/alice",
                "published": blank,
                "object": "https://example.org/notes/1",
            }
        )


@pytest.mark.spec("CLP-15-006")
@pytest.mark.spec("MV-03-002")
def test_parse_activity_reports_unparseable_published_as_malformed():
    """Blank is absence; garbage is malformed, and the two stay distinct.

    Pins the boundary the blank guard must not cross.  A bare falsy check would
    also absorb ``0`` and ``[]``, reporting a corrupt timestamp as a missing
    one and telling the sender to add a field they already sent.
    """
    for value in ("not-a-date", 0, [], {}):
        with pytest.raises(VultronParseValidationError):
            parse_activity(
                {
                    "type": "Create",
                    "actor": "https://example.org/alice",
                    "published": value,
                    "object": "https://example.org/notes/1",
                }
            )


@pytest.mark.spec("CLP-15-004")
def test_parse_activity_raises_missing_published_for_empty_string():
    """``"published": ""`` is absence-by-empty-value and refused the same way.

    ``body.get("published") is None`` evaluates to False for ``""``, so an
    is-None guard silently passes an empty string on to ``model_validate``
    which then raises a Pydantic ``ValidationError`` instead of the
    protocol-level ``VultronParseMissingPublishedError`` callers expect.
    """
    with pytest.raises(VultronParseMissingPublishedError):
        parse_activity(
            {
                "type": "Create",
                "actor": "https://example.org/alice",
                "published": "",
                "object": "https://example.org/notes/1",
            }
        )


@pytest.mark.spec("CLP-15-004")
def test_parse_activity_preserves_the_senders_published_verbatim():
    """The guard is non-vacuous only if the sender's value survives parsing.

    Pins the value against the receiver's clock: a regression that reinstated
    the default would produce ``now``, not the 2026 timestamp asserted here.
    """
    from datetime import datetime, timezone

    result = parse_activity(
        {
            "type": "Create",
            "actor": "https://example.org/alice",
            "published": PUBLISHED,
            "object": "https://example.org/notes/1",
        }
    )

    assert result.published == datetime(
        2026, 3, 4, 5, 6, 7, tzinfo=timezone.utc
    )
    assert result.published != datetime.now(tz=timezone.utc)


@pytest.mark.spec("MV-01-001")
def test_parse_activity_raises_validation_error_for_invalid_data(monkeypatch):
    from vultron.wire.as2 import parser as p
    from vultron.wire.as2.vocab.base.objects.activities.base import as_Activity

    class _FailingModel(as_Activity):
        @classmethod
        def model_validate(cls, data, **kwargs):  # type: ignore[override]
            raise ValueError("bad data")

    monkeypatch.setattr(p, "find_in_vocabulary", lambda _: _FailingModel)
    with pytest.raises(VultronParseValidationError):
        parse_activity({"type": "Create", "published": PUBLISHED})


@pytest.mark.spec("MV-01-001")
def test_parse_activity_returns_typed_activity_for_valid_create():
    from vultron.wire.as2.vocab.base.objects.activities.transitive import (
        as_Create,
    )

    result = parse_activity(
        {
            "type": "Create",
            "actor": "https://example.org/alice",
            "published": PUBLISHED,
            "object": "https://example.org/notes/1",
        }
    )
    assert isinstance(result, as_Create)


def _invite_response_body(activity_type: str) -> dict[str, object]:
    return {
        "type": activity_type,
        "id": f"urn:uuid:{activity_type.lower()}-invite-response-1",
        "actor": "https://example.org/actors/coordinator",
        "published": PUBLISHED,
        "inReplyTo": "urn:uuid:invite-1",
        "object": {
            "type": "Invite",
            "id": "urn:uuid:invite-1",
            "actor": "https://example.org/actors/vendor",
            "object": {
                "type": "Organization",
                "id": "https://example.org/actors/coordinator",
                "name": "Coordinator",
            },
            "target": {
                "type": "VulnerabilityCase",
                "id": "https://example.org/cases/case-1",
            },
            "to": ["https://example.org/actors/coordinator"],
        },
    }


@pytest.mark.parametrize(
    ("activity_type", "expected_semantics"),
    [
        ("Accept", MessageSemantics.ACCEPT_INVITE_ACTOR_TO_CASE),
        ("Reject", MessageSemantics.REJECT_INVITE_ACTOR_TO_CASE),
    ],
)
def test_parse_activity_extracts_invite_response_semantics_from_nested_stub_case(
    activity_type: str, expected_semantics: MessageSemantics
):
    parsed = parse_activity(_invite_response_body(activity_type))

    event = extract_event(parsed)

    assert event.semantic_type == expected_semantics
    assert event.in_reply_to == "urn:uuid:invite-1"
    assert event.object_ is not None
    assert event.object_.id_ == "urn:uuid:invite-1"

    if activity_type == "Accept":
        assert (
            getattr(event, "case_id", None)
            == "https://example.org/cases/case-1"
        )
        assert (
            getattr(event, "invitee_id", None)
            == "https://example.org/actors/coordinator"
        )


@pytest.mark.spec("CS-08-001")
@pytest.mark.spec("MV-04-003")
def test_parse_activity_keeps_nested_subtype_when_nested_published_is_blank():
    """A blank timestamp on a nested object must not erase that object's type.

    ``_expand_inline_value`` types nested dicts so pattern matching can see the
    inner ``Invite``.  When that validation failed the raw dict was returned
    instead, the parent validated it as a bare ``as_Link``, and the activity
    parsed *clean* — extracting as ``UNKNOWN`` with the case id gone, so the
    inbox answered 202 for a real Accept it had silently mis-routed
    (ISSUE-3217).  Reading the blank as absence keeps the subtype.
    """
    body = _invite_response_body("Accept")
    body["object"]["published"] = ""  # type: ignore[index]

    event = extract_event(parse_activity(body))

    assert event.semantic_type == MessageSemantics.ACCEPT_INVITE_ACTOR_TO_CASE
    assert event.case_id == "https://example.org/cases/case-1"


@pytest.mark.spec("MV-04-003")
def test_parse_activity_refuses_malformed_nested_object_of_known_type():
    """A nested object we recognised but cannot validate is refused, not degraded.

    Substituting the raw dict is silent data loss: the parent accepts it as a
    bare ``as_Link``, so a corrupt inner object produces a *successful* parse
    and a 202 for a message the receiver never understood.  Once the type has
    resolved to a wire class, failing that class's validation is a message
    fault and belongs in the 422 (ADR-0032: validate at the edge).
    """
    body = _invite_response_body("Accept")
    body["object"]["published"] = "not-a-date"  # type: ignore[index]

    with pytest.raises(VultronParseValidationError):
        parse_activity(body)


@pytest.mark.spec("ARCH-22-001")
@pytest.mark.spec("MV-04-003")
def test_parse_activity_keeps_inline_actor_subtype_with_core_only_collections():
    """An inline actor's subtype must survive its ``inbox``/``outbox``.

    ``OrderedCollection`` is registered only in ``CORE_TYPE_MAP``, so
    ``find_in_vocabulary`` used to hand the nested expansion a *core*
    ``CoreActorCollection``; ``as_VultronOrganization.inbox`` rejects a core
    instance, and the swallowed failure degraded the whole actor to an
    ``as_Link``.  Nested expansion inside a wire tree resolves wire classes
    only (MV-04-003), so the mismatch cannot arise.  The rule is MV-04-003, not
    ARCH-22-001 as this previously cited: it is about which registry an inline
    type string resolves against, not about which modules may import which.
    """
    actor = {
        "type": "Organization",
        "id": "https://example.org/alice",
        "name": "Alice",
        "inbox": {
            "type": "OrderedCollection",
            "id": "https://example.org/alice/inbox",
            "items": [],
        },
        "outbox": {
            "type": "OrderedCollection",
            "id": "https://example.org/alice/outbox",
            "items": [],
        },
    }

    result = parse_activity(
        {
            "type": "Create",
            "id": "urn:uuid:create-with-inline-actor",
            "published": PUBLISHED,
            "actor": actor,
            "object": "https://example.org/notes/1",
        }
    )

    assert type(result.actor).__name__ == "VultronOrganization"
    assert getattr(result.actor, "id_", None) == "https://example.org/alice"


def test_parsing_activity_line_is_debug_not_info(caplog):
    """ "Parsing activity from body" is HTTP handler internals (SL-04-007)."""
    import logging

    with caplog.at_level(logging.DEBUG, logger="vultron.wire.as2.parser"):
        parse_activity(
            {
                "type": "Create",
                "actor": "https://example.org/alice",
                "published": PUBLISHED,
                "object": "https://example.org/notes/1",
            }
        )

    parsing = [
        r for r in caplog.records if "Parsing activity from" in r.getMessage()
    ]
    assert parsing, "Expected the 'Parsing activity from body' log entry"
    assert all(r.levelno == logging.DEBUG for r in parsing)


#: ``type`` values that are present and name *something*, but not a string we
#: can look up.  ``[]`` and ``{}`` are the load-bearing pair: they are
#: unhashable, so a dict membership test on them raises ``TypeError`` rather
#: than ``KeyError``.
NON_STRING_TYPES: tuple[object, ...] = (
    0,
    123,
    True,
    [],
    {},
    ["Create"],
    {"type": "Create"},
)


@pytest.mark.spec("MV-04-001")
@pytest.mark.spec("MV-03-002")
@pytest.mark.parametrize("bad_type", NON_STRING_TYPES)
def test_parse_activity_reports_non_string_type_as_unknown(bad_type: object):
    """A non-string ``type`` is an unknown type, never an escaping exception.

    ``find_in_vocabulary`` resolves by dict membership, so an unhashable
    ``type`` such as ``[]`` or ``{}`` raised ``TypeError`` — which the local
    ``except KeyError`` did not catch and which the inbox adapter does not map,
    so it escaped ``parse_activity`` and drew a 500.  That is the very
    unhandled-exception symptom ISSUE-3217 was filed about, in a sibling
    spelling of the same field.
    """
    with pytest.raises(VultronParseUnknownTypeError):
        parse_activity(
            {
                "type": bad_type,
                "actor": "https://example.org/alice",
                "published": PUBLISHED,
                "object": "https://example.org/notes/1",
            }
        )


@pytest.mark.spec("MV-04-003")
def test_refusal_of_malformed_inline_object_names_the_field_path():
    """A refusal must say *where* the fault is, not only which type failed.

    ``_expand_inline_value`` recurses before it raises, so naming just the
    innermost class left the sender unable to tell which of two same-typed
    objects was corrupt (MV-04-003 is only actionable if the sender can locate
    the fault).
    """
    with pytest.raises(VultronParseValidationError) as exc_info:
        parse_activity(
            {
                "type": "Accept",
                "actor": "https://example.org/alice",
                "published": PUBLISHED,
                "object": {
                    "type": "Invite",
                    "id": "https://example.org/invites/1",
                    "published": "not-a-date",
                },
            }
        )

    message = str(exc_info.value)
    assert "as_Invite" in message
    assert "'object'" in message


@pytest.mark.spec("MV-04-003")
@pytest.mark.spec("ARCH-22-001")
def test_core_only_inline_type_is_left_for_the_parent_field():
    """A ``CORE_TYPE_MAP``-only ``type`` must not resolve to a core class here.

    ``find_in_vocabulary`` falls back to the core map (ARCH-12-003), where
    ``OrderedCollection`` alone is registered.  Resolving it would place a core
    instance in a wire tree; the wire parent then rejected it and the whole
    object degraded to a bare ``as_Link``.  Leaving the dict unexpanded hands
    the decision to the parent field, which is its declared authority.
    """
    result = parse_activity(
        {
            "type": "Create",
            "actor": "https://example.org/alice",
            "published": PUBLISHED,
            "object": {
                "type": "OrderedCollection",
                "id": "https://example.org/collections/1",
                "items": [],
            },
        }
    )

    inline = getattr(result, "object_", None)
    assert type(inline).__name__ == "as_Object"
    assert type(inline).__name__ != "CoreActorCollection"
