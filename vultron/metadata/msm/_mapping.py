"""MSM mapping facts derived from the occasions on ``SEMANTIC_REGISTRY``.

Each ``SemanticEntry`` declares its occasions and its message page (ADR-0128).
This module derives what the occasions already say, so nothing here is typed
by hand:

- the mapping status of an entry (MSM-06-003, MSM-08-006);
- the "Distinguished by" value of an occasion, the field value or state
  context that tells it apart from its entry's other occasions;
- the "Sent by" value of an occasion, from the sender entitlement its received
  use case declares (MSM-08-005).

:class:`RowSpec` is the derived view of one entry that the MSM-06-002 ratchet
reads.
"""

#  Copyright (c) 2026 Carnegie Mellon University and Contributors.
#  - see Contributors.md for a full list of Contributors
#  - see ContributionInstructions.md for information on how you can Contribute to this project
#  Vultron Multiparty Coordinated Vulnerability Disclosure Protocol Prototype is
#  licensed under a MIT (SEI)-style license, please see LICENSE.md distributed
#  with this Software or contact permission@sei.cmu.edu for full terms.
#  Created, in part, with funding and support from the United States Government
#  (see Acknowledgments file). This program may include and/or can make use of
#  certain third party source code, object code, documentation and other files
#  ("Third Party Software"). See LICENSE.md for more details.
#  Carnegie Mellon®, CERT® and CERT Coordination Center® are registered in the
#  U.S. Patent and Trademark Office by Carnegie Mellon University

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Annotated, Final, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from vultron.core.behaviors.sender_entitlement import (
    SenderEntitlementKind,
    SenderExemption,
)
from vultron.core.models.events.base import MessageSemantics
from vultron.metadata.base import repo_root
from vultron.metadata.file_loading import (
    display_path,
    loads_yaml,
    read_utf8,
    validate,
    yaml_node_positions,
)
from vultron.primitives import NonEmptyString
from vultron.semantic_registry import SEMANTIC_REGISTRY
from vultron.semantic_registry._entry import (
    DISPATCHER_FALLBACKS,
    SemanticEntry,
)
from vultron.semantic_registry._occasion import (
    ANCHOR_PATTERN,
    FieldValue,
    MessagePage,
    Occasion,
    ProtocolShorthand,
    StateContext,
)
from vultron.wire.as2.extractor._pattern import ActivityPattern


class MappingStatus(StrEnum):
    """How a protocol shorthand relates to a ``SEMANTIC_REGISTRY`` entry."""

    DIRECT = "direct"
    """One shorthand maps to exactly one semantics value."""
    COLLAPSE = "collapse"
    """Several shorthands share one wire form, told apart by a distinguisher."""
    EXPANSION = "expansion"
    """One shorthand expands across several wire forms."""
    EVOLVED = "evolved"
    """The shorthand's purpose is served by a mechanism on a different axis."""
    NONE = "none"
    """No formal protocol shorthand; wire activity with no formal counterpart."""


#: Dispatcher fallbacks: no page, no occasion (MSM-06-002).
EXEMPTED_SEMANTICS: frozenset[MessageSemantics] = DISPATCHER_FALLBACKS

#: All known page slugs, in canonical display order.
PAGE_SLUGS: tuple[str, ...] = tuple(page.value for page in MessagePage)


# ---------------------------------------------------------------------------
# Mapping status (MSM-08-006).
# ---------------------------------------------------------------------------


def entry_shorthands(entry: SemanticEntry) -> tuple[ProtocolShorthand, ...]:
    """Return the distinct shorthands *entry*'s occasions carry, in order."""
    return tuple(
        dict.fromkeys(
            o.shorthand for o in entry.occasions if o.shorthand is not None
        )
    )


def mapping_status(
    entry: SemanticEntry, registry: Sequence[SemanticEntry]
) -> MappingStatus:
    """Derive *entry*'s mapping status from the occasions in *registry*.

    - ``evolved`` when an occasion declares an evolved mechanism (MSM-05),
      which has no shorthand to count;
    - ``none`` when no occasion carries a shorthand;
    - ``collapse`` when the occasions carry several distinct shorthands;
    - ``expansion`` when its one shorthand is also carried by another entry;
    - ``direct`` otherwise, including several occasions sharing one shorthand.

    Args:
        entry: The entry to classify.
        registry: Every entry, so a shorthand spread across entries is seen.

    Returns:
        The derived :class:`MappingStatus`.
    """
    if any(o.evolved for o in entry.occasions):
        return MappingStatus.EVOLVED
    shorthands = entry_shorthands(entry)
    if not shorthands:
        return MappingStatus.NONE
    if len(shorthands) > 1:
        return MappingStatus.COLLAPSE
    shorthand = next(iter(shorthands))
    if shorthand_is_shared(shorthand, registry):
        return MappingStatus.EXPANSION
    return MappingStatus.DIRECT


