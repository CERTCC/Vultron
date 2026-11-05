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
"""A shared seam for read-only ``git`` calls, for new metadata tools to reuse.

``spec-backstop`` (and the planning tools built on it) and
``pr-size --calibrate`` take a :data:`GitRunner` so their tests fake ``git``;
:func:`git_runner` builds the real one for a repository root. Each tool picks
the exception a failure raises, so its own CLI keeps catching the error type
it already reports.
"""

from __future__ import annotations

import subprocess  # nosec B404 - runs fixed git commands only
from collections.abc import Callable, Sequence
from pathlib import Path

GitRunner = Callable[[Sequence[str]], str]
"""Runs a ``git`` argument list and returns its standard output."""


class GitError(Exception):
    """``git`` could not be run, or exited non-zero."""


def git_runner(
    root: Path, error: Callable[[str], Exception] = GitError
) -> GitRunner:
    """A :data:`GitRunner` for the repository at *root*.

    Output is read as UTF-8 with any undecodable byte replaced: ``git blame``
    and ``git show`` carry file content, which need not be valid UTF-8.

    Args:
        root: The directory each command runs in.
        error: Builds the exception a failure raises from its message;
            :class:`GitError` unless the caller names its own.

    The runner raises ``error(message)`` when ``git`` cannot be started, the
    message naming the ``OSError``, or exits non-zero, the message carrying
    the command and git's stderr (or the exit code when stderr is empty).
    """

    def run(args: Sequence[str]) -> str:
        try:
            proc = subprocess.run(  # nosec B603 B607 - fixed git argv
                ["git", *args],
                cwd=root,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=False,
            )
        except OSError as exc:
            raise error(f"cannot run git: {exc}") from exc
        if proc.returncode != 0:
            detail = proc.stderr.strip() or f"exit {proc.returncode}"
            raise error(f"git {' '.join(args)}: {detail}")
        return proc.stdout

    return run
