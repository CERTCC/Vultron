"""`prepush-delta.sh` measures the delta on the branch's own lines (PAD-07-007/008)."""

import json
import subprocess
from pathlib import Path

import pytest

SCRIPT = (
    Path(__file__).resolve().parents[2]
    / ".agents/skills/pr-triage/prepush-delta.sh"
)

_BRANCH = "task/1-demo"
_ARTIFACT = ".claude/pr-prepush-task-1-demo-triage.json"


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _run(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(SCRIPT), *args],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )


def _fields(result: subprocess.CompletedProcess[str]) -> dict[str, str]:
    return dict(
        line.split("=", 1)
        for line in result.stdout.splitlines()
        if "=" in line
    )


def _write(repo: Path, name: str, text: str) -> None:
    (repo / name).write_text(text)


def _commit_all(repo: Path, message: str) -> str:
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", message)
    return _git(repo, "rev-parse", "HEAD")


def _record_review(repo: Path, base: str, head: str) -> None:
    artifact = {
        "pr_metadata": {"reviewed_base_sha": base, "reviewed_head_sha": head}
    }
    (repo / _ARTIFACT).write_text(json.dumps(artifact))


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    """A branch that changed one line of a 50-line file, reviewed pre-push."""
    _git(tmp_path, "init", "-q", "-b", "main")
    _write(tmp_path, "a.txt", "".join(f"{n}\n" for n in range(1, 51)))
    _write(tmp_path, "b.txt", "x\n")
    (tmp_path / ".gitignore").write_text(".claude/\n")
    base = _commit_all(tmp_path, "base")
    _git(tmp_path, "checkout", "-qb", _BRANCH)
    _write(
        tmp_path,
        "a.txt",
        "".join(("ten\n" if n == 10 else f"{n}\n") for n in range(1, 51)),
    )
    head = _commit_all(tmp_path, "change")
    (tmp_path / ".claude").mkdir()
    _record_review(tmp_path, base, head)
    return tmp_path


def _freshen_onto_moved_main(repo: Path) -> None:
    """Move main on another line of the file, then cherry-pick the branch."""
    head = _git(repo, "rev-parse", "HEAD")
    _git(repo, "checkout", "-q", "main")
    _write(
        repo,
        "a.txt",
        "".join(("forty\n" if n == 40 else f"{n}\n") for n in range(1, 51)),
    )
    _commit_all(repo, "main moves")
    _git(repo, "checkout", "-q", "-B", _BRANCH, "main")
    _git(repo, "cherry-pick", head)


def test_path_names_the_artifact_after_the_branch(repo: Path) -> None:
    result = _run(repo, "--path")
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == str(repo / _ARTIFACT)


def test_unchanged_branch_is_a_delta_review(repo: Path) -> None:
    result = _run(repo, "main")
    assert result.returncode == 0, result.stderr
    fields = _fields(result)
    assert fields["mode"] == "delta"
    assert fields["reviewed_lines"] == "2"
    assert fields["delta_lines"] == "0"
    assert fields["delta_files"] == ""


def test_freshen_onto_a_newer_base_adds_no_delta(repo: Path) -> None:
    _freshen_onto_moved_main(repo)
    result = _run(repo, "main")
    assert result.returncode == 0, result.stderr
    assert _fields(result)["delta_lines"] == "0"


def test_small_fix_is_reviewed_as_delta(repo: Path) -> None:
    _write(repo, "b.txt", "x\ny\n")
    _commit_all(repo, "fix")
    result = _run(repo, "main")
    assert result.returncode == 0, result.stderr
    fields = _fields(result)
    assert fields["mode"] == "delta"
    assert fields["delta_lines"] == "1"
    assert fields["delta_files"] == "b.txt"


def test_delta_over_half_the_reviewed_lines_is_a_full_triage(
    repo: Path,
) -> None:
    _write(repo, "b.txt", "x\ny\nz\n")
    _commit_all(repo, "bigger fix")
    result = _run(repo, "main")
    assert result.returncode == 3
    fields = _fields(result)
    assert fields["mode"] == "full"
    assert fields["delta_lines"] == "2"


def test_missing_artifact_is_a_full_triage(repo: Path) -> None:
    (repo / _ARTIFACT).unlink()
    result = _run(repo, "main")
    assert result.returncode == 3
    assert _fields(result)["reason"] == "no pre-push artifact"


def test_artifact_without_reviewed_shas_is_a_full_triage(repo: Path) -> None:
    (repo / _ARTIFACT).write_text(json.dumps({"pr_metadata": {}}))
    result = _run(repo, "main")
    assert result.returncode == 3
    assert "reviewed_base_sha" in _fields(result)["reason"]


def test_unknown_reviewed_head_is_a_full_triage(repo: Path) -> None:
    base = _git(repo, "rev-parse", "main")
    _record_review(repo, base, "0" * 40)
    result = _run(repo, "main")
    assert result.returncode == 3
    assert "not in the object store" in _fields(result)["reason"]


def test_detached_head_is_a_usage_error(repo: Path) -> None:
    _git(repo, "checkout", "-q", "--detach")
    result = _run(repo, "main")
    assert result.returncode == 2
