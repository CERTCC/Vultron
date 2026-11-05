"""Markdown rendering of a spec file and of the whole registry."""

from __future__ import annotations

from vultron.metadata.specs.registry import SpecRegistry
from vultron.metadata.specs.schema import (
    BehavioralSpec,
    Spec,
    SpecFile,
    SpecGroup,
)


def _priority_line(spec: Spec) -> str:
    # Use RFC 2119 keyword inline in the statement per meta-specifications.md
    return f"- `{spec.id}` {spec.statement}"


def _append_behavioral_markdown(
    lines: list[str], spec: BehavioralSpec
) -> None:
    for precondition in spec.preconditions or []:
        lines.append(f"  - *Precondition*: {precondition.description}")

    for step in spec.steps or []:
        lines.append(f"  - *Step {step.order}* [{step.actor}]: {step.action}")
        if step.expected:
            lines.append(f"    - *Expected*: {step.expected}")

    for postcondition in spec.postconditions or []:
        lines.append(f"  - *Postcondition*: {postcondition.description}")


def _append_relationship_markdown(lines: list[str], spec: Spec) -> None:
    for relationship in spec.relationships or []:
        note = f" ({relationship.note})" if relationship.note else ""
        lines.append(
            f"  - {spec.id} {relationship.rel_type.value} "
            f"{relationship.spec_id}{note}"
        )
    for entry in spec.see_also:
        lines.append(
            f"  - {spec.id} see also {entry.spec_id} ({entry.reason})"
        )


def _append_spec_markdown(lines: list[str], spec: Spec) -> None:
    lines.append(_priority_line(spec))
    lines.append(f"  - *Rationale*: {spec.rationale}")
    if isinstance(spec, BehavioralSpec):
        _append_behavioral_markdown(lines, spec)
    _append_relationship_markdown(lines, spec)


def _append_group_markdown(lines: list[str], group: SpecGroup) -> None:
    lines.append(f"## {group.title}")
    lines.append("")
    if group.description:
        lines.append(group.description)
        lines.append("")
    for spec in group.specs:
        _append_spec_markdown(lines, spec)
    lines.append("")


def render_markdown(spec_file: SpecFile) -> str:
    """Render a single SpecFile as a Markdown string (SR-07-002, SR-07-004).

    The output follows the ``meta-specifications.md`` style guide:
    one requirement per bullet, grouped by category, RFC 2119 keyword inline.
    """
    lines = [
        f"# {spec_file.title}",
        "",
        "## Overview",
        "",
        spec_file.description,
        "",
        "---",
        "",
    ]
    for group in spec_file.groups:
        _append_group_markdown(lines, group)
    return "\n".join(lines)


def render_registry_markdown(registry: SpecRegistry) -> str:
    """Render all spec files in the registry as concatenated Markdown."""
    parts = [render_markdown(f) for f in registry.files]
    return "\n\n---\n\n".join(parts)
