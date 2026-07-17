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

from vultron.metadata.specs.registry import SpecRegistry, load_registry
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

# Maps RFC2119 priority to a MkDocs Material badge string.
_PRIORITY_BADGE: dict[RFC2119Priority, str] = {
    RFC2119Priority.MUST: ":octicons-dot-fill-24:{ .must } **MUST**",
    RFC2119Priority.MUST_NOT: ":octicons-dot-fill-24:{ .must-not } **MUST NOT**",
    RFC2119Priority.SHOULD: ":octicons-dot-fill-24:{ .should } **SHOULD**",
    RFC2119Priority.SHOULD_NOT: ":octicons-dot-fill-24:{ .should-not } **SHOULD NOT**",
    RFC2119Priority.MAY: ":octicons-dot-fill-24:{ .may } **MAY**",
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


def _render_relationships(
    lines: list[str],
    spec: Spec,
    registry: SpecRegistry,
    current_kind: SpecKind,
) -> None:
    for rel in spec.relationships or []:
        label = _REL_LABEL.get(rel.rel_type, rel.rel_type.value)
        # Resolve target kind from registry if possible; fall back to current
        try:
            target_kind = registry.get_effective_kind(rel.spec_id)
        except KeyError:
            target = rel.spec_id
        else:
            target = _cross_link(rel.spec_id, target_kind, current_kind)
        note = f" — {rel.note}" if rel.note else ""
        lines.append(f"    - *{label}*: {target}{note}")


def _render_preconditions(lines: list[str], spec: BehavioralSpec) -> None:
    if not spec.preconditions:
        return
    lines.append("        **Preconditions**")
    lines.append("")
    for pc in spec.preconditions:
        lines.append(f"        - {pc.description}")
        if pc.rm_state:
            states = ", ".join(s.value for s in pc.rm_state)
            lines.append(f"          - RM state: `{states}`")
        if pc.em_state:
            states = ", ".join(s.value for s in pc.em_state)
            lines.append(f"          - EM state: `{states}`")
        if pc.role:
            roles = ", ".join(r.value for r in pc.role)
            lines.append(f"          - Role: `{roles}`")
        if pc.cs_pattern:
            lines.append(f"          - CS pattern: `{pc.cs_pattern}`")
    lines.append("")


def _render_steps(lines: list[str], spec: BehavioralSpec) -> None:
    if not spec.steps:
        return
    lines.append("        **Steps**")
    lines.append("")
    for step in spec.steps:
        expected = f" → {step.expected}" if step.expected else ""
        lines.append(
            f"        {step.order}. [{step.actor}] {step.action}{expected}"
        )
    lines.append("")


def _render_postconditions(lines: list[str], spec: BehavioralSpec) -> None:
    if not spec.postconditions:
        return
    lines.append("        **Postconditions**")
    lines.append("")
    for pc in spec.postconditions:
        lines.append(f"        - {pc.description}")
    lines.append("")


def _render_behavioral(lines: list[str], spec: BehavioralSpec) -> None:
    if not any([spec.preconditions, spec.steps, spec.postconditions]):
        return
    lines.append("")
    lines.append('    ??? details "ECA Details"')
    lines.append("")
    _render_preconditions(lines, spec)
    _render_steps(lines, spec)
    _render_postconditions(lines, spec)


def _is_behavioral_file(spec_file: SpecFile) -> bool:
    return any(
        isinstance(spec, BehavioralSpec)
        for group in spec_file.groups
        for spec in group.specs
    )


def _has_behavioral_tag(spec_file: SpecFile) -> bool:
    return SpecTag.BEHAVIORAL in (spec_file.tags or [])


def _render_spec(
    lines: list[str],
    spec: Spec,
    registry: SpecRegistry,
    current_kind: SpecKind,
) -> None:
    badge = _PRIORITY_BADGE[spec.priority]
    anchor = _spec_anchor(spec.id)
    lines.append(f'<a id="{anchor}"></a>')
    lines.append(f"- **`{spec.id}`** {badge} {spec.statement}")
    if spec.rationale:
        lines.append(f"    - *Rationale*: {spec.rationale}")
    if isinstance(spec, BehavioralSpec):
        _render_behavioral(lines, spec)
    _render_relationships(lines, spec, registry, current_kind)


def _render_group(
    lines: list[str],
    group: SpecGroup,
    registry: SpecRegistry,
    current_kind: SpecKind,
    heading: str = "###",
) -> None:
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
    for spec in group.specs:
        _render_spec(lines, spec, registry, current_kind)
    lines.append("")


def _render_file(
    lines: list[str],
    spec_file: SpecFile,
    registry: SpecRegistry,
    current_kind: SpecKind,
    is_behavioral_section: bool,
) -> None:
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
        _render_group(
            lines, group, registry, current_kind, heading=group_heading
        )


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

    matching = [f for f in registry.files if f.kind == target_kind]
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