# ---------------------------------------------------------------------------
# "Sent by" (MSM-08-005).
# ---------------------------------------------------------------------------

#: The "Sent by" wording per entitlement kind, from
#: ``notes/message-type-reference.md`` § "Planning decisions (#4418)".
#: ``NAMED_ACTOR`` is worded from the answered request; see :func:`sent_by`.
SENT_BY_WORDING: dict[SenderEntitlementKind, str] = {
    SenderEntitlementKind.CASE_MANAGER: "the case manager",
    SenderEntitlementKind.CASE_OWNER: "the case owner",
    SenderEntitlementKind.ACTIVE_PARTICIPANT: "an active participant",
    SenderEntitlementKind.INVITEE: "the invitee",
    SenderEntitlementKind.EXECUTING_ACTOR: "the receiving actor itself",
    SenderEntitlementKind.ANY_ACTOR: "any actor",
}

#: The "Sent by" wording for a use case whose sender is not yet checked.
NOT_YET_CHECKED = "not yet checked"


def _words(type_name: str) -> str:
    """``"CaseProposal"`` → ``"case proposal"``."""
    return " ".join(re.findall(r"[A-Z][a-z0-9]*", type_name)).lower()


def answered_request(entry: SemanticEntry) -> str:
    """Name the request *entry*'s activity answers, from its object type.

    ``Accept(CaseProposal)`` answers a case proposal; for a nested pattern
    such as ``Accept(Offer(VulnerabilityCase))`` the request is the inner
    object, a vulnerability case.

    Raises:
        ValueError: When the entry's pattern names no object type.
    """
    pattern = entry.pattern
    obj = None if pattern is None else pattern.object_
    if isinstance(obj, ActivityPattern):
        obj = obj.object_
    if obj is None or isinstance(obj, ActivityPattern):
        raise ValueError(
            f"{entry.semantics.name}: the pattern names no object type to"
            " word an addressee from (MSM-08-005)"
        )
    return _words(str(obj))


def sent_by(entry: SemanticEntry, occasion: Occasion) -> str:
    """Derive the "Sent by" value of *occasion* on *entry* (MSM-08-005).

    The value is the wording of the sender entitlement that the entry's
    received use case declares, or :data:`NOT_YET_CHECKED` for an exemption.
    The occasion's usual sender roles, when it has any, follow in
    parentheses: "an active participant (usually: vendor)".

    Raises:
        ValueError: When the use case declares no sender entitlement.
    """
    declared = getattr(entry.use_case_class, "sender_entitlement", None)
    if isinstance(declared, SenderExemption):
        wording = NOT_YET_CHECKED
    elif declared is SenderEntitlementKind.NAMED_ACTOR:
        wording = f"the addressee of the {answered_request(entry)}"
    elif isinstance(declared, SenderEntitlementKind):
        wording = SENT_BY_WORDING[declared]
    else:
        raise ValueError(
            f"{entry.use_case_class.__name__} declares no sender_entitlement"
            " (HP-01-007)"
        )
    if not occasion.usual_senders:
        return wording
    usual = ", ".join(
        role.value.replace("_", " ") for role in occasion.usual_senders
    )
    return f"{wording} (usually: {usual})"


# ---------------------------------------------------------------------------
# Section heading and details link text (MSM-08-008).
# ---------------------------------------------------------------------------


def shorthand_is_shared(
    shorthand: ProtocolShorthand, registry: Sequence[SemanticEntry]
) -> bool:
    """Return whether more than one entry in *registry* carries *shorthand*.

    A shared shorthand is an expansion (``GI``, and ``RV``, ``RI`` and ``RC``,
    which the Full-Case Invite replies carry too), so it names no one
    occasion.
    """
    carriers = sum(
        1 for entry in registry if shorthand in entry_shorthands(entry)
    )
    return carriers > 1


