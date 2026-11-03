"""Requirement selection for the LLM export: topic, group, ID, ADR and
attribute selectors.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from dataclasses import dataclass

from vultron.metadata.specs.registry import (
    SpecRegistry,
    effective_scope,
    effective_tags,
)
from vultron.metadata.specs.schema import (
    Spec,
    SpecFile,
    SpecGroup,
)


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
        return not (
            self.tags
            and not set(self.tags).issubset(
                {item.value for item in effective_tags(spec, file)}
            )
        )


def select_spec_ids(
    registry: SpecRegistry,
    *,
    topics: str | Iterable[str] | None = None,
    groups: Iterable[str] | None = None,
    spec_ids: Iterable[str] | None = None,
    adrs: Iterable[str] | None = None,
    include_deps: bool = False,
) -> set[str] | None:
    """Resolve the selectors to a set of spec IDs (their union).

    *adrs* selects every requirement whose ``adr:`` field names one of the
    given ``ADR-NNNN`` ids: the structured edge read in the
    record-to-requirements direction (SR-07-017).

    Returns *None* when no selector is given, meaning "every spec".  With
    *include_deps*, the selection is expanded with the transitive
    dependencies of every selected spec.
    """
    topic_list = _as_list(topics)
    group_list = _as_list(groups)
    id_list = _as_list(spec_ids)
    adr_list = _as_list(adrs)
    if all(
        selector is None
        for selector in (topic_list, group_list, id_list, adr_list)
    ):
        return None

    topic_set = set(topic_list or [])
    group_set = set(group_list or [])
    adr_set = set(adr_list or [])
    selected = set(id_list or [])
    for spec_id, (group, file) in registry._spec_context.items():
        if file.id in topic_set or group.id in group_set:
            selected.add(spec_id)
    if adr_set:
        selected |= {
            spec_id
            for spec_id, spec in registry.all_specs.items()
            if adr_set.intersection(spec.adr or [])
        }
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


def uncited_adrs(registry: SpecRegistry, adrs: Iterable[str]) -> list[str]:
    """Return the ids in *adrs* that no requirement names in its ``adr:`` field.

    Such a record is reached only by a prose citation in ``specs/`` or
    ``notes/`` (or is record-only), so ``--adr`` selects nothing for it; the
    caller says so rather than printing an empty selection silently.
    """
    cited = {
        adr for spec in registry.all_specs.values() for adr in spec.adr or []
    }
    return sorted(set(adrs) - cited)


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
