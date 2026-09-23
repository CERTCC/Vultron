"""Tests for the ``spec-dump`` selection flags, ``--index`` and ``--slim``.

Requirements: specs/spec-registry.yaml SR-07-007 through SR-07-013.
"""

import json
import sys

import pytest
import yaml

from vultron.metadata.specs import CROSS_CUTTING_TOPICS
from vultron.metadata.specs.llm_export import to_index_text, to_llm_json
from vultron.metadata.specs.registry import load_registry
from vultron.metadata.specs.render import main_llm_json

ARCH_YAML = {
    "id": "ARCH",
    "title": "Architecture",
    "description": "Cross-cutting fixture",
    "version": "1.0",
    "scope": ["prototype"],
    "groups": [
        {
            "id": "ARCH-01",
            "title": "Layering",
            "specs": [
                {
                    "id": "ARCH-01-001",
                    "priority": "MUST",
                    "kind": "architecture",
                    "statement": "ARCH-01-001 MUST hold",
                    "rationale": "Because layers.",
                    "tags": ["protocol"],
                },
                {
                    "id": "ARCH-01-002",
                    "priority": "SHOULD",
                    "kind": "architecture",
                    "statement": "ARCH-01-002 SHOULD hold",
                    "relationships": [
                        {"rel_type": "depends_on", "spec_id": "ARCH-01-001"}
                    ],
                },
            ],
        }
    ],
}

CM_YAML = {
    "id": "CM",
    "title": "Case Management",
    "description": "Topic fixture",
    "version": "1.0",
    "scope": ["prototype", "production"],
    "groups": [
        {
            "id": "CM-01",
            "title": "Cases",
            "specs": [
                {
                    "id": "CM-01-001",
                    "priority": "MUST",
                    "kind": "protocol",
                    "statement": "CM-01-001 MUST depend on ARCH-01-002",
                    "relationships": [
                        {"rel_type": "depends_on", "spec_id": "ARCH-01-002"}
                    ],
                },
            ],
        },
        {
            "id": "CM-02",
            "title": "Participants",
            "specs": [
                {
                    "id": "CM-02-001",
                    "priority": "MAY",
                    "kind": "protocol",
                    "statement": "CM-02-001 MAY exist",
                    "scope": ["production"],
                },
            ],
        },
    ],
}


@pytest.fixture
def dump_dir(tmp_path):
    (tmp_path / "arch.yaml").write_text(yaml.dump(ARCH_YAML))
    (tmp_path / "cm.yaml").write_text(yaml.dump(CM_YAML))
    return tmp_path


@pytest.fixture
def registry(dump_dir):
    return load_registry(dump_dir)


def _run(monkeypatch, capsys, *argv):
    monkeypatch.setattr(sys, "argv", ["spec-dump", *argv])
    main_llm_json()
    return capsys.readouterr()


def _ids(out: str) -> set[str]:
    return {r["id"] for r in json.loads(out)["requirements"]}


def _exit_code(monkeypatch, *argv) -> object:
    monkeypatch.setattr(sys, "argv", ["spec-dump", *argv])
    with pytest.raises(SystemExit) as exc_info:
        main_llm_json()
    return exc_info.value.code


# ---------------------------------------------------------------------------
# Library: multi-topic, groups, union semantics, slim
# ---------------------------------------------------------------------------


