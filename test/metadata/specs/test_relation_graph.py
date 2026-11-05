"""Tests for vultron.metadata.specs.relation_graph (SR-13-012 to SR-13-015)."""

from __future__ import annotations

import pytest

from test.metadata.specs.conftest import spec_file_data
from vultron.metadata.specs import relation_graph
from vultron.metadata.specs.registry import SpecRegistry
from vultron.metadata.specs.schema import SpecFile, written_spec_ids


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


def _citing_registry(
    statement: str,
    *,
    see_also: list[dict[str, str]] | None = None,
    links: tuple[tuple[str, str, str], ...] = (),
) -> SpecRegistry:
    """TST-01-001..003, where A's statement is *statement* (SR-13-022)."""
    rels: dict[str, list[dict[str, str]]] = {}
    for source, rel_type, target in links:
        rels.setdefault(source, []).append(
            {"rel_type": rel_type, "spec_id": target}
        )
    extras: dict[str, dict[str, object]] = {
        spec_id: {"relationships": spec_rels}
        for spec_id, spec_rels in rels.items()
    }
    extras.setdefault(A, {})["statement"] = statement
    if see_also is not None:
        extras[A]["see_also"] = see_also
    items = [
        (spec_id, "MUST", "project", extras.get(spec_id, {}))
        for spec_id in (A, B, C)
    ]
    return SpecRegistry(files=[SpecFile.model_validate(spec_file_data(items))])


def _see(spec_id: str) -> dict[str, str]:
    return {"spec_id": spec_id, "reason": "context for the reader"}


@pytest.mark.spec("SR-13-023")
def test_unlinked_unlisted_citation_is_reported_naming_both():
    registry = _citing_registry(f"{A} MUST do what {B} describes.")

    errors = relation_graph.check_statement_citations(registry)

    assert len(errors) == 1
    assert f"{A}'s statement cites {B}, but no relationship links" in errors[0]


@pytest.mark.spec("SR-13-023")
@pytest.mark.parametrize(
    "links",
    [((A, "refines", B),), ((B, "constrains", A),)],
    ids=["recorded-on-the-citer", "recorded-on-the-cited"],
)
def test_citation_linked_at_either_end_passes(links):
    registry = _citing_registry(f"{A} MUST do what {B} says.", links=links)

    assert relation_graph.check_statement_citations(registry) == []


@pytest.mark.spec("SR-13-023")
def test_citation_listed_in_see_also_passes():
    registry = _citing_registry(
        f"{A} MUST do this, except where {B} applies.", see_also=[_see(B)]
    )

    assert relation_graph.check_statement_citations(registry) == []


@pytest.mark.spec("SR-13-023")
def test_own_id_in_statement_needs_no_entry():
    registry = _citing_registry(f"{A} MUST do the thing.")

    assert relation_graph.check_statement_citations(registry) == []


@pytest.mark.spec("SR-13-023")
def test_slash_list_member_is_a_citation():
    registry = _citing_registry(
        f"{A} MUST follow {B}/003.", see_also=[_see(B)]
    )

    errors = relation_graph.check_statement_citations(registry)

    assert len(errors) == 1
    assert f"{A}'s statement cites {C}" in errors[0]


@pytest.mark.spec("SR-13-023")
def test_range_interior_is_not_a_citation():
    # A range writes only its ends; TST-01-002 lies between them.
    registry = _citing_registry(
        f"{A} MUST hold for TST-01-001 through {C}.", see_also=[_see(C)]
    )

    assert relation_graph.check_statement_citations(registry) == []


@pytest.mark.spec("SR-13-023")
@pytest.mark.parametrize("mark", ["–", ".."], ids=["en-dash", "dots"])
def test_short_range_end_is_a_citation(mark):
    # A range writes its ends; "TST-01-001–003" writes TST-01-003.
    registry = _citing_registry(f"{A} MUST hold for {A}{mark}003.")

    errors = relation_graph.check_statement_citations(registry)

    assert len(errors) == 1
    assert f"{A}'s statement cites {C}" in errors[0]


@pytest.mark.spec("SR-13-023")
def test_backward_short_range_end_is_not_a_citation():
    registry = _citing_registry(
        f"{A} MUST hold for {C}–002.", see_also=[_see(C)]
    )

    assert relation_graph.check_statement_citations(registry) == []


