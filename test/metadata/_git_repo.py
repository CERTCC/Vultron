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
"""A throwaway git repository for tests that compare a branch with its base.

Shared by the tests of the branch-scoped checks (``pr-body-lint``,
``spec-lint --changed-since``), so each one builds its repository the same way:
hooks and signing off, a fixed identity, and the tree committed on ``base``.
"""

from __future__ import annotations

import subprocess
from pathlib import Path


def git(root: Path, *args: str) -> None:
    """Run ``git *args`` in *root*, failing the test on a non-zero exit."""
    subprocess.run(["git", *args], cwd=root, check=True, capture_output=True)


def commit_base(root: Path) -> None:
    """Commit the whole tree under *root* on a fresh ````base```` branch."""
    git(root, "init", "-q", "-b", "base")
    git(root, "add", ".")
    git(
        root,
        "-c", "user.email=t@example.org",
        "-c", "user.name=t",
        "-c", "commit.gpgsign=false",
        "commit", "-q", "--no-verify", "-m", "base",
    )  # fmt: skip


def commit_all(root: Path, message: str = "work") -> None:
    """Commit every change under *root* on the current branch."""
    git(root, "add", ".")
    git(
        root,
        "-c", "user.email=t@example.org",
        "-c", "user.name=t",
        "-c", "commit.gpgsign=false",
        "commit", "-q", "--no-verify", "-m", message,
    )  # fmt: skip


def head_sha(root: Path) -> str:
    """The commit ``HEAD`` names in *root*."""
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
