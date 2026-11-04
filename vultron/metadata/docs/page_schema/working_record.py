"""The working-record frontmatter and the paths that hold working records."""

from __future__ import annotations

from typing import Annotated

from pathspec.gitignore import GitIgnoreSpec
from pydantic import (
    AfterValidator,
    BaseModel,
    field_validator,
)

from vultron.metadata.docs.page_schema.frontmatter import (
    StakeholderType,
    StakeholderTypes,
)


def _check_addressed_to_contributors(value: object) -> object:
    """Require exactly ``[project-contributor]`` (DF-11-012)."""
    if value != [StakeholderType.PROJECT_CONTRIBUTOR]:
        raise ValueError(
            f"a working-record page must declare "
            f"[{StakeholderType.PROJECT_CONTRIBUTOR.value}]"
        )
    return value


#: The ``stakeholder_type`` a working-record page declares: well-formed as any
#: page's (:data:`StakeholderTypes`), and then exactly ``[project-contributor]``.
#: :class:`~vultron.metadata.adr.schema.AdrFrontmatter` reuses it, so a decision
#: record's declaration is checked by the same rule wherever it is loaded.
WorkingRecordStakeholderTypes = Annotated[
    StakeholderTypes, AfterValidator(_check_addressed_to_contributors)
]


class WorkingRecordFrontmatter(BaseModel):
    """The declarations a project working-record page makes (DF-11-012).

    The working record is addressed to ``project-contributor`` and has no
    level, no page type and no subject. Each absence is enforced rather than
    defaulted: a level on a decision record is a category error, not a
    harmless extra, the working record's door (DF-11-003) already says what
    kind of page it is (DF-11-036), and the working record is out of the nav
    whose sections the subject is checked over (DF-11-026).
    """

    stakeholder_type: WorkingRecordStakeholderTypes
    level: None = None
    page_type: None = None
    subject: None = None

    @field_validator("level", mode="before")
    @classmethod
    def no_level(cls, value: object) -> object:
        """Refuse any declared level, including ``null``."""
        raise ValueError(
            "a working-record page must not declare a level (DF-11-033)"
        )

    @field_validator("page_type", mode="before")
    @classmethod
    def no_page_type(cls, value: object) -> object:
        """Refuse any declared page type, including ``null``."""
        raise ValueError(
            "a working-record page must not declare a page_type (DF-11-036)"
        )

    @field_validator("subject", mode="before")
    @classmethod
    def no_subject(cls, value: object) -> object:
        """Refuse any declared subject, including ``null``."""
        raise ValueError(
            "a working-record page must not declare a subject (DF-11-026)"
        )


#: ``docs/``-relative glob patterns naming the project working record
#: (DF-11-003): decision records, generated code documentation, exhaustively
#: enumerated state pages, retained design history, and agent- and
#: contributor-facing material. Matched as gitignore lines, exactly as MkDocs
#: matches ``not_in_nav``, so the two lists cannot read one pattern two ways.
#: A page matched here must stay out of the ``mkdocs.yml`` nav, which
#: :mod:`~vultron.metadata.docs.page_frontmatter` checks; ``not_in_nav`` lists it
#: so the build does not warn about the omission.
WORKING_RECORD_PATTERNS: tuple[str, ...] = (
    # Decision records, archived ones included.
    "adr/**",
    # Agent- and contributor-facing material.
    "agents/**",
    "developer/**",
    "about/contributing.md",
    "reference/codebase/**",
    "reference/specs/process.md",
    "reference/specs/project.md",
    # Generated code documentation, including the rendered behavior trees.
    "reference/behaviors/**",
    "reference/code/**",
    # Exhaustively enumerated state pages.
    "reference/case_states/**",
    # Retained design history: the "Original Design" behavior-tree pages
    # (#3281 decided to keep them, not to retire them).
    "topics/behavior_logic/*_bt.md",
    "topics/behavior_logic/original_design.md",
    # The tombstone page for the unmaintained OWL ontology files (#3526).
    "reference/ontology/index.md",
    # Requirements-traceability records: the individual user stories and the
    # contributor-facing matrix that routes them. The stories' index.md is
    # addressed to readers and stays leveled (#3526).
    "reference/user_stories/story_*.md",
    "reference/user_stories/traceability.md",
)


_WORKING_RECORD_SPEC = GitIgnoreSpec.from_lines(WORKING_RECORD_PATTERNS)


def is_working_record(docs_path: str) -> bool:
    """Whether a ``docs/``-relative POSIX path is project working record."""
    return _WORKING_RECORD_SPEC.match_file(docs_path)
