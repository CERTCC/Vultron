#!/usr/bin/env python

#  Copyright (c) 2026 Carnegie Mellon University and Contributors.
#  - see Contributors.md for a full list of Contributors
#  - see ContributionInstructions.md for information on how you can Contribute to this project
#  Vultron Multiparty Coordinated Vulnerability Disclosure Protocol Prototype is
#  licensed under a MIT (SEI)-style license, please see LICENSE.md distributed
#  with this Software or contact permission@sei.cmu.edu for full terms.
#  Created, in part, with funding and support from the United States Government
#  (see Acknowledgments file). This program may include and/or can make use of
#  certain third party source code, object code, documentation and other files
#  ("Third Party Software"). See LICENSE.md for more details.
#  Carnegie Mellon®, CERT® and CERT Coordination Center® are registered in the
#  U.S. Patent and Trademark Office by Carnegie Mellon University

"""Drift and shape tests for the scenario-tree index (DEMOCI-11-016).

``vultron/metadata/demo_scenarios/export_tree.py`` writes
``ui/src/data/scenario_tree.json`` from the branch-point table, the
``@scenario`` paths and the committed recordings.  These tests fail when the
committed index no longer matches a fresh export, and check the shape the
spec names: the branch-point table, one root whose descendants include every
scenario's ending, and one entry per scenario with its recordings keyed by
actor and then by case.

To fix a drift failure here::

    uv run export-demo-tree
    git add ui/src/data/scenario_tree.json
"""

import json
import re
from pathlib import Path
from typing import Any

import pytest
import yaml

from vultron.demo.recordings.layout import RECORDINGS_DIR, recording_path
from vultron.demo.scenario.branch_points import (
    BRANCH_POINTS,
    BranchPoint,
    Choice,
    build_branch_point_table,
)
from vultron.demo.scenario.registry import discover_scenarios
from vultron.demo.scenario.tree import TreeNode
from vultron.enums.roles import CVDRole
from vultron.errors import DemoRecordingError, DemoScenarioRegistryError
from vultron.metadata.demo_scenarios import export_tree
from vultron.metadata.demo_scenarios.export_states import REPO_ROOT
from vultron.metadata.demo_scenarios.export_tree import (
    OUTPUT_PATH,
    REGEN_COMMAND,
    UI_SRC_DIR,
    build_payload,
    recording_files,
    stale_hint,
    tree_node,
)
from vultron.metadata.generated_files import read_committed, serialize_json

ARTIFACT = "ui/src/data/scenario_tree.json"


def _endings(node: dict[str, Any]) -> list[str]:
    """Every scenario name at or below *node*, depth first."""
    if "scenario" in node:
        return [node["scenario"]]
    return [
        name for child in node["choices"].values() for name in _endings(child)
    ]


def _path_to(node: dict[str, Any], name: str) -> list[dict[str, str]] | None:
    """The ``(branch point, choice)`` steps from *node* to *name*'s ending."""
    if node.get("scenario") == name:
        return []
    for choice_id, child in node.get("choices", {}).items():
        rest = _path_to(child, name)
        if rest is not None:
            return [
                {"branch_point": node["branch_point"], "choice": choice_id},
                *rest,
            ]
    return None


@pytest.fixture(scope="module")
def payload() -> dict[str, Any]:
    return build_payload()


# ---------------------------------------------------------------------------
# Drift (DEMOCI-11-005)
# ---------------------------------------------------------------------------


def test_artifact_path_is_the_one_the_hint_names() -> None:
    assert OUTPUT_PATH.as_posix().endswith(ARTIFACT)


def test_committed_index_matches_a_fresh_export() -> None:
    # read_committed keeps line endings, so a CRLF copy fails here too.
    committed = read_committed(OUTPUT_PATH)
    assert committed == serialize_json(build_payload()), stale_hint(
        OUTPUT_PATH
    )


def test_stale_hint_names_the_regeneration_command_and_path() -> None:
    hint = stale_hint(OUTPUT_PATH)
    assert f"`{REGEN_COMMAND}`" in hint
    assert REGEN_COMMAND == "uv run export-demo-tree"
    assert ARTIFACT in hint


def test_check_passes_on_the_committed_index() -> None:
    export_tree.main(["--check"])


