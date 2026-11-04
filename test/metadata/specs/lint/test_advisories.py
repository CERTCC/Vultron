"""Tests for vultron.metadata.specs.lint.advisories: advisory warnings,
lint_suppress, and missing_story_reference (SR-11).
"""

import pytest

from test.metadata.specs._helpers import write_yaml
from test.metadata.specs.lint._helpers import (
    _minimal_spec,
    _minimal_spec_no_stories,
)
from vultron.metadata.specs.lint import lint, sr_11_003_gate_applies
from vultron.metadata.specs.schema import RFC2119Priority, SpecKind

# ---------------------------------------------------------------------------
# Advisory warnings (non-blocking — return 0)
# ---------------------------------------------------------------------------


def test_lint_advisory_testable_without_steps(tmp_path, capsys):
    data = _minimal_spec(extra={"testable": False})
    write_yaml(tmp_path, data)
    result = lint(tmp_path)
    captured = capsys.readouterr()
    assert result == 0
    assert "[WARN]" in captured.out
    assert "testable=false" in captured.out


def test_lint_advisory_rationale_too_long(tmp_path, capsys):
    data = _minimal_spec(extra={"rationale": "x" * 501})
    write_yaml(tmp_path, data)
    result = lint(tmp_path)
    captured = capsys.readouterr()
    assert result == 0
    assert "[WARN]" in captured.out
    assert "rationale" in captured.out


def test_lint_advisory_missing_tags(tmp_path, capsys):
    data = _minimal_spec()
    del data["groups"][0]["specs"][0]["tags"]
    write_yaml(tmp_path, data)
    result = lint(tmp_path)
    captured = capsys.readouterr()
    assert result == 0
    assert "[WARN]" in captured.out
    assert "tags" in captured.out


# ---------------------------------------------------------------------------
# lint_suppress suppression
# ---------------------------------------------------------------------------


def test_lint_suppress_testable_without_steps(tmp_path, capsys):
    data = _minimal_spec(
        extra={
            "testable": False,
            "lint_suppress": ["testable_without_steps"],
        }
    )
    write_yaml(tmp_path, data)
    result = lint(tmp_path)
    captured = capsys.readouterr()
    assert result == 0
    assert "testable=false" not in captured.out


def test_lint_suppress_rationale_too_long(tmp_path, capsys):
    data = _minimal_spec(
        extra={
            "rationale": "x" * 501,
            "lint_suppress": ["rationale_too_long"],
        }
    )
    write_yaml(tmp_path, data)
    result = lint(tmp_path)
    captured = capsys.readouterr()
    assert result == 0
    assert "rationale exceeds" not in captured.out


def test_lint_suppress_missing_tags(tmp_path, capsys):
    data = _minimal_spec()
    del data["groups"][0]["specs"][0]["tags"]
    data["groups"][0]["specs"][0]["lint_suppress"] = ["missing_tags"]
    write_yaml(tmp_path, data)
    result = lint(tmp_path)
    captured = capsys.readouterr()
    assert result == 0
    assert "no tags" not in captured.out


def test_protocol_must_no_stories_is_hard_error(tmp_path, capsys):
    """kind=protocol + priority=MUST + no stories: is a hard error (SR-11-003)."""
    write_yaml(tmp_path, _minimal_spec_no_stories(priority="MUST"))
    result = lint(tmp_path)
    captured = capsys.readouterr()
    assert result == 1
    assert "SR-11-003" in captured.err
    assert "missing_story_reference" in captured.err


def test_protocol_must_with_stories_passes(tmp_path, capsys):
    """kind=protocol + priority=MUST with a stories: entry does not hard-error."""
    data = _minimal_spec_no_stories(priority="MUST")
    data["groups"][0]["specs"][0]["stories"] = ["story_2022_001"]
    write_yaml(tmp_path, data)
    result = lint(tmp_path)
    captured = capsys.readouterr()
    assert result == 0
    assert "SR-11-003" not in captured.err


@pytest.mark.spec("SR-11-007")
def test_protocol_must_suppress_missing_story_reference(tmp_path, capsys):
    """lint_suppress: [missing_story_reference] silences the SR-11-003 hard error."""
    data = _minimal_spec_no_stories(priority="MUST")
    data["groups"][0]["specs"][0]["lint_suppress"] = [
        "missing_story_reference"
    ]
    write_yaml(tmp_path, data)
    result = lint(tmp_path)
    captured = capsys.readouterr()
    assert result == 0
    assert "SR-11-003" not in captured.err


def test_non_protocol_must_no_stories_no_hard_error(tmp_path, capsys):
    """kind=architecture + priority=MUST with no stories does NOT hard-error."""
    write_yaml(
        tmp_path,
        _minimal_spec_no_stories(priority="MUST", kind="architecture"),
    )
    result = lint(tmp_path)
    captured = capsys.readouterr()
    assert result == 0
    assert "SR-11-003" not in captured.err


