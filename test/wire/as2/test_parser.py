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


@pytest.mark.spec("MV-01-001")
def test_parse_activity_raises_missing_type_when_type_absent():
    with pytest.raises(VultronParseMissingTypeError):
        parse_activity({})


@pytest.mark.spec("MV-01-001")
def test_parse_activity_raises_unknown_type_for_unrecognized_type():
    with pytest.raises(VultronParseUnknownTypeError):
        parse_activity({"type": "NoSuchActivityType"})


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
