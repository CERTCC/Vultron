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
