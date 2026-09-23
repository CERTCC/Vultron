"""Context generation tool for the spec registry.

Provides a markdown renderer, a JSON exporter, and a YAML exporter for
agent/human consumption.

Context generation requirements: specs/spec-registry.yaml SR-07.

Usage::

    from pathlib import Path
    from vultron.metadata.specs import load_registry
    from vultron.metadata.specs.render import render_markdown, export_json

    registry = load_registry(Path("specs/"))
    md = render_markdown(registry.files[0])
    js = export_json(registry)
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, NoReturn

from vultron.metadata.specs.llm_export import CROSS_CUTTING_TOPICS

from vultron.metadata.specs.registry import (
    SpecRegistry,
    load_registry,
)
from vultron.metadata.specs.schema import (
    BehavioralSpec,
    Spec,
    SpecFile,
    SpecGroup,
)

try:
    import yaml
except ImportError as exc:  # pragma: no cover
    raise ImportError(
        "pyyaml is required for YAML export. "
        "Install it with: pip install pyyaml"
    ) from exc


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


def _append_spec_markdown(lines: list[str], spec: Spec) -> None:
    lines.append(_priority_line(spec))
    if spec.rationale:
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
        f"**Version**: {spec_file.version}",
        "",
        "---",
        "",
    ]
    for group in spec_file.groups:
        _append_group_markdown(lines, group)
    return "\n".join(lines)


def _precondition_dict(pc: object) -> dict:
    d: dict = {}
    if pc.rm_state is not None:  # type: ignore[attr-defined]
        d["rm_state"] = [s.value for s in pc.rm_state]  # type: ignore[attr-defined]
    if pc.em_state is not None:  # type: ignore[attr-defined]
        d["em_state"] = [s.value for s in pc.em_state]  # type: ignore[attr-defined]
    if pc.role is not None:  # type: ignore[attr-defined]
        d["role"] = [r.value for r in pc.role]  # type: ignore[attr-defined]
    if pc.cs_pattern is not None:  # type: ignore[attr-defined]
        d["cs_pattern"] = pc.cs_pattern  # type: ignore[attr-defined]
    d["description"] = pc.description  # type: ignore[attr-defined]
    return d


def _add_behavioral_spec_fields(d: dict, spec: BehavioralSpec) -> None:
    authored_sequences = {
        "preconditions": [
            _precondition_dict(item) for item in spec.preconditions or []
        ],
        "steps": [_step_dict(item) for item in spec.steps or []],
        "postconditions": [
            {"description": item.description}
            for item in spec.postconditions or []
        ],
    }
    for field, value in authored_sequences.items():
        if value:
            d[field] = value


def _spec_to_dict(spec: Spec, group: SpecGroup, file: SpecFile) -> dict:
    """Serialize a spec to a dict with only authored (non-inherited) fields."""
    _ = group, file
    d: dict = {
        "id": spec.id,
        "priority": spec.priority.value,
        "statement": spec.statement,
    }
    authored_optional_fields = {
        "rationale": spec.rationale,
        "kind": spec.kind.value if spec.kind is not None else None,
        "scope": (
            [s.value for s in spec.scope] if spec.scope is not None else None
        ),
        "tags": (
            [t.value for t in spec.tags] if spec.tags is not None else None
        ),
        "relationships": (
            [_rel_dict(relationship) for relationship in spec.relationships]
            if spec.relationships
            else None
        ),
        "lint_suppress": (
            [warning.value for warning in spec.lint_suppress]
            if spec.lint_suppress
            else None
        ),
    }
    for field, value in authored_optional_fields.items():
        if value is not None:
            d[field] = value
    if not spec.testable:
        d["testable"] = False
    if isinstance(spec, BehavioralSpec):
        _add_behavioral_spec_fields(d, spec)
    return d


def _rel_dict(r: object) -> dict:
    d = {
        "rel_type": r.rel_type.value,  # type: ignore[attr-defined]
        "spec_id": r.spec_id,  # type: ignore[attr-defined]
    }
    if r.note is not None:  # type: ignore[attr-defined]
        d["note"] = r.note  # type: ignore[attr-defined]
    return d


def _step_dict(s: object) -> dict:
    d = {
        "order": s.order,  # type: ignore[attr-defined]
        "actor": s.actor,  # type: ignore[attr-defined]
        "action": s.action,  # type: ignore[attr-defined]
    }
    if s.expected is not None:  # type: ignore[attr-defined]
        d["expected"] = s.expected  # type: ignore[attr-defined]
    return d


def _group_to_dict(group: SpecGroup, file: SpecFile) -> dict:
    """Serialize a group to a dict with only authored fields."""
    d: dict = {"id": group.id, "title": group.title}
    if group.description is not None:
        d["description"] = group.description
    if group.scope is not None:
        d["scope"] = [s.value for s in group.scope]
    if group.trigger is not None:
        d["trigger"] = {
            "type": group.trigger.type.value,
            "value": group.trigger.value,
        }
    d["specs"] = [_spec_to_dict(s, group, file) for s in group.specs]
    return d


def _file_to_dict(spec_file: SpecFile) -> dict:
    """Serialize a SpecFile to a dict with only authored fields."""
    d: dict = {
        "id": spec_file.id,
        "title": spec_file.title,
        "description": spec_file.description,
        "version": spec_file.version,
        "scope": [s.value for s in spec_file.scope],
    }
    if spec_file.tags is not None:
        d["tags"] = [t.value for t in spec_file.tags]
    d["groups"] = [_group_to_dict(g, spec_file) for g in spec_file.groups]
    return d


class _YamlDumper(yaml.SafeDumper):
    """Custom YAML dumper with folded block scalars for long strings."""

    pass


def _str_representer(dumper: yaml.SafeDumper, data: str) -> yaml.ScalarNode:
    if "\n" in data or len(data) > 80:
        return dumper.represent_scalar(
            "tag:yaml.org,2002:str", data, style=">"
        )
    return dumper.represent_scalar("tag:yaml.org,2002:str", data)


_YamlDumper.add_representer(str, _str_representer)


def export_yaml(spec_file: SpecFile) -> str:
    """Serialize a single :class:`SpecFile` to authoritative YAML.

    Only authored fields are emitted — inherited defaults are omitted so
    that the YAML remains the canonical source of truth.
    """
    return yaml.dump(
        _file_to_dict(spec_file),
        Dumper=_YamlDumper,
        default_flow_style=False,
        sort_keys=False,
        allow_unicode=True,
    )


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
        eff_kind = registry.get_effective_kind(spec_id)
        eff_scope = registry.get_effective_scope(spec_id)
        eff_tags = registry.get_effective_tags(spec_id)

        if kind and eff_kind.value != kind:
            continue
        if scope and scope not in [s.value for s in eff_scope]:
            continue
        if tags and not all(t in [tg.value for tg in eff_tags] for t in tags):
            continue
        if priority and spec.priority.value != priority:
            continue
        record = spec.model_dump(mode="json")
        if eff_tags and record.get("tags") is None:
            record["tags"] = [t.value for t in eff_tags]
        result[spec_id] = record

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
        python -m vultron.metadata.specs.render --format yaml specs/
        python -m vultron.metadata.specs.render --format llm-json specs/
        python -m vultron.metadata.specs.render --format llm-json --topic CM specs/
    """
    import sys

    fmt = "md"
    topic = None
    args = sys.argv[1:]
    if "--format" in args:
        idx = args.index("--format")
        fmt = args[idx + 1]
        args = args[:idx] + args[idx + 2 :]
    if "--topic" in args:
        idx = args.index("--topic")
        topic = args[idx + 1]
        args = args[:idx] + args[idx + 2 :]

    if not args:
        print(
            f"Usage: {sys.argv[0]} [--format md|json|yaml|llm-json]"
            " [--topic FILEID] <spec_dir>",
            file=sys.stderr,
        )
        sys.exit(2)

    spec_dir = Path(args[0])
    registry = load_registry(spec_dir)

    if fmt == "json":
        print(export_json(registry))
    elif fmt == "yaml":
        for sf in registry.files:
            print(export_yaml(sf))
            print("---")
    elif fmt == "llm-json":
        from vultron.metadata.specs.llm_export import to_llm_json

        print(to_llm_json(registry, topic=topic))
    else:
        print(render_registry_markdown(registry))