def test_protocol_should_no_stories_is_advisory(tmp_path, capsys):
    """kind=protocol + priority=SHOULD + no stories emits advisory [WARN] (SR-11-004)."""
    write_yaml(tmp_path, _minimal_spec_no_stories(priority="SHOULD"))
    result = lint(tmp_path)
    captured = capsys.readouterr()
    assert result == 0
    assert "[WARN]" in captured.out
    assert "missing_story_reference" in captured.out


def test_protocol_may_no_stories_is_advisory(tmp_path, capsys):
    """kind=protocol + priority=MAY + no stories emits advisory [WARN] (SR-11-004)."""
    write_yaml(tmp_path, _minimal_spec_no_stories(priority="MAY"))
    result = lint(tmp_path)
    captured = capsys.readouterr()
    assert result == 0
    assert "[WARN]" in captured.out
    assert "missing_story_reference" in captured.out


@pytest.mark.spec("SR-11-004")
def test_protocol_should_not_no_stories_is_advisory(tmp_path, capsys):
    """kind=protocol + priority=SHOULD_NOT + no stories emits advisory [WARN]
    (SR-11-004 — SHOULD_NOT is the SHOULD tier, MS-02-003)."""
    write_yaml(tmp_path, _minimal_spec_no_stories(priority="SHOULD_NOT"))
    result = lint(tmp_path)
    captured = capsys.readouterr()
    assert result == 0
    assert "[WARN]" in captured.out
    assert "missing_story_reference" in captured.out
    assert "priority=SHOULD_NOT" in captured.out


def _without_suppression_totals(out: str) -> str:
    """*out* minus the ``[INFO] lint_suppress …`` totals spec-lint prints.

    Those totals name the suppression code on every run (MS-12-007), so a
    test asserting that no warning names the code must look past them.
    """
    return "\n".join(
        line
        for line in out.splitlines()
        if not line.startswith("[INFO] lint_suppress ")
    )


@pytest.mark.spec("SR-11-003")
def test_protocol_must_not_no_stories_is_hard_error(tmp_path, capsys):
    """SR-11-003 covers the whole MUST tier (MS-02-003), so a story-less
    protocol MUST_NOT is a hard error too."""
    write_yaml(tmp_path, _minimal_spec_no_stories(priority="MUST_NOT"))
    result = lint(tmp_path)
    captured = capsys.readouterr()
    assert result == 1
    assert "SR-11-003" in captured.err
    assert "priority=MUST_NOT" in captured.err
    assert "missing_story_reference" in captured.err


@pytest.mark.spec("SR-11-003")
def test_protocol_must_not_with_stories_passes(tmp_path, capsys):
    """A protocol MUST_NOT with a stories: entry does not hard-error."""
    data = _minimal_spec_no_stories(priority="MUST_NOT")
    data["groups"][0]["specs"][0]["stories"] = ["story_2022_001"]
    write_yaml(tmp_path, data)
    result = lint(tmp_path)
    captured = capsys.readouterr()
    assert result == 0
    assert "SR-11-003" not in captured.err


@pytest.mark.parametrize(
    ("kind", "priority", "expected"),
    [
        ("protocol", "MUST", True),
        ("protocol", "MUST_NOT", True),
        ("protocol", "SHOULD", False),
        ("protocol", "SHOULD_NOT", False),
        ("protocol", "MAY", False),
        ("architecture", "MUST", False),
        ("architecture", "MUST_NOT", False),
    ],
)
@pytest.mark.spec("SR-11-003")
def test_sr_11_003_gate_applies_selects_protocol_must_tier(
    kind, priority, expected
):
    """The gate's scope is the protocol MUST tier, MUST and MUST_NOT alike."""
    assert (
        sr_11_003_gate_applies(SpecKind(kind), RFC2119Priority(priority))
        is expected
    )


def test_protocol_should_with_stories_no_story_warn(tmp_path, capsys):
    """kind=protocol + priority=SHOULD with stories: does not emit advisory."""
    data = _minimal_spec_no_stories(priority="SHOULD")
    data["groups"][0]["specs"][0]["stories"] = ["story_2022_042"]
    write_yaml(tmp_path, data)
    result = lint(tmp_path)
    captured = capsys.readouterr()
    assert result == 0
    assert "missing_story_reference" not in _without_suppression_totals(
        captured.out
    )


@pytest.mark.spec("SR-11-008")
def test_protocol_should_suppress_advisory_story_warn(tmp_path, capsys):
    """lint_suppress: [missing_story_reference] silences the SHOULD advisory."""
    data = _minimal_spec_no_stories(priority="SHOULD")
    data["groups"][0]["specs"][0]["lint_suppress"] = [
        "missing_story_reference"
    ]
    write_yaml(tmp_path, data)
    result = lint(tmp_path)
    captured = capsys.readouterr()
    assert result == 0
    assert "missing_story_reference" not in _without_suppression_totals(
        captured.out
    )


