"""``merged-tree-tests`` gates a fix push on the branch merged with its base.

PAD-18-024: when both sides changed a path, the targeted set runs on the merge
of ``HEAD`` with ``origin/<base>``. PAD-18-025: that merge happens in a scratch
worktree, which is removed afterwards, and the PR branch does not move.

Each test builds a branch and a moved base in a throwaway repository and
stands in for the gate, so it can look at the tree it was given.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path

import pytest

from test.support.git_repo import git, init_git_repo
from vultron.metadata.planning.ci_mirror import merged_tree


def _rev(repo: Path, ref: str = "HEAD") -> str:
    import subprocess

    return subprocess.run(
        ["git", "rev-parse", ref], cwd=repo, capture_output=True, text=True,
        check=True,
    ).stdout.strip()  # fmt: skip


def _worktrees(repo: Path) -> list[str]:
    import subprocess

    out = subprocess.run(
        ["git", "worktree", "list", "--porcelain"], cwd=repo,
        capture_output=True, text=True, check=True,
    ).stdout  # fmt: skip
    return [line for line in out.splitlines() if line.startswith("worktree ")]


def _commit(repo: Path, name: str, text: str) -> None:
    (repo / name).write_text(text)
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", name)


@pytest.fixture(autouse=True)
def _private_tempdir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # The log and the scratch worktree go under the temp directory.
    import tempfile

    temp = tmp_path / "temp"
    temp.mkdir()
    monkeypatch.setattr(tempfile, "tempdir", str(temp))


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A ``feature`` branch and an ``origin/main`` that moved since it forked."""
    root = tmp_path / "repo"
    root.mkdir()
    (root / "shared.txt").write_text("one\ntwo\nthree\nfour\nfive\n")
    (root / "other.txt").write_text("x\n")
    init_git_repo(root, monkeypatch)
    fork = _rev(root)
    _commit(root, "shared.txt", "ONE base\ntwo\nthree\nfour\nfive\n")
    _commit(root, "base_only.txt", "base\n")
    git(root, "update-ref", "refs/remotes/origin/main", "HEAD")
    git(root, "checkout", "-q", "-b", "feature", fork)
    monkeypatch.chdir(root)
    return root


class _Gate:
    def __init__(self, code: int = 0) -> None:
        self.code = code
        self.trees: list[dict[str, str]] = []
        self.paths: list[list[str]] = []

    def __call__(
        self,
        scratch: Path,
        paths: Sequence[str],
        log: Path,
        env: Mapping[str, str],
    ) -> int:
        self.paths.append(list(paths))
        self.trees.append(
            {p.name: p.read_text() for p in scratch.iterdir() if p.is_file()}
        )
        log.write_text("gate log\n")
        return self.code


def _run(gate: _Gate) -> int:
    return merged_tree.main(["--no-fetch"], run_gate=gate)


@pytest.mark.spec("PAD-18-024")
def test_the_gate_runs_on_the_merge_of_both_sides(repo: Path, capsys):
    _commit(repo, "shared.txt", "one\ntwo\nthree\nfour\nFIVE branch\n")
    head = _rev(repo)
    gate = _Gate()

    assert _run(gate) == 0

    [tree] = gate.trees
    assert gate.paths == [["shared.txt"]]
    assert tree["shared.txt"] == "ONE base\ntwo\nthree\nfour\nFIVE branch\n"
    assert tree["base_only.txt"] == "base\n"
    out = capsys.readouterr().out
    assert "overlap_path=shared.txt" in out
    assert out.rstrip().endswith("merged-tree exit: 0")
    assert _rev(repo) == head
    assert len(_worktrees(repo)) == 1


@pytest.mark.spec("PAD-18-024")
def test_no_overlap_runs_nothing(repo: Path, capsys):
    _commit(repo, "other.txt", "y\n")
    gate = _Gate()

    assert _run(gate) == 0

    assert gate.trees == []
    assert "merged-tree: no overlap" in capsys.readouterr().out


@pytest.mark.spec("PAD-18-025")
def test_a_failing_gate_fails_and_leaves_no_worktree(repo: Path, capsys):
    _commit(repo, "shared.txt", "one\ntwo\nthree\nfour\nFIVE branch\n")
    head = _rev(repo)

    assert _run(_Gate(code=1)) == 1

    assert "gate log" in capsys.readouterr().out
    assert len(_worktrees(repo)) == 1
    assert _rev(repo) == head


@pytest.mark.spec("PAD-18-025")
def test_a_conflict_is_reported_and_leaves_no_worktree(repo: Path):
    _commit(repo, "shared.txt", "ONE branch\ntwo\nthree\nfour\nfive\n")
    head = _rev(repo)
    gate = _Gate()

    assert _run(gate) == 3

    assert gate.trees == []
    assert len(_worktrees(repo)) == 1
    assert _rev(repo) == head


