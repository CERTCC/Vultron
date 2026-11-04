"""The reader-facing page frontmatter: audience, level, page type and subject (DF-11)."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Annotated, Literal, get_args

from pydantic import (
    BaseModel,
    BeforeValidator,
)


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
#: never ``[ALL]`` and never a list naming every member (DF-11-027).
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
    whose links are a routing page's (DF-11-028) but whose prose mostly
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


class Subject(StrEnum):
    """Whether a reader-facing ``docs/`` page is about the protocol (DF-11-025).

    The protocol and CERT/CC's reference implementation never share a nav
    section (DF-11-020); this key is what lets ``docs-nav-subjects`` check it.
    A page's subject is what it is about, not who reads it: a page about the
    Trigger API is ``implementation`` however protocol-shaped its content is,
    and a tutorial that teaches protocol behavior on the reference
    implementation is ``protocol``.
    """

    #: The Vultron protocol: its specification, requirements, messages,
    #: models and design, binding on or explaining what binds any
    #: implementation.
    PROTOCOL = "protocol"
    #: CERT/CC's reference implementation: its code, demos, architecture and
    #: project record.
    IMPLEMENTATION = "implementation"
    #: Neither: CVD practice, research, routing and project pages, which may
    #: sit beside either.
    NEUTRAL = "neutral"


def _member_of(enum: type[StrEnum]) -> Callable[[object], object]:
    """A validator accepting only a bare string naming a member of *enum*."""
    permitted = [member.value for member in enum]

    def check(value: object) -> object:
        if value not in permitted:
            raise ValueError(f"must be one of {', '.join(permitted)}")
        return value

    return check


_check_page_type = _member_of(PageType)


_check_subject = _member_of(Subject)


def declared_subject(value: object) -> Subject | None:
    """The :class:`Subject` a raw frontmatter *value* names, or ``None``.

    For a check that reads ``subject`` but leaves an invalid or missing one to
    ``docs-frontmatter``, so one fault is not named by two tools. Accepts
    exactly what :class:`PageFrontmatter` accepts.
    """
    try:
        _check_subject(value)
    except ValueError:
        return None
    return Subject(str(value))


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
    """The declarations a reader-facing page makes (DF-11-001, DF-11-018,
    DF-11-025).

    Only the four declaration keys are validated; a page's other frontmatter
    (``title``, ``status``, and so on) belongs to other schemas.
    """

    page_type: Annotated[PageType, BeforeValidator(_check_page_type)]
    subject: Annotated[Subject, BeforeValidator(_check_subject)]
