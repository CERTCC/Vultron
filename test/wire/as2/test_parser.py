"""Tests for vultron.wire.as2.parser."""

import pytest

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
