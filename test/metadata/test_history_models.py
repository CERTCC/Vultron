"""Tests for NewHistoryEntry and HistoryEntryFrontmatter Pydantic models.

Covers: HM-02-001, HM-06-001 through HM-06-005.
"""

from __future__ import annotations

import datetime

import pytest
from pydantic import ValidationError

from vultron.metadata.history.types import HistoryEntryType

_UTC = datetime.timezone.utc


class TestNewHistoryEntry:
    """NewHistoryEntry (write model) self-timestamps and validates."""

    @pytest.fixture()
    def model_cls(self):  # type: ignore[no-untyped-def]
        from vultron.metadata.history.models import NewHistoryEntry

        return NewHistoryEntry

    def test_auto_timestamps_to_utc_now(self, model_cls) -> None:  # type: ignore[no-untyped-def]
        """HM-06-001: model is the timestamper-of-record; no explicit timestamp needed."""
        before = datetime.datetime.now(_UTC)
        entry = model_cls(title="T", type=HistoryEntryType.idea, source="SRC")
        after = datetime.datetime.now(_UTC)
        assert before <= entry.timestamp <= after
        assert entry.timestamp.tzinfo == _UTC

    def test_explicit_timestamp_override_accepted(self, model_cls) -> None:  # type: ignore[no-untyped-def]
        """Backfill callers may supply a timestamp explicitly (HM-07-002)."""
        ts = datetime.datetime(2026, 1, 15, 10, 30, 0, tzinfo=_UTC)
        entry = model_cls(
            title="T", type=HistoryEntryType.idea, source="SRC", timestamp=ts
        )
        assert entry.timestamp == ts

    def test_naive_timestamp_rejected(self, model_cls) -> None:  # type: ignore[no-untyped-def]
        with pytest.raises(ValidationError):
            model_cls(
                title="T",
                type=HistoryEntryType.idea,
                source="SRC",
                timestamp=datetime.datetime(2026, 4, 28, 12, 0, 0),
            )

    def test_offset_timestamp_normalised_to_utc(self, model_cls) -> None:  # type: ignore[no-untyped-def]
        plus_two = datetime.timezone(datetime.timedelta(hours=2))
        ts = datetime.datetime(2026, 4, 28, 14, 0, 0, tzinfo=plus_two)
        entry = model_cls(
            title="T", type=HistoryEntryType.idea, source="SRC", timestamp=ts
        )
        assert entry.timestamp.tzinfo == _UTC
        assert entry.timestamp.hour == 12

    def test_missing_title_rejected(self, model_cls) -> None:  # type: ignore[no-untyped-def]
        with pytest.raises(ValidationError):
            model_cls(type=HistoryEntryType.idea, source="SRC")

    def test_empty_source_rejected(self, model_cls) -> None:  # type: ignore[no-untyped-def]
        with pytest.raises(ValidationError):
            model_cls(title="T", type=HistoryEntryType.idea, source="")


