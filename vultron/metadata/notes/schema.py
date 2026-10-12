"""Pydantic schema for notes/*.md YAML frontmatter.

Schema requirements: specs/notes-frontmatter.yaml NF-01, NF-02.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated

from pydantic import (
    BaseModel,
    StringConstraints,
    field_validator,
    model_validator,
)

from vultron.metadata.base import NonEmptyStr, NonEmptyStrList

IssueRef = Annotated[str, StringConstraints(pattern=r"^#[1-9][0-9]*$")]
"""A GitHub issue reference in ``#N`` form (NF-01-010)."""

GENERATED_MARKER = "<!-- GENERATED"
"""Body prefix every ``kind: generated`` note carries (NF-01-011)."""


class NoteStatus(StrEnum):
    """Valid values for the ``status`` frontmatter field."""

    ACTIVE = "active"
    DRAFT = "draft"
    SUPERSEDED = "superseded"
    ARCHIVED = "archived"


class NoteKind(StrEnum):
    """Valid values for the ``kind`` frontmatter field (NF-01-009, NF-08)."""

    GUIDANCE = "guidance"
    PLAN = "plan"
    GENERATED = "generated"


class NotesFrontmatter(BaseModel):
    """Validated representation of a ``notes/*.md`` YAML frontmatter block.

    Required fields: ``title``, ``status``, ``kind``; ``tracks`` is required
    on, and only allowed on, ``plan`` notes. All other fields are optional
    but must be non-empty when present.
    """

    title: NonEmptyStr
    status: NoteStatus
    kind: NoteKind
    tracks: list[IssueRef] | None = None
    superseded_by: NonEmptyStr | None = None
    description: NonEmptyStr | None = None
    related_specs: NonEmptyStrList | None = None
    related_notes: NonEmptyStrList | None = None
    relevant_packages: NonEmptyStrList | None = None

    @field_validator(
        "related_specs",
        "related_notes",
        "relevant_packages",
        "tracks",
        mode="before",
    )
    @classmethod
    def non_empty_list_if_present(cls, v: object) -> object:
        """Reject present-and-empty list fields (NF-01-006 to -008, NF-01-010)."""
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

    @model_validator(mode="after")
    def tracks_iff_plan(self) -> NotesFrontmatter:
        """Require ``tracks`` on ``plan`` notes, forbid it elsewhere (NF-01-010)."""
        if self.kind == NoteKind.PLAN and not self.tracks:
            raise ValueError("'tracks' is required when kind is 'plan'")
        if self.kind != NoteKind.PLAN and self.tracks is not None:
            raise ValueError("'tracks' is only allowed when kind is 'plan'")
        return self
