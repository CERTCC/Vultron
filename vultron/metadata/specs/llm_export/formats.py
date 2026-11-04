"""Output formats for the LLM export: JSON, requirements text and the
topic/group index.
"""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Iterable
from typing import Any

from vultron.metadata.specs.llm_export.records import (
    CROSS_CUTTING_TOPICS,
    _edge_record,
    _full_edges,
    _slim_record,
    _spec_record,
    _topic_record,
)
from vultron.metadata.specs.llm_export.selection import (
    _AttrFilters,
    _iter_matching,
    select_spec_ids,
)
from vultron.metadata.specs.registry import SpecRegistry


def to_llm_json(
    registry: SpecRegistry,
    *,
    topic: str | Iterable[str] | None = None,
    groups: Iterable[str] | None = None,
    spec_ids: Iterable[str] | None = None,
    adrs: Iterable[str] | None = None,
    include_deps: bool = False,
    kinds: list[str] | None = None,
    scope: str | None = None,
    tags: list[str] | None = None,
    priority: str | None = None,
    slim: bool = False,
) -> str:
    """Produce a flat, inheritance-resolved JSON projection of the registry.

    Selectors (*topic*, *groups*, *spec_ids*, *adrs*) are combined as a
    **union**;
    attribute filters (*kinds*, *scope*, *tags*, *priority*) then narrow
    that selection.  With no selector, every spec is a candidate.

    Args:
        registry: The loaded SpecRegistry.
        topic: A topic (file) ID or an iterable of topic IDs.
        groups: Group IDs (e.g. ``["ARCH-01"]``).
        spec_ids: Specific spec IDs.
        adrs: ``ADR-NNNN`` ids; selects the requirements whose ``adr:``
            field names one of them.
        include_deps: Expand the selection with the transitive dependencies
            of every selected spec via the requirements graph.
        kinds: Filter to specs whose kind value is in this list (e.g.
            ``["protocol", "architecture"]``).  *None* means no filter.
        scope: Filter to specs whose effective scope contains this value.
        tags: Filter to specs that have ALL of the given tags.
        priority: Filter to specs with this priority value.
        slim: Reduce each requirement to ``id``/``priority``/``statement``
            (plus ``note`` when set), keep only relationship edges whose
            both ends are selected.

    Returns:
        Compact JSON string (no indentation).
    """
    selected_ids = select_spec_ids(
        registry,
        topics=topic,
        groups=groups,
        spec_ids=spec_ids,
        adrs=adrs,
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
    adrs: Iterable[str] | None = None,
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
        adrs=adrs,
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
    adrs: Iterable[str] | None = None,
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
        adrs=adrs,
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