class TestHistoryEntryFrontmatter:
    """HistoryEntryFrontmatter (read model) requires timestamp; fails loudly."""

    @pytest.fixture()
    def model_cls(self):  # type: ignore[no-untyped-def]
        from vultron.metadata.history.models import HistoryEntryFrontmatter

        return HistoryEntryFrontmatter

    def test_valid_model_with_timestamp_accepted(self, model_cls) -> None:  # type: ignore[no-untyped-def]
        ts = datetime.datetime(2026, 4, 28, 12, 0, 0, tzinfo=_UTC)
        m = model_cls(
            title="Test",
            type=HistoryEntryType.idea,
            timestamp=ts,
            source="IDEA-001",
        )
        assert m.title == "Test"
        assert m.type == HistoryEntryType.idea
        assert m.source == "IDEA-001"
        assert m.timestamp == ts

    def test_missing_timestamp_rejected(self, model_cls) -> None:  # type: ignore[no-untyped-def]
        """HM-06-002: missing timestamp must fail loudly."""
        with pytest.raises(ValidationError):
            model_cls.model_validate(
                {"title": "T", "type": "idea", "source": "IDEA-004"}
            )

    def test_legacy_date_field_rejected(self, model_cls) -> None:  # type: ignore[no-untyped-def]
        """date: field is no longer supported; all entries must use timestamp:."""
        with pytest.raises(ValidationError):
            model_cls.model_validate(
                {
                    "title": "T",
                    "type": "idea",
                    "date": "2026-04-28",
                    "source": "SRC",
                }
            )

    def test_naive_timestamp_rejected(self, model_cls) -> None:  # type: ignore[no-untyped-def]
        """HM-06-005: naive timestamps (no tz info) must be rejected."""
        with pytest.raises(ValidationError):
            model_cls.model_validate(
                {
                    "title": "T",
                    "type": "idea",
                    "timestamp": datetime.datetime(2026, 4, 28, 12, 0, 0),
                    "source": "IDEA-005",
                }
            )

    def test_timezone_normalised_to_utc(self, model_cls) -> None:  # type: ignore[no-untyped-def]
        """Offset-aware timestamps are normalised to UTC (HM-06-005)."""
        plus_two = datetime.timezone(datetime.timedelta(hours=2))
        ts_local = datetime.datetime(2026, 4, 28, 14, 0, 0, tzinfo=plus_two)
        m = model_cls.model_validate(
            {
                "title": "T",
                "type": "idea",
                "timestamp": ts_local,
                "source": "IDEA-006",
            }
        )
        assert m.timestamp.tzinfo == _UTC
        assert m.timestamp.hour == 12  # 14:00+02:00 → 12:00 UTC

    @pytest.mark.parametrize("missing", ["title", "type", "source"])
    def test_missing_field_raises(self, model_cls, missing: str) -> None:  # type: ignore[no-untyped-def]
        ts = datetime.datetime(2026, 4, 28, 12, 0, 0, tzinfo=_UTC)
        data = {
            "title": "T",
            "type": "idea",
            "timestamp": ts,
            "source": "SRC-1",
        }
        del data[missing]
        with pytest.raises(ValidationError):
            model_cls.model_validate(data)

    @pytest.mark.parametrize("field", ["title", "source"])
    def test_empty_string_rejected(self, model_cls, field: str) -> None:  # type: ignore[no-untyped-def]
        ts = datetime.datetime(2026, 4, 28, 12, 0, 0, tzinfo=_UTC)
        data = {
            "title": "T",
            "type": "idea",
            "timestamp": ts,
            "source": "SRC-2",
        }
        data[field] = ""
        with pytest.raises(ValidationError):
            model_cls.model_validate(data)

    @pytest.mark.parametrize("field", ["title", "source"])
    def test_whitespace_only_rejected(self, model_cls, field: str) -> None:  # type: ignore[no-untyped-def]
        ts = datetime.datetime(2026, 4, 28, 12, 0, 0, tzinfo=_UTC)
        data = {
            "title": "T",
            "type": "idea",
            "timestamp": ts,
            "source": "SRC-3",
        }
        data[field] = "   "
        with pytest.raises(ValidationError):
            model_cls.model_validate(data)

    def test_invalid_type_rejected(self, model_cls) -> None:  # type: ignore[no-untyped-def]
        ts = datetime.datetime(2026, 4, 28, 12, 0, 0, tzinfo=_UTC)
        with pytest.raises(ValidationError):
            model_cls.model_validate(
                {
                    "title": "T",
                    "type": "bogus",
                    "timestamp": ts,
                    "source": "SRC-4",
                }
            )

    def test_timestamp_string_coerced(self, model_cls) -> None:  # type: ignore[no-untyped-def]
        """ISO 8601 timestamp strings are accepted and normalised to datetime."""
        m = model_cls.model_validate(
            {
                "title": "T",
                "type": "idea",
                "timestamp": "2026-04-28T12:00:00+00:00",
                "source": "SRC-6",
            }
        )
        assert m.timestamp == datetime.datetime(
            2026, 4, 28, 12, 0, 0, tzinfo=_UTC
        )
