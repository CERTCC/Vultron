"""MkDocs Material markdown renderer for ``docs/reference/specs/`` pages.

Produces rich reference pages (one per :class:`SpecKind`) from the loaded
:class:`SpecRegistry`.  Unlike ``render.py`` (agent/LLM export), this module
targets human readers via the published documentation site.

Usage (in a markdown-exec Python block)::

    from vultron.metadata.specs import load_registry
    from vultron.metadata.specs.docs_render import render_for_kind

    registry = load_registry()
    print(render_for_kind("domain", registry))
"""

from __future__ import annotations

from vultron.metadata.specs.registry import (
    SpecRegistry,
    effective_kind,
    load_registry,
)
from vultron.metadata.specs.schema import (
    BehavioralSpec,
    RFC2119Priority,
    RelationType,
    Spec,
    SpecFile,
    SpecGroup,
    SpecKind,
    SpecTag,
)

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
}

# SpecKind → URL slug for cross-kind anchor links
_KIND_SLUG: dict[SpecKind, str] = {
    SpecKind.GENERAL: "general",
    SpecKind.PATTERN: "pattern",
    SpecKind.DOMAIN: "domain",
    SpecKind.LANGUAGE: "language",
    SpecKind.IMPLEMENTATION: "implementation",
    SpecKind.DEV_PROCESS: "dev-process",
}


def _spec_anchor(spec_id: str) -> str:
    """Return MkDocs-compatible anchor for a spec ID (lower-cased, dashes)."""
    return spec_id.lower().replace("_", "-")


def _cross_link(
    spec_id: str, target_kind: SpecKind, current_kind: SpecKind
) -> str:
    """Return a markdown link to *spec_id* on the correct kind page."""
    anchor = _spec_anchor(spec_id)
    if target_kind == current_kind:
        return f"[{spec_id}](#{anchor})"
    slug = _KIND_SLUG[target_kind]
    return f"[{spec_id}](../{slug}/#{anchor})"


def _render_relationships_cell(
    spec: Spec,
    registry: SpecRegistry,
    current_kind: SpecKind,
) -> str:
    """Return the Related cell content for a spec table row."""
    if not spec.relationships:
        return ""
    parts = []
    for rel in spec.relationships:
        label = _REL_LABEL.get(rel.rel_type, rel.rel_type.value)
        try:
            target_kind = registry.get_effective_kind(rel.spec_id)
        except KeyError:
            target = rel.spec_id
        else:
            target = _cross_link(rel.spec_id, target_kind, current_kind)
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
    cell = spec.statement
    if spec.rationale:
        cell += f"<br><br>*{spec.rationale}*"
    if isinstance(spec, BehavioralSpec):
        eca = _render_behavioral_cell(spec)
        if eca:
            cell += "<br><br>" + eca
    return cell


def _render_spec_row(
    spec: Spec,
    registry: SpecRegistry,
    current_kind: SpecKind,
) -> str:
    """Return a single markdown table row for *spec*."""
    anchor = _spec_anchor(spec.id)
    id_cell = f'<a id="{anchor}"></a>`{spec.id}`'
    priority_cell = _PRIORITY_BADGE[spec.priority]
    requirement_cell = _render_requirement_cell(spec)
    related_cell = _render_relationships_cell(spec, registry, current_kind)
    # Escape pipe chars inside cells to avoid breaking the table
    requirement_cell = requirement_cell.replace("|", "&#124;")
    related_cell = related_cell.replace("|", "&#124;")
    return f"| {id_cell} | {priority_cell} | {requirement_cell} | {related_cell} |"


def _render_group(
    lines: list[str],
    group: SpecGroup,
    registry: SpecRegistry,
    current_kind: SpecKind,
    heading: str = "###",
    specs: list[Spec] | None = None,
) -> None:
    """Render *group* to *lines*.

    When *specs* is provided only those specs are rendered (used to suppress
    items whose effective kind does not match *current_kind* — SR-09-002).
    When *specs* is ``None`` all items in the group are rendered.
    """
    visible = specs if specs is not None else group.specs
    anchor = _spec_anchor(group.id)
    lines.append(f"{heading} {group.title} {{#{anchor}}}")
    lines.append("")
    if group.description:
        lines.append(group.description)
        lines.append("")
    if group.trigger:
        trigger_type = group.trigger.type.value.replace("_", " ").title()
        lines.append(f"*Trigger*: {trigger_type} — `{group.trigger.value}`")
        lines.append("")
    # Table header
    lines.append("| ID | Priority | Requirement | Related |")
    lines.append("|---|---|---|---|")
    for spec in visible:
        lines.append(_render_spec_row(spec, registry, current_kind))
    lines.append("")


