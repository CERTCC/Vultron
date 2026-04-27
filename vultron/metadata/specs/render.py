"""Context generation tool for the spec registry.

Provides a markdown renderer and a JSON exporter for agent/human consumption.

Context generation requirements: specs/spec-registry.md SR-07.

Usage::

    from pathlib import Path
    from vultron.metadata.specs import load_registry
    from vultron.metadata.specs.render import render_markdown, export_json

    registry = load_registry(Path("specs/"))
    md = render_markdown(registry.files[0])
    js = export_json(registry)
"""

from __future__ import annotations

import json
from pathlib import Path

from vultron.metadata.specs.registry import SpecRegistry, load_registry
from vultron.metadata.specs.schema import BehavioralSpec, Spec, SpecFile


def _priority_line(spec: Spec) -> str:
    # Use RFC 2119 keyword inline in the statement per meta-specifications.md
    return f"- `{spec.id}` {spec.statement}"


def render_markdown(spec_file: SpecFile) -> str:
    """Render a single SpecFile as a Markdown string (SR-07-002, SR-07-004).

    The output follows the ``meta-specifications.md`` style guide:
    one requirement per bullet, grouped by category, RFC 2119 keyword inline.
    """
    lines: list[str] = []
    lines.append(f"# {spec_file.title}")
    lines.append("")
    lines.append("## Overview")
    lines.append("")
    lines.append(spec_file.description)
    lines.append("")
    lines.append(f"**Version**: {spec_file.version}")
    lines.append("")
    lines.append("---")
    lines.append("")

    for group in spec_file.groups:
        lines.append(f"## {group.title}")
        lines.append("")
        if group.description:
            lines.append(group.description)
            lines.append("")
        for spec in group.specs:
            lines.append(_priority_line(spec))
            if spec.rationale:
                lines.append(f"  - *Rationale*: {spec.rationale}")
            if isinstance(spec, BehavioralSpec):
                if spec.preconditions:
                    for pre in spec.preconditions:
                        lines.append(f"  - *Precondition*: {pre.description}")
                for step in spec.steps:
                    lines.append(
                        f"  - *Step {step.order}* [{step.actor}]: {step.action}"
                    )
                    if step.expected:
                        lines.append(f"    - *Expected*: {step.expected}")
                if spec.postconditions:
                    for post in spec.postconditions:
                        lines.append(
                            f"  - *Postcondition*: {post.description}"
                        )
            for rel in spec.relationships:
                note = f" ({rel.note})" if rel.note else ""
                lines.append(
                    f"  - {spec.id} {rel.rel_type.value} {rel.spec_id}{note}"
                )
        lines.append("")

    return "\n".join(lines)


def export_json(
    registry: SpecRegistry,
    *,
    kind: str | None = None,
    scope: str | None = None,
    tags: list[str] | None = None,
    priority: str | None = None,
) -> str:
    """Serialize the registry (or a filtered subset) to JSON (SR-07-003,
    SR-07-005).

    Args:
        registry: The loaded SpecRegistry.
        kind: Filter to specs with this kind value (e.g. ``"general"``).
        scope: Filter to specs whose scope list contains this value.
        tags: Filter to specs that have ALL of the given tags.
        priority: Filter to specs with this priority value (e.g. ``"MUST"``).

    Returns:
        A JSON string of the filtered spec index.
    """
    result = {}
    for spec_id, spec in registry.all_specs.items():
        if kind and spec.kind.value != kind:
            continue
        if scope and scope not in [s.value for s in spec.scope]:
            continue
        if tags and not all(t in [tg.value for tg in spec.tags] for t in tags):
            continue
        if priority and spec.priority.value != priority:
            continue
        result[spec_id] = spec.model_dump(mode="json")

    return json.dumps(result, indent=2)


def render_registry_markdown(registry: SpecRegistry) -> str:
    """Render all spec files in the registry as concatenated Markdown."""
    parts = [render_markdown(f) for f in registry.files]
    return "\n\n---\n\n".join(parts)


def main() -> None:
    """CLI entry point for context generation.

    Usage::

        python -m vultron.metadata.specs.render --format md specs/
        python -m vultron.metadata.specs.render --format json specs/
    """
    import sys

    fmt = "md"
    args = sys.argv[1:]
    if "--format" in args:
        idx = args.index("--format")
        fmt = args[idx + 1]
        args = args[:idx] + args[idx + 2 :]

    if not args:
        print(
            f"Usage: {sys.argv[0]} [--format md|json] <spec_dir>",
            file=sys.stderr,
        )
        sys.exit(2)

    spec_dir = Path(args[0])
    registry = load_registry(spec_dir)

    if fmt == "json":
        print(export_json(registry))
    else:
        print(render_registry_markdown(registry))


if __name__ == "__main__":
    main()