class TestToLlmJsonSelection:
    @pytest.mark.spec("SR-07-008")
    def test_topic_accepts_list(self, registry):
        data = json.loads(to_llm_json(registry, topic=["ARCH", "CM"]))
        assert len(data["requirements"]) == 4

    @pytest.mark.spec("SR-07-008")
    def test_topic_accepts_single_string(self, registry):
        data = json.loads(to_llm_json(registry, topic="CM"))
        assert {r["topic"] for r in data["requirements"]} == {"CM"}

    @pytest.mark.spec("SR-07-008")
    def test_groups_filter(self, registry):
        data = json.loads(to_llm_json(registry, groups=["CM-02"]))
        assert {r["id"] for r in data["requirements"]} == {"CM-02-001"}

    @pytest.mark.spec("SR-07-008")
    def test_selectors_are_a_union(self, registry):
        data = json.loads(
            to_llm_json(registry, topic=["ARCH"], spec_ids=["CM-02-001"])
        )
        ids = {r["id"] for r in data["requirements"]}
        assert ids == {"ARCH-01-001", "ARCH-01-002", "CM-02-001"}

    @pytest.mark.spec("SR-07-008")
    def test_attribute_filters_narrow_the_selection(self, registry):
        data = json.loads(to_llm_json(registry, topic=["CM"], priority="MUST"))
        assert {r["id"] for r in data["requirements"]} == {"CM-01-001"}

    @pytest.mark.spec("SR-07-008")
    def test_deps_expand_group_selection(self, registry):
        data = json.loads(
            to_llm_json(registry, groups=["CM-01"], include_deps=True)
        )
        ids = {r["id"] for r in data["requirements"]}
        assert ids == {"CM-01-001", "ARCH-01-002", "ARCH-01-001"}


class TestSlim:
    @pytest.mark.spec("SR-07-012")
    def test_slim_records_have_only_core_fields(self, registry):
        data = json.loads(to_llm_json(registry, topic=["ARCH"], slim=True))
        for rec in data["requirements"]:
            assert set(rec) <= {"id", "priority", "statement", "note"}

    @pytest.mark.spec("SR-07-012")
    def test_slim_keeps_only_internal_edges(self, registry):
        data = json.loads(to_llm_json(registry, topic=["CM"], slim=True))
        # CM-01-001 -> ARCH-01-002 leaves the selection, so it is dropped.
        assert data["edges"] == []
        data = json.loads(to_llm_json(registry, topic=["ARCH"], slim=True))
        assert data["edges"] == [
            {
                "from": "ARCH-01-002",
                "rel_type": "depends_on",
                "to": "ARCH-01-001",
            }
        ]

    @pytest.mark.spec("SR-07-012")
    def test_slim_topics_are_minimal(self, registry):
        data = json.loads(to_llm_json(registry, topic=["ARCH"], slim=True))
        assert data["topics"] == [{"id": "ARCH", "title": "Architecture"}]


class TestIndexText:
    @pytest.mark.spec("SR-07-007")
    def test_index_lists_topics_and_groups_with_counts(self, registry):
        text = to_index_text(registry)
        lines = text.splitlines()
        assert "ARCH  Architecture  (2 reqs)" in lines
        assert "  ARCH-01  Layering (2)" in lines
        assert "CM  Case Management  (2 reqs)" in lines
        assert "  CM-01  Cases (1)" in lines
        assert "  CM-02  Participants (1)" in lines

    @pytest.mark.spec("SR-07-007")
    def test_index_is_narrowed_by_filters(self, registry):
        body = to_index_text(registry, priority="MAY").splitlines()[1:]
        assert body == [
            "CM  Case Management  (1 reqs)",
            "  CM-02  Participants (1)",
        ]


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