def _render_file(
    lines: list[str],
    spec_file: SpecFile,
    registry: SpecRegistry,
    current_kind: SpecKind,
    is_behavioral_section: bool,
) -> None:
    """Render *spec_file* groups that have at least one item matching
    *current_kind* (SR-09-001, SR-09-002).

    Groups are routed by their effective kind resolved via ``effective_kind()``.
    Mixed-kind groups appear here only when they contain at least one item whose
    effective kind matches *current_kind*; non-matching items are suppressed.
    """
    anchor = spec_file.id.lower()
    if is_behavioral_section:
        lines.append(f"### {spec_file.title} {{#{anchor}}}")
        group_heading = "####"
    else:
        lines.append(f"## {spec_file.title} {{#{anchor}}}")
        group_heading = "###"
    lines.append("")
    lines.append(spec_file.description)
    lines.append("")
    lines.append(
        f"*File ID*: `{spec_file.id}` | " f"*Version*: {spec_file.version}"
    )
    lines.append("")
    for group in spec_file.groups:
        # Collect items whose effective kind matches current_kind.
        matching_specs = [
            spec
            for spec in group.specs
            if effective_kind(spec, group, spec_file) == current_kind
        ]
        if not matching_specs:
            continue
        _render_group(
            lines,
            group,
            registry,
            current_kind,
            heading=group_heading,
            specs=matching_specs,
        )


def _is_behavioral_file(spec_file: SpecFile) -> bool:
    return any(
        isinstance(spec, BehavioralSpec)
        for group in spec_file.groups
        for spec in group.specs
    )


def _has_behavioral_tag(spec_file: SpecFile) -> bool:
    return SpecTag.BEHAVIORAL in (spec_file.tags or [])


def render_for_kind(kind: str, registry: SpecRegistry) -> str:
    """Render all spec files matching *kind* as rich MkDocs Material markdown.

    Args:
        kind: A :class:`SpecKind` string value (e.g. ``"domain"``).
        registry: A loaded :class:`SpecRegistry`.

    Returns:
        A markdown string ready for embedding via markdown-exec.

    Raises:
        ValueError: If no spec files have this kind in the registry.
    """
    try:
        target_kind = SpecKind(kind)
    except ValueError:
        valid = [k.value for k in SpecKind]
        raise ValueError(f"Unknown SpecKind: {kind!r}. Valid values: {valid}")

    # Route by effective kind: a file contributes to this page when it has at
    # least one item whose effective kind matches target_kind (SR-09-001).
    matching = [
        f
        for f in registry.files
        if any(
            effective_kind(spec, group, f) == target_kind
            for group in f.groups
            for spec in group.specs
        )
    ]
    if not matching:
        raise ValueError(
            f"No spec files with kind={kind!r} found in registry. "
            "Add a new docs page when you add a new SpecKind."
        )

    lines: list[str] = []

    # Separate behavioral files (tagged or containing BehavioralSpec items)
    regular: list[SpecFile] = []
    behavioral: list[SpecFile] = []
    for sf in matching:
        if _has_behavioral_tag(sf) or _is_behavioral_file(sf):
            behavioral.append(sf)
        else:
            regular.append(sf)

    for sf in regular:
        _render_file(
            lines, sf, registry, target_kind, is_behavioral_section=False
        )

    if behavioral:
        lines.append("## Behavioral Specifications")
        lines.append("")
        lines.append(
            "The following specifications define Event-Condition-Action (ECA) "
            "behavioral requirements with typed preconditions, ordered steps, "
            "and postconditions."
        )
        lines.append("")
        for sf in behavioral:
            _render_file(
                lines, sf, registry, target_kind, is_behavioral_section=True
            )

    return "\n".join(lines)


__all__ = ["render_for_kind", "load_registry"]
