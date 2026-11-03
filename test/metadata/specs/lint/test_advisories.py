"""Tests for vultron.metadata.specs.lint.advisories: advisory warnings,
lint_suppress, and missing_story_reference (SR-11).
"""

import pytest

from test.metadata.specs._helpers import write_yaml
from test.metadata.specs.lint._helpers import (
    _minimal_spec,
    _minimal_spec_no_stories,
)
from vultron.metadata.specs.lint import lint

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
def test_protocol_must_not_no_stories_is_not_a_hard_error(tmp_path, capsys):
    """SR-11-003 is MUST-only for now — the recorded MS-02-003 exception —
    so a story-less protocol MUST_NOT neither hard-errors nor warns."""
    write_yaml(tmp_path, _minimal_spec_no_stories(priority="MUST_NOT"))
    result = lint(tmp_path)
    captured = capsys.readouterr()
    assert result == 0
    assert "missing_story_reference" not in captured.err
    assert "missing_story_reference" not in _without_suppression_totals(
        captured.out
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
