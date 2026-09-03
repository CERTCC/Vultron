"""MkDocs Material markdown renderer for ``docs/reference/messages/`` pages.

Produces shorthand↔wire-form mapping tables for the consolidated per-message-type
reference pages.  Each page covers one family of protocol messages; the tables
are rendered from the MSM mapping table (:mod:`vultron.metadata.msm._mapping`)
joined against ``SEMANTIC_REGISTRY``.

Usage (in a ``markdown-exec`` Python block)::

    from vultron.metadata.msm.render import render_page
    print(render_page("rm"))

Page slugs correspond to filenames under ``docs/reference/messages/``:
``rm``, ``em``, ``cs``, ``general``, ``faults_and_acknowledgements``,
``case_management``, ``case_proposal``, ``ledger_replication``.

Column semantics:

- **Shorthand(s)**: formal protocol shorthand symbol(s) from the 28-message
  set, or ``—`` when the wire activity has no formal counterpart.
- **`MessageSemantics`**: the ``SEMANTIC_REGISTRY`` key used for dispatch.
- **Wire Form**: ActivityStreams 2.0 verb+object(±qualifier) derived from the
  entry's :class:`~vultron.wire.as2.extractor.ActivityPattern`.
- **Discriminator**: the payload field that distinguishes shorthands in a
  collapse mapping, or ``—`` for direct/expansion/none rows.
- **Status**: one of ``direct``, ``collapse``, ``expansion``,
  ``evolved``, or ``none`` (MSM-06-003).

The *many-to-many* relationship is expressed as follows:

- A shorthand appearing in **multiple rows** is an expansion (one shorthand,
  many wire forms — e.g. ``GI`` or ``EP``).
- **Multiple shorthands in one row** is a collapse (many shorthands, one wire
  form — e.g. ``CP CX CA`` → ``Add(CaseStatus)``).
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

from vultron.metadata.msm._mapping import (
    PAGE_ROWS,
    PAGE_SLUGS,
    MappingStatus,
    RowSpec,
)
from vultron.semantic_registry import SEMANTIC_REGISTRY
from vultron.semantic_registry._entry import SemanticEntry
from vultron.wire.as2.extractor._pattern import ActivityPattern

# ---------------------------------------------------------------------------
# Internal fast-lookup: MessageSemantics → SemanticEntry.
# ---------------------------------------------------------------------------

_ENTRY_MAP: dict = {e.semantics: e for e in SEMANTIC_REGISTRY}

# ---------------------------------------------------------------------------
# Wire form string extraction from ActivityPattern.
# ---------------------------------------------------------------------------

# Page titles shown in rendered output.
_PAGE_TITLES: dict[str, str] = {
    "rm": "Report Management (RM) Messages",
    "em": "Embargo Management (EM) Messages",
    "cs": "Case State (CS) Messages",
    "general": "General (GI) Messages",
    "faults_and_acknowledgements": "Fault and Acknowledgement Mechanisms",
    "case_management": "Case Management Wire Activities",
    "case_proposal": "Case Proposal Wire Activities",
    "ledger_replication": "Ledger Replication Wire Activities",
}


def _type_name(value: object) -> str:
    """Return the human-readable type name from a ``VOtype``, ``AOtype``, or
    ``TAtype`` / ``IAtype`` enum value.

    All four enums are ``StrEnum``; their string representation is the value
    (e.g. ``"VulnerabilityReport"``, ``"Create"``).
    """
    return str(value)


def _format_pattern(pattern: ActivityPattern) -> str:
    """Render *pattern* as a compact wire-form string.

    Examples::

        Offer(VulnerabilityReport)
        Accept(Invite(Event)[context=VulnerabilityCase])
        Add(CaseStatus)[target=VulnerabilityCase]
    """
    act = _type_name(pattern.activity_)
    parts: list[str] = []

    if pattern.object_ is not None:
        if isinstance(pattern.object_, ActivityPattern):
            parts.append(f"({_format_pattern(pattern.object_)})")
        else:
            parts.append(f"({_type_name(pattern.object_)})")

    qualifiers: list[str] = []
    if pattern.target_ is not None:
        if isinstance(pattern.target_, ActivityPattern):
            qualifiers.append(f"target={_format_pattern(pattern.target_)}")
        else:
            qualifiers.append(f"target={_type_name(pattern.target_)}")
    if pattern.context_ is not None:
        if isinstance(pattern.context_, ActivityPattern):
            qualifiers.append(f"context={_format_pattern(pattern.context_)}")
        else:
            qualifiers.append(f"context={_type_name(pattern.context_)}")

    qualifier_str = "[" + ", ".join(qualifiers) + "]" if qualifiers else ""
    return act + "".join(parts) + qualifier_str


def _wire_form(entry: SemanticEntry) -> str:
    """Return the wire form string for *entry*, or ``—`` if no pattern."""
    if entry.pattern is None:
        return "—"
    return f"`{_format_pattern(entry.pattern)}`"


# ---------------------------------------------------------------------------
# Status badge.
# ---------------------------------------------------------------------------

_STATUS_LABELS: dict[MappingStatus, str] = {
    MappingStatus.DIRECT: "direct",
    MappingStatus.COLLAPSE: "collapse",
    MappingStatus.EXPANSION: "expansion",
    MappingStatus.EVOLVED: "evolved",
    MappingStatus.NONE: "—",
}


def _status_cell(status: MappingStatus) -> str:
    return _STATUS_LABELS[status]


# ---------------------------------------------------------------------------
# Table row rendering.
# ---------------------------------------------------------------------------


def _shorthand_cell(row: RowSpec) -> str:
    if not row.shorthands:
        return "—"
    return " ".join(f"`{s}`" for s in row.shorthands)


def _render_table_row(row: RowSpec) -> str:
    entry: SemanticEntry | None = _ENTRY_MAP.get(row.semantics)
    if entry is None:
        wire = "—"
    else:
        wire = _wire_form(entry)

    shorthand = _shorthand_cell(row)
    semantics_cell = f"`{row.semantics.name}`"
    discriminator = f"`{row.discriminator}`" if row.discriminator else "—"
    status = _status_cell(row.status)

    # Escape pipe chars inside cells
    wire = wire.replace("|", "&#124;")
    return f"| {shorthand} | {semantics_cell} | {wire} | {discriminator} | {status} |"


def _render_table(rows: tuple[RowSpec, ...]) -> str:
    lines: list[str] = [
        "| Shorthand(s) | `MessageSemantics` | Wire Form | Discriminator | Status |",
        "|---|---|---|---|---|",
    ]
    for row in rows:
        lines.append(_render_table_row(row))
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Public API.
# ---------------------------------------------------------------------------


def render_page(slug: str) -> str:
    """Render the mapping table for *slug* as MkDocs Material markdown.

    Args:
        slug: Page slug from :data:`~vultron.metadata.msm._mapping.PAGE_SLUGS`
            (e.g. ``"rm"``, ``"em"``, ``"cs"``).

    Returns:
        A markdown string containing a heading and a mapping table, ready for
        embedding via ``markdown-exec``.

    Raises:
        ValueError: When *slug* is not a known page.
    """
    if slug not in PAGE_ROWS:
        valid = ", ".join(PAGE_SLUGS)
        raise ValueError(f"Unknown page slug {slug!r}. Valid slugs: {valid}")

    title = _PAGE_TITLES.get(slug, slug.replace("_", " ").title())
    rows = PAGE_ROWS[slug]
    table = _render_table(rows)

    lines = [
        f"## {title}",
        "",
        table,
    ]
    return "\n".join(lines)


__all__ = ["render_page", "PAGE_SLUGS", "_format_pattern", "_wire_form"]
