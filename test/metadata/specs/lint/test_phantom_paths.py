"""Tests for vultron.metadata.specs.lint.phantom_paths: phantom path and
directory references (MS-15-001).
"""

from test.metadata.specs._helpers import write_yaml
from test.metadata.specs.lint._helpers import (
    _VERIFIED,
    _minimal_spec,
    _repo_with_specs,
)
from vultron.metadata.specs.lint import lint


def test_lint_phantom_path_is_hard_error(tmp_path, capsys):
    """A statement naming a non-existent repo-relative path fails (MS-15-001)."""
    _, spec_dir = _repo_with_specs(tmp_path)
    data = _minimal_spec()
    data["groups"][0]["specs"][0]["statement"] = (
        "The harness MUST be registered in `vultron/nope.py`"
    )
    write_yaml(spec_dir, data)
    result = lint(spec_dir)
    captured = capsys.readouterr()
    assert result == 1
    assert "MS-15-001" in captured.err
    assert "vultron/nope.py" in captured.err


def test_lint_phantom_path_existing_file_passes(tmp_path):
    """A statement naming a path that exists is accepted."""
    repo, spec_dir = _repo_with_specs(tmp_path)
    (repo / "vultron" / "real.py").write_text("x = 1\n")
    data = _minimal_spec()
    data["groups"][0]["specs"][0]["statement"] = (
        "The thing MUST live in `vultron/real.py`"
    )
    write_yaml(spec_dir, data)
    assert lint(spec_dir) == 0


def test_lint_phantom_path_placeholder_exempt(tmp_path):
    """Placeholder path forms describe a shape, not a file, and are exempt."""
    _, spec_dir = _repo_with_specs(tmp_path)
    data = _minimal_spec()
    data["groups"][0]["specs"][0]["statement"] = (
        "Each scenario MUST have a `test/ci/invariants/test_XXX_invariants.py`"
    )
    write_yaml(spec_dir, data)
    assert lint(spec_dir) == 0


def test_lint_phantom_path_without_placeholder_token_fails(tmp_path):
    """The same path minus the placeholder token is checked and fails.

    Guards the exemption above against becoming vacuous: `test/` exists in the
    fixture repo, so this path reaches the existence check.
    """
    _, spec_dir = _repo_with_specs(tmp_path)
    data = _minimal_spec()
    data["groups"][0]["specs"][0]["statement"] = (
        "Each scenario MUST have a `test/ci/invariants/test_rv_invariants.py`"
    )
    write_yaml(spec_dir, data)
    assert lint(spec_dir) == 1


def test_lint_phantom_path_placeholder_basename_exempt(tmp_path):
    """Placeholder basenames are exempt, but only as a whole path segment."""
    repo, spec_dir = _repo_with_specs(tmp_path)
    (repo / "notes").mkdir()
    data = _minimal_spec()
    data["groups"][0]["specs"][0]["statement"] = (
        "A new note MUST be created at `notes/new-topic.md`"
    )
    write_yaml(spec_dir, data)
    assert lint(spec_dir) == 0


def test_lint_phantom_path_placeholder_basename_not_a_substring(tmp_path):
    """A real path merely *starting* with a placeholder name is still checked."""
    repo, spec_dir = _repo_with_specs(tmp_path)
    (repo / "notes").mkdir()
    data = _minimal_spec()
    data["groups"][0]["specs"][0]["statement"] = (
        "The workflow MUST be documented in `notes/new-topic-workflow.md`"
    )
    write_yaml(spec_dir, data)
    assert lint(spec_dir) == 1


def test_lint_phantom_path_dot_directory_is_checked(tmp_path, capsys):
    """Dot-directories such as `.claude/` are enforced, not silently skipped."""
    _, spec_dir = _repo_with_specs(tmp_path)
    data = _minimal_spec()
    data["groups"][0]["specs"][0]["statement"] = (
        "Linting MUST run via `.claude/skills/format-markdown/SKILL.md`"
    )
    write_yaml(spec_dir, data)
    result = lint(spec_dir)
    captured = capsys.readouterr()
    assert result == 1
    assert ".claude/skills/format-markdown/SKILL.md" in captured.err


