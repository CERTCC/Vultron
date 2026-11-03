"""Tests for the kind_classification checks the linter wires in:
protocol_kind_with_code_reference (MS-12-006) and foundation standard tags
(MS-12-018, MS-12-019).
"""

import pytest

from test.metadata.specs._helpers import write_yaml
from test.metadata.specs.lint._helpers import (
    _minimal_spec_no_stories,
    _repo_with_specs,
)
from vultron.metadata.specs.lint import lint

# ---------------------------------------------------------------------------
# MS-12-006: protocol_kind_with_code_reference — hard error, story-bearing
# exemption, suppression path, and the tiers SR-11-003 does not reach
# ---------------------------------------------------------------------------


def _protocol_spec_naming_code(
    tmp_path,
    *,
    field="statement",
    text=None,
    priority="MUST",
    kind="protocol",
):
    """Return (spec_dir, data): a story-less spec whose *field* names a real
    ``test/`` file inside the fake repo, so only MS-12-006 can fire on it.

    *field* defaults to ``statement``, the one field MS-12-006 scans."""
    repo, spec_dir = _repo_with_specs(tmp_path)
    (repo / "test" / "test_thing.py").write_text("")
    data = _minimal_spec_no_stories(priority=priority, kind=kind)
    data["groups"][0]["specs"][0][field] = (
        text or "The transition MUST be driven by `test/test_thing.py`."
    )
    return spec_dir, data


def _ms12_lines(captured_err: str) -> list[str]:
    return [line for line in captured_err.splitlines() if "MS-12-006" in line]


def test_protocol_no_stories_code_reference_is_hard_error(tmp_path, capsys):
    """kind=protocol, no stories:, statement names test/…py → exit 1 (MS-12-006)."""
    spec_dir, data = _protocol_spec_naming_code(tmp_path)
    data["groups"][0]["specs"][0]["lint_suppress"] = [
        "missing_story_reference"
    ]
    write_yaml(spec_dir, data)
    result = lint(spec_dir)
    captured = capsys.readouterr()
    assert result == 1
    lines = _ms12_lines(captured.err)
    assert len(lines) == 1
    assert "TST-01-001" in lines[0]
    assert "its statement" in lines[0]
    assert "test/test_thing.py" in lines[0]
    assert "protocol_kind_with_code_reference" in lines[0]


@pytest.mark.spec("MS-12-015")
def test_protocol_code_reference_message_advises_reword_or_split(
    tmp_path, capsys
):
    """The message says reword or split, never relabel, and names no kind (MS-12-006).

    Who must obey a rule decides its kind, and naming code never does
    (MS-12-002, ADR-0134): a code token in a protocol statement means the
    statement is spelled in this codebase's terms or mixes in how this
    codebase meets the rule, so the remedy is to reword it or split it
    (MS-12-010), not to move the rule to another kind.
    """
    spec_dir, data = _protocol_spec_naming_code(tmp_path)
    data["groups"][0]["specs"][0]["lint_suppress"] = [
        "missing_story_reference"
    ]
    write_yaml(spec_dir, data)
    lint(spec_dir)
    (line,) = _ms12_lines(capsys.readouterr().err)
    assert "Reword" in line and "split" in line
    assert "MS-12-002" in line and "MS-12-010" in line
    assert "relabel" not in line.lower()
    for kind in ("project", "process", "architecture", "foundation"):
        assert f"kind: {kind}" not in line
        assert f"kind={kind}" not in line


def test_protocol_code_reference_only_in_verification_passes(tmp_path, capsys):
    """A story-less protocol spec naming code only in verification: is clean (MS-12-006).

    MS-10-003 and MS-15-001 oblige a MUST's verification clause to name the
    test that checks it; that path says nothing about whether the rule itself
    is protocol content, so MS-12-006 scans the statement only (#3943).
    """
    spec_dir, data = _protocol_spec_naming_code(
        tmp_path,
        field="verification",
        text="Covered by `test/test_thing.py`, which drives the transition.",
    )
    data["groups"][0]["specs"][0]["lint_suppress"] = [
        "missing_story_reference"
    ]
    write_yaml(spec_dir, data)
    result = lint(spec_dir)
    captured = capsys.readouterr()
    assert result == 0
    assert "MS-12-006" not in captured.err


def test_protocol_with_stories_and_code_reference_passes(tmp_path, capsys):
    """A story-bearing protocol spec is exempt by construction (MS-12-006)."""
    spec_dir, data = _protocol_spec_naming_code(tmp_path)
    data["groups"][0]["specs"][0]["stories"] = ["story_2022_001"]
    write_yaml(spec_dir, data)
    result = lint(spec_dir)
    captured = capsys.readouterr()
    assert result == 0
    assert "MS-12-006" not in captured.err


@pytest.mark.spec("MS-12-014")
def test_protocol_code_reference_suppressed(tmp_path, capsys):
    """lint_suppress: [protocol_kind_with_code_reference] silences MS-12-006."""
    spec_dir, data = _protocol_spec_naming_code(tmp_path)
    data["groups"][0]["specs"][0]["lint_suppress"] = [
        "missing_story_reference",
        "protocol_kind_with_code_reference",
    ]
    write_yaml(spec_dir, data)
    result = lint(spec_dir)
    captured = capsys.readouterr()
    assert result == 0
    assert "MS-12-006" not in captured.err


