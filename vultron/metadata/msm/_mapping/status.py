"""Mapping status, section headings and the per-entry row specs (MSM-06-002/003)."""

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

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum

from vultron.core.models.events.base import MessageSemantics
from vultron.semantic_registry import SEMANTIC_REGISTRY
from vultron.semantic_registry._entry import (
    DISPATCHER_FALLBACKS,
    SemanticEntry,
)
from vultron.semantic_registry._occasion import (
    MessagePage,
    Occasion,
    ProtocolShorthand,
)


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