@pytest.mark.spec("PAD-18-025")
def test_a_gate_that_raises_still_removes_the_worktree(repo: Path):
    _commit(repo, "shared.txt", "one\ntwo\nthree\nfour\nFIVE branch\n")

    def boom(
        scratch: Path, paths: Sequence[str], log: Path, env: Mapping[str, str]
    ) -> int:
        raise RuntimeError("gate crashed")

    with pytest.raises(RuntimeError, match="gate crashed"):
        merged_tree.main(["--no-fetch"], run_gate=boom)

    assert len(_worktrees(repo)) == 1


def test_a_dirty_tree_is_a_setup_error(repo: Path, capsys):
    (repo / "other.txt").write_text("dirty\n")

    assert _run(_Gate()) == 2
    assert "merged-tree exit: 2" in capsys.readouterr().out


def test_an_unknown_base_is_a_setup_error(repo: Path):
    assert (
        merged_tree.main(["--no-fetch", "--base", "nope"], run_gate=_Gate())
        == 2
    )


def _fake_uv(tmp_path: Path, stdout: str, code: int = 0) -> dict[str, str]:
    """A PATH whose ``uv`` prints *stdout* and exits *code*."""
    import os

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    uv = bin_dir / "uv"
    uv.write_text(f"#!/bin/sh\nprintf '%s' '{stdout}'\nexit {code}\n")
    uv.chmod(0o755)
    return {**os.environ, "PATH": f"{bin_dir}:{os.environ['PATH']}"}


@pytest.mark.parametrize(("command", "expected"), [("true", 0), ("false", 1)])
def test_the_targeted_gate_runs_the_printed_command(
    tmp_path: Path, command: str, expected: int
):
    env = _fake_uv(tmp_path, command)
    log = tmp_path / "gate.log"

    assert (
        merged_tree.run_targeted_gate(tmp_path, ["a.py"], log, env) == expected
    )
    assert f"[merged-tree] {command}" in log.read_text()


def test_a_gate_that_cannot_be_derived_is_a_setup_error(tmp_path: Path):
    env = _fake_uv(tmp_path, "boom", code=2)

    with pytest.raises(merged_tree.MergedTreeError, match="could not derive"):
        merged_tree.run_targeted_gate(
            tmp_path, ["a.py"], tmp_path / "gate.log", env
        )


@pytest.mark.spec("PAD-18-025")
def test_an_underivable_gate_exits_2_and_leaves_no_worktree(repo: Path):
    _commit(repo, "shared.txt", "one\ntwo\nthree\nfour\nFIVE branch\n")

    def underivable(
        scratch: Path, paths: Sequence[str], log: Path, env: Mapping[str, str]
    ) -> int:
        raise merged_tree.MergedTreeError("could not derive the gate")

    assert merged_tree.main(["--no-fetch"], run_gate=underivable) == 2
    assert len(_worktrees(repo)) == 1


@pytest.mark.spec("PAD-18-025")
def test_sigterm_removes_the_worktree_and_exits_143(repo: Path, capsys):
    import os
    import signal

    _commit(repo, "shared.txt", "one\ntwo\nthree\nfour\nFIVE branch\n")
    head = _rev(repo)

    def terminated(
        scratch: Path, paths: Sequence[str], log: Path, env: Mapping[str, str]
    ) -> int:
        os.kill(os.getpid(), signal.SIGTERM)
        return 0

    assert merged_tree.main(["--no-fetch"], run_gate=terminated) == 143

    assert "merged-tree exit: 143" in capsys.readouterr().out
    assert len(_worktrees(repo)) == 1
    assert _rev(repo) == head
    assert signal.getsignal(signal.SIGTERM) is not merged_tree._on_sigterm


def test_a_merge_that_fails_without_a_conflict_is_a_setup_error(repo: Path):
    with pytest.raises(merged_tree.MergedTreeError, match="git merge"):
        merged_tree._merge(repo, "no-such-base")


@pytest.mark.spec("PAD-18-024")
def test_the_gate_selects_tests_for_the_shared_paths_only(tmp_path: Path):
    import os

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    argv_file = tmp_path / "argv"
    uv = bin_dir / "uv"
    uv.write_text(f'#!/bin/sh\necho "$@" > {argv_file}\nprintf true\n')
    uv.chmod(0o755)
    env = {**os.environ, "PATH": f"{bin_dir}:{os.environ['PATH']}"}

    merged_tree.run_targeted_gate(
        tmp_path, ["a.py", "specs/x.yaml"], tmp_path / "gate.log", env
    )

    assert argv_file.read_text().split() == [
        "run", "targeted-tests", "--pytest", "--paths", "a.py", "specs/x.yaml",
    ]  # fmt: skip
