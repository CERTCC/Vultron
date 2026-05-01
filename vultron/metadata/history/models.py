"""Pydantic model for history entry YAML frontmatter.

Defines the required-field contract for ``append-history`` entries
(HM-02-001, HM-06-002 through HM-06-005). Used by both the CLI
(``cli.py``) and the README generator (``readme_gen.py``) so the
validation rule is a single source of truth.
"""

from __future__ import annotations

import datetime
from typing import Optional

from pydantic import BaseModel, field_validator, model_validator

from vultron.metadata.history.types import HistoryEntryType

_UTC = datetime.timezone.utc


class HistoryEntryFrontmatter(BaseModel):
    """Required frontmatter fields for every history entry file (HM-02-001).

    Exactly one of ``timestamp`` or the legacy ``date`` field must be
    supplied (HM-06-002).  When only ``date`` is present the
    ``normalize_legacy_date`` validator converts it to a UTC midnight
    ``timestamp`` so all downstream code can use ``timestamp``
    exclusively (HM-06-003).
    """

    title: str
    type: HistoryEntryType
    source: str
    timestamp: Optional[datetime.datetime] = None
    date: Optional[datetime.date] = (
        None  # legacy; normalised to timestamp on load
    )

    @field_validator("title", "source", mode="before")
    @classmethod
    def must_be_non_empty(cls, v: object) -> str:
        if not isinstance(v, str):
            raise ValueError("must be a string")
        stripped = v.strip()
        if not stripped:
            raise ValueError("must not be empty or whitespace-only")
        return stripped

    @model_validator(mode="before")
    @classmethod
    def normalize_legacy_date(cls, values: object) -> object:
        """Enforce mutual exclusivity and convert legacy ``date`` → ``timestamp``.

        Raises:
            ValueError: If both ``date`` and ``timestamp`` are present, or if
                neither is provided.
        """
        if not isinstance(values, dict):
            return values
        has_date = values.get("date") is not None
        has_timestamp = values.get("timestamp") is not None
        if has_date and has_timestamp:
            raise ValueError("supply either 'date' or 'timestamp', not both")
        if not has_date and not has_timestamp:
            raise ValueError("one of 'date' or 'timestamp' must be provided")
        if has_date:
            d = values["date"]
            if isinstance(d, str):
                try:
                    d = datetime.date.fromisoformat(d)
                except ValueError as exc:
                    raise ValueError(
                        f"invalid date value '{d}'; expected YYYY-MM-DD"
                    ) from exc
            if isinstance(d, datetime.datetime):
                # YAML may parse date+time together; normalise to date first.
                d = d.date()
            if isinstance(d, datetime.date):
                values["timestamp"] = datetime.datetime(
                    d.year, d.month, d.day, tzinfo=_UTC
                )
                values.pop("date", None)
        return values

    @field_validator("timestamp")
    @classmethod
    def validate_timestamp(
        cls, v: datetime.datetime | None
    ) -> datetime.datetime | None:
        """Enforce tz-aware UTC timestamps (HM-06-005).

        Future-date rejection (HM-06-004) is enforced at creation time in the
        CLI layer, not here, so that existing entries with future-asserted
        dates can still be read without error by README generation.
        """
        if v is None:
            return v
        if v.tzinfo is None:
            raise ValueError(
                "timestamp must be timezone-aware "
                "(provide a UTC offset, e.g. +00:00)"
            )
        return v.astimezone(_UTC)
