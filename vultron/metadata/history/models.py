"""Pydantic models for history entry YAML frontmatter.

Provides two distinct models (HM-02-001, HM-06-002 through HM-06-005):

- :class:`NewHistoryEntry` — write model.  Self-timestamps to UTC now via
  ``default_factory``; external code MUST NOT supply a timestamp except for
  backfill overrides (HM-07-002).
- :class:`HistoryEntryFrontmatter` — read model.  ``timestamp`` is required
  and must be tz-aware; fails loudly on missing or malformed values so that
  corrupt files are never silently accepted.

Both inherit :class:`_HistoryEntryBase` which validates the shared fields
``title``, ``type``, and ``source``.
"""

from __future__ import annotations

import datetime

from pydantic import BaseModel, Field, field_validator

from vultron.metadata.history.types import HistoryEntryType

_UTC = datetime.timezone.utc


def _now_utc() -> datetime.datetime:
    return datetime.datetime.now(_UTC)


def _coerce_to_utc(v: datetime.datetime) -> datetime.datetime:
    """Require a tz-aware datetime and normalise it to UTC."""
    if v.tzinfo is None:
        raise ValueError(
            "timestamp must be timezone-aware "
            "(provide a UTC offset, e.g. +00:00)"
        )
    return v.astimezone(_UTC)


class _HistoryEntryBase(BaseModel):
    """Shared validated fields for all history entry frontmatter."""

    title: str
    type: HistoryEntryType
    source: str

    @field_validator("title", "source", mode="before")
    @classmethod
    def must_be_non_empty(cls, v: object) -> str:
        if not isinstance(v, str):
            raise ValueError("must be a string")
        stripped = v.strip()
        if not stripped:
            raise ValueError("must not be empty or whitespace-only")
        return stripped


class NewHistoryEntry(_HistoryEntryBase):
    """Write model: self-timestamps new entries to UTC now unless overridden.

    The model is the timestamper-of-record for new entries (HM-06-001,
    HM-07-002).  Pass ``timestamp`` only for backfill/migration overrides.
    """

    timestamp: datetime.datetime = Field(default_factory=_now_utc)

    @field_validator("timestamp")
    @classmethod
    def validate_timestamp(cls, v: datetime.datetime) -> datetime.datetime:
        return _coerce_to_utc(v)


class HistoryEntryFrontmatter(_HistoryEntryBase):
    """Read model: parses existing history entry files.

    ``timestamp`` is required; fails loudly if absent or malformed
    (HM-06-002).  Does not supply a default so that corrupt files
    are never silently accepted.
    """

    timestamp: datetime.datetime

    @field_validator("timestamp")
    @classmethod
    def validate_timestamp(cls, v: datetime.datetime) -> datetime.datetime:
        return _coerce_to_utc(v)
