"""What the committed-data check reads from git: the tracked tree, and with
``--history`` each branch commit (VSD-02-001)."""

import json
from pathlib import Path

import pytest

from test.metadata._git_repo import commit_all, commit_base, git
from vultron.metadata.vince_data import check as check_module
from vultron.metadata.vince_data.check import (
    generate,
    history_faults,
    tracked_json_files,
)
from vultron.metadata.vince_data.generator import (
    SYNTHETIC_CASES,
    generated_fixtures,
)
from vultron.metadata.vince_data.marker import CLEARED_CASES_PATH, FIXTURE_DIR

_CASE = json.dumps(SYNTHETIC_CASES["999901-active-embargoed"]["case"])


def _repo(tmp_path: Path) -> Path:
    generate(tmp_path)
    (tmp_path / CLEARED_CASES_PATH).write_text("cleared: []\n", "utf-8")
    (tmp_path / "keep.json").write_text("{}", "utf-8")
    (tmp_path / "gone.json").write_text("{}", "utf-8")
    commit_base(tmp_path)
    git(tmp_path, "checkout", "-q", "-b", "work")
    return tmp_path


def test_the_tree_lists_staged_files_and_skips_deleted_ones(
    tmp_path: Path,
) -> None:
    root = _repo(tmp_path)
    (root / "new.JSON").write_text("{}", "utf-8")
    (root / "notes.txt").write_text("{}", "utf-8")
    git(root, "add", "new.JSON", "notes.txt")
    (root / "gone.json").unlink()
    listed = tracked_json_files(root)
    assert "new.JSON" in listed
    assert "notes.txt" not in listed
    assert "gone.json" not in listed
    assert "keep.json" in listed
    assert set(generated_fixtures()) <= set(listed)


@pytest.mark.spec("VSD-02-001")
def test_a_response_added_then_deleted_on_the_branch_is_refused(
    tmp_path: Path,
) -> None:
    root = _repo(tmp_path)
    (root / "docs").mkdir()
    (root / "docs" / "recorded.json").write_text(_CASE, "utf-8")
    commit_all(root, "add a recording")
    (root / "docs" / "recorded.json").unlink()
    commit_all(root, "remove it")
    [fault] = history_faults(root, "base")
    assert "docs/recorded.json: holds a VINCE case object" in fault
    assert check_module.check(root, tracked_json_files(root)) == []


def test_an_earlier_generation_on_the_branch_is_accepted(
    tmp_path: Path,
) -> None:
    root = _repo(tmp_path)
    path = root / next(iter(generated_fixtures()))
    path.write_text(path.read_text("utf-8").replace("Alpha", "Older"), "utf-8")
    commit_all(root, "an earlier generator's output")
    generate(root)
    commit_all(root, "regenerate")
    assert history_faults(root, "base") == []


@pytest.mark.spec("VSD-02-005")
def test_a_real_case_under_the_generator_marker_is_refused(
    tmp_path: Path,
) -> None:
    root = _repo(tmp_path)
    path = root / next(iter(generated_fixtures()))
    path.write_text(path.read_text("utf-8").replace("999901", "123456"))
    commit_all(root, "a real case at the generator's path")
    generate(root)
    commit_all(root, "regenerate")
    [fault] = history_faults(root, "base")
    assert "names 123456, not only the synthetic cases" in fault


@pytest.mark.spec("VSD-02-001")
def test_a_response_added_in_a_merge_commit_is_refused(
    tmp_path: Path,
) -> None:
    root = _repo(tmp_path)
    git(root, "checkout", "-q", "-b", "side")
    (root / "side.json").write_text("{}", "utf-8")
    commit_all(root, "side")
    git(root, "checkout", "-q", "work")
    (root / "work.json").write_text("{}", "utf-8")
    commit_all(root, "work")
    # A merge records its committer even with --no-commit; CI has no
    # global identity.
    git(
        root,
        "-c", "user.email=t@example.org",
        "-c", "user.name=t",
        "merge", "-q", "--no-commit", "--no-ff", "side",
    )  # fmt: skip
    (root / "leak.json").write_text(_CASE, "utf-8")
    commit_all(root, "merge side")
    (root / "leak.json").unlink()
    commit_all(root, "remove it")
    [fault] = history_faults(root, "base")
    assert "leak.json: holds a VINCE case object" in fault


def test_history_reads_a_type_change_and_skips_other_files(
    tmp_path: Path,
) -> None:
    root = _repo(tmp_path)
    (root / "link.json").symlink_to("keep.json")
    (root / "recorded.txt").write_text(_CASE, "utf-8")
    commit_all(root, "a link, and a recording the check does not read")
    (root / "link.json").unlink()
    (root / "link.json").write_text(_CASE, "utf-8")
    commit_all(root, "the link becomes a file")
    (root / "link.json").unlink()
    commit_all(root, "remove it")
    [fault] = history_faults(root, "base")
    assert "link.json: holds a VINCE case object" in fault


def test_history_refuses_a_blob_that_is_not_utf8(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    (root / "bad.json").write_bytes(b'{"a": "\xff"}')
    commit_all(root, "latin-1")
    [fault] = history_faults(root, "base")
    assert "bad.json: cannot be read as JSON" in fault
    assert "not valid UTF-8" in fault


def test_history_leaves_the_cleared_list_fault_to_the_tree_check(
    tmp_path: Path,
) -> None:
    root = _repo(tmp_path)
    (root / CLEARED_CASES_PATH).unlink()
    commit_all(root, "drop the list")
    assert history_faults(root, "base") == []
    faults = check_module.check(root, tracked_json_files(root))
    assert any("cleared-case list is missing" in f for f in faults)


def test_a_generator_marker_at_a_path_it_does_not_own_is_refused(
    tmp_path: Path,
) -> None:
    root = _repo(tmp_path)
    text = next(iter(generated_fixtures().values()))
    (root / FIXTURE_DIR / "copy.json").write_text(text, "utf-8")
    commit_all(root, "a copy")
    [fault] = history_faults(root, "base")
    assert "generator writes no file at this path" in fault


def test_main_check_runs_the_history_scan(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    root = _repo(tmp_path)
    (root / "recorded.json").write_text(_CASE, "utf-8")
    commit_all(root, "add")
    (root / "recorded.json").unlink()
    commit_all(root, "remove")
    monkeypatch.setattr(check_module, "repo_root", lambda: root)
    assert check_module.main(["check"]) == 0
    assert check_module.main(["check", "--history", "base"]) == 1
    assert "recorded.json" in capsys.readouterr().err
