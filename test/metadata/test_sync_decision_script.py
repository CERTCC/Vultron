"""`sync-decision.sh` is pr-execute's Phase 5 Step 2 table (PAD-18-004, PAD-18-014).

`--decide` is checked row by row, first match wins; the default mode is checked
end to end on a real repository whose origin moved, with `gh` answering
`merge-state.sh` and `uv` answering `targeted-tests --overlap`.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from test.metadata._script_sandbox import (
    commit,
    fields,
    git,
    pr_view,
    run_script,
)

pytestmark = pytest.mark.skipif(
    shutil.which("jq") is None, reason="sync-decision.sh needs jq"
)

SCRIPT = "sync-decision.sh"


def _decide(tmp_path: Path, *inputs: str) -> tuple[int, dict[str, list[str]]]:
    result = run_script(
        tmp_path, SCRIPT, "--decide", *inputs, cwd=tmp_path, rules=[]
    )
    return result.returncode, fields(result)


@pytest.mark.parametrize(
    ("inputs", "verdict", "reason"),
    [
        # Row 1: setup error — merge-tree neither 0 nor 1, or overlap exit 2.
        (("0", "CLEAN", "128", "0"), "setup-error", None),
        (("1", "DIRTY", "1", "2"), "setup-error", None),
        # Row 2: CONFLICTING (exit 1), and DIRTY whatever the exit code.
        (("1", "DIRTY", "0", "0"), "merge", "conflicting"),
        (("0", "DIRTY", "0", "1"), "merge", "conflicting"),
        (("2", "DIRTY", "0", "0"), "merge", "conflicting"),
        # Row 3: a trial-merge conflict GitHub has not seen yet.
        (("0", "CLEAN", "1", "0"), "merge", "conflicting"),
        (("2", "UNKNOWN", "1", "1"), "merge", "conflicting"),
        # Row 4: BEHIND with a clean trial merge is updated on GitHub.
        (("0", "BEHIND", "0", "0"), "update-on-github", "behind"),
        (("0", "BEHIND", "0", "1"), "update-on-github", "behind"),
        # Row 5: an overlap alone is recorded, never merged.
        (("0", "CLEAN", "0", "1"), "no-merge", "deferred"),
        (("2", "UNKNOWN", "0", "1"), "no-merge", "deferred"),
        # Row 6: nothing to do; BEHIND needs merge-state exit 0 to update.
        (("0", "CLEAN", "0", "0"), "no-merge", "none"),
        (("2", "UNKNOWN", "0", "0"), "no-merge", "none"),
        (("2", "BEHIND", "0", "0"), "no-merge", "none"),
    ],
)
def test_decide_takes_the_first_matching_row(
    tmp_path: Path, inputs: tuple[str, ...], verdict: str, reason: str | None
) -> None:
    rc, out = _decide(tmp_path, *inputs)
    assert out["verdict"] == [verdict]
    assert rc == (2 if verdict == "setup-error" else 0)
    assert out.get("merge_reason") == ([reason] if reason else None)
    assert out["merge_state_exit"] == [inputs[0]]
    assert out["merge_state_status"] == [inputs[1]]


@pytest.mark.parametrize(
    "inputs",
    [("0", "CLEAN", "0"), ("3", "CLEAN", "0", "0"), ("0", "CLEAN", "x", "0")],
)
def test_decide_refuses_malformed_inputs(
    tmp_path: Path, inputs: tuple[str, ...]
) -> None:
    rc, out = _decide(tmp_path, *inputs)
    assert rc == 2
    assert "verdict" not in out


@pytest.fixture()
def clone(tmp_path: Path) -> Path:
    """A PR branch whose origin/main moved on its own line of `shared.txt`."""
    origin = tmp_path / "origin.git"
    seed = tmp_path / "seed"
    seed.mkdir()
    git(seed, "init", "-q", "-b", "main")
    commit(seed, "shared.txt", "a\nb\nc\n", "base")
    git(tmp_path, "clone", "-q", "--bare", str(seed), str(origin))
    work = tmp_path / "work"
    git(tmp_path, "clone", "-q", str(origin), str(work))
    git(work, "checkout", "-qb", "task/7-x")
    return work


def _move_main(clone: Path, text: str) -> None:
    other = clone.parent / "other"
    git(
        clone.parent,
        "clone",
        "-q",
        str(clone.parent / "origin.git"),
        str(other),
    )
    commit(other, "shared.txt", text, "main moves")
    git(other, "push", "-q", "origin", "main")


def test_conflict_with_the_moved_base_is_merged(
    tmp_path: Path, clone: Path
) -> None:
    commit(clone, "shared.txt", "a\nBRANCH\nc\n")
    _move_main(clone, "a\nMAIN\nc\n")
    result = run_script(
        tmp_path, SCRIPT, "7", "main", cwd=clone, rules=[pr_view()]
    )
    out = fields(result)
    assert result.returncode == 0, result.stderr
    assert out["verdict"] == ["merge"]
    assert out["merge_tree_exit"] == ["1"]
    assert out["conflict_path"] == ["shared.txt"]


def test_overlap_without_conflict_is_deferred(
    tmp_path: Path, clone: Path
) -> None:
    commit(clone, "shared.txt", "BRANCH\nb\nc\n")
    _move_main(clone, "a\nb\nMAIN\n")
    result = run_script(
        tmp_path,
        SCRIPT,
        "7",
        "main",
        cwd=clone,
        rules=[pr_view()],
        env={"FAKE_UV_STDOUT": "shared.txt\n", "FAKE_UV_EXIT": "1"},
    )
    out = fields(result)
    assert result.returncode == 0, result.stderr
    assert out["verdict"] == ["no-merge"]
    assert out["merge_reason"] == ["deferred"]
    assert out["overlap_path"] == ["shared.txt"]
    assert "conflict_path" not in out


def test_behind_on_github_is_updated_there(
    tmp_path: Path, clone: Path
) -> None:
    commit(clone, "mine.txt", "x\n")
    _move_main(clone, "a\nb\nMAIN\n")
    result = run_script(
        tmp_path,
        SCRIPT,
        "7",
        "main",
        cwd=clone,
        rules=[pr_view(status="BEHIND")],
    )
    out = fields(result)
    assert result.returncode == 0, result.stderr
    assert out["verdict"] == ["update-on-github"]


def test_failed_fetch_is_a_setup_error(tmp_path: Path, clone: Path) -> None:
    result = run_script(
        tmp_path, SCRIPT, "7", "no-such-base", cwd=clone, rules=[pr_view()]
    )
    out = fields(result)
    assert result.returncode == 2
    assert out["verdict"] == ["setup-error"]
    assert "fetch" in out["reason"][0]


def test_collect_mode_needs_a_pr_and_a_base(
    tmp_path: Path, clone: Path
) -> None:
    result = run_script(tmp_path, SCRIPT, "7", cwd=clone, rules=[])
    assert result.returncode == 2
    assert "verdict" not in fields(result)