def test_lint_phantom_path_dot_directory_existing_passes(tmp_path):
    """A dot-directory path that does exist is accepted."""
    repo, spec_dir = _repo_with_specs(tmp_path)
    skill = repo / ".claude" / "skills" / "format-markdown"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text("# skill\n")
    data = _minimal_spec()
    data["groups"][0]["specs"][0]["statement"] = (
        "Linting MUST run via `.claude/skills/format-markdown/SKILL.md`"
    )
    write_yaml(spec_dir, data)
    assert lint(spec_dir) == 0


def test_lint_phantom_path_package_relative_resolves_as_suffix(tmp_path):
    """A package-relative illustration resolves against a real file's suffix."""
    repo, spec_dir = _repo_with_specs(tmp_path)
    pkg = repo / "vultron" / "wire" / "received"
    pkg.mkdir(parents=True)
    (pkg / "sync.py").write_text("x = 1\n")
    data = _minimal_spec()
    data["groups"][0]["specs"][0]["statement"] = (
        "Patterns MUST be defined in `received/sync.py`"
    )
    write_yaml(spec_dir, data)
    assert lint(spec_dir) == 0


def test_lint_phantom_path_package_relative_unresolvable_fails(tmp_path):
    """A package-relative path matching nothing in the tree is still an error."""
    _, spec_dir = _repo_with_specs(tmp_path)
    data = _minimal_spec()
    data["groups"][0]["specs"][0]["statement"] = (
        "Patterns MUST be defined in `received/sync.py`"
    )
    write_yaml(spec_dir, data)
    assert lint(spec_dir) == 1


def test_lint_phantom_path_mistyped_leading_segment_fails(tmp_path, capsys):
    """A mistyped first segment does not escape via the suffix path.

    `tests/` (plural) is not a top-level dir, so the match is resolved as a
    suffix — and no file ends with `tests/ci/common.py`, so it errors.
    """
    repo, spec_dir = _repo_with_specs(tmp_path)
    real = repo / "test" / "ci"
    real.mkdir(parents=True)
    (real / "common.py").write_text("x = 1\n")
    data = _minimal_spec()
    data["groups"][0]["specs"][0]["statement"] = (
        "Checks MUST live in `tests/ci/common.py`"
    )
    write_yaml(spec_dir, data)
    result = lint(spec_dir)
    captured = capsys.readouterr()
    assert result == 1
    assert "tests/ci/common.py" in captured.err


def test_lint_phantom_path_suffix_ignores_build_artifacts(tmp_path):
    """A path satisfied only inside `.venv/` or `__pycache__/` is not resolved."""
    repo, spec_dir = _repo_with_specs(tmp_path)
    vendored = repo / ".venv" / "lib" / "received"
    vendored.mkdir(parents=True)
    (vendored / "sync.py").write_text("x = 1\n")
    data = _minimal_spec()
    data["groups"][0]["specs"][0]["statement"] = (
        "Patterns MUST be defined in `received/sync.py`"
    )
    write_yaml(spec_dir, data)
    assert lint(spec_dir) == 1


def test_lint_phantom_path_absolute_rejected(tmp_path, capsys):
    """An absolute path is rejected outright, not exempted."""
    _, spec_dir = _repo_with_specs(tmp_path)
    data = _minimal_spec()
    data["groups"][0]["specs"][0]["statement"] = (
        "Config MUST be read from `/etc/vultron/settings.yaml`"
    )
    write_yaml(spec_dir, data)
    result = lint(spec_dir)
    captured = capsys.readouterr()
    assert result == 1
    assert "not a valid repo-relative path" in captured.err


def test_lint_phantom_path_parent_traversal_rejected(tmp_path, capsys):
    """A `..` segment is rejected even when it resolves on the filesystem."""
    repo, spec_dir = _repo_with_specs(tmp_path)
    (repo / "vultron" / "real.py").write_text("x = 1\n")
    data = _minimal_spec()
    data["groups"][0]["specs"][0]["statement"] = (
        "The thing MUST live in `test/../vultron/real.py`"
    )
    write_yaml(spec_dir, data)
    result = lint(spec_dir)
    captured = capsys.readouterr()
    assert result == 1
    assert "not a valid repo-relative path" in captured.err


