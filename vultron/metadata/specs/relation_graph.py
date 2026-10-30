"""Direction checks over the requirement-to-requirement relationship graph.

Every relationship is recorded once, on one of the two requirements it links
(SR-13-012), and each type says which of its ends is upstream (SR-13-001 to
SR-13-011 and SR-13-017,
:data:`~vultron.metadata.specs.schema.RELATION_DEFINITIONS`).
Pointing every edge from its downstream end to its upstream end gives one
graph in which "what does a change to this requirement affect?" is a walk
against the arrows. That walk is only meaningful when the graph has no loops,
so spec-lint fails on a loop (SR-13-014) and on a link recorded at both ends
(SR-13-015).
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import NamedTuple

import networkx as nx

from vultron.metadata.specs.registry import SpecRegistry
from vultron.metadata.specs.schema import RelationEnd, RelationType


class RecordedRelationship(NamedTuple):
    """One relationship as written: recorded on ``source``, naming ``target``."""

    source: str
    rel_type: RelationType
    target: str

    def __str__(self) -> str:
        return f"{self.source} {self.rel_type.value} {self.target}"


def recorded_relationships(
    registry: SpecRegistry,
) -> Iterator[RecordedRelationship]:
    """Yield every relationship in the registry, in corpus order."""
    for spec_id, spec in registry.all_specs.items():
        for rel in spec.relationships or []:
            yield RecordedRelationship(spec_id, rel.rel_type, rel.spec_id)


def upstream_graph(registry: SpecRegistry) -> nx.DiGraph:
    """Return the graph with one arc per relationship, downstream to upstream.

    A ``constrains`` relationship is recorded on its upstream end, so its arc
    runs target to source; ``conflicts`` has no upstream end and adds no arc.
    Each arc's ``relationships`` attribute lists the recorded relationships
    that produced it.
    """
    graph: nx.DiGraph = nx.DiGraph()
    graph.add_nodes_from(registry.all_specs)
    for rel in recorded_relationships(registry):
        upstream_end = rel.rel_type.upstream_end
        if upstream_end is RelationEnd.NEITHER:
            continue
        if upstream_end is RelationEnd.TARGET:
            arc = (rel.source, rel.target)
        else:
            arc = (rel.target, rel.source)
        if graph.has_edge(*arc):
            graph.edges[arc]["relationships"].append(rel)
        else:
            graph.add_edge(*arc, relationships=[rel])
    return graph


def check_relationship_loops(registry: SpecRegistry) -> list[str]:
    """Report every loop in :func:`upstream_graph` (SR-13-014).

    A loop is a strongly connected component of more than one requirement, or
    a requirement whose relationships name itself. Each error names every
    member and the relationships that close the loop (SR-13-020).
    """
    graph = upstream_graph(registry)
    errors: list[str] = []
    for component in nx.strongly_connected_components(graph):
        members = sorted(component)
        if len(members) == 1 and not graph.has_edge(members[0], members[0]):
            continue
        edges = sorted(
            str(rel)
            for arc in graph.subgraph(members).edges
            for rel in graph.edges[arc]["relationships"]
        )
        errors.append(
            f"Relationship loop among {', '.join(members)}: "
            f"{'; '.join(edges)}. Every relationship points from its "
            f"downstream end to its upstream end, so a loop means at least one "
            f"of these is recorded on the wrong requirement or with the wrong "
            f"type (SR-13-014)"
        )
    return sorted(errors)


def check_both_ends_recorded(registry: SpecRegistry) -> list[str]:
    """Report each pair of requirements whose relationships name each other.

    A link is recorded at one end only (SR-13-012), so two requirements that
    each name the other, under any types, record one fact twice (SR-13-015).
    """
    by_pair: dict[frozenset[str], list[RecordedRelationship]] = {}
    for rel in recorded_relationships(registry):
        by_pair.setdefault(frozenset((rel.source, rel.target)), []).append(rel)
    errors: list[str] = []
    for pair, rels in by_pair.items():
        if len({rel.source for rel in rels}) < 2:
            continue
        first, second = sorted(pair)
        errors.append(
            f"{first} and {second} each record a relationship naming the "
            f"other: {'; '.join(sorted(str(rel) for rel in rels))}. Record "
            f"the link once, at the end SR-13-012 names (SR-13-015)"
        )
    return sorted(errors)
