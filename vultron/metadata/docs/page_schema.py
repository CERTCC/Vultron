"""Pydantic schema for the audience and level declared in ``docs/`` frontmatter.

Schema requirements: specs/diataxis-requirements.yaml DF-11-001 (reader-facing
pages), DF-11-012 (working-record pages), DF-11-003 (which pages are working
record). Design rationale: ``notes/site-information-architecture.md``
(ADR-0102).

This module is the single machine source for the ``stakeholder_type`` members
and the ``level`` ladder. Anything that needs either — the validator in
:mod:`vultron.metadata.docs.page_frontmatter`, the generated
``docs/includes/stakeholder_types.md`` fragment (DF-11-011), the coverage
matrix (DF-11-008) — imports :class:`StakeholderType`, :data:`LEVELS` and
:data:`AUDIENCE_DESCRIPTIONS` rather than restating them.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Annotated, Literal, get_args

from pydantic import BaseModel, BeforeValidator, field_validator


class StakeholderType(StrEnum):
    """Who a ``docs/`` page is addressed to (DF-11-001).

    Records the reader a page is written for, not what it is about. No member
    is a ``CVDRole`` value, so a reader type cannot be confused with a role a
    participant holds in a case.
    """

    CVD_PRACTITIONER = "cvd-practitioner"
    PLATFORM_DEVELOPER = "platform-developer"
    PROCESS_RESEARCHER = "process-researcher"
    PROJECT_CONTRIBUTOR = "project-contributor"


#: The only permitted spelling of "every stakeholder type": a bare scalar,
#: never ``[ALL]`` and never a list naming every member (DF-11-001).
ALL_STAKEHOLDERS = "ALL"

#: Every ``stakeholder_type`` key in display order: each member, then ``ALL``.
AUDIENCE_KEYS: tuple[str, ...] = (
    *(member.value for member in StakeholderType),
    ALL_STAKEHOLDERS,
)


@dataclass(frozen=True, slots=True)
class AudienceDescription:
    """What the shared ``stakeholder_types.md`` fragment says about one entry.

    Attributes:
        who: Who the reader is.
        wants: What that reader wants from the documentation.
    """

    who: str
    wants: str


#: The reader each :class:`StakeholderType` member names, and the meaning of
#: :data:`ALL_STAKEHOLDERS`. The generated ``docs/includes/stakeholder_types.md``
#: fragment renders these (DF-11-011), so a member added to the enum without a
#: description here fails the generator rather than shipping a blank row.
AUDIENCE_DESCRIPTIONS: Mapping[str, AudienceDescription] = MappingProxyType(
    {
        StakeholderType.CVD_PRACTITIONER: AudienceDescription(
            who=(
                "Works CVD cases or the programs around them — including "
                "security researchers who report vulnerabilities, vendor "
                "PSIRTs, and national CSIRTs, ISACs, and ISAOs"
            ),
            wants=(
                "To decide whether to adopt, and how the process changes if "
                "they do"
            ),
        ),
        StakeholderType.PLATFORM_DEVELOPER: AudienceDescription(
            who=(
                "Builds or maintains a tracker, platform, or tool that must "
                "coordinate with others"
            ),
            wants=(
                "What to send and when, and where their own system plugs in"
            ),
        ),
        StakeholderType.PROCESS_RESEARCHER: AudienceDescription(
            who=(
                "CVD process engineering, process-improvement research, "
                "cross-case ecosystem health"
            ),
            wants=(
                "The models, the measurements, and where the process theory "
                "leads"
            ),
        ),
        StakeholderType.PROJECT_CONTRIBUTOR: AudienceDescription(
            who="Works on this reference implementation",
            wants=(
                "How this codebase is built, and why it was built that way"
            ),
        ),
        ALL_STAKEHOLDERS: AudienceDescription(
            who="Genuinely every type above",
            wants="Declared explicitly; never inferred from an absent key",
        ),
    }
)

#: The prerequisite ladder. A page's level is never rendered or navigated by
#: (DF-11-004); it exists so page ordering can be checked (DF-11-002).
Level = Literal[100, 200, 300, 400, 500]
LEVELS: tuple[int, ...] = get_args(Level)


def _check_level(value: object) -> object:
    """Accept only an integer on the ladder — not ``"100"``, ``100.0``, or a bool.

    Pydantic's lax mode would coerce ``100.0``; a level is a rung, and a
    spelling that only coerces to one is a second spelling of the same fact.
    """
    if type(value) is not int or value not in LEVELS:
        raise ValueError(
            f"must be one of {', '.join(str(n) for n in LEVELS)}, written as "
            f"an unquoted integer"
        )
    return value


def _check_stakeholder_type(value: object) -> object:
    """Reject every shape but a bare ``ALL`` or a proper subset of members.

    The checks run before type validation so each shape fault gets one
    sentence naming the fix, rather than Pydantic's union error listing every
    alternative it tried.
    """
    if value == ALL_STAKEHOLDERS:
        return value
    if isinstance(value, str):
        raise ValueError(
            f"must be a list of stakeholder types or the bare scalar "
            f"{ALL_STAKEHOLDERS}; write [{value}] for a single type"
        )
    if not isinstance(value, list) or not value:
        raise ValueError(
            f"must be a non-empty list of stakeholder types or the bare "
            f"scalar {ALL_STAKEHOLDERS}"
        )
    if ALL_STAKEHOLDERS in value:
        raise ValueError(
            f"write the bare scalar {ALL_STAKEHOLDERS}, not a list "
            f"containing it"
        )
    permitted = {member.value for member in StakeholderType}
    unknown = [str(v) for v in value if v not in permitted]
    if unknown:
        raise ValueError(
            f"unknown stakeholder type {', '.join(unknown)}; permitted: "
            f"{', '.join(sorted(permitted))}, or the bare scalar "
            f"{ALL_STAKEHOLDERS}"
        )
    if len(set(value)) != len(value):
        raise ValueError("lists a stakeholder type more than once")
    if set(value) == permitted:
        raise ValueError(
            f"names every stakeholder type; write the bare scalar "
            f"{ALL_STAKEHOLDERS} instead, so the fact has one spelling"
        )
    return value


StakeholderTypes = Annotated[
    Literal["ALL"] | list[StakeholderType],
    BeforeValidator(_check_stakeholder_type),
]


class PageFrontmatter(BaseModel):
    """The declarations a reader-facing page makes (DF-11-001).

    Only the two declaration keys are validated; a page's other frontmatter
    (``title``, ``status``, and so on) belongs to other schemas.
    """

    stakeholder_type: StakeholderTypes
    level: Annotated[Level, BeforeValidator(_check_level)]


class WorkingRecordFrontmatter(BaseModel):
    """The declarations a project working-record page makes (DF-11-012).

    The working record is addressed to ``project-contributor`` and has no
    level. The absence is enforced rather than defaulted: a level on a
    decision record is a category error, not a harmless extra.
    """

    stakeholder_type: StakeholderTypes
    level: None = None

    @field_validator("stakeholder_type")
    @classmethod
    def addressed_to_contributors(cls, value: object) -> object:
        """Require exactly ``[project-contributor]``."""
        if value != [StakeholderType.PROJECT_CONTRIBUTOR]:
            raise ValueError(
                f"a working-record page must declare "
                f"[{StakeholderType.PROJECT_CONTRIBUTOR.value}]"
            )
        return value

    @field_validator("level", mode="before")
    @classmethod
    def no_level(cls, value: object) -> object:
        """Refuse any declared level, including ``null``."""
        raise ValueError(
            "a working-record page must not declare a level (DF-11-012)"
        )


#: ``docs/``-relative glob patterns naming the project working record
#: (DF-11-003): decision records, generated code documentation, exhaustively
#: enumerated state pages, retained design history, and agent- and
#: contributor-facing material. ``**`` spans directories; ``*`` does not.
#: #3528 maintains this set as the working record moves behind its door.
WORKING_RECORD_PATTERNS: tuple[str, ...] = (
    # Decision records, archived ones included.
    "adr/**",
    # Agent- and contributor-facing material.
    "agents/**",
    "developer/**",
    "about/contributing.md",
    "reference/codebase/**",
    "reference/inbox_handler.md",
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
    # The tombstone page for the unmaintained OWL ontology files (#3526).
    "reference/ontology/index.md",
    # Requirements-traceability records: the individual user stories and the
    # contributor-facing matrix that routes them. The stories' index.md is
    # addressed to readers and stays leveled (#3526).
    "reference/user_stories/story_*.md",
    "reference/user_stories/traceability.md",
)


_GLOB_TOKENS = {"**/": "(?:.*/)?", "**": ".*", "*": "[^/]*"}


def _glob_regex(pattern: str) -> re.Pattern[str]:
    """Compile a ``docs/``-relative glob; ``**`` spans directories.

    Hand-rolled because ``PurePath.full_match`` needs Python 3.13 and
    ``fnmatch`` lets ``*`` cross ``/``.
    """
    parts = re.split(r"(\*\*/?|\*)", pattern)
    body = "".join(_GLOB_TOKENS.get(part, re.escape(part)) for part in parts)
    return re.compile(f"{body}\\Z")


_WORKING_RECORD_RES = tuple(_glob_regex(p) for p in WORKING_RECORD_PATTERNS)


def is_working_record(docs_path: str) -> bool:
    """Whether a ``docs/``-relative POSIX path is project working record."""
    return any(rx.match(docs_path) for rx in _WORKING_RECORD_RES)
