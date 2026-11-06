"""Tests for the shared ``git`` seam (:mod:`vultron.metadata.git_runner`).

``subprocess.run`` is replaced in every test, so no git is called.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from vultron.metadata import git_runner
from vultron.metadata.git_runner import GitError
from vultron.metadata.specs.backstop import BackstopError, run_git

ROOT = Path("/repo")


def _returning(code: int, out: str = "", err: str = "", seen=None):
    def run(args, **kwargs):
        if seen is not None:
            seen.update(kwargs, args=args)
        return subprocess.CompletedProcess(args, code, out, err)

    return run


def _raising(exc: BaseException):
    def run(args, **kwargs):
        raise exc

    return run


class TestGitRunner:
    def test_output_is_returned_from_the_root_decoded_leniently(
        self, monkeypatch
    ):
        seen: dict[str, object] = {}
        monkeypatch.setattr(
            git_runner.subprocess, "run", _returning(0, "out\n", seen=seen)
        )
        assert git_runner.git_runner(ROOT)(["status"]) == "out\n"
        assert seen["args"] == ["git", "status"]
        assert seen["cwd"] == ROOT
        assert (seen["encoding"], seen["errors"]) == ("utf-8", "replace")

    def test_a_failure_carries_the_command_and_stderr(self, monkeypatch):
        monkeypatch.setattr(
            git_runner.subprocess, "run", _returning(128, err="fatal: bad\n")
        )
        with pytest.raises(GitError, match=r"^git blame x: fatal: bad$"):
            git_runner.git_runner(ROOT)(["blame", "x"])

    def test_a_silent_failure_names_the_exit_code(self, monkeypatch):
        monkeypatch.setattr(git_runner.subprocess, "run", _returning(3))
        with pytest.raises(GitError, match=r"^git status: exit 3$"):
            git_runner.git_runner(ROOT)(["status"])

    @pytest.mark.parametrize(
        "exc", [FileNotFoundError("git"), PermissionError("denied")]
    )
    def test_git_that_cannot_start_is_a_git_error(self, monkeypatch, exc):
        monkeypatch.setattr(git_runner.subprocess, "run", _raising(exc))
        with pytest.raises(GitError, match=r"^cannot run git: "):
            git_runner.git_runner(ROOT)(["status"])

    def test_the_caller_picks_the_exception(self, monkeypatch):
        monkeypatch.setattr(git_runner.subprocess, "run", _returning(1))
        with pytest.raises(BackstopError, match=r"^git status: exit 1$"):
            git_runner.git_runner(ROOT, BackstopError)(["status"])


class TestBackstopRunner:
    def test_backstop_failures_stay_backstop_errors(self, monkeypatch):
        monkeypatch.setattr(
            git_runner.subprocess, "run", _raising(FileNotFoundError("git"))
        )
        with pytest.raises(BackstopError, match="cannot run git"):
            run_git(ROOT)(["status"])