def test_lint_phantom_path_rationale_not_scanned(tmp_path):
    """rationale may name a removed path as the problem it prevents (MS-10-012)."""
    _, spec_dir = _repo_with_specs(tmp_path)
    data = _minimal_spec()
    data["groups"][0]["specs"][0]["rationale"] = (
        "`vultron/old_config.py` has been converted to a package."
    )
    write_yaml(spec_dir, data)
    assert lint(spec_dir) == 0


def test_lint_phantom_path_suppress(tmp_path, capsys):
    """lint_suppress: [phantom_path_ref] allows a deliberate forward reference."""
    _, spec_dir = _repo_with_specs(tmp_path)
    data = _minimal_spec(extra={"lint_suppress": ["phantom_path_ref"]})
    data["groups"][0]["specs"][0]["statement"] = (
        "A new module MUST be created at `vultron/planned.py`"
    )
    write_yaml(spec_dir, data)
    result = lint(spec_dir)
    captured = capsys.readouterr()
    assert result == 0
    assert "MS-15-001" not in captured.err


def test_lint_phantom_path_in_verification_is_hard_error(tmp_path, capsys):
    """A verification field naming a non-existent path fails (MS-15-001)."""
    _, spec_dir = _repo_with_specs(tmp_path)
    data = _minimal_spec()
    data["groups"][0]["specs"][0]["verification"] = (
        "Assert via `vultron/nope.py` that the invariant holds."
    )
    write_yaml(spec_dir, data)
    result = lint(spec_dir)
    captured = capsys.readouterr()
    assert result == 1
    assert "MS-15-001" in captured.err
    assert "vultron/nope.py" in captured.err


def test_lint_phantom_path_in_verification_existing_passes(tmp_path):
    """A verification field naming an existing path is accepted."""
    repo, spec_dir = _repo_with_specs(tmp_path)
    (repo / "vultron" / "real.py").write_text("x = 1\n")
    data = _minimal_spec()
    data["groups"][0]["specs"][0]["verification"] = (
        "Assert via `vultron/real.py` that the invariant holds."
    )
    write_yaml(spec_dir, data)
    assert lint(spec_dir) == 0


def test_lint_phantom_path_verification_suppress(tmp_path, capsys):
    """lint_suppress: [phantom_path_ref] exempts phantom paths in verification."""
    _, spec_dir = _repo_with_specs(tmp_path)
    data = _minimal_spec(extra={"lint_suppress": ["phantom_path_ref"]})
    data["groups"][0]["specs"][0]["verification"] = (
        "A test at `vultron/future.py` will assert this."
    )
    write_yaml(spec_dir, data)
    result = lint(spec_dir)
    captured = capsys.readouterr()
    assert result == 0
    assert "MS-15-001" not in captured.err


# ---------------------------------------------------------------------------
# MS-15-001: directory reference checks
# ---------------------------------------------------------------------------


def test_lint_phantom_dir_is_hard_error(tmp_path, capsys):
    """A statement naming a non-existent multi-segment directory fails (MS-15-001)."""
    _, spec_dir = _repo_with_specs(tmp_path)
    data = _minimal_spec()
    data["groups"][0]["specs"][0]["statement"] = (
        "Helpers MUST live in `vultron/missing/`"
    )
    write_yaml(spec_dir, data)
    result = lint(spec_dir)
    captured = capsys.readouterr()
    assert result == 1
    assert "MS-15-001" in captured.err
    assert "vultron/missing/" in captured.err


def test_lint_phantom_dir_existing_passes(tmp_path):
    """A statement naming an existing directory passes."""
    repo, spec_dir = _repo_with_specs(tmp_path)
    (repo / "vultron" / "real").mkdir()
    data = _minimal_spec()
    data["groups"][0]["specs"][0]["statement"] = (
        "Helpers MUST live in `vultron/real/`"
    )
    write_yaml(spec_dir, data)
    assert lint(spec_dir) == 0


