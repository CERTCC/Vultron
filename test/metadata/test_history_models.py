"""Tests for HistoryEntryFrontmatter Pydantic model.

Covers: HM-02-001 required-field contract.
"""

from __future__ import annotations

import datetime

import pytest
from pydantic import ValidationError

from vultron.metadata.history.types import HistoryEntryType


class TestHistoryEntryFrontmatter:
    """HistoryEntryFrontmatter validates required frontmatter fields."""

    @pytest.fixture()
    def model_cls(self):  # type: ignore[no-untyped-def]
        from vultron.metadata.history.models import HistoryEntryFrontmatter

        return HistoryEntryFrontmatter

    def test_valid_model_accepted(self, model_cls) -> None:  # type: ignore[no-untyped-def]
        m = model_cls(
            title="Test",
            type=HistoryEntryType.idea,
            date=datetime.date(2026, 4, 28),
            source="IDEA-001",
        )
        assert m.title == "Test"
        assert m.type == HistoryEntryType.idea
        assert m.source == "IDEA-001"

    @pytest.mark.parametrize("missing", ["title", "type", "date", "source"])
    def test_missing_field_raises(self, model_cls, missing: str) -> None:  # type: ignore[no-untyped-def]
        data = {
            "title": "T",
            "type": "idea",
            "date": "2026-04-28",
            "source": "SRC-1",
        }
        del data[missing]
        with pytest.raises(ValidationError):
            model_cls.model_validate(data)

    @pytest.mark.parametrize("field", ["title", "source"])
    def test_empty_string_rejected(self, model_cls, field: str) -> None:  # type: ignore[no-untyped-def]
        data = {
            "title": "T",
            "type": "idea",
            "date": "2026-04-28",
            "source": "SRC-2",
        }
        data[field] = ""
        with pytest.raises(ValidationError):
            model_cls.model_validate(data)

    @pytest.mark.parametrize("field", ["title", "source"])
    def test_whitespace_only_rejected(self, model_cls, field: str) -> None:  # type: ignore[no-untyped-def]
        data = {
            "title": "T",
            "type": "idea",
            "date": "2026-04-28",
            "source": "SRC-3",
        }
        data[field] = "   "
        with pytest.raises(ValidationError):
            model_cls.model_validate(data)

    def test_invalid_type_rejected(self, model_cls) -> None:  # type: ignore[no-untyped-def]
        with pytest.raises(ValidationError):
            model_cls.model_validate(
                {
                    "title": "T",
                    "type": "bogus",
                    "date": "2026-04-28",
                    "source": "SRC-4",
                }
            )

    def test_invalid_date_rejected(self, model_cls) -> None:  # type: ignore[no-untyped-def]
        with pytest.raises(ValidationError):
            model_cls.model_validate(
                {
                    "title": "T",
                    "type": "idea",
                    "date": "not-a-date",
                    "source": "SRC-5",
                }
            )

    def test_date_string_coerced(self, model_cls) -> None:  # type: ignore[no-untyped-def]
        m = model_cls.model_validate(
            {
                "title": "T",
                "type": "idea",
                "date": "2026-04-28",
                "source": "SRC-6",
            }
        )
        assert m.date == datetime.date(2026, 4, 28)
