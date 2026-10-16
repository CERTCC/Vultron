#  Copyright (c) 2026 Carnegie Mellon University and Contributors.
#  - see Contributors.md for a full list of Contributors
#  - see ContributionInstructions.md for information on how you can Contribute to this project
#  Vultron Multiparty Coordinated Vulnerability Disclosure Protocol Prototype is
#  licensed under a MIT (SEI)-style license, please see LICENSE.md distributed
#  with this Software or contact permission@sei.cmu.edu for full terms.
#  Created, in part, with funding and support from the United States Government
#  (see Acknowledgments file). This program may include and/or can make use of
#  certain third party source code, object code, documentation and other files
#  ("Third Party Software"). See LICENSE.md for more details.
#  Carnegie Mellon®, CERT® and CERT Coordination Center® are registered in the
#  U.S. Patent and Trademark Office by Carnegie Mellon University

"""`sync-check.sh` delegates to the host's manage-worktree when it can.

When ``~/.copilot/.../manage_worktree.sh`` is installed the script runs its
``ensure-synced``; when that script refuses the repo because the repo keeps
its own ``start-dev.sh``, the script falls back to the fetch-and-count check
it runs when nothing is installed.  Any other failure is reported as is.
"""

import os
import shutil
import subprocess
from pathlib import Path

import pytest

SCRIPT = (
    Path(__file__).resolve().parents[2] / ".agents/skills/shared/sync-check.sh"
)

_REFUSAL = (
    "manage-worktree: this repo manages worktrees via its own start-dev.sh"
)


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        [
            "git",
            "-c", "user.email=t@t",
            "-c", "user.name=t",
            "-c", "commit.gpgsign=false",
            *args,
        ],
        cwd=repo,
        check=True,
        capture_output=True,
    )  # fmt: skip


@pytest.fixture
def clone(tmp_path: Path) -> Path:
    """A clone of a one-commit ``main``, in sync with its origin."""
    origin = tmp_path / "origin"
    origin.mkdir()
    _git(origin, "init", "-q", "-b", "main")
    (origin / "f.txt").write_text("one\n")
    _git(origin, "add", ".")
    _git(origin, "commit", "-q", "--no-verify", "-m", "one")
    work = tmp_path / "work"
    _git(tmp_path, "clone", "-q", str(origin), str(work))
    return work


def _advance_origin(clone: Path) -> None:
    """Put a commit on origin's ``main`` that *clone* does not have."""
    origin = clone.parent / "origin"
    (origin / "f.txt").write_text("two\n")
    _git(origin, "commit", "-q", "--no-verify", "-am", "two")


def _home(tmp_path: Path, script_body: str | None) -> Path:
    """A HOME holding a fake manage_worktree.sh, or none when *script_body*
    is ``None``."""
    home = tmp_path / "home"
    scripts = home / ".copilot/skills/manage-worktree/scripts"
    scripts.mkdir(parents=True)
    if script_body is not None:
        (scripts / "manage_worktree.sh").write_text(script_body)
    return home


def _run(clone: Path, home: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [shutil.which("bash") or "bash", str(SCRIPT)],
        cwd=clone,
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ, "HOME": str(home)},
    )


_REFUSING = f'echo "{_REFUSAL}" >&2\nexit 1\n'
_FAILING = 'echo "manage-worktree: worktree diverged" >&2\nexit 1\n'
_SUCCEEDING = 'echo "manage-worktree: synced" >&2\nexit 0\n'


@pytest.mark.parametrize(
    "script_body", [None, _REFUSING], ids=["absent", "refuses"]
)
def test_fallback_passes_a_synced_clone(clone, tmp_path, script_body):
    """With no host script, or one that refuses the repo, an in-sync clone
    passes the fallback check."""
    result = _run(clone, _home(tmp_path, script_body))

    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize(
    "script_body", [None, _REFUSING], ids=["absent", "refuses"]
)
def test_fallback_refuses_a_clone_behind_origin(clone, tmp_path, script_body):
    """The fallback check counts the commits the clone lacks and aborts."""
    _advance_origin(clone)

    result = _run(clone, _home(tmp_path, script_body))

    assert result.returncode == 1
    assert "1 commit(s) behind origin/main" in result.stderr
    assert _REFUSAL not in result.stderr


def test_any_other_host_failure_is_reported_not_bypassed(clone, tmp_path):
    """A host-script failure for another reason fails the check with the
    host's message, even on an in-sync clone."""
    result = _run(clone, _home(tmp_path, _FAILING))

    assert result.returncode == 1
    assert "worktree diverged" in result.stderr


def test_host_success_is_trusted_and_its_output_shown(clone, tmp_path):
    """A succeeding host script decides; its stderr is passed through."""
    _advance_origin(clone)

    result = _run(clone, _home(tmp_path, _SUCCEEDING))

    assert result.returncode == 0
    assert "manage-worktree: synced" in result.stderr