class _DumpArgParser(argparse.ArgumentParser):
    """ArgumentParser that reports errors as ``Error: ...`` and exits 2.

    A flag given without its value is reported as ``--flag requires a
    value`` (the wording SR-07-006 tests pin) instead of argparse's default.
    """

    def error(self, message: str) -> NoReturn:
        missing = re.match(
            r"argument (--[\w-]+).*: expected one argument", message
        )
        if missing:
            message = f"{missing.group(1)} requires a value"
        self.print_usage(sys.stderr)
        self.exit(2, f"Error: {message}\n")


def _csv(raw: str) -> list[str]:
    return [item.strip() for item in raw.split(",") if item.strip()]


def _build_dump_parser() -> _DumpArgParser:
    parser = _DumpArgParser(
        prog="spec-dump",
        description=(
            "Export specs as LLM-optimized JSON. Selectors (--topic, --group,"
            " --ids, --cross-cutting) are unioned; --kind/--tag/--scope/"
            "--priority narrow the result. Start with --index."
        ),
    )
    parser.add_argument("spec_dir", nargs="?", default="specs")
    parser.add_argument(
        "--index",
        action="store_true",
        help="print a plain-text topic/group map instead of JSON",
    )
    parser.add_argument("--topic", type=_csv, help="comma list of topic IDs")
    parser.add_argument("--group", type=_csv, help="comma list of group IDs")
    parser.add_argument("--ids", type=_csv, help="comma list of spec IDs")
    parser.add_argument(
        "--deps",
        action="store_true",
        help="add transitive dependencies of the selected specs",
    )
    parser.add_argument(
        "--cross-cutting",
        action="store_true",
        help=f"add topics {','.join(CROSS_CUTTING_TOPICS)} to the selection",
    )
    parser.add_argument("--kind", type=_csv, help="comma list of kinds")
    parser.add_argument("--tag", type=_csv, help="comma list; ALL must match")
    parser.add_argument("--scope", help="prototype or production")
    parser.add_argument("--priority", help="e.g. MUST, SHOULD, MAY")
    parser.add_argument(
        "--slim",
        action="store_true",
        help="only id/priority/statement(/note) per requirement",
    )
    return parser


