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

"""Throwaway git repositories for tests of tools that read a branch diff.

``spec-backstop`` and ``targeted-tests`` both run git against ``tmp_path``.
Two environment leaks would point them at the wrong repository or fail them
outright: a ``GIT_DIR``/``GIT_INDEX_FILE`` inherited from a git hook running
the suite, and a global ``commit.gpgsign``. :func:`init_git_repo` scrubs the
first through *monkeypatch* and every :func:`git` call overrides the second.
"""

import os
import shutil
import subprocess
from pathlib import Path

import pytest

_CONFIG = (
    "-c",
    "user.name=t",
    "-c",
    "user.email=t@t",
    "-c",
    "commit.gpgsign=false",
)


def git(root: Path, *args: str) -> None:
    """Run ``git *args`` in *root*, raising on a non-zero exit."""
    subprocess.run(
        ["git", *_CONFIG, *args],
        cwd=root,
        check=True,
        capture_output=True,
    )


def init_git_repo(root: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Commit everything under *root* as ``init`` on branch ``main``.

    Skips the test when git is not installed.
    """
    if shutil.which("git") is None:
        pytest.skip("git not available")
    for name in list(os.environ):
        if name.startswith("GIT_"):
            monkeypatch.delenv(name)
    git(root, "init", "-q", "-b", "main")
    git(root, "add", ".")
    git(root, "commit", "-q", "-m", "init")
    return root
