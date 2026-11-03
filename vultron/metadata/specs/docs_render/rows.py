"""One requirement's table row for the docs site, and the cells it is built
from.
"""

from __future__ import annotations

from collections.abc import Callable

from vultron.metadata.docs.requirement_catalog import requirement_anchor
from vultron.metadata.specs.schema import (
    BehavioralSpec,
    RelationType,
    RFC2119Priority,
    Spec,
)

#: Maps a requirement ID to the link target its row shows on the page being
#: rendered, or ``None`` when the ID names no requirement.
RequirementHref = Callable[[str], str | None]

# Maps RFC2119 priority to a distinct Material icon + bold label.
# Icons are chosen to convey the strength of the obligation at a glance.
_PRIORITY_BADGE: dict[RFC2119Priority, str] = {
    RFC2119Priority.MUST: ":material-check-all: **MUST**",
    RFC2119Priority.MUST_NOT: ":material-cancel: **MUST NOT**",
    RFC2119Priority.SHOULD: ":material-check: **SHOULD**",
    RFC2119Priority.SHOULD_NOT: ":material-alert-outline: **SHOULD NOT**",
    RFC2119Priority.MAY: ":material-information-outline: **MAY**",
}

# Relationship type label → human-readable prefix
_REL_LABEL: dict[RelationType, str] = {
    RelationType.IMPLEMENTS: "Implements",
    RelationType.SUPERSEDES: "Supersedes",
    RelationType.EXTENDS: "Extends",
    RelationType.DEPENDS_ON: "Depends on",
    RelationType.CONFLICTS: "Conflicts with",
    RelationType.REFINES: "Refines",
    RelationType.DERIVES_FROM: "Derives from",
    RelationType.VERIFIES: "Verifies",
    RelationType.PART_OF: "Part of",
    RelationType.CONSTRAINS: "Constrains",
    RelationType.SATISFIES: "Satisfies",
    RelationType.USES_DEFINITION: "Uses definition from",
}

#: Rendered in place of the requirement list for a kind no spec carries yet.
_EMPTY_KIND_NOTICE = (
    '!!! note "No requirements yet"\n\n'
    "    No requirement in the specification corpus carries "
    "`kind: {kind}` yet.\n"
)


_TABLE_HEADER = (
    "| ID | Priority | Requirement | Related |",
    "|---|---|---|---|",
)


def _render_relationships_cell(spec: Spec, href: RequirementHref) -> str:
    """Return the Related cell content for a spec table row."""
    if not spec.relationships:
        return ""
    parts = []
    for rel in spec.relationships:
        label = _REL_LABEL.get(rel.rel_type, rel.rel_type.value)
        target_href = href(rel.spec_id)
        target = (
            rel.spec_id
            if target_href is None
            else f"[{rel.spec_id}]({target_href})"
        )
        note = f" — {rel.note}" if rel.note else ""
        parts.append(f"*{label}*: {target}{note}")
    return "<br>".join(parts)


def _render_preconditions_lines(
    lines: list[str], spec: BehavioralSpec
) -> None:
    if not spec.preconditions:
        return
    lines.append("**Preconditions**")
    lines.append("")
    for pc in spec.preconditions:
        lines.append(f"- {pc.description}")
        if pc.rm_state:
            lines.append(
                f"    - RM state: `{', '.join(s.value for s in pc.rm_state)}`"
            )
        if pc.em_state:
            lines.append(
                f"    - EM state: `{', '.join(s.value for s in pc.em_state)}`"
            )
        if pc.role:
            lines.append(
                f"    - Role: `{', '.join(r.value for r in pc.role)}`"
            )
        if pc.cs_pattern:
            lines.append(f"    - CS pattern: `{pc.cs_pattern}`")
    lines.append("")


def _render_steps_lines(lines: list[str], spec: BehavioralSpec) -> None:
    if not spec.steps:
        return
    lines.append("**Steps**")
    lines.append("")
    for step in spec.steps:
        expected = f" → {step.expected}" if step.expected else ""
        lines.append(f"{step.order}. [{step.actor}] {step.action}{expected}")
    lines.append("")


def _render_postconditions_lines(
    lines: list[str], spec: BehavioralSpec
) -> None:
    if not spec.postconditions:
        return
    lines.append("**Postconditions**")
    lines.append("")
    for pc in spec.postconditions:
        lines.append(f"- {pc.description}")
    lines.append("")


def _render_behavioral_cell(spec: BehavioralSpec) -> str:
    """Return inline collapsible ECA details for embedding in a table cell."""
    if not any([spec.preconditions, spec.steps, spec.postconditions]):
        return ""
    lines: list[str] = []
    lines.append("<details><summary>ECA Details</summary>")
    lines.append("")
    _render_preconditions_lines(lines, spec)
    _render_steps_lines(lines, spec)
    _render_postconditions_lines(lines, spec)
    lines.append("</details>")
    return "<br>".join(lines)


def _render_requirement_cell(
    spec: Spec,
) -> str:
    """Return the Requirement cell content for a spec table row."""
    cell = f"{spec.statement}<br><br>*{spec.rationale}*"
    if isinstance(spec, BehavioralSpec):
        eca = _render_behavioral_cell(spec)
        if eca:
            cell += "<br><br>" + eca
    return cell


def render_requirement_row(
    spec: Spec, href: RequirementHref, *, define_anchor: bool
) -> str:
    """Return the requirement table row for *spec*.

    Every requirement row on the site comes from here: the per-kind pages,
    the Requirements Catalog and the callouts share one format (DF-12-003).

    Args:
        spec: The requirement.
        href: Link targets for the IDs the row names, on the page rendered.
        define_anchor: ``True`` for the row that is the requirement's anchor
            (a catalog or per-kind row); ``False`` for a callout row, whose
            ID cell links that anchor and defines none (DF-12-002).
    """
    if define_anchor:
        id_cell = f'<a id="{requirement_anchor(spec.id)}"></a>`{spec.id}`'
    else:
        id_href = href(spec.id)
        id_cell = (
            f"`{spec.id}`" if id_href is None else f"[`{spec.id}`]({id_href})"
        )
    priority_cell = _PRIORITY_BADGE[spec.priority]
    requirement_cell = _render_requirement_cell(spec)
    related_cell = _render_relationships_cell(spec, href)
    # Escape pipe chars inside cells to avoid breaking the table
    requirement_cell = requirement_cell.replace("|", "&#124;")
    related_cell = related_cell.replace("|", "&#124;")
    return f"| {id_cell} | {priority_cell} | {requirement_cell} | {related_cell} |"
