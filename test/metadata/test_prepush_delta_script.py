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
_ARTIFACT = ".claude/pr-prepush-task%2F1-demo-triage.json"


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _run(
    repo: Path, *args: str, cwd: Path | None = None
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(SCRIPT), *args],
        cwd=cwd or repo,
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


def test_path_takes_an_explicit_branch(repo: Path) -> None:
    _git(repo, "checkout", "-q", "--detach")
    result = _run(repo, "--path", _BRANCH)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == str(repo / _ARTIFACT)


def test_path_encoding_keeps_slash_and_dash_branches_apart(repo: Path) -> None:
    slash = _run(repo, "--path", "task/1-x").stdout.strip()
    dash = _run(repo, "--path", "task-1-x").stdout.strip()
    assert slash != dash


def test_run_from_a_subdirectory_sees_the_whole_diff(repo: Path) -> None:
    (repo / "sub").mkdir()
    _write(repo, "sub/c.txt", "c\n")
    _commit_all(repo, "sub file")
    result = _run(repo, "main", cwd=repo / "sub")
    fields = _fields(result)
    assert fields["reviewed_lines"] == "2"
    assert fields["delta_files"] == "sub/c.txt"


def test_non_ascii_file_names_count_toward_the_delta(repo: Path) -> None:
    _write(repo, "\u00e9.txt", "1\n2\n3\n")
    _commit_all(repo, "accented")
    result = _run(repo, "main")
    assert result.returncode == 3
    fields = _fields(result)
    assert fields["delta_lines"] == "3"
    assert fields["delta_files"] == "\u00e9.txt"


def test_content_lines_that_look_like_headers_are_counted(repo: Path) -> None:
    _write(repo, "b.txt", "x\n-- signature\n")
    _commit_all(repo, "dash dash line")
    assert _fields(_run(repo, "main"))["delta_lines"] == "1"


def test_binary_change_counts_toward_the_delta(repo: Path) -> None:
    (repo / "blob.bin").write_bytes(b"\x00\x01\x02")
    _commit_all(repo, "binary")
    fields = _fields(_run(repo, "main"))
    assert fields["delta_files"] == "blob.bin"
    assert fields["delta_lines"] == "1"


def test_empty_reviewed_diff_is_a_full_triage(repo: Path) -> None:
    base = _git(repo, "rev-parse", "main")
    _record_review(repo, base, base)
    result = _run(repo, "main")
    assert result.returncode == 3
    assert _fields(result)["reason"] == "the reviewed diff is empty"


def test_malformed_artifact_is_a_full_triage(repo: Path) -> None:
    (repo / _ARTIFACT).write_text('{"pr_metadata": ')
    result = _run(repo, "main")
    assert result.returncode == 3
    assert _fields(result)["reason"] == "artifact is not valid JSON"


def test_artifact_without_reviewed_head_is_a_full_triage(repo: Path) -> None:
    base = _git(repo, "rev-parse", "main")
    artifact = {"pr_metadata": {"reviewed_base_sha": base}}
    (repo / _ARTIFACT).write_text(json.dumps(artifact))
    result = _run(repo, "main")
    assert result.returncode == 3
    assert "reviewed_head_sha" in _fields(result)["reason"]


def test_artifact_for_another_branch_is_a_full_triage(repo: Path) -> None:
    artifact = json.loads((repo / _ARTIFACT).read_text())
    artifact["pr_metadata"]["head_ref"] = "task/2-other"
    (repo / _ARTIFACT).write_text(json.dumps(artifact))
    result = _run(repo, "main")
    assert result.returncode == 3
    assert "task/2-other" in _fields(result)["reason"]


def test_unknown_reviewed_base_is_a_full_triage(repo: Path) -> None:
    head = _git(repo, "rev-parse", "HEAD")
    _record_review(repo, "0" * 40, head)
    result = _run(repo, "main")
    assert result.returncode == 3
    assert "reviewed base" in _fields(result)["reason"]


def test_unrelated_base_ref_is_a_usage_error(repo: Path) -> None:
    _git(repo, "checkout", "-q", "--orphan", "island")
    _commit_all(repo, "island root")
    _git(repo, "checkout", "-q", _BRANCH)
    result = _run(repo, "island")
    assert result.returncode == 2
