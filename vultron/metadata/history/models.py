"""Pydantic model for history entry YAML frontmatter.

Defines the required-field contract for ``append-history`` entries
(HM-02-001). Used by both the CLI (``cli.py``) and the README generator
(``readme_gen.py``) so the validation rule is a single source of truth.
"""

from __future__ import annotations

import datetime

from pydantic import BaseModel, field_validator

from vultron.metadata.history.types import HistoryEntryType


class HistoryEntryFrontmatter(BaseModel):
    """Required frontmatter fields for every history entry file (HM-02-001)."""

    title: str
    type: HistoryEntryType
    date: datetime.date
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