def test_lint_phantom_dir_single_segment_not_checked(tmp_path):
    """A single-segment directory ref is not checked — high false-positive risk."""
    _, spec_dir = _repo_with_specs(tmp_path)
    data = _minimal_spec()
    data["groups"][0]["specs"][0]["statement"] = (
        "Output MUST be written to the `devlogs/` directory"
    )
    write_yaml(spec_dir, data)
    assert lint(spec_dir) == 0


def test_lint_phantom_dir_placeholder_exempt(tmp_path):
    """A directory ref containing a placeholder token is exempt."""
    _, spec_dir = _repo_with_specs(tmp_path)
    data = _minimal_spec()
    data["groups"][0]["specs"][0]["statement"] = (
        "Each run MUST write to `plan/history/YYMM/`"
    )
    write_yaml(spec_dir, data)
    assert lint(spec_dir) == 0


def test_lint_phantom_dir_placeholder_negative(tmp_path):
    """The same path without the placeholder token fails.

    Guards the exemption above against becoming vacuous: the directory
    `plan/history/2601/` is expected to not exist in the fixture tree.
    """
    _, spec_dir = _repo_with_specs(tmp_path)
    (tmp_path / "plan").mkdir()
    (tmp_path / "plan" / "history").mkdir()
    data = _minimal_spec()
    data["groups"][0]["specs"][0]["statement"] = (
        "Each run MUST write to `plan/history/2601/`"
    )
    write_yaml(spec_dir, data)
    assert lint(spec_dir) == 1


def test_lint_phantom_dir_package_relative_resolves(tmp_path):
    """A package-relative directory resolves against a real directory suffix."""
    repo, spec_dir = _repo_with_specs(tmp_path)
    (repo / "vultron" / "wire" / "received").mkdir(parents=True)
    data = _minimal_spec()
    data["groups"][0]["specs"][0]["statement"] = (
        "Handlers MUST live in `wire/received/`"
    )
    write_yaml(spec_dir, data)
    assert lint(spec_dir) == 0


def test_lint_phantom_dir_package_relative_fails(tmp_path):
    """A package-relative directory matching nothing in the tree fails."""
    _, spec_dir = _repo_with_specs(tmp_path)
    data = _minimal_spec()
    data["groups"][0]["specs"][0]["statement"] = (
        "Handlers MUST live in `wire/received/`"
    )
    write_yaml(spec_dir, data)
    assert lint(spec_dir) == 1


def test_lint_phantom_dir_suppress(tmp_path):
    """lint_suppress: [phantom_path_ref] exempts phantom directory refs."""
    _, spec_dir = _repo_with_specs(tmp_path)
    data = _minimal_spec(extra={"lint_suppress": ["phantom_path_ref"]})
    data["groups"][0]["specs"][0]["statement"] = (
        "Helpers MUST live in `vultron/planned/`"
    )
    write_yaml(spec_dir, data)
    assert lint(spec_dir) == 0


def test_lint_phantom_dir_in_verification_is_hard_error(tmp_path, capsys):
    """A verification field naming a non-existent directory fails (MS-15-001)."""
    _, spec_dir = _repo_with_specs(tmp_path)
    data = _minimal_spec()
    data["groups"][0]["specs"][0]["verification"] = (
        "Assert via `test/ci/invariants/` that the invariant holds."
    )
    write_yaml(spec_dir, data)
    result = lint(spec_dir)
    captured = capsys.readouterr()
    assert result == 1
    assert "MS-15-001" in captured.err
    assert "test/ci/invariants/" in captured.err


# ---------------------------------------------------------------------------
# MS-15-001: behavioral step / precondition / postcondition scanning
# ---------------------------------------------------------------------------


def _minimal_behavioral_spec_data(
    step_action="Execute workflow",
    precondition_desc="System is ready",
    postcondition_desc="Workflow complete",
):
    """Return a minimal spec file containing one BehavioralSpec item."""
    spec = {
        "id": "TST-01-001",
        "priority": "MUST",
        "kind": "protocol",
        "statement": "TST-01-001 MUST execute the workflow",
        "rationale": "ECA required",
        "verification": _VERIFIED,
        "tags": ["testing"],
        "stories": ["story_2022_001"],
        "preconditions": [{"description": precondition_desc}],
        "steps": [{"order": 1, "actor": "finder", "action": step_action}],
        "postconditions": [{"description": postcondition_desc}],
    }
    return {
        "id": "TST",
        "title": "Test File",
        "description": "Test spec file",
        "scope": ["production"],
        "groups": [{"id": "TST-01", "title": "Group", "specs": [spec]}],
    }


