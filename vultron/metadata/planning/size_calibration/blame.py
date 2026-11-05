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
"""Trace each bug-fix PR's changed lines back to the commits that wrote them.

For a bug-fix PR (:attr:`.model.MergedPr.is_bug_fix`), the lines its merge
deletes or rewrites under ``vultron/`` are blamed at the merge's first parent:
the base branch just before the fix landed. The commits blame names are what
:func:`.measures.later_fixes` maps back to the PRs the fix rewrote. Lines a fix
only adds have no earlier author, so they are not traced.

:func:`complete_commits` reads, from the clone, the commit ids of a PR too
long for the GitHub query to list in full, so every commit maps to its PR.

:func:`old_ranges` and :func:`blamed_commits` are pure and do the reading;
:func:`trace_fixes` and :func:`complete_commits` only loop :data:`GitRunner`
calls over them.
"""

from __future__ import annotations

import re
import subprocess
from collections.abc import Callable, Sequence
from dataclasses import replace

from vultron.metadata.base import repo_root
from vultron.metadata.planning.size_calibration.model import FixTrace, MergedPr

TRACED_PATHS = "vultron/"
"""The tree a fix's changed lines are traced in: the product code."""

GitRunner = Callable[[Sequence[str]], str]
"""Runs a ``git`` argument list and returns its standard output.

Raises :class:`GitError` on failure.
"""


class GitError(Exception):
    """``git`` could not be run, failed, or its output could not be read."""


def run_git(args: Sequence[str]) -> str:
    """Run ``git`` in the repository root and return its standard output.

    Output is read as UTF-8, with any undecodable byte replaced: blame
    carries file content, which need not be valid UTF-8, and only the commit
    ids in it are read.

    Raises:
        GitError: If ``git`` cannot be run or exits non-zero; the message
            carries its stderr.
    """
    try:
        result = subprocess.run(
            ["git", *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=repo_root(),
            check=False,
        )
    except FileNotFoundError as exc:
        raise GitError("git is not installed or not on PATH") from exc
    except OSError as exc:
        raise GitError(f"cannot run git: {exc}") from exc
    if result.returncode != 0:
        raise GitError(
            f"`git {' '.join(args)}` failed: {result.stderr.strip()}"
        )
    return result.stdout


_HUNK = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+\d+(?:,\d+)? @@")
_BLAME_HEADER = re.compile(r"^([0-9a-f]{40}) \d+ \d+(?: \d+)?$")


def old_ranges(diff: str) -> dict[str, tuple[tuple[int, int], ...]]:
    """The old-side ``(start, count)`` line ranges of a ``--unified=0`` diff.

    Keyed by the file's path before the change, so a renamed file is blamed
    under the name it had. A hunk that only adds lines has no old side and is
    left out, as is a file the diff creates. File headers are read only
    between a ``diff --git`` line and the file's first hunk, so a deleted line
    whose text opens with ``-- `` is not taken for one. The diff must carry
    the ``a/`` prefix (:func:`_trace` asks for it).

    Raises:
        GitError: If a path is quoted (git quotes unusual characters), since
            the unquoted name is needed to blame it.
    """
    ranges: dict[str, list[tuple[int, int]]] = {}
    path: str | None = None
    in_header = False
    for line in diff.splitlines():
        if line.startswith("diff --git "):
            path, in_header = None, True
        elif in_header and line.startswith("--- "):
            name = line[4:].rstrip("\t")
            if name.startswith('"'):
                raise GitError(f"cannot blame a quoted path: {name}")
            path = name[2:] if name.startswith("a/") else None
        elif hunk := _HUNK.match(line):
            in_header = False
            if path is None:
                continue
            start = int(hunk.group(1))
            count = 1 if hunk.group(2) is None else int(hunk.group(2))
            if count:
                ranges.setdefault(path, []).append((start, count))
    return {name: tuple(spans) for name, spans in ranges.items()}


def blamed_commits(porcelain: str) -> frozenset[str]:
    """Every commit a ``git blame --porcelain`` output names.

    Each blamed line opens with a header of the commit id and line numbers;
    the line's content follows on a tab-led line, so it can never be read as a
    header.
    """
    return frozenset(
        header.group(1)
        for line in porcelain.splitlines()
        if (header := _BLAME_HEADER.match(line))
    )


def _merge_of(pr: MergedPr, git: GitRunner) -> str:
    """The PR's merge commit, refused when it or its first parent is missing.

    Checking the first parent, not just the merge, also catches a shallow
    clone, where the merge is present but what it merged onto is not.
    """
    merge = pr.merge_commit
    if merge is None:
        raise GitError(f"PR #{pr.number} has no merge commit to trace")
    try:
        git(["cat-file", "-e", f"{merge}^1^{{commit}}"])
    except GitError as exc:
        raise GitError(
            f"PR #{pr.number}'s merge commit {merge}, or its first parent, is "
            "not in this clone; fetch the base branch (`git fetch origin "
            "main`, and `git fetch --unshallow` in a shallow clone) and re-run"
        ) from exc
    return merge


def complete_commits(
    prs: Sequence[MergedPr], git: GitRunner = run_git
) -> tuple[MergedPr, ...]:
    """``prs``, each PR whose commit ids were cut short read in full from git.

    A merge brings in what its first parent lacks, so the commits reachable
    from the merge commit but not from its first parent are the PR's. PRs
    already complete pass through untouched, in their order.

    Raises:
        GitError: If a short PR's merge commit is unknown or not in this
            clone, or ``git`` fails.
    """
    completed: list[MergedPr] = []
    for pr in prs:
        if pr.commits_complete:
            completed.append(pr)
            continue
        merge = _merge_of(pr, git)
        listed = git(["rev-list", f"{merge}^1..{merge}"]).split()
        completed.append(replace(pr, commits=tuple(listed)))
    return tuple(completed)


def _trace(pr: MergedPr, git: GitRunner) -> FixTrace:
    merge = _merge_of(pr, git)
    parent = f"{merge}^1"
    diff = git(
        [
            "-c",
            "core.quotePath=false",
            "diff",
            "--unified=0",
            "--no-color",
            "--no-ext-diff",
            "--find-renames",
            "--src-prefix=a/",
            "--dst-prefix=b/",
            parent,
            merge,
            "--",
            TRACED_PATHS,
        ]
    )
    blamed: set[str] = set()
    for path, spans in sorted(old_ranges(diff).items()):
        lines = [
            arg
            for start, count in spans
            for arg in ("-L", f"{start},+{count}")
        ]
        blamed |= blamed_commits(
            git(["blame", "--porcelain", *lines, parent, "--", path])
        )
    return FixTrace(pr.number, frozenset(blamed))


def trace_fixes(
    prs: Sequence[MergedPr], git: GitRunner = run_git
) -> tuple[FixTrace, ...]:
    """One :class:`.model.FixTrace` per bug-fix PR in ``prs``, by PR number.

    Raises:
        GitError: If a bug-fix PR has no known merge commit, its merge commit
            is not in this clone, or a ``git`` call fails.
    """
    return tuple(
        _trace(pr, git)
        for pr in sorted(prs, key=lambda pr: pr.number)
        if pr.is_bug_fix
    )
