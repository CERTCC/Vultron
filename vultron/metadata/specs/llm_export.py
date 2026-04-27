"""LLM-optimized export for the spec registry.

Produces a flat, inheritance-resolved JSON projection designed for
coding agent consumption.  Requirements become primary objects with
denormalized group/file provenance and resolved kind/scope/tags.

Usage::

    from vultron.metadata.specs.registry import load_registry
    from vultron.metadata.specs.llm_export import to_llm_json

    registry = load_registry()
    # All specs
    print(to_llm_json(registry))
    # Single topic
    print(to_llm_json(registry, topic="CM"))
    # Specific IDs with transitive dependencies
    print(to_llm_json(registry, spec_ids=["EP-04-001"], include_deps=True))
"""

from __future__ import annotations

import json
from typing import Any

from vultron.metadata.specs.registry import (
    SpecRegistry,
    effective_kind,
    effective_scope,
    effective_tags,
)
from vultron.metadata.specs.schema import (
    BehavioralSpec,
    Spec,
    SpecFile,
    SpecGroup,
)


def _spec_record(
    spec: Spec,
    group: SpecGroup,
    file: SpecFile,
) -> dict[str, Any]:
    """Build a flat, inheritance-resolved dict for a single spec."""
    rec: dict[str, Any] = {
        "id": spec.id,
        "file": file.id,
        "group": group.id,
        "group_title": group.title,
        "type": (
            "behavioral" if isinstance(spec, BehavioralSpec) else "statement"
        ),
        "priority": spec.priority.value,
        "statement": spec.statement,
        "kind": effective_kind(spec, group, file).value,
        "scope": [s.value for s in effective_scope(spec, group, file)],
    }

    tags = effective_tags(spec)
    if tags:
        rec["tags"] = [t.value for t in tags]

    if spec.rationale is not None:
        rec["rationale"] = spec.rationale

    if not spec.testable:
        rec["testable"] = False

    if spec.relationships:
        rec["relationships"] = [_rel_record(r) for r in spec.relationships]

    if isinstance(spec, BehavioralSpec):
        if spec.preconditions:
            rec["preconditions"] = [p.description for p in spec.preconditions]
        if spec.steps:
            rec["steps"] = [_step_record(s) for s in spec.steps]
        if spec.postconditions:
            rec["postconditions"] = [
                p.description for p in spec.postconditions
            ]

    return rec


def _rel_record(r: object) -> dict[str, str]:
    d: dict[str, str] = {
        "rel_type": r.rel_type.value,  # type: ignore[attr-defined]
        "spec_id": r.spec_id,  # type: ignore[attr-defined]
    }
    if r.note is not None:  # type: ignore[attr-defined]
        d["note"] = r.note  # type: ignore[attr-defined]
    return d


def _step_record(s: object) -> dict[str, Any]:
    d: dict[str, Any] = {
        "order": s.order,  # type: ignore[attr-defined]
        "actor": s.actor,  # type: ignore[attr-defined]
        "action": s.action,  # type: ignore[attr-defined]
    }
    if s.expected is not None:  # type: ignore[attr-defined]
        d["expected"] = s.expected  # type: ignore[attr-defined]
    return d


def _file_record(file: SpecFile) -> dict[str, str]:
    return {
        "id": file.id,
        "title": file.title,
        "version": file.version,
        "kind": file.kind,
    }


def to_llm_json(
    registry: SpecRegistry,
    *,
    topic: str | None = None,
    spec_ids: list[str] | None = None,
    include_deps: bool = False,
    kind: str | None = None,
    scope: str | None = None,
    tags: list[str] | None = None,
    priority: str | None = None,
) -> str:
    """Produce a flat, inheritance-resolved JSON projection of the registry.

    Args:
        registry: The loaded SpecRegistry.
        topic: Filter to specs from the file with this ID prefix.
        spec_ids: Filter to these specific spec IDs.
        include_deps: When True and *spec_ids* is given, expand to include
            transitive dependencies via the requirements graph.
        kind: Filter to specs with this effective kind value.
        scope: Filter to specs whose effective scope contains this value.
        tags: Filter to specs that have ALL of the given tags.
        priority: Filter to specs with this priority value.

    Returns:
        Compact JSON string (no indentation).
    """
    # Determine which spec IDs to include.
    selected_ids: set[str] | None = None

    if spec_ids is not None:
        selected_ids = set(spec_ids)
        if include_deps:
            for sid in list(selected_ids):
                selected_ids |= registry.transitive_deps(sid)

    requirements: list[dict[str, Any]] = []
    edges: list[dict[str, str]] = []
    file_ids_seen: set[str] = set()

    for spec_id, spec in registry.all_specs.items():
        group, file = registry._spec_context[spec_id]

        # Apply filters.
        if topic is not None and file.id != topic:
            continue
        if selected_ids is not None and spec_id not in selected_ids:
            continue

        eff_kind = effective_kind(spec, group, file)
        eff_scope = effective_scope(spec, group, file)
        eff_tags = effective_tags(spec)

        if kind and eff_kind.value != kind:
            continue
        if scope and scope not in [s.value for s in eff_scope]:
            continue
        if tags and not all(t in [tg.value for tg in eff_tags] for t in tags):
            continue
        if priority and spec.priority.value != priority:
            continue

        requirements.append(_spec_record(spec, group, file))
        file_ids_seen.add(file.id)

        # Collect edges for the centralized array.
        for rel in spec.relationships or []:
            edge: dict[str, str] = {
                "from": spec_id,
                "rel_type": rel.rel_type.value,
                "to": rel.spec_id,
            }
            if rel.note:
                edge["note"] = rel.note
            edges.append(edge)

    # Build lightweight file metadata for included files.
    files_meta = [
        _file_record(f) for f in registry.files if f.id in file_ids_seen
    ]

    result: dict[str, Any] = {
        "files": files_meta,
        "requirements": requirements,
        "edges": edges,
    }

    return json.dumps(result, separators=(",", ":"))
