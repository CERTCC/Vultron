"""Tests for SpecRegistry graph integration and llm_export module."""

import json

import pytest
import yaml

from vultron.metadata.specs.llm_export import to_llm_json
from vultron.metadata.specs.registry import load_registry

# ---------------------------------------------------------------------------
# Fixtures with relationships for graph testing
# ---------------------------------------------------------------------------

GRAPH_YAML_A = {
    "id": "GA",
    "title": "Graph Test A",
    "description": "Spec file A for graph tests",
    "version": "1.0",
    "kind": "general",
    "scope": ["prototype", "production"],
    "groups": [
        {
            "id": "GA-01",
            "title": "Group A1",
            "specs": [
                {
                    "id": "GA-01-001",
                    "priority": "MUST",
                    "statement": "GA-01-001 MUST be foundational",
                    "tags": ["protocol"],
                },
                {
                    "id": "GA-01-002",
                    "priority": "SHOULD",
                    "statement": "GA-01-002 SHOULD depend on GA-01-001",
                    "relationships": [
                        {
                            "rel_type": "depends_on",
                            "spec_id": "GA-01-001",
                            "note": "foundational dep",
                        }
                    ],
                },
            ],
        },
        {
            "id": "GA-02",
            "title": "Group A2",
            "kind": "implementation",
            "specs": [
                {
                    "id": "GA-02-001",
                    "priority": "MAY",
                    "statement": "GA-02-001 MAY extend GA-01-002",
                    "scope": ["production"],
                    "relationships": [
                        {
                            "rel_type": "extends",
                            "spec_id": "GA-01-002",
                        }
                    ],
                },
            ],
        },
    ],
}

GRAPH_YAML_B = {
    "id": "GB",
    "title": "Graph Test B",
    "description": "Spec file B for graph tests",
    "version": "1.0",
    "kind": "general",
    "scope": ["prototype"],
    "groups": [
        {
            "id": "GB-01",
            "title": "Group B1",
            "specs": [
                {
                    "id": "GB-01-001",
                    "priority": "MUST",
                    "statement": "GB-01-001 MUST cross-reference GA-01-001",
                    "relationships": [
                        {
                            "rel_type": "depends_on",
                            "spec_id": "GA-01-001",
                        }
                    ],
                },
            ],
        }
    ],
}


@pytest.fixture
def graph_spec_dir(tmp_path):
    """Spec dir with two files and cross-file relationships."""
    (tmp_path / "ga.yaml").write_text(yaml.dump(GRAPH_YAML_A))
    (tmp_path / "gb.yaml").write_text(yaml.dump(GRAPH_YAML_B))
    return tmp_path


@pytest.fixture
def graph_registry(graph_spec_dir):
    return load_registry(graph_spec_dir)


# ---------------------------------------------------------------------------
# Graph property tests
# ---------------------------------------------------------------------------


class TestRegistryGraph:
    def test_graph_has_all_nodes(self, graph_registry):
        g = graph_registry.graph
        assert set(g.nodes) == {
            "GA-01-001",
            "GA-01-002",
            "GA-02-001",
            "GB-01-001",
        }

    def test_graph_has_edges(self, graph_registry):
        g = graph_registry.graph
        assert g.has_edge("GA-01-002", "GA-01-001")
        assert g.has_edge("GA-02-001", "GA-01-002")
        assert g.has_edge("GB-01-001", "GA-01-001")
        assert not g.has_edge("GA-01-001", "GA-01-002")

    def test_graph_node_attrs(self, graph_registry):
        g = graph_registry.graph
        attrs = g.nodes["GA-01-001"]
        assert attrs["priority"] == "MUST"
        assert attrs["kind"] == "general"
        assert attrs["scope"] == ["prototype", "production"]
        assert attrs["file_id"] == "GA"
        assert attrs["group_id"] == "GA-01"
        # BehavioralSpec is tried first in Union; statement-only specs
        # with no steps/pre/post still parse as behavioral.
        assert attrs["type"] in ("statement", "behavioral")
        assert "foundational" in attrs["statement"]

    def test_graph_node_inherits_kind_from_group(self, graph_registry):
        attrs = graph_registry.graph.nodes["GA-02-001"]
        assert attrs["kind"] == "implementation"

    def test_graph_node_overrides_scope(self, graph_registry):
        attrs = graph_registry.graph.nodes["GA-02-001"]
        assert attrs["scope"] == ["production"]

    def test_graph_edge_attrs(self, graph_registry):
        g = graph_registry.graph
        data = g.edges["GA-01-002", "GA-01-001"]
        assert data["rel_type"] == "depends_on"
        assert data["note"] == "foundational dep"

    def test_graph_edge_no_note(self, graph_registry):
        g = graph_registry.graph
        data = g.edges["GA-02-001", "GA-01-002"]
        assert data["rel_type"] == "extends"
        assert data["note"] is None

    def test_subgraph_for_topic(self, graph_registry):
        sub = graph_registry.subgraph_for_topic("GA")
        assert set(sub.nodes) == {"GA-01-001", "GA-01-002", "GA-02-001"}
        assert sub.has_edge("GA-01-002", "GA-01-001")

    def test_subgraph_for_unknown_topic(self, graph_registry):
        sub = graph_registry.subgraph_for_topic("ZZ")
        assert len(sub.nodes) == 0

    def test_transitive_deps(self, graph_registry):
        deps = graph_registry.transitive_deps("GA-02-001")
        assert deps == {"GA-01-001", "GA-01-002"}

    def test_transitive_deps_leaf_node(self, graph_registry):
        deps = graph_registry.transitive_deps("GA-01-001")
        assert deps == set()

    def test_transitive_deps_unknown_id(self, graph_registry):
        deps = graph_registry.transitive_deps("ZZ-99-999")
        assert deps == set()

    def test_transitive_deps_cross_file(self, graph_registry):
        deps = graph_registry.transitive_deps("GB-01-001")
        assert "GA-01-001" in deps


