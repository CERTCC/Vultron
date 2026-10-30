"""Tests for vultron.metadata.specs.relation_graph (SR-13-012 to SR-13-015)."""

from __future__ import annotations

import pytest

from test.metadata.specs.conftest import spec_file_data
from vultron.metadata.specs import relation_graph
from vultron.metadata.specs.registry import SpecRegistry
from vultron.metadata.specs.schema import SpecFile


def _registry(*links: tuple[str, str, str]) -> SpecRegistry:
    """A registry of TST-01-001..005 carrying ``(source, rel_type, target)``."""
    rels: dict[str, list[dict[str, str]]] = {}
    for source, rel_type, target in links:
        rels.setdefault(source, []).append(
            {"rel_type": rel_type, "spec_id": target}
        )
    items = [
        (
            spec_id,
            "MUST",
            "project",
            {"relationships": rels[spec_id]} if spec_id in rels else {},
        )
        for spec_id in (f"TST-01-00{n}" for n in range(1, 6))
    ]
    return SpecRegistry(files=[SpecFile.model_validate(spec_file_data(items))])


A, B, C = "TST-01-001", "TST-01-002", "TST-01-003"


@pytest.mark.spec("SR-13-020")
@pytest.mark.spec("SR-13-014")
def test_two_node_loop_is_reported_naming_both_members():
    registry = _registry((A, "depends_on", B), (B, "depends_on", A))

    errors = relation_graph.check_relationship_loops(registry)

    assert len(errors) == 1
    assert f"loop among {A}, {B}:" in errors[0]


@pytest.mark.spec("SR-13-020")
@pytest.mark.spec("SR-13-014")
def test_three_node_loop_is_reported_naming_every_member():
    registry = _registry(
        (A, "refines", B), (B, "depends_on", C), (C, "derives_from", A)
    )

    errors = relation_graph.check_relationship_loops(registry)

    assert len(errors) == 1
    assert f"loop among {A}, {B}, {C}:" in errors[0]
    for edge in (
        f"{A} refines {B}",
        f"{B} depends_on {C}",
        f"{C} derives_from {A}",
    ):
        assert edge in errors[0]


@pytest.mark.spec("SR-13-014")
def test_self_loop_is_reported():
    registry = _registry((A, "refines", A))

    errors = relation_graph.check_relationship_loops(registry)

    assert len(errors) == 1
    assert f"loop among {A}:" in errors[0]


@pytest.mark.spec("SR-13-014")
def test_constrains_recorded_backwards_closes_a_loop():
    # A refines B makes B upstream; A constrains B makes A upstream.
    registry = _registry((A, "refines", B), (A, "constrains", B))

    errors = relation_graph.check_relationship_loops(registry)

    assert len(errors) == 1
    assert f"loop among {A}, {B}:" in errors[0]


@pytest.mark.spec("SR-13-014")
def test_loop_error_lists_every_link_sharing_an_arc():
    registry = _registry(
        (A, "refines", B), (A, "depends_on", B), (B, "depends_on", A)
    )

    (error,) = relation_graph.check_relationship_loops(registry)

    for edge in (
        f"{A} refines {B}",
        f"{A} depends_on {B}",
        f"{B} depends_on {A}",
    ):
        assert edge in error


@pytest.mark.spec("SR-13-014")
def test_chain_without_a_loop_passes():
    registry = _registry(
        (A, "refines", B), (B, "depends_on", C), (C, "constrains", A)
    )

    assert relation_graph.check_relationship_loops(registry) == []


@pytest.mark.spec("SR-13-014")
def test_conflicts_adds_no_arc():
    registry = _registry((A, "refines", B), (B, "conflicts", A))

    assert relation_graph.check_relationship_loops(registry) == []


@pytest.mark.spec("SR-13-012")
@pytest.mark.spec("SR-13-015")
def test_both_ends_recorded_is_reported():
    registry = _registry((A, "derives_from", B), (B, "satisfies", A))

    errors = relation_graph.check_both_ends_recorded(registry)

    assert errors == [
        f"{A} and {B} each record a relationship naming the other: "
        f"{A} derives_from {B}; {B} satisfies {A}. Record the link once, at "
        f"the end SR-13-012 names (SR-13-015)"
    ]


@pytest.mark.spec("SR-13-013")
@pytest.mark.spec("SR-13-015")
def test_mirror_image_double_recording_is_reported():
    # Both arcs point A -> B, so this is no loop: only the pair check sees it.
    registry = _registry((A, "refines", B), (B, "constrains", A))

    assert relation_graph.check_relationship_loops(registry) == []
    errors = relation_graph.check_both_ends_recorded(registry)
    assert len(errors) == 1
    assert f"{A} refines {B}; {B} constrains {A}" in errors[0]


@pytest.mark.spec("SR-13-015")
def test_conflicts_recorded_at_both_ends_is_reported():
    registry = _registry((A, "conflicts", B), (B, "conflicts", A))

    assert len(relation_graph.check_both_ends_recorded(registry)) == 1


@pytest.mark.spec("SR-13-015")
def test_one_end_recording_two_types_passes():
    registry = _registry((A, "refines", B), (A, "depends_on", B))

    assert relation_graph.check_both_ends_recorded(registry) == []


@pytest.mark.spec("SR-13-014")
def test_upstream_graph_reverses_constrains_and_drops_conflicts():
    registry = _registry(
        (A, "refines", B), (C, "constrains", A), (B, "conflicts", C)
    )

    graph = relation_graph.upstream_graph(registry)

    assert set(graph.edges) == {(A, B), (A, C)}


@pytest.mark.spec_corpus
@pytest.mark.spec("SR-13-014")
def test_real_specs_have_no_relationship_loops(real_registry):
    assert relation_graph.check_relationship_loops(real_registry) == []


@pytest.mark.spec_corpus
@pytest.mark.spec("SR-13-015")
def test_real_specs_record_each_link_once(real_registry):
    assert relation_graph.check_both_ends_recorded(real_registry) == []