def _enum_problems(args: argparse.Namespace) -> list[str]:
    """Validate enum-valued flags; one message per offending flag."""
    from vultron.metadata.specs.schema import (
        RFC2119Priority,
        Scope,
        SpecKind,
        SpecTag,
    )

    checks = (
        ("kind", args.kind, SpecKind),
        ("tag", args.tag, SpecTag),
        ("scope", [args.scope] if args.scope else None, Scope),
        (
            "priority",
            [args.priority] if args.priority else None,
            RFC2119Priority,
        ),
    )
    problems: list[str] = []
    for label, values, enum in checks:
        valid = {item.value for item in enum}
        invalid = sorted(set(values or []) - valid)
        if invalid:
            problems.append(
                f"unknown {label} value(s): {', '.join(invalid)}."
                f" Valid values: {', '.join(sorted(valid))}"
            )
    return problems


def _fail(problems: list[str]) -> NoReturn:
    for problem in problems:
        print(f"Error: {problem}", file=sys.stderr)
    sys.exit(2)


def _emit(text: str) -> None:
    """Print *text*; a closed pipe (``spec-dump --index | head``) is not an error."""
    try:
        print(text)
        sys.stdout.flush()
    except BrokenPipeError:
        devnull = os.open(os.devnull, os.O_WRONLY)
        os.dup2(devnull, sys.stdout.fileno())


def _selection_kwargs(args: argparse.Namespace) -> dict[str, Any]:
    topics = args.topic
    if args.cross_cutting:
        topics = [*(topics or []), *CROSS_CUTTING_TOPICS]
    return {
        "topic": topics,
        "groups": args.group,
        "spec_ids": args.ids,
        "include_deps": args.deps,
        "kinds": args.kind,
        "scope": args.scope,
        "tags": args.tag,
        "priority": args.priority,
    }


def main_llm_json() -> None:
    """LLM-optimized spec dump entry point (spec-dump / spec-dump-llm-json).

    Exports specs as flat, inheritance-resolved JSON for coding agents
    (SR-07-006 through SR-07-013).  Defaults to the ``specs/`` directory
    relative to the current working directory.

    Usage::

        spec-dump --index                       # plain-text topic/group map
        spec-dump --cross-cutting --slim        # ARCH, CS, TB, HP, SL, EH
        spec-dump --topic CM,EP --group ARCH-01
        spec-dump --ids EP-04-001 --deps
        spec-dump --kind protocol,architecture --priority MUST
        spec-dump [specs/]                      # full dump (large; warns)

    Agents should start with ``--index`` and load targeted subsets rather
    than reading raw YAML files or the full dump.
    """
    from vultron.metadata.specs.llm_export import (
        to_index_text,
        to_llm_json,
        unknown_selectors,
    )

    args = _build_dump_parser().parse_args()
    problems = _enum_problems(args)
    if problems:
        _fail(problems)

    spec_dir = Path(args.spec_dir)
    if not spec_dir.is_dir():
        _fail([f"spec directory not found: {spec_dir}"])

    registry = load_registry(spec_dir)
    problems = unknown_selectors(
        registry, topics=args.topic, groups=args.group, spec_ids=args.ids
    )
    if problems:
        _fail(problems)

    kwargs = _selection_kwargs(args)
    if args.index:
        _emit(to_index_text(registry, **kwargs))
        return

    output = to_llm_json(registry, slim=args.slim, **kwargs)
    if not any(
        value for key, value in kwargs.items() if key != "include_deps"
    ):
        print(
            f"spec-dump: warning: unfiltered dump is ~{len(output) / 1e6:.1f} MB"
            f" (~{len(output) // 4000}k tokens); use --index for a map and"
            " --topic/--group/--ids/--cross-cutting [--slim] to load subsets",
            file=sys.stderr,
        )
    _emit(output)


if __name__ == "__main__":
    main()