def section_heading(
    occasion: Occasion, registry: Sequence[SemanticEntry]
) -> str:
    """Return the heading of *occasion*'s section, which its link text reuses.

    An occasion whose shorthand no other entry carries is headed by the formal
    message and its shorthand, "Fix Readiness (CF)".  Any other occasion is
    headed by its declared plain-English heading (MSM-08-008, DF-09-010).

    Raises:
        ValueError: When an occasion that needs a declared heading has none,
            or one headed by its formal name declares one anyway, which would
            be prose that renders nowhere.
    """
    shorthand = occasion.shorthand
    if shorthand is None or shorthand_is_shared(shorthand, registry):
        if occasion.heading is None:
            raise ValueError(
                f"occasion {occasion.anchor!r} has no shorthand of its own,"
                " so it needs a plain-English heading (MSM-08-008)"
            )
        return occasion.heading
    if occasion.heading is not None:
        raise ValueError(
            f"occasion {occasion.anchor!r} is headed by its formal name"
            f" {shorthand.formal_name!r}, so its declared heading"
            f" {occasion.heading!r} would render nowhere (MSM-08-008)"
        )
    return f"{shorthand.formal_name} ({shorthand.value})"


def distinguished_by(occasion: Occasion) -> str | None:
    """Render what tells *occasion* apart, as markdown, or ``None``.

    A field value reads "`vf_state` = `VF`"; a state context reads
    "EM state `NONE` or `PROPOSED`".  Enum members are named, not valued,
    because a composite state such as ``CS_pxa.Pxa`` has no scalar value.
    """
    d = occasion.distinguisher
    if isinstance(d, FieldValue):
        return f"`{d.field}` = `{d.value.name}`"
    if isinstance(d, StateContext):
        states = " or ".join(f"`{state.name}`" for state in d.states)
        return f"{d.machine.__name__} state {states}"
    return None


# ---------------------------------------------------------------------------
# Derived rows.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RowSpec:
    """The mapping-table row of one ``SEMANTIC_REGISTRY`` entry, all derived.

    Attributes:
        semantics: The ``MessageSemantics`` enum value.
        page: Primary page slug under ``docs/reference/messages/``.
        shorthands: The distinct shorthands the entry's occasions carry.
        status: How the shorthands relate to this wire form.
    """

    semantics: MessageSemantics
    page: str
    shorthands: tuple[str, ...]
    status: MappingStatus


def row_for(
    entry: SemanticEntry, registry: Sequence[SemanticEntry]
) -> RowSpec:
    """Derive the :class:`RowSpec` of *entry* (a non-fallback entry).

    Raises:
        ValueError: When *entry* is a dispatcher fallback, which owns no page.
    """
    if entry.page is None:
        raise ValueError(
            f"{entry.semantics.name} is a dispatcher fallback and has no row"
        )
    return RowSpec(
        semantics=entry.semantics,
        page=entry.page.value,
        shorthands=tuple(s.value for s in entry_shorthands(entry)),
        status=mapping_status(entry, registry),
    )


#: One derived row per non-fallback ``SEMANTIC_REGISTRY`` entry, grouped by
#: page in :data:`PAGE_SLUGS` order and in registry order within a page.
ROW_SPECS: tuple[RowSpec, ...] = tuple(
    sorted(
        (
            row_for(e, SEMANTIC_REGISTRY)
            for e in SEMANTIC_REGISTRY
            if e.semantics not in EXEMPTED_SEMANTICS
        ),
        key=lambda row: PAGE_SLUGS.index(row.page),
    )
)

#: Mapping from ``MessageSemantics`` → ``RowSpec`` for O(1) lookup.
SEMANTICS_TO_ROW: dict[MessageSemantics, RowSpec] = {
    row.semantics: row for row in ROW_SPECS
}


# ---------------------------------------------------------------------------
# The occasion table: the committed YAML projection (ADR-0128).
# ---------------------------------------------------------------------------

#: The committed, generated occasion table.  Internal: publishing it as an
#: interface belongs to protocol versioning (#2959).
OCCASION_TABLE_PATH: Path = Path(__file__).with_name("occasions.yaml")

#: The occasion table's format version, written into the file from the start
#: so that a later reader can tell the shapes apart.  Version 2 replaced each
#: row's declared ``howto`` link with the derived ``seen_in`` pages (#4432).
OCCASION_TABLE_FORMAT_VERSION: Final = 2