# ---------------------------------------------------------------------------
# SR-11-009: per-file advisory for project/process requirements with no stories
# ---------------------------------------------------------------------------


def _story_less_spec(spec_id, kind, stories=None):
    """One SHOULD requirement of *kind*, citing *stories* when given."""
    spec = {
        "id": spec_id,
        "priority": "SHOULD",
        "kind": kind,
        "statement": f"{spec_id} SHOULD do the thing",
        "rationale": "Because testing",
        "tags": ["testing"],
    }
    if stories:
        spec["stories"] = stories
    return spec


def _spec_file(file_id, *specs):
    return {
        "id": file_id,
        "title": f"{file_id} File",
        "description": "Test spec file",
        "scope": ["production"],
        "groups": [
            {"id": f"{file_id}-01", "title": "Group", "specs": list(specs)}
        ],
    }


def _advisory_lines(out):
    return [ln for ln in out.splitlines() if "no_project_process_story" in ln]


@pytest.mark.spec("SR-11-009")
def test_project_no_story_advisory_per_file(tmp_path, capsys):
    """One summary line per file, counting only its story-less
    project/process requirements (SR-11-009)."""
    write_yaml(
        tmp_path,
        _spec_file(
            "TST",
            _story_less_spec("TST-01-001", "project"),
            _story_less_spec("TST-01-002", "process"),
            _story_less_spec("TST-01-003", "project", ["story_2022_001"]),
        ),
        "tst.yaml",
    )
    write_yaml(
        tmp_path,
        _spec_file("TSU", _story_less_spec("TSU-01-001", "process")),
        "tsu.yaml",
    )
    lint(tmp_path)
    lines = _advisory_lines(capsys.readouterr().out)
    assert len(lines) == 2
    tst = next(ln for ln in lines if "TST (" in ln)
    tsu = next(ln for ln in lines if "TSU (" in ln)
    assert tst.startswith("[INFO] no_project_process_story: ")
    assert ": 2 project/process requirement(s)" in tst
    assert ": 1 project/process requirement(s)" in tsu


@pytest.mark.spec("SR-11-009")
def test_project_no_story_advisory_list_ids_opt_in(tmp_path, capsys):
    """The opt-in flag lists the IDs under the summary line (SR-11-009)."""
    write_yaml(
        tmp_path,
        _spec_file(
            "TST",
            _story_less_spec("TST-01-002", "process"),
            _story_less_spec("TST-01-001", "project"),
        ),
    )
    lint(tmp_path, list_no_story_ids=True)
    lines = capsys.readouterr().out.splitlines()
    at = next(
        i for i, ln in enumerate(lines) if "no_project_process_story" in ln
    )
    assert lines[at + 1 : at + 3] == ["    TST-01-001", "    TST-01-002"]


@pytest.mark.spec("SR-11-009")
def test_project_no_story_advisory_ids_hidden_by_default(tmp_path, capsys):
    """Without the opt-in flag the IDs do not appear (SR-11-009)."""
    write_yaml(
        tmp_path, _spec_file("TST", _story_less_spec("TST-01-001", "project"))
    )
    lint(tmp_path)
    out = capsys.readouterr().out
    assert _advisory_lines(out)
    assert "TST-01-001" not in out


@pytest.mark.spec("SR-11-009")
@pytest.mark.parametrize("kind", ["protocol", "architecture"])
def test_protocol_architecture_excluded_from_project_story_advisory(
    tmp_path, capsys, kind
):
    """Story-less protocol and architecture requirements are not counted
    (SR-11-009)."""
    write_yaml(
        tmp_path, _spec_file("TST", _story_less_spec("TST-01-001", kind))
    )
    lint(tmp_path, list_no_story_ids=True)
    assert _advisory_lines(capsys.readouterr().out) == []


@pytest.mark.spec("SR-11-009")
def test_project_process_story_advisory_exit_code_unaffected(tmp_path, capsys):
    """The exit code stays 0 when only this advisory fires (SR-11-009)."""
    write_yaml(
        tmp_path, _spec_file("TST", _story_less_spec("TST-01-001", "project"))
    )
    result = lint(tmp_path, list_no_story_ids=True)
    captured = capsys.readouterr()
    assert _advisory_lines(captured.out)
    assert "[ERROR]" not in captured.err
    assert result == 0


@pytest.mark.spec("SR-11-009")
def test_project_no_story_advisory_silent_when_stories_present(
    tmp_path, capsys
):
    """No advisory line when every project/process requirement cites a
    story (SR-11-009)."""
    write_yaml(
        tmp_path,
        _spec_file(
            "TST",
            _story_less_spec("TST-01-001", "project", ["story_2022_001"]),
        ),
    )
    lint(tmp_path)
    assert _advisory_lines(capsys.readouterr().out) == []
