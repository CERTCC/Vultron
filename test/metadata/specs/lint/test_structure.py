"""Tests for vultron.metadata.specs.lint.structure and the registry hard
errors: duplicate IDs, dangling relationships, prefixes (MS-04-004), missing
kind and scenario_start groups (MS-13-004).
"""

import pytest

from test.metadata.specs._helpers import write_yaml
from test.metadata.specs.conftest import spec_file_data
from test.metadata.specs.lint._helpers import _VERIFIED, _minimal_spec
from vultron.metadata.specs.lint import lint

# ---------------------------------------------------------------------------
# Hard errors
# ---------------------------------------------------------------------------


def test_lint_duplicate_spec_ids(tmp_path):
    data = _minimal_spec("DUP-01-001")
    data["id"] = "DUP"
    data["groups"][0]["id"] = "DUP-01"
    data["groups"][0]["specs"][0]["statement"] = "DUP-01-001 MUST be unique"
    write_yaml(tmp_path, data, "file1.yaml")
    write_yaml(tmp_path, data, "file2.yaml")
    result = lint(tmp_path)
    assert result == 1


def test_lint_dangling_relationship(tmp_path, capsys):
    data = _minimal_spec(
        extra={
            "relationships": [
                {"rel_type": "depends_on", "spec_id": "XX-99-999"}
            ]
        }
    )
    write_yaml(tmp_path, data)
    result = lint(tmp_path)
    captured = capsys.readouterr()
    assert result == 1
    assert "XX-99-999" in captured.err


def _write_linked_pair(tmp_path, a_rel: str, b_rel: str) -> None:
    """Two SHOULD requirements, each naming the other under the given types."""
    write_yaml(
        tmp_path,
        spec_file_data(
            [
                (
                    "TST-01-001",
                    "SHOULD",
                    "project",
                    {
                        "relationships": [
                            {"rel_type": a_rel, "spec_id": "TST-01-002"}
                        ]
                    },
                ),
                (
                    "TST-01-002",
                    "SHOULD",
                    "project",
                    {
                        "relationships": [
                            {"rel_type": b_rel, "spec_id": "TST-01-001"}
                        ]
                    },
                ),
            ]
        ),
    )


@pytest.mark.spec("SR-13-014")
def test_lint_fails_on_a_relationship_loop(tmp_path, capsys):
    _write_linked_pair(tmp_path, "depends_on", "depends_on")

    result = lint(tmp_path)

    assert result == 1
    assert (
        "Relationship loop among TST-01-001, TST-01-002"
        in capsys.readouterr().err
    )


@pytest.mark.spec("SR-13-012")
@pytest.mark.spec("SR-13-015")
def test_lint_fails_on_a_link_recorded_at_both_ends(tmp_path, capsys):
    # refines one way and constrains the other point the same way: no loop.
    _write_linked_pair(tmp_path, "refines", "constrains")

    result = lint(tmp_path)

    err = capsys.readouterr().err
    assert result == 1
    assert "Relationship loop" not in err
    assert (
        "TST-01-001 and TST-01-002 each record a relationship naming the other"
        in err
    )


def test_lint_prefix_mismatch(tmp_path, capsys):
    data = {
        "id": "TST",
        "title": "Test File",
        "description": "Prefix mismatch test",
        "scope": ["production"],
        "groups": [
            {
                "id": "OTHER-01",  # prefix "OTHER" != file id "TST"
                "title": "Wrong Group",
                "specs": [
                    {
                        "id": "OTHER-01-001",
                        "priority": "MUST",
                        "kind": "protocol",
                        "statement": "OTHER-01-001 MUST be consistent",
                        "rationale": "Consistency",
                        "tags": ["testing"],
                    }
                ],
            }
        ],
    }
    write_yaml(tmp_path, data)
    result = lint(tmp_path)
    captured = capsys.readouterr()
    assert result == 1
    assert "OTHER-01" in captured.err


# ---------------------------------------------------------------------------
# Spec ID vs group prefix check (MS-04-004)
# ---------------------------------------------------------------------------


