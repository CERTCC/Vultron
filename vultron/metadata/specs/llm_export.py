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
    # Several topics plus a group, slimmed down
    print(to_llm_json(registry, topic=["CM", "EP"], groups=["ARCH-01"],
                      slim=True))
    # Plain-text topic/group map
    print(to_index_text(registry))
"""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from typing import Any

from vultron.metadata.specs.registry import (
    SpecRegistry,
    effective_scope,
    effective_tags,
)
from vultron.metadata.specs.schema import (
    BehavioralSpec,
    Spec,
    SpecFile,
    SpecGroup,
)

#: Topics whose requirements apply to every change regardless of its primary
#: topic.  Single source of truth for ``spec-dump --cross-cutting``; skills
#: reference the flag rather than repeating this list.
CROSS_CUTTING_TOPICS: tuple[str, ...] = ("ARCH", "CS", "TB", "HP", "SL", "EH")


def _behavioral_fields(spec: BehavioralSpec) -> dict[str, Any]:
    """Return the fields only a :class:`BehavioralSpec` carries.

    Split out of :func:`_spec_record` so that function stays within the
    complexity gate as optional fields are added to the export.
    """
    rec: dict[str, Any] = {}
    if spec.preconditions:
        rec["preconditions"] = [p.description for p in spec.preconditions]
    if spec.steps:
        rec["steps"] = [_step_record(s) for s in spec.steps]
    if spec.postconditions:
        rec["postconditions"] = [p.description for p in spec.postconditions]
    return rec


def _spec_record(
    spec: Spec,
    group: SpecGroup,
    file: SpecFile,
) -> dict[str, Any]:
    """Build a flat, inheritance-resolved dict for a single spec."""
    rec: dict[str, Any] = {
        "id": spec.id,
        "topic": file.id,
        "group": group.id,
        "group_title": group.title,
        "type": (
            "behavioral" if isinstance(spec, BehavioralSpec) else "statement"
        ),
        "priority": spec.priority.value,
        "statement": spec.statement,
        "kind": spec.kind.value,
        "scope": [s.value for s in effective_scope(spec, group, file)],
    }

    tags = effective_tags(spec, file)
    if tags:
        rec["tags"] = [t.value for t in tags]

    if spec.rationale is not None:
        rec["rationale"] = spec.rationale

    # ``note`` carries the caveats that keep a requirement from being read the
    # wrong way — which side an obligation binds, what a receiver must *not* do
    # about it.  Dropping it made that guidance unreachable for any agent
    # following AGENTS.md, which says to load specs through this exporter and
    # never to read raw ``specs/*.yaml``.  ``_rel_record`` already exports a
    # relationship's ``note``; omitting the spec-level one was an oversight.
    if spec.note is not None:
        rec["note"] = spec.note

    if not spec.testable:
        rec["testable"] = False

    if spec.relationships:
        rec["relationships"] = [_rel_record(r) for r in spec.relationships]

    if spec.adr:
        rec["adr"] = list(spec.adr)

    rec["verification"] = spec.verification

    if isinstance(spec, BehavioralSpec):
        rec.update(_behavioral_fields(spec))

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


def _topic_record(file: SpecFile) -> dict[str, str]:
    return {
        "id": file.id,
        "title": file.title,
        "version": file.version,
    }


def _as_list(value: str | Iterable[str] | None) -> list[str] | None:
    if value is None:
        return None
    if isinstance(value, str):
        return [value]
    return list(value)


@dataclass(frozen=True)
class _AttrFilters:
    """Attribute filters that narrow (intersect) a selection."""

    kinds: list[str] | None = None
    scope: str | None = None
    tags: list[str] | None = None
    priority: str | None = None

    def matches(self, spec: Spec, group: SpecGroup, file: SpecFile) -> bool:
        if self.kinds and spec.kind.value not in self.kinds:
            return False
        if self.priority and spec.priority.value != self.priority:
            return False
        if self.scope and self.scope not in {
            item.value for item in effective_scope(spec, group, file)
        }:
            return False
        if self.tags and not set(self.tags).issubset(
            {item.value for item in effective_tags(spec, file)}
        ):
            return False
        return True


def select_spec_ids(
    registry: SpecRegistry,
    *,
    topics: str | Iterable[str] | None = None,
    groups: Iterable[str] | None = None,
    spec_ids: Iterable[str] | None = None,
    include_deps: bool = False,
) -> set[str] | None:
    """Resolve the selectors to a set of spec IDs (their union).

    Returns *None* when no selector is given, meaning "every spec".  With
    *include_deps*, the selection is expanded with the transitive
    dependencies of every selected spec.
    """
    topic_list = _as_list(topics)
    group_list = _as_list(groups)
    id_list = _as_list(spec_ids)
    if topic_list is None and group_list is None and id_list is None:
        return None

    topic_set = set(topic_list or [])
    group_set = set(group_list or [])
    selected = set(id_list or [])
    for spec_id, (group, file) in registry._spec_context.items():
        if file.id in topic_set or group.id in group_set:
            selected.add(spec_id)
    if include_deps:
        for spec_id in list(selected):
            selected |= registry.transitive_deps(spec_id)
    return selected


def unknown_selectors(
    registry: SpecRegistry,
    *,
    topics: Iterable[str] | None = None,
    groups: Iterable[str] | None = None,
    spec_ids: Iterable[str] | None = None,
) -> list[str]:
    """Return one message per selector kind that names unknown values."""
    known = {
        "topic": {f.id for f in registry.files},
        "group": {g.id for f in registry.files for g in f.groups},
        "id": set(registry.all_specs),
    }
    problems: list[str] = []
    for label, values in (
        ("topic", topics),
        ("group", groups),
        ("id", spec_ids),
    ):
        missing = sorted(set(values or []) - known[label])
        if missing:
            problems.append(f"unknown {label} value(s): {', '.join(missing)}")
    return problems


def _iter_matching(
    registry: SpecRegistry,
    selected_ids: set[str] | None,
    filters: _AttrFilters,
) -> Iterator[tuple[str, Spec, SpecGroup, SpecFile]]:
    for spec_id, spec in registry.all_specs.items():
        if selected_ids is not None and spec_id not in selected_ids:
            continue
        group, file = registry._spec_context[spec_id]
        if filters.matches(spec, group, file):
            yield spec_id, spec, group, file


def _edge_record(spec_id: str, relationship: object) -> dict[str, str]:
    edge: dict[str, str] = {
        "from": spec_id,
        "rel_type": relationship.rel_type.value,  # type: ignore[attr-defined]
        "to": relationship.spec_id,  # type: ignore[attr-defined]
    }
    if relationship.note:  # type: ignore[attr-defined]
        edge["note"] = relationship.note  # type: ignore[attr-defined]
    return edge


def _slim_record(spec: Spec) -> dict[str, Any]:
    rec: dict[str, Any] = {
        "id": spec.id,
        "priority": spec.priority.value,
        "statement": spec.statement,
    }
    # ``note`` is kept even in slim output: it is the guidance that stops a
    # requirement being implemented on the wrong side (see _spec_record).
    if spec.note is not None:
        rec["note"] = spec.note
    return rec


def _full_edges(spec_id: str, spec: Spec) -> list[dict[str, str]]:
    edges = [_edge_record(spec_id, r) for r in spec.relationships or []]
    edges.extend(
        {"from": spec_id, "rel_type": "derives_from", "to": adr_id}
        for adr_id in spec.adr or []
    )
    return edges


def to_llm_json(
    registry: SpecRegistry,
    *,
    topic: str | Iterable[str] | None = None,
    groups: Iterable[str] | None = None,
    spec_ids: Iterable[str] | None = None,
    include_deps: bool = False,
    kinds: list[str] | None = None,
    scope: str | None = None,
    tags: list[str] | None = None,
    priority: str | None = None,
    slim: bool = False,
) -> str:
    """Produce a flat, inheritance-resolved JSON projection of the registry.

    Selectors (*topic*, *groups*, *spec_ids*) are combined as a **union**;
    attribute filters (*kinds*, *scope*, *tags*, *priority*) then narrow
    that selection.  With no selector, every spec is a candidate.

    Args:
        registry: The loaded SpecRegistry.
        topic: A topic (file) ID or an iterable of topic IDs.
        groups: Group IDs (e.g. ``["ARCH-01"]``).
        spec_ids: Specific spec IDs.
        include_deps: Expand the selection with the transitive dependencies
            of every selected spec via the requirements graph.
        kinds: Filter to specs whose kind value is in this list (e.g.
            ``["protocol", "architecture"]``).  *None* means no filter.
        scope: Filter to specs whose effective scope contains this value.
        tags: Filter to specs that have ALL of the given tags.
        priority: Filter to specs with this priority value.
        slim: Reduce each requirement to ``id``/``priority``/``statement``
            (plus ``note`` when set), keep only relationship edges whose
            both ends are selected, and reduce topics to ``id``/``title``.

    Returns:
        Compact JSON string (no indentation).
    """
    selected_ids = select_spec_ids(
        registry,
        topics=topic,
        groups=groups,
        spec_ids=spec_ids,
        include_deps=include_deps,
    )
    filters = _AttrFilters(
        kinds=kinds, scope=scope, tags=tags, priority=priority
    )
    requirements: list[dict[str, Any]] = []
    edges: list[dict[str, str]] = []
    topic_ids_seen: set[str] = set()

    for spec_id, spec, group, file in _iter_matching(
        registry, selected_ids, filters
    ):
        topic_ids_seen.add(file.id)
        if slim:
            requirements.append(_slim_record(spec))
            edges.extend(
                _edge_record(spec_id, r) for r in spec.relationships or []
            )
        else:
            requirements.append(_spec_record(spec, group, file))
            edges.extend(_full_edges(spec_id, spec))

    if slim:
        kept = {r["id"] for r in requirements}
        edges = [e for e in edges if e["to"] in kept]
        topics: list[dict[str, str]] = [
            {"id": f.id, "title": f.title}
            for f in registry.files
            if f.id in topic_ids_seen
        ]
    else:
        topics = [
            _topic_record(f) for f in registry.files if f.id in topic_ids_seen
        ]

    result = {"topics": topics, "requirements": requirements, "edges": edges}
    return json.dumps(result, separators=(",", ":"))


def to_requirements_text(
    registry: SpecRegistry,
    *,
    topic: str | Iterable[str] | None = None,
    groups: Iterable[str] | None = None,
    spec_ids: Iterable[str] | None = None,
    include_deps: bool = False,
    kinds: list[str] | None = None,
    scope: str | None = None,
    tags: list[str] | None = None,
    priority: str | None = None,
) -> str:
    """Render selected requirements as line-per-requirement text (SR-07-014).

    ``to_llm_json`` emits one long line, so an agent that prints a load of
    any size sees a truncated prefix of a single unreadable token — the same
    failure the full dump had.  This renders the same selection as indented
    text: a topic header, a group header, then ``ID PRIORITY statement`` per
    requirement, which truncates gracefully and costs ~30% fewer bytes.
    """
    selected_ids = select_spec_ids(
        registry,
        topics=topic,
        groups=groups,
        spec_ids=spec_ids,
        include_deps=include_deps,
    )
    filters = _AttrFilters(
        kinds=kinds, scope=scope, tags=tags, priority=priority
    )
    by_group: dict[str, list[str]] = {}
    for spec_id, spec, group, _file in _iter_matching(
        registry, selected_ids, filters
    ):
        statement = " ".join(spec.statement.split())
        by_group.setdefault(group.id, []).append(
            f"    {spec_id} {spec.priority.value}  {statement}"
        )

    lines: list[str] = []
    n_reqs = 0
    for file in registry.files:
        rendered = [
            (g, by_group[g.id]) for g in file.groups if g.id in by_group
        ]
        if not rendered:
            continue
        lines.append(f"{file.id}  {file.title}")
        for group, reqs in rendered:
            lines.append(f"  {group.id}  {group.title}")
            lines.extend(reqs)
            n_reqs += len(reqs)

    header = (
        f"# {n_reqs} requirements, statements only. Relationships,"
        " verification, and tags are omitted here — drop --text for the"
        " full JSON record of any ID below."
    )
    return "\n".join([header, *lines]) + "\n"


def to_index_text(
    registry: SpecRegistry,
    *,
    topic: str | Iterable[str] | None = None,
    groups: Iterable[str] | None = None,
    spec_ids: Iterable[str] | None = None,
    include_deps: bool = False,
    kinds: list[str] | None = None,
    scope: str | None = None,
    tags: list[str] | None = None,
    priority: str | None = None,
) -> str:
    """Render a compact plain-text spec map (SR-07-007).

    One header line per topic (``ID  Title  (N reqs)``) followed by one
    indented line per group (``  GROUP-ID  group title (N)``).  Takes the
    same selectors and filters as :func:`to_llm_json`; topics and groups
    with no matching requirement are omitted.
    """
    selected_ids = select_spec_ids(
        registry,
        topics=topic,
        groups=groups,
        spec_ids=spec_ids,
        include_deps=include_deps,
    )
    filters = _AttrFilters(
        kinds=kinds, scope=scope, tags=tags, priority=priority
    )
    group_counts: Counter[str] = Counter()
    for _spec_id, _spec, group, _file in _iter_matching(
        registry, selected_ids, filters
    ):
        group_counts[group.id] += 1

    lines: list[str] = []
    for file in registry.files:
        counted = [
            (g, group_counts[g.id]) for g in file.groups if group_counts[g.id]
        ]
        if not counted:
            continue
        total = sum(n for _g, n in counted)
        lines.append(f"{file.id}  {file.title}  ({total} reqs)")
        lines.extend(f"  {g.id}  {g.title} ({n})" for g, n in counted)

    n_topics = sum(1 for line in lines if not line.startswith(" "))
    header = (
        f"# spec map: {n_topics} topics, {sum(group_counts.values())} reqs."
        " Load with: spec-dump --text --topic T | --group G | --ids I"
        f" [--deps]; --cross-cutting adds {','.join(CROSS_CUTTING_TOPICS)}."
        " Drop --text for the full JSON record of one group."
    )
    return "\n".join([header, *lines])
