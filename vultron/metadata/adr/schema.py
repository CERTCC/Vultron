"""Pydantic schema for docs/adr/*.md YAML frontmatter.

Schema requirements: specs/meta-specifications.yaml MS-14 (ADR-0043).

Mirrors the notes frontmatter package (``vultron.metadata.notes``): a validated
model plus a loader, enforced by pytest and pre-commit. The ADR ``status`` field
is the confidence signal coding agents read, so it is validated against the
:class:`~vultron.metadata.specs.schema.AdrStatus` StrEnum rather than free text.
"""

from __future__ import annotations

import datetime as _dt
from enum import StrEnum

from pydantic import BaseModel, field_validator, model_validator

from vultron.metadata.base import NonEmptyStr
from vultron.metadata.specs.schema import AdrStatus

# A frontmatter person field (deciders/consulted/informed) may be a bare string
# or a list of strings — both forms occur across the existing ADR corpus.
PersonField = NonEmptyStr | list[NonEmptyStr]


class AdrLintSuppressCode(StrEnum):
    """Named ADR lint warnings suppressible via ``lint_suppress`` (MS-14-002).

    Mirrors the spec-level ``LintWarningCode`` mechanism (SR-02-011).
    """

    STATUS_PROSE_CONTRADICTION = "status_prose_contradiction"


class AdrFrontmatter(BaseModel):
    """Validated representation of a ``docs/adr/*.md`` YAML frontmatter block.

    Required field: ``status`` (a member of :class:`AdrStatus`; the inline MADR
    form ``superseded by <link>`` is normalised to ``superseded``). A retired
    ADR (``superseded`` or ``deprecated``) MUST carry a ``superseded_by`` link.
    All other fields are optional but must be non-empty when present.
    """

    status: AdrStatus
    date: _dt.date | None = None
    deciders: PersonField | None = None
    consulted: PersonField | None = None
    informed: PersonField | None = None
    superseded_by: NonEmptyStr | None = None
    supersedes: NonEmptyStr | None = None
    amended: NonEmptyStr | None = None
    lint_suppress: list[AdrLintSuppressCode] | None = None

    @model_validator(mode="before")
    @classmethod
    def normalise_inline_superseded(cls, data: object) -> object:
        """Map the inline MADR ``superseded by <link>`` form to the split form.

        MADR allows ``status: superseded by <link>``; the project convention is
        bare ``superseded`` plus a separate ``superseded_by:`` field. Accept
        both by collapsing the inline form to ``status: superseded`` and lifting
        the embedded link into ``superseded_by`` when that field is absent.
        """
        if not isinstance(data, dict):
            return data
        status = data.get("status")
        if isinstance(status, str):
            stripped = status.strip().strip("{}")
            if stripped.lower().startswith("superseded by"):
                data = dict(data)
                data["status"] = AdrStatus.SUPERSEDED.value
                if not data.get("superseded_by"):
                    link = stripped[len("superseded by") :].strip()
                    if link:
                        data["superseded_by"] = link
        return data

    @field_validator("lint_suppress", mode="before")
    @classmethod
    def non_empty_list_if_present(cls, v: object) -> object:
        """Reject a present-but-empty ``lint_suppress`` list."""
        if v is not None and isinstance(v, list) and len(v) == 0:
            raise ValueError("'lint_suppress' must be non-empty if present")
        return v

    @model_validator(mode="after")
    def superseded_by_required_when_retired(self) -> AdrFrontmatter:
        """Require ``superseded_by`` when the ADR is retired (MS-14-004).

        A ``superseded`` or ``deprecated`` ADR without a pointer to its
        replacement is a dead end for the agent that lands on it.
        """
        if (
            self.status in (AdrStatus.SUPERSEDED, AdrStatus.DEPRECATED)
            and not self.superseded_by
        ):
            raise ValueError(
                "'superseded_by' is required when status is "
                f"'{self.status.value}'"
            )
        return self