# ---------------------------------------------------------------------------
# LLM export tests
# ---------------------------------------------------------------------------


class TestLlmExport:
    def test_all_specs(self, graph_registry):
        raw = to_llm_json(graph_registry)
        data = json.loads(raw)
        assert len(data["topics"]) == 2
        assert len(data["requirements"]) == 4
        assert len(data["edges"]) == 3

    def test_topic_filter(self, graph_registry):
        data = json.loads(to_llm_json(graph_registry, topic="GA"))
        assert len(data["topics"]) == 1
        assert data["topics"][0]["id"] == "GA"
        assert len(data["requirements"]) == 3
        assert all(r["topic"] == "GA" for r in data["requirements"])

    def test_spec_ids_filter(self, graph_registry):
        data = json.loads(to_llm_json(graph_registry, spec_ids=["GA-01-001"]))
        assert len(data["requirements"]) == 1
        assert data["requirements"][0]["id"] == "GA-01-001"

    def test_spec_ids_with_deps(self, graph_registry):
        data = json.loads(
            to_llm_json(
                graph_registry,
                spec_ids=["GA-02-001"],
                include_deps=True,
            )
        )
        ids = {r["id"] for r in data["requirements"]}
        assert ids == {"GA-01-001", "GA-01-002", "GA-02-001"}

    def test_priority_filter(self, graph_registry):
        data = json.loads(to_llm_json(graph_registry, priority="MUST"))
        assert all(r["priority"] == "MUST" for r in data["requirements"])
        ids = {r["id"] for r in data["requirements"]}
        assert "GA-01-001" in ids
        assert "GA-01-002" not in ids

    def test_kind_filter(self, graph_registry):
        data = json.loads(to_llm_json(graph_registry, kind="implementation"))
        assert len(data["requirements"]) == 1
        assert data["requirements"][0]["id"] == "GA-02-001"

    def test_scope_filter(self, graph_registry):
        data = json.loads(to_llm_json(graph_registry, scope="prototype"))
        ids = {r["id"] for r in data["requirements"]}
        # GA-02-001 has scope=[production], should be excluded
        assert "GA-02-001" not in ids
        # GA-01-001 inherits [prototype, production], should be included
        assert "GA-01-001" in ids

    def test_tags_filter(self, graph_registry):
        data = json.loads(to_llm_json(graph_registry, tags=["protocol"]))
        assert len(data["requirements"]) == 1
        assert data["requirements"][0]["id"] == "GA-01-001"

    def test_compact_json_no_indentation(self, graph_registry):
        raw = to_llm_json(graph_registry)
        # Compact JSON has no newlines (single line)
        assert "\n" not in raw

    def test_spec_record_shape(self, graph_registry):
        data = json.loads(to_llm_json(graph_registry, topic="GA"))
        spec = next(r for r in data["requirements"] if r["id"] == "GA-01-002")
        assert spec["topic"] == "GA"
        assert spec["group"] == "GA-01"
        assert spec["group_title"] == "Group A1"
        assert spec["type"] in ("statement", "behavioral")
        assert spec["priority"] == "SHOULD"
        assert spec["kind"] == "general"
        assert spec["scope"] == ["prototype", "production"]
        assert "relationships" in spec
        assert spec["relationships"][0]["rel_type"] == "depends_on"

    def test_edges_centralized(self, graph_registry):
        data = json.loads(to_llm_json(graph_registry))
        edge_set = {(e["from"], e["to"]) for e in data["edges"]}
        assert ("GA-01-002", "GA-01-001") in edge_set
        assert ("GA-02-001", "GA-01-002") in edge_set
        assert ("GB-01-001", "GA-01-001") in edge_set

    def test_omits_default_testable(self, graph_registry):
        data = json.loads(to_llm_json(graph_registry))
        for req in data["requirements"]:
            # testable=True is the default, should be omitted
            assert "testable" not in req

    def test_omits_absent_rationale(self, graph_registry):
        data = json.loads(to_llm_json(graph_registry))
        for req in data["requirements"]:
            assert "rationale" not in req

    def test_empty_result(self, graph_registry):
        data = json.loads(to_llm_json(graph_registry, topic="NONEXISTENT"))
        assert data["topics"] == []
        assert data["requirements"] == []
        assert data["edges"] == []