@pytest.mark.parametrize(
    "stale",
    [None, "{}\n", "edited by hand", "crlf"],
    ids=["missing", "stale", "hand-edited", "crlf"],
)
def test_check_fails_on_a_stale_index_and_names_the_command(
    stale: str | None, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "scenario_tree.json"
    if stale == "crlf":
        fresh = serialize_json(build_payload())
        stale = fresh.replace("\n", "\r\n")
    if stale is not None:
        target.write_bytes(stale.encode("utf-8"))
    monkeypatch.setattr(export_tree, "OUTPUT_PATH", target)
    with pytest.raises(SystemExit) as excinfo:
        export_tree.main(["--check"])
    message = str(excinfo.value.code)
    assert REGEN_COMMAND in message
    assert str(target) in message
    if stale is not None:
        assert target.read_bytes().decode("utf-8") == stale


def test_write_mode_writes_a_fresh_export(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "data" / "scenario_tree.json"
    monkeypatch.setattr(export_tree, "OUTPUT_PATH", target)
    monkeypatch.setattr(export_tree, "REPO_ROOT", tmp_path)
    export_tree.main([])
    assert target.read_bytes().decode("utf-8") == serialize_json(
        build_payload()
    )
    export_tree.main(["--check"])


def test_pre_commit_runs_the_check() -> None:
    config = yaml.safe_load(
        (REPO_ROOT / ".pre-commit-config.yaml").read_text(encoding="utf-8")
    )
    hooks = {
        hook["id"]: hook for repo in config["repos"] for hook in repo["hooks"]
    }
    hook = hooks["demo-tree-sync"]
    assert hook["entry"] == f"{REGEN_COMMAND} --check"
    # Every module the export reads or renders through, the recordings and
    # the index itself.
    for watched in (
        "vultron/demo/scenario/branch_points.py",
        "vultron/demo/scenario/registry.py",
        "vultron/demo/scenario/tree.py",
        "vultron/demo/scenario/rv_demo.py",
        "vultron/demo/recordings/layout.py",
        "vultron/enums/roles.py",
        "vultron/metadata/demo_scenarios/export_tree.py",
        "vultron/metadata/demo_scenarios/export_states.py",
        "vultron/metadata/generated_files.py",
        "ui/src/recordings/rv/case-actor.jsonl",
        ARTIFACT,
    ):
        assert re.match(hook["files"], watched), watched


# ---------------------------------------------------------------------------
# Shape (DEMOCI-11-016)
# ---------------------------------------------------------------------------


def test_index_has_the_documented_top_level_keys(
    payload: dict[str, Any],
) -> None:
    assert list(payload) == ["_README", "branch_points", "tree", "scenarios"]
    assert "Do not edit by hand" in payload["_README"]
    assert REGEN_COMMAND in payload["_README"]


def test_index_carries_the_branch_point_table(payload: dict[str, Any]) -> None:
    assert list(payload["branch_points"]) == list(BRANCH_POINTS)
    assert payload["branch_points"]["vendor-join"] == {
        "role": "vendor",
        "prompt": "As the Vendor, choose whether to join the case.",
        "choices": [
            {
                "id": "reject",
                "label": "Reject the invite",
                "trigger": "reject-case-invite",
            },
            {
                "id": "accept",
                "label": "Accept the invite",
                "trigger": "accept-case-invite",
            },
        ],
    }
    for branch_point_id, row in payload["branch_points"].items():
        branch_point = BRANCH_POINTS[branch_point_id]
        assert row["role"] == branch_point.role.value
        assert row["prompt"] == branch_point.prompt
        assert [c["id"] for c in row["choices"]] == [
            c.id for c in branch_point.choices
        ]


def test_one_root_whose_endings_are_every_scenario_once(
    payload: dict[str, Any],
) -> None:
    names = [spec.name for spec in discover_scenarios()]
    endings = _endings(payload["tree"])
    assert sorted(endings) == sorted(names)
    assert len(endings) == len(set(endings))


def test_every_interior_node_follows_the_branch_point_table(
    payload: dict[str, Any],
) -> None:
    def check(node: dict[str, Any]) -> None:
        if "scenario" in node:
            assert set(node) == {"scenario"}
            return
        assert set(node) == {"branch_point", "choices"}
        table_order = [
            c.id for c in BRANCH_POINTS[node["branch_point"]].choices
        ]
        taken = list(node["choices"])
        assert taken, node["branch_point"]
        assert taken == [c for c in table_order if c in taken]
        for child in node["choices"].values():
            check(child)

    check(payload["tree"])


def test_one_entry_per_scenario_with_label_and_path(
    payload: dict[str, Any],
) -> None:
    specs = discover_scenarios()
    assert list(payload["scenarios"]) == [spec.name for spec in specs]
    for spec in specs:
        row = payload["scenarios"][spec.name]
        assert set(row) == {"label", "path", "recordings"}
        assert row["label"] == spec.label
        assert row["path"] == [
            {"branch_point": bp, "choice": choice} for bp, choice in spec.path
        ]
        assert _path_to(payload["tree"], spec.name) == row["path"]


def test_recordings_are_keyed_by_actor_then_case(
    payload: dict[str, Any],
) -> None:
    for name, row in payload["scenarios"].items():
        recordings = row["recordings"]
        assert recordings, name
        for actor, by_case in recordings.items():
            assert by_case, (name, actor)
            for case_id, rel_path in by_case.items():
                assert case_id.startswith("urn:uuid:"), case_id
                file = UI_SRC_DIR / rel_path
                assert file.is_file(), rel_path
                assert file.name == f"{actor}.jsonl"
                case_ids = {
                    json.loads(line)["caseId"]
                    for line in file.read_text(encoding="utf-8").splitlines()
                }
                assert case_id in case_ids
    rv = payload["scenarios"]["rv"]["recordings"]
    assert list(rv) == ["case-actor"]
    assert list(rv["case-actor"].values()) == [
        recording_path("rv").relative_to(UI_SRC_DIR).as_posix()
    ]


# ---------------------------------------------------------------------------
# Recording files, on fixture directories
# ---------------------------------------------------------------------------


def _write(path: Path, *entries: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(entry) + "\n" for entry in entries),
        encoding="utf-8",
    )


def test_a_file_holding_two_cases_is_listed_under_each_in_order(
    tmp_path: Path,
) -> None:
    _write(
        tmp_path / "split" / "case-actor.jsonl",
        {"caseId": "urn:uuid:b", "logIndex": 0},
        {"caseId": "urn:uuid:a", "logIndex": 0},
        {"caseId": "urn:uuid:b", "logIndex": 1},
    )
    _write(
        tmp_path / "split" / "vendor.jsonl",
        {"caseId": "urn:uuid:a", "logIndex": 0},
    )
    (tmp_path / "split" / "notes.txt").write_text("ignored", encoding="utf-8")
    files = recording_files("split", tmp_path, tmp_path)
    assert files == {
        "case-actor": {
            "urn:uuid:b": "split/case-actor.jsonl",
            "urn:uuid:a": "split/case-actor.jsonl",
        },
        "vendor": {"urn:uuid:a": "split/vendor.jsonl"},
    }
    assert list(files["case-actor"]) == ["urn:uuid:b", "urn:uuid:a"]


def test_a_scenario_without_a_recording_is_refused(tmp_path: Path) -> None:
    with pytest.raises(DemoRecordingError, match="export-demo-recordings"):
        recording_files("absent", tmp_path, tmp_path)
    (tmp_path / "empty-dir").mkdir()
    with pytest.raises(DemoRecordingError, match="no recording"):
        recording_files("empty-dir", tmp_path, tmp_path)


@pytest.mark.parametrize(
    "line",
    ["not json", '{"logIndex": 0}', '{"caseId": ""}', '{"caseId": 7}', "[]"],
    ids=[
        "not-json",
        "no-case-id",
        "empty-case-id",
        "non-string",
        "not-object",
    ],
)
def test_a_line_without_a_case_id_is_refused(
    line: str, tmp_path: Path
) -> None:
    path = tmp_path / "bad" / "case-actor.jsonl"
    path.parent.mkdir()
    path.write_text(line + "\n", encoding="utf-8")
    with pytest.raises(DemoRecordingError, match="line 1"):
        recording_files("bad", tmp_path, tmp_path)


def test_an_empty_recording_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "blank" / "case-actor.jsonl"
    path.parent.mkdir()
    path.write_text("", encoding="utf-8")
    with pytest.raises(DemoRecordingError, match="no ledger entry"):
        recording_files("blank", tmp_path, tmp_path)


def test_an_empty_registry_has_no_tree(tmp_path: Path) -> None:
    with pytest.raises(DemoScenarioRegistryError, match="neither"):
        build_payload(specs=(), recordings_dir=tmp_path, relative_to=tmp_path)


def test_the_committed_recordings_are_the_ones_listed(
    payload: dict[str, Any],
) -> None:
    listed = {
        (UI_SRC_DIR / rel_path).resolve()
        for row in payload["scenarios"].values()
        for by_case in row["recordings"].values()
        for rel_path in by_case.values()
    }
    committed = {path.resolve() for path in RECORDINGS_DIR.glob("*/*.jsonl")}
    assert listed == committed


# ---------------------------------------------------------------------------
# Tree nodes, on fixture tables
# ---------------------------------------------------------------------------

_FIXTURE_TABLE = build_branch_point_table(
    (
        BranchPoint(
            id="fork",
            role=CVDRole.VENDOR,
            prompt="As the Vendor, choose.",
            choices=(
                Choice(id="a", label="Do A", trigger="notify-fix-ready"),
                Choice(id="b", label="Do B", trigger="notify-published"),
            ),
        ),
    )
)


def _fork(*choices: str, branch_point: str = "fork") -> TreeNode:
    root = TreeNode(prefix=(), branch_point=branch_point)
    for choice in choices:
        root.children[choice] = TreeNode(
            prefix=((branch_point, choice),), scenario=f"s-{choice}"
        )
    return root


def test_tree_node_orders_choices_by_the_table() -> None:
    node = tree_node(_fork("b", "a"), _FIXTURE_TABLE)
    assert list(node["choices"]) == ["a", "b"]
    assert node["choices"]["b"] == {"scenario": "s-b"}


def test_tree_node_refuses_a_choice_the_table_does_not_list() -> None:
    with pytest.raises(DemoScenarioRegistryError, match="'c'"):
        tree_node(_fork("a", "c"), _FIXTURE_TABLE)


def test_tree_node_refuses_an_unknown_branch_point() -> None:
    with pytest.raises(DemoScenarioRegistryError, match="'elsewhere'"):
        tree_node(_fork("a", branch_point="elsewhere"), _FIXTURE_TABLE)
