"""Pydantic schema for notes/*.md YAML frontmatter.

Schema requirements: specs/notes-frontmatter.md NF-01, NF-02.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, field_validator, model_validator

from vultron.metadata.base import NonEmptyStr, NonEmptyStrList


class NoteStatus(StrEnum):
    """Valid values for the ``status`` frontmatter field."""

    ACTIVE = "active"
    DRAFT = "draft"
    SUPERSEDED = "superseded"
    ARCHIVED = "archived"


class NotesFrontmatter(BaseModel):
    """Validated representation of a ``notes/*.md`` YAML frontmatter block.

    Required fields: ``title``, ``status``.
    All other fields are optional but must be non-empty when present.
    """

    title: NonEmptyStr
    status: NoteStatus
    superseded_by: NonEmptyStr | None = None
    description: NonEmptyStr | None = None
    related_specs: NonEmptyStrList | None = None
    related_notes: NonEmptyStrList | None = None
    relevant_packages: NonEmptyStrList | None = None

    @field_validator(
        "related_specs", "related_notes", "relevant_packages", mode="before"
    )
    @classmethod
    def non_empty_list_if_present(cls, v: object) -> object:
        """Reject present-and-empty list fields (NF-01-006 through NF-01-008)."""
        if v is not None and isinstance(v, list) and len(v) == 0:
            raise ValueError("list field must be non-empty if present")
        return v

    @model_validator(mode="after")
    def superseded_by_required_when_superseded(self) -> NotesFrontmatter:
        """Require ``superseded_by`` when ``status`` is ``superseded`` (NF-01-004)."""
        if self.status == NoteStatus.SUPERSEDED and not self.superseded_by:
            raise ValueError(
                "'superseded_by' is required when status is 'superseded'"
            )
        return self