def test_lint_phantom_dir_in_behavioral_step_is_hard_error(tmp_path, capsys):
    """A behavioral step action naming a non-existent directory fails (MS-15-001)."""
    _, spec_dir = _repo_with_specs(tmp_path)
    data = _minimal_behavioral_spec_data(
        step_action="Write output to `vultron/output/`"
    )
    write_yaml(spec_dir, data)
    result = lint(spec_dir)
    captured = capsys.readouterr()
    assert result == 1
    assert "MS-15-001" in captured.err
    assert "vultron/output/" in captured.err


def test_lint_phantom_path_in_behavioral_step_is_hard_error(tmp_path, capsys):
    """A behavioral step action naming a non-existent path fails (MS-15-001)."""
    _, spec_dir = _repo_with_specs(tmp_path)
    data = _minimal_behavioral_spec_data(
        step_action="Register via `vultron/nope.py`"
    )
    write_yaml(spec_dir, data)
    result = lint(spec_dir)
    captured = capsys.readouterr()
    assert result == 1
    assert "MS-15-001" in captured.err
    assert "vultron/nope.py" in captured.err


def test_lint_phantom_path_in_behavioral_step_existing_passes(tmp_path):
    """A behavioral step action naming an existing file passes."""
    repo, spec_dir = _repo_with_specs(tmp_path)
    (repo / "vultron" / "real.py").write_text("x = 1\n")
    data = _minimal_behavioral_spec_data(
        step_action="Register via `vultron/real.py`"
    )
    write_yaml(spec_dir, data)
    assert lint(spec_dir) == 0


def test_lint_phantom_path_in_precondition_is_hard_error(tmp_path, capsys):
    """A precondition description naming a non-existent path fails (MS-15-001)."""
    _, spec_dir = _repo_with_specs(tmp_path)
    data = _minimal_behavioral_spec_data(
        precondition_desc="File `vultron/missing.py` is loaded"
    )
    write_yaml(spec_dir, data)
    result = lint(spec_dir)
    captured = capsys.readouterr()
    assert result == 1
    assert "MS-15-001" in captured.err
    assert "vultron/missing.py" in captured.err


def test_lint_phantom_path_in_postcondition_is_hard_error(tmp_path, capsys):
    """A postcondition description naming a non-existent path fails (MS-15-001)."""
    _, spec_dir = _repo_with_specs(tmp_path)
    data = _minimal_behavioral_spec_data(
        postcondition_desc="Result written to `vultron/missing.py`"
    )
    write_yaml(spec_dir, data)
    result = lint(spec_dir)
    captured = capsys.readouterr()
    assert result == 1
    assert "MS-15-001" in captured.err
    assert "vultron/missing.py" in captured.err


def test_lint_phantom_path_behavioral_step_suppress(tmp_path):
    """lint_suppress: [phantom_path_ref] exempts phantom paths in behavioral fields."""
    _, spec_dir = _repo_with_specs(tmp_path)
    spec = {
        "id": "TST-01-001",
        "priority": "MUST",
        "kind": "protocol",
        "statement": "TST-01-001 MUST execute",
        "rationale": "Required",
        "verification": _VERIFIED,
        "tags": ["testing"],
        "stories": ["story_2022_001"],
        "preconditions": [{"description": "System ready"}],
        "steps": [
            {
                "order": 1,
                "actor": "system",
                "action": "Create `vultron/future.py`",
            }
        ],
        "postconditions": [{"description": "Complete"}],
        "lint_suppress": ["phantom_path_ref"],
    }
    data = {
        "id": "TST",
        "title": "T",
        "description": "T",
        "scope": ["production"],
        "groups": [{"id": "TST-01", "title": "G", "specs": [spec]}],
    }
    write_yaml(spec_dir, data)
    assert lint(spec_dir) == 0
