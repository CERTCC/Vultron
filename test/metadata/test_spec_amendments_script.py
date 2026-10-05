"""`spec-amendments.sh` flags changed/removed spec statements, not additions."""

import subprocess
from pathlib import Path

import pytest

SCRIPT = (
    Path(__file__).resolve().parents[2]
    / ".agents/skills/shared/spec-amendments.sh"
)

_SPEC = """\
id: demo
groups:
  - id: grp
    specs:
      - id: req-a
        priority: MUST
        statement: >-
          The system MUST do the thing
          across two lines.
      - id: req-b
        priority: SHOULD
        statement: Another requirement.
"""


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", *args],
        cwd=repo,
        check=True,
        capture_output=True,
    )


def _run(repo: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(SCRIPT), "main", "HEAD"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    _git(tmp_path, "init", "-q", "-b", "main")
    (tmp_path / "specs").mkdir()
    (tmp_path / "specs" / "xx.yaml").write_text(_SPEC)
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-qm", "base")
    _git(tmp_path, "checkout", "-qb", "work")
    return tmp_path


def _commit_spec(repo: Path, text: str) -> None:
    (repo / "specs" / "xx.yaml").write_text(text)
    _git(repo, "commit", "-qam", "edit")


def test_unchanged_specs_exit_zero(repo: Path) -> None:
    (repo / "README.md").write_text("x")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "unrelated")
    result = _run(repo)
    assert result.returncode == 0, result.stderr
    assert result.stdout == ""


def test_mid_statement_edit_is_flagged(repo: Path) -> None:
    _commit_spec(repo, _SPEC.replace("across two lines", "across many lines"))
    result = _run(repo)
    assert result.returncode == 1, result.stderr
    assert result.stdout.strip() == "req-a\tchanged\tstatement"


def test_priority_change_is_flagged(repo: Path) -> None:
    _commit_spec(repo, _SPEC.replace("priority: SHOULD", "priority: MAY"))
    result = _run(repo)
    assert result.returncode == 1, result.stderr
    assert result.stdout.strip() == "req-b\tchanged\tpriority"


def test_reflow_only_is_not_an_amendment(repo: Path) -> None:
    _commit_spec(
        repo,
        _SPEC.replace(
            "MUST do the thing\n          across two lines.",
            "MUST do the thing across\n          two lines.",
        ),
    )
    assert _run(repo).returncode == 0


def test_removed_requirement_is_flagged(repo: Path) -> None:
    _commit_spec(repo, _SPEC.split("      - id: req-b", maxsplit=1)[0])
    result = _run(repo)
    assert result.returncode == 1, result.stderr
    assert result.stdout.strip().startswith("req-b\tremoved")


def test_added_requirement_is_not_an_amendment(repo: Path) -> None:
    _commit_spec(
        repo,
        _SPEC
        + "      - id: req-c\n        priority: MAY\n"
        + "        statement: Brand new.\n",
    )
    assert _run(repo).returncode == 0


def test_requirement_moved_unchanged_to_another_file_is_not_flagged(
    repo: Path,
) -> None:
    (repo / "specs" / "xx.yaml").rename(repo / "specs" / "yy.yaml")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "move")
    assert _run(repo).returncode == 0


def test_deleted_spec_file_flags_its_requirements(repo: Path) -> None:
    (repo / "specs" / "xx.yaml").unlink()
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "delete")
    result = _run(repo)
    assert result.returncode == 1, result.stderr
    assert "req-a\tremoved" in result.stdout
    assert "req-b\tremoved" in result.stdout