def test_lint_spec_id_prefix_mismatch(tmp_path, capsys):
    """A spec with ID TST-01-001 living in group TST-02 must be a hard error."""
    data = {
        "id": "TST",
        "title": "Test File",
        "description": "Spec ID prefix mismatch test",
        "scope": ["production"],
        "groups": [
            {
                "id": "TST-02",
                "title": "Group Two",
                "specs": [
                    {
                        "id": "TST-01-001",  # prefix TST-01 != group TST-02
                        "priority": "MUST",
                        "kind": "protocol",
                        "statement": "TST-01-001 MUST be in group TST-01",
                        "rationale": "Prefix consistency",
                        "tags": ["testing"],
                    }
                ],
            }
        ],
    }
    write_yaml(tmp_path, data)
    result = lint(tmp_path)
    captured = capsys.readouterr()
    assert result == 1
    assert "TST-01-001" in captured.err
    assert "TST-02" in captured.err


def test_lint_spec_id_prefix_match_passes(tmp_path, capsys):
    """A spec ID whose prefix matches its group must not produce an error."""
    data = _minimal_spec("TST-01-001")  # lives in group TST-01 — correct
    write_yaml(tmp_path, data)
    result = lint(tmp_path)
    captured = capsys.readouterr()
    assert result == 0
    assert "TST-01-001" not in captured.err


# ---------------------------------------------------------------------------
# Missing item-level kind is a hard error
# ---------------------------------------------------------------------------


def test_lint_missing_item_kind_is_hard_error(tmp_path):
    """A spec item missing kind: is a hard error (exit 1)."""
    data = _minimal_spec()
    del data["groups"][0]["specs"][0]["kind"]
    write_yaml(tmp_path, data)
    result = lint(tmp_path)
    assert result == 1


# ---------------------------------------------------------------------------
# scenario_start group must contain a BehavioralSpec with steps (MS-13-004)
# ---------------------------------------------------------------------------


def _scenario_start_group(with_behavioral_spec: bool):
    """Return a minimal spec file with one scenario_start group.

    When ``with_behavioral_spec`` is True the group contains a BehavioralSpec
    item with steps; otherwise it contains only a StatementSpec item.
    """
    if with_behavioral_spec:
        workflow_item = {
            "id": "SCN-01-002",
            "priority": "MUST",
            "kind": "project",
            "statement": "SCN-01-002 MUST execute the scenario workflow",
            "rationale": "ECA required",
            "verification": _VERIFIED,
            "tags": ["demo"],
            "preconditions": [{"description": "Actors running"}],
            "steps": [
                {"order": 1, "actor": "finder", "action": "Submit report"}
            ],
            "postconditions": [{"description": "Case created"}],
        }
    else:
        workflow_item = {
            "id": "SCN-01-002",
            "priority": "MUST",
            "kind": "project",
            "statement": "SCN-01-002 MUST reach final state VFDPxa",
            "rationale": "Terminal state required",
            "verification": _VERIFIED,
            "tags": ["demo"],
        }

    return {
        "id": "SCN",
        "title": "Scenario Spec",
        "description": "Scenario spec file",
        "scope": ["prototype"],
        "groups": [
            {
                "id": "SCN-01",
                "title": "rv Scenario",
                "trigger": {"type": "scenario_start", "value": "rv"},
                "specs": [
                    {
                        "id": "SCN-01-001",
                        "priority": "MUST",
                        "kind": "project",
                        "statement": "SCN-01-001 MUST reach VFDPxa",
                        "rationale": "Terminal state",
                        "verification": _VERIFIED,
                        "tags": ["demo"],
                    },
                    workflow_item,
                ],
            }
        ],
    }


def test_scenario_start_with_behavioral_spec_passes(tmp_path, capsys):
    """scenario_start group with a BehavioralSpec+steps item must pass."""
    write_yaml(tmp_path, _scenario_start_group(with_behavioral_spec=True))
    result = lint(tmp_path)
    captured = capsys.readouterr()
    assert result == 0
    assert "MS-13-004" not in captured.err


def test_scenario_start_without_behavioral_spec_fails(tmp_path, capsys):
    """scenario_start group with only StatementSpec items must be a hard error."""
    write_yaml(tmp_path, _scenario_start_group(with_behavioral_spec=False))
    result = lint(tmp_path)
    captured = capsys.readouterr()
    assert result == 1
    assert "SCN-01" in captured.err
    assert "MS-13-004" in captured.err


def test_non_scenario_start_group_not_checked(tmp_path, capsys):
    """Groups without a scenario_start trigger are not subject to MS-13-004."""
    data = _minimal_spec()  # no trigger on group TST-01
    write_yaml(tmp_path, data)
    result = lint(tmp_path)
    captured = capsys.readouterr()
    assert result == 0
    assert "MS-13-004" not in captured.err