@pytest.mark.spec("MS-12-006")
def test_foundation_no_stories_code_reference_is_hard_error(tmp_path, capsys):
    """A foundation spec naming this codebase's code is a mixed spec (MS-12-006)."""
    spec_dir, data = _protocol_spec_naming_code(tmp_path, kind="foundation")
    data["groups"][0]["specs"][0]["tags"] = ["http"]
    write_yaml(spec_dir, data)
    result = lint(spec_dir)
    (line,) = _ms12_lines(capsys.readouterr().err)
    assert result == 1
    assert "TST-01-001" in line
    assert "kind=foundation" in line
    assert "MS-12-010" in line


def test_non_implementer_kind_with_code_reference_not_flagged(
    tmp_path, capsys
):
    """MS-12-006 scans protocol and foundation specs only; a project spec may
    name code."""
    spec_dir, data = _protocol_spec_naming_code(tmp_path, kind="project")
    write_yaml(spec_dir, data)
    result = lint(spec_dir)
    captured = capsys.readouterr()
    assert result == 0
    assert "MS-12-006" not in captured.err


@pytest.mark.parametrize(
    "priority", ["MUST_NOT", "SHOULD", "SHOULD_NOT", "MAY"]
)
def test_protocol_code_reference_is_not_priority_scoped(
    tmp_path, capsys, priority
):
    """MS-12-006 fires on every tier; SR-11-003's MUST-only gate never reached these."""
    spec_dir, data = _protocol_spec_naming_code(tmp_path, priority=priority)
    write_yaml(spec_dir, data)
    result = lint(spec_dir)
    captured = capsys.readouterr()
    assert result == 1
    assert len(_ms12_lines(captured.err)) == 1


def test_protocol_code_reference_in_statement_is_hard_error(tmp_path, capsys):
    """A token in the statement is caught too; the field is named in the message."""
    spec_dir, data = _protocol_spec_naming_code(
        tmp_path,
        field="statement",
        text="The tree MUST be built from `py_trees` composites",
    )
    data["groups"][0]["specs"][0]["lint_suppress"] = [
        "missing_story_reference"
    ]
    write_yaml(spec_dir, data)
    result = lint(spec_dir)
    (line,) = _ms12_lines(capsys.readouterr().err)
    assert result == 1
    assert "its statement" in line
    assert "'py_trees'" in line


# ---------------------------------------------------------------------------
# MS-12-018, MS-12-019: a foundation spec names the standard it is inherited from
# ---------------------------------------------------------------------------


def _foundation_lines(captured_err: str) -> list[str]:
    return [line for line in captured_err.splitlines() if "MS-12-018" in line]


@pytest.mark.spec("MS-12-019")
def test_foundation_without_standard_tag_is_hard_error(tmp_path, capsys):
    """kind=foundation whose tags name no standard → exit 1, naming the tags."""
    write_yaml(tmp_path, _minimal_spec_no_stories(kind="foundation"))
    result = lint(tmp_path)
    (line,) = _foundation_lines(capsys.readouterr().err)
    assert result == 1
    assert "TST-01-001" in line
    assert "activitypub, as2, http" in line


@pytest.mark.spec("MS-12-018")
@pytest.mark.parametrize("tag", ["as2", "activitypub", "http"])
def test_foundation_with_standard_tag_passes(tmp_path, capsys, tag):
    """Any one source-standard tag satisfies MS-12-018; no story is needed."""
    data = _minimal_spec_no_stories(kind="foundation")
    data["groups"][0]["specs"][0]["tags"] = ["messaging", tag]
    write_yaml(tmp_path, data)
    result = lint(tmp_path)
    captured = capsys.readouterr()
    assert result == 0, captured.err
    assert not _foundation_lines(captured.err)


@pytest.mark.spec("MS-12-018")
def test_foundation_standard_tag_inherited_from_file_passes(tmp_path, capsys):
    """A file-level standard tag counts: the check reads effective tags."""
    data = _minimal_spec_no_stories(kind="foundation")
    del data["groups"][0]["specs"][0]["tags"]
    data["tags"] = ["http"]
    write_yaml(tmp_path, data)
    assert lint(tmp_path) == 0
    assert not _foundation_lines(capsys.readouterr().err)


@pytest.mark.spec("MS-12-018")
def test_foundation_spec_tags_replace_file_standard_tag(tmp_path, capsys):
    """Spec-level tags replace file-level ones, so a file's standard tag does
    not rescue a foundation spec whose own tags name no standard."""
    data = _minimal_spec_no_stories(kind="foundation")
    data["groups"][0]["specs"][0]["tags"] = ["messaging"]
    data["tags"] = ["as2"]
    write_yaml(tmp_path, data)
    result = lint(tmp_path)
    (line,) = _foundation_lines(capsys.readouterr().err)
    assert result == 1
    assert "TST-01-001" in line


def test_standard_tag_on_a_protocol_spec_is_allowed(tmp_path, capsys):
    """A protocol rule that narrows a standard may carry its tag (MS-12-009)."""
    data = _minimal_spec_no_stories(kind="protocol")
    data["groups"][0]["specs"][0]["tags"] = ["as2"]
    data["groups"][0]["specs"][0]["stories"] = ["story_2022_001"]
    write_yaml(tmp_path, data)
    assert lint(tmp_path) == 0
    assert not _foundation_lines(capsys.readouterr().err)
