"""Pydantic schema for the audience, level and page type in ``docs/`` frontmatter.

Schema requirements: specs/diataxis-requirements.yaml DF-11-001 (reader-facing
pages), DF-11-018 (page type), DF-11-012 (working-record pages), DF-11-003
(which pages are working record), DF-11-013 (a start page's reading-path
thread). Design rationale: ``notes/site-information-architecture.md``
(ADR-0102, ADR-0136, ADR-0150).

This module is the single machine source for the ``stakeholder_type`` members,
the ``level`` ladder and the ``page_type`` values. Anything that needs one —
the validator in :mod:`vultron.metadata.docs.page_frontmatter`, the generated
``docs/includes/stakeholder_types.md`` fragment (DF-11-011), the coverage
matrix (DF-11-008), the page-type badge's tests — imports
:class:`StakeholderType`, :data:`LEVELS`, :data:`AUDIENCE_DESCRIPTIONS`,
:class:`PageType` and :data:`PAGE_TYPE_BADGES` rather than restating them.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Annotated, Literal, get_args
from urllib.parse import urlsplit

from pathspec.gitignore import GitIgnoreSpec
from pydantic import (
    AfterValidator,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    StrictBool,
    field_validator,
)

from vultron.primitives import NonEmptyString


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


class PageType(StrEnum):
    """What kind of page a reader-facing ``docs/`` page is (DF-11-018).

    The four Diátaxis content types, plus ``routing`` for a page that mainly
    gives directions: the home page, the start pages, and indexes that only
    route. A page's type is independent of its ``contents:`` shape: an index
    whose links are a routing page's (DF-11-005) but whose prose mostly
    explains is ``explanation``.
    """

    TUTORIAL = "tutorial"
    HOW_TO = "how-to"
    EXPLANATION = "explanation"
    REFERENCE = "reference"
    ROUTING = "routing"


#: The label each page type's badge shows. ``routing`` renders no badge, so it
#: has no entry. ``overrides/partials/page_type.html`` holds the same labels;
#: a test renders that template for every member and compares, so the two
#: cannot disagree.
PAGE_TYPE_BADGES: Mapping[PageType, str] = MappingProxyType(
    {
        PageType.TUTORIAL: "Tutorial",
        PageType.HOW_TO: "How-to guide",
        PageType.EXPLANATION: "Explanation",
        PageType.REFERENCE: "Reference",
    }
)


def _check_page_type(value: object) -> object:
    """Accept only a bare string naming a :class:`PageType` member."""
    permitted = [member.value for member in PageType]
    if value not in permitted:
        raise ValueError(f"must be one of {', '.join(permitted)}")
    return value


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
        raise ValueError(  # noqa: TRY004  # ruff-baseline #3353
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


class AudienceDeclaration(BaseModel):
    """Who a reader-facing page is for, and at what level (DF-11-001).

    The part of :class:`PageFrontmatter` the coverage matrix (DF-11-008)
    counts, which is why it stands alone.
    """

    stakeholder_type: StakeholderTypes
    level: Annotated[Level, BeforeValidator(_check_level)]


class PageFrontmatter(AudienceDeclaration):
    """The declarations a reader-facing page makes (DF-11-001, DF-11-018).

    Only the three declaration keys are validated; a page's other frontmatter
    (``title``, ``status``, and so on) belongs to other schemas.
    """

    page_type: Annotated[PageType, BeforeValidator(_check_page_type)]


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
    level and no page type. Each absence is enforced rather than defaulted: a
    level on a decision record is a category error, not a harmless extra, and
    the working record's door (DF-11-003) already says what kind of page it
    is (DF-11-018).
    """

    stakeholder_type: WorkingRecordStakeholderTypes
    level: None = None
    page_type: None = None

    @field_validator("level", mode="before")
    @classmethod
    def no_level(cls, value: object) -> object:
        """Refuse any declared level, including ``null``."""
        raise ValueError(
            "a working-record page must not declare a level (DF-11-012)"
        )

    @field_validator("page_type", mode="before")
    @classmethod
    def no_page_type(cls, value: object) -> object:
        """Refuse any declared page type, including ``null``."""
        raise ValueError(
            "a working-record page must not declare a page_type (DF-11-018)"
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


#: The ``docs/``-relative directory holding the start pages. Every page in it
#: but its ``index.md`` opens one reading-path thread (DF-11-013).
START_DIR = "start"

#: Frontmatter key carrying a start page's thread (DF-11-013).
THREAD_KEY = "thread"


def is_start_page(docs_path: str) -> bool:
    """Whether a ``docs/``-relative POSIX path is a start page.

    A start page is a page directly in :data:`START_DIR` other than its
    ``index.md``, which routes to the start pages rather than opening a thread.
    """
    head, _, name = docs_path.rpartition("/")
    return head == START_DIR and name.endswith(".md") and name != "index.md"


def _check_member_page(value: str) -> str:
    """Accept only a ``docs/``-relative ``.md`` path, with an optional fragment.

    A thread is a path through pages, so an external URL, an absolute path, a
    path climbing out of ``docs/``, or a non-Markdown file is not a member
    (DF-11-013). A link that is not a page belongs in a stage's ``framing``.
    """
    path, hash_, fragment = value.partition("#")
    if urlsplit(value).scheme or value.startswith("/"):
        raise ValueError(
            "must be a docs/-relative page path, not a URL or an absolute "
            "path; put a link that is not a page in the stage's framing"
        )
    if not path.endswith(".md") or ".." in path.split("/"):
        raise ValueError(
            "must name a .md page under docs/, written relative to docs/ "
            "without '..' segments"
        )
    if hash_ and not fragment:
        raise ValueError("has an empty #fragment")
    return value


class StageKind(StrEnum):
    """Whether a thread stage's pages are read in order (DF-11-013)."""

    #: Read in any order; rendered as a bulleted list.
    SET = "set"
    #: Read in order; rendered as a numbered list.
    CHAIN = "chain"


class ThreadMember(BaseModel):
    """One page on a reading-path thread.

    Attributes:
        page: ``docs/``-relative page path, optionally with a ``#fragment``.
        blurb: What the reader gets from the page, written for this thread; it
            need not match the page's ``description:``.
        label: The link text, when it should differ from the page's title (a
            link to one section of a page names the section).
    """

    model_config = ConfigDict(extra="forbid")

    page: Annotated[str, AfterValidator(_check_member_page)]
    blurb: NonEmptyString
    label: NonEmptyString | None = None

    @property
    def path(self) -> str:
        """The member's page, without its fragment."""
        return self.page.partition("#")[0]


class ThreadStage(BaseModel):
    """One stage of a thread: an unordered set or an ordered chain of pages.

    Attributes:
        title: The reader's goal at this stage, never a page type.
        kind: :attr:`StageKind.SET` or :attr:`StageKind.CHAIN`.
        stopping_point: The reader who only needed this far is done.
        framing: Prose shown under the stage's heading, before its pages; a
            link that is not a page lives here.
        members: The stage's pages, in reading order for a chain.
    """

    model_config = ConfigDict(extra="forbid")

    title: NonEmptyString
    kind: StageKind
    stopping_point: StrictBool = False
    framing: NonEmptyString | None = None
    members: Annotated[list[ThreadMember], Field(min_length=1)]


class ThreadDeclaration(BaseModel):
    """A start page's reading-path thread: its ordered stages (DF-11-013).

    Only the ``thread`` key is validated; the page's other frontmatter belongs
    to :class:`PageFrontmatter`.
    """

    thread: Annotated[list[ThreadStage], Field(min_length=1)]