@pytest.mark.spec("SR-13-022")
@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("IO-03-003a–003b", {"IO-03-003a", "IO-03-003b"}),
        ("IO-03-003a–003", {"IO-03-003a"}),
        ("CM-10-001/002–004", {"CM-10-001", "CM-10-002", "CM-10-004"}),
        ("CM-10-001–003/005", {"CM-10-001", "CM-10-003", "CM-10-005"}),
        (
            "CM-10-001 to CM-10-003–005",
            {"CM-10-001", "CM-10-003", "CM-10-005"},
        ),
        ("CM-10-001–002–003", {"CM-10-001", "CM-10-002", "CM-10-003"}),
        ("CM-10-001..11-002", {"CM-10-001", "CM-11-002"}),
        ("CM-10-001 — 100 actors", {"CM-10-001"}),
        ("CM-10-001 – 003", {"CM-10-001"}),
        ("CM-10-001 — 11-002", {"CM-10-001", "CM-11-002"}),
        ("CM-10-001s and CM-10-002", {"CM-10-001s", "CM-10-002"}),
    ],
    ids=[
        "suffixed-short-end",
        "backward-suffix",
        "slash-then-range",
        "range-then-slash",
        "word-range-then-dash",
        "chained-range",
        "cross-group-short-end",
        "spaced-dash-is-prose",
        "spaced-en-dash-is-prose",
        "spaced-group-end-is-a-range",
        "plural-reads-as-sub-item",
    ],
)
def test_written_spec_ids_reads_each_written_end(text, expected):
    assert written_spec_ids(text) == expected


@pytest.mark.spec("SR-13-023")
def test_plural_id_is_reported_as_naming_no_requirement():
    registry = _citing_registry(f"{A} MUST hold for {B}s.")

    errors = relation_graph.check_statement_citations(registry)

    assert errors == [
        f"{A}'s statement cites {B}s, but no requirement has that ID. "
        f"Cite the requirement meant (SR-13-022)"
    ]


@pytest.mark.spec("SR-13-023")
@pytest.mark.spec("SR-13-024")
def test_listing_an_unknown_cited_id_reports_both_faults():
    registry = _citing_registry(
        f"{A} MUST follow TST-01-009.", see_also=[_see("TST-01-009")]
    )

    errors = relation_graph.check_statement_citations(registry)

    assert len(errors) == 2
    assert any("cites TST-01-009, but no requirement" in e for e in errors)
    assert any("lists TST-01-009 in `see_also` but no" in e for e in errors)


@pytest.mark.spec("SR-13-023")
def test_cited_id_naming_no_requirement_is_reported():
    registry = _citing_registry(f"{A} MUST follow TST-01-009.")

    errors = relation_graph.check_statement_citations(registry)

    assert errors == [
        f"{A}'s statement cites TST-01-009, but no requirement has that ID. "
        "Cite the requirement meant (SR-13-022)"
    ]


@pytest.mark.spec("SR-13-024")
@pytest.mark.parametrize(
    ("statement", "see_also", "links", "problem"),
    [
        (
            f"{A} MUST do the thing.",
            [B],
            (),
            "but its statement does not cite it",
        ),
        (
            f"{A} MUST do what {B} says.",
            [B],
            ((A, "refines", B),),
            f"but a relationship links the two: {A} refines {B}",
        ),
        (
            f"{A} MUST do what {B} says.",
            [B],
            ((B, "constrains", A),),
            f"but a relationship links the two: {B} constrains {A}",
        ),
        (
            f"{A} MUST do the thing.",
            ["TST-01-009"],
            (),
            "but no requirement has that ID",
        ),
        (
            f"{A} MUST do what {B} says.",
            [B, B],
            (),
            "a second time",
        ),
        (
            f"{A} MUST do the thing.",
            [A],
            (),
            "but that is its own ID",
        ),
    ],
    ids=[
        "not-cited",
        "linked-on-the-citer",
        "linked-on-the-cited",
        "unknown-id",
        "repeated",
        "own-id",
    ],
)
def test_stale_see_also_entry_is_reported(statement, see_also, links, problem):
    registry = _citing_registry(
        statement, see_also=[_see(s) for s in see_also], links=links
    )

    errors = relation_graph.check_statement_citations(registry)

    assert len(errors) == 1
    assert errors[0].startswith(f"{A} lists ")
    assert problem in errors[0]
    assert errors[0].endswith("(SR-13-024)")


@pytest.mark.spec_corpus
@pytest.mark.spec("SR-13-022")
def test_real_specs_link_or_list_every_cited_requirement(real_registry):
    assert relation_graph.check_statement_citations(real_registry) == []
