"""Tests for vultron.wire.as2.parser."""

import pytest

from vultron.core.models.events import MessageSemantics
from vultron.semantic_registry import extract_event

from vultron.wire.as2.errors import (
    VultronParseMissingTypeError,
    VultronParseUnknownTypeError,
    VultronParseValidationError,
)
from vultron.wire.as2.parser import parse_activity


def test_parse_activity_raises_missing_type_when_type_absent():
    with pytest.raises(VultronParseMissingTypeError):
        parse_activity({})


def test_parse_activity_raises_unknown_type_for_unrecognized_type():
    with pytest.raises(VultronParseUnknownTypeError):
        parse_activity({"type": "NoSuchActivityType"})


def test_parse_activity_raises_validation_error_for_invalid_data(monkeypatch):
    from vultron.wire.as2 import parser as p
    from vultron.wire.as2.vocab.base.objects.activities.base import as_Activity

    class _FailingModel(as_Activity):
        @classmethod
        def model_validate(cls, data, **kwargs):  # type: ignore[override]
            raise ValueError("bad data")

    monkeypatch.setattr(p, "find_in_vocabulary", lambda _: _FailingModel)
    with pytest.raises(VultronParseValidationError):
        parse_activity({"type": "Create"})


def test_parse_activity_returns_typed_activity_for_valid_create():
    from vultron.wire.as2.vocab.base.objects.activities.transitive import (
        as_Create,
    )

    result = parse_activity(
        {
            "type": "Create",
            "actor": "https://example.org/alice",
            "object": "https://example.org/notes/1",
        }
    )
    assert isinstance(result, as_Create)


def _invite_response_body(activity_type: str) -> dict[str, object]:
    return {
        "type": activity_type,
        "id": f"urn:uuid:{activity_type.lower()}-invite-response-1",
        "actor": "https://example.org/actors/coordinator",
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