class TestCli:
    @pytest.mark.spec("SR-07-007")
    def test_index_flag_prints_plain_text(self, dump_dir, monkeypatch, capsys):
        out = _run(monkeypatch, capsys, "--index", str(dump_dir)).out
        assert out.startswith("#")
        assert "  CM-02  Participants (1)" in out
        with pytest.raises(json.JSONDecodeError):
            json.loads(out)

    @pytest.mark.spec("SR-07-008")
    def test_topic_flag_comma_list(self, dump_dir, monkeypatch, capsys):
        out = _run(
            monkeypatch, capsys, "--topic", "ARCH, CM", str(dump_dir)
        ).out
        assert len(_ids(out)) == 4

    @pytest.mark.spec("SR-07-008")
    def test_group_flag(self, dump_dir, monkeypatch, capsys):
        out = _run(monkeypatch, capsys, "--group", "CM-01", str(dump_dir)).out
        assert _ids(out) == {"CM-01-001"}

    @pytest.mark.spec("SR-07-008")
    def test_ids_with_deps(self, dump_dir, monkeypatch, capsys):
        out = _run(
            monkeypatch, capsys, "--ids", "CM-01-001", "--deps", str(dump_dir)
        ).out
        assert _ids(out) == {"CM-01-001", "ARCH-01-002", "ARCH-01-001"}

    @pytest.mark.spec("SR-07-009")
    def test_tag_scope_priority_passthrough(
        self, dump_dir, monkeypatch, capsys
    ):
        out = _run(monkeypatch, capsys, "--tag", "protocol", str(dump_dir)).out
        assert _ids(out) == {"ARCH-01-001"}
        out = _run(
            monkeypatch, capsys, "--scope", "production", str(dump_dir)
        ).out
        assert _ids(out) == {"CM-01-001", "CM-02-001"}
        out = _run(monkeypatch, capsys, "--priority", "MAY", str(dump_dir)).out
        assert _ids(out) == {"CM-02-001"}

    @pytest.mark.spec("SR-07-010")
    def test_cross_cutting_unions_with_topic(
        self, dump_dir, monkeypatch, capsys
    ):
        out = _run(monkeypatch, capsys, "--cross-cutting", str(dump_dir)).out
        assert _ids(out) == {"ARCH-01-001", "ARCH-01-002"}
        out = _run(
            monkeypatch,
            capsys,
            "--cross-cutting",
            "--group",
            "CM-02",
            str(dump_dir),
        ).out
        assert _ids(out) == {"ARCH-01-001", "ARCH-01-002", "CM-02-001"}

    @pytest.mark.spec("SR-07-010")
    def test_cross_cutting_constant(self):
        assert CROSS_CUTTING_TOPICS == ("ARCH", "CS", "TB", "HP", "SL", "EH")

    @pytest.mark.spec("SR-07-012")
    def test_slim_flag(self, dump_dir, monkeypatch, capsys):
        out = _run(
            monkeypatch, capsys, "--slim", "--topic", "CM", str(dump_dir)
        )
        for rec in json.loads(out.out)["requirements"]:
            assert "rationale" not in rec and "group" not in rec

    @pytest.mark.spec("SR-07-011")
    @pytest.mark.parametrize(
        ("flag", "value"),
        [
            ("--topic", "NOPE"),
            ("--group", "CM-99"),
            ("--ids", "CM-01-999"),
            ("--tag", "not-a-tag"),
            ("--scope", "galaxy"),
            ("--priority", "MAYBE"),
        ],
    )
    def test_unknown_selector_values_exit_2(
        self, dump_dir, monkeypatch, capsys, flag, value
    ):
        assert _exit_code(monkeypatch, flag, value, str(dump_dir)) == 2
        err = capsys.readouterr().err
        assert value in err
        assert "Error" in err

    @pytest.mark.spec("SR-07-011")
    def test_topic_flag_missing_value_exits_2(self, monkeypatch, capsys):
        assert _exit_code(monkeypatch, "--topic") == 2
        assert "--topic requires a value" in capsys.readouterr().err

    @pytest.mark.spec("SR-07-013")
    def test_unfiltered_dump_warns_on_stderr(
        self, dump_dir, monkeypatch, capsys
    ):
        captured = _run(monkeypatch, capsys, str(dump_dir))
        assert len(_ids(captured.out)) == 4
        err_lines = captured.err.strip().splitlines()
        assert len(err_lines) == 1
        assert "--index" in err_lines[0]

    @pytest.mark.spec("SR-07-013")
    def test_filtered_dump_does_not_warn(self, dump_dir, monkeypatch, capsys):
        captured = _run(monkeypatch, capsys, "--topic", "CM", str(dump_dir))
        assert captured.err == ""

    @pytest.mark.spec("SR-07-013")
    def test_index_does_not_warn(self, dump_dir, monkeypatch, capsys):
        assert _run(monkeypatch, capsys, "--index", str(dump_dir)).err == ""