_ANCHOR = Annotated[str, Field(pattern=ANCHOR_PATTERN)]
_RECORD = ConfigDict(frozen=True, extra="forbid")


class PageLink(BaseModel):
    """A ``docs/`` page that embeds an occasion, with its page title.

    Attributes:
        path: The page, relative to ``docs/``.
        title: The page's H1, the text a link to it carries.
    """

    model_config = _RECORD

    path: NonEmptyString
    title: NonEmptyString


class OccasionRow(BaseModel):
    """One occasion as the table and its section render it; all derived.

    Attributes:
        anchor: The section anchor on the group's message page.
        heading: The section heading, which the details link text reuses
            (MSM-08-008).
        when: The sender's situation, completing "When…".
        send: The wire summary, rendered from the entry's ``ActivityPattern``.
        sent_by: The "Sent by" value (MSM-08-005).
        distinguished_by: What tells the occasion apart, as markdown.
        semantics: The ``SEMANTIC_REGISTRY`` entry the occasion belongs to.
        shorthand: The formal protocol message it carries, if any.
        status: The entry's mapping status (MSM-06-003).
        description: What the activity does.
        notes: Further prose for the section.
        seen_in: The published pages outside the message pages that embed
            the occasion, derived from their include directives, in path
            order.
        example: The ``vocab_examples`` function that builds its example.
    """

    model_config = _RECORD

    anchor: _ANCHOR
    heading: NonEmptyString
    when: NonEmptyString
    send: NonEmptyString
    sent_by: NonEmptyString
    distinguished_by: NonEmptyString | None = None
    semantics: MessageSemantics
    shorthand: ProtocolShorthand | None = None
    status: MappingStatus
    description: NonEmptyString
    notes: NonEmptyString | None = None
    seen_in: tuple[PageLink, ...] = ()
    example: NonEmptyString


class OccasionGroup(BaseModel):
    """The occasions of one message page, in registry (dispatch) order.

    Attributes:
        page: The message page the occasions' sections live on.
        title: The group's title in the whole table.
        mechanics: ``True`` for protocol mechanics, which follow the case
            lifecycle groups.
        occasions: The group's rows.
    """

    model_config = _RECORD

    page: MessagePage
    title: NonEmptyString
    mechanics: bool
    occasions: tuple[OccasionRow, ...] = Field(min_length=1)


class OccasionTable(BaseModel):
    """The whole occasion table, as committed in :data:`OCCASION_TABLE_PATH`.

    Validation fails when a page has two groups, an anchor is not unique
    (MSM-08-004), or the lifecycle groups do not all precede the mechanics.
    """

    model_config = _RECORD

    format_version: Literal[2]
    groups: tuple[OccasionGroup, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _pages_and_anchors_are_unique(self) -> OccasionTable:
        problems: list[str] = []
        pages = Counter(group.page for group in self.groups)
        problems.extend(
            f"page {page.value!r} has {count} groups"
            for page, count in pages.items()
            if count > 1
        )
        anchors = Counter(
            row.anchor for group in self.groups for row in group.occasions
        )
        problems.extend(
            f"anchor {anchor!r} is used {count} times (MSM-08-004)"
            for anchor, count in anchors.items()
            if count > 1
        )
        kinds = [group.mechanics for group in self.groups]
        if kinds != sorted(kinds):
            problems.append(
                "a lifecycle group follows a protocol-mechanics group"
            )
        if problems:
            raise ValueError("; ".join(problems))
        return self


def load_occasion_table(
    path: Path = OCCASION_TABLE_PATH, *, root: Path | None = None
) -> OccasionTable:
    """Load and validate the occasion table YAML at *path* (MS-17).

    Args:
        path: The YAML file; defaults to the committed table.
        root: Root the displayed path is made relative to; defaults to the
            repository root.

    Raises:
        MetadataLoadError: When the file does not parse or does not
            validate, naming ``path:line:col`` of the fault (a check across
            the whole table, such as a duplicate anchor, names the path).
        FileNotFoundError: When *path* does not exist.
    """
    shown_root = repo_root(Path(__file__).parent) if root is None else root
    shown = display_path(path, shown_root)
    text = read_utf8(path, shown)
    return validate(
        OccasionTable,
        loads_yaml(text, Path(shown)),
        path=path,
        root=shown_root,
        prefix="invalid occasion table",
        positions=yaml_node_positions(text),
    )
