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
"""Diff parsing and git change collection (SR-12-001)."""

from __future__ import annotations

import re
import subprocess  # nosec B404 - runs fixed git commands only
from collections.abc import Iterable, Sequence
from pathlib import Path

from vultron.metadata.specs.backstop._model import (
    GitRunner,
    BackstopError,
    FileChange,
)

_HUNK_RE = re.compile(r"^@@ -\S+ \+(\d+)(?:,(\d+))? @@")


def _hunk_lines(line: str) -> set[int]:
    match = _HUNK_RE.match(line)
    if match is None:
        return set()
    start = int(match.group(1))
    count = int(match.group(2) or "1")
    if count == 0:  # pure deletion: mark the line it followed
        return {max(start, 1)}
    return set(range(start, start + count))


def parse_diff_hunks(diff: str) -> tuple[dict[str, set[int]], set[str]]:
    """Parse ``git diff -U0`` output into changed new-side lines per file.

    Returns:
        ``(changed, deleted)``: new-side line numbers per surviving ``.py``
        file, and the paths of deleted ``.py`` files.
    """
    changed: dict[str, set[int]] = {}
    deleted: set[str] = set()
    old_path = current = None
    for line in diff.splitlines():
        if line.startswith("--- "):
            old_path = line[6:] if line.startswith("--- a/") else None
        elif line.startswith("+++ "):
            current = line[6:] if line.startswith("+++ b/") else None
            if current is None and old_path and old_path.endswith(".py"):
                deleted.add(old_path)
            if current is not None and not current.endswith(".py"):
                current = None
        elif current is not None and line.startswith("@@"):
            changed.setdefault(current, set()).update(_hunk_lines(line))
    return changed, deleted


def _run_git(root: Path) -> GitRunner:
    def run(args: Sequence[str]) -> str:
        proc = subprocess.run(  # nosec B603 B607 - fixed git argv
            ["git", *args], cwd=root, capture_output=True, text=True
        )
        if proc.returncode != 0:
            detail = proc.stderr.strip() or f"exit {proc.returncode}"
            raise BackstopError(f"git {' '.join(args)}: {detail}")
        return proc.stdout

    return run


def git_toplevel(cwd: Path) -> Path:
    """Return the git work-tree root containing *cwd*."""
    return Path(_run_git(cwd)(["rev-parse", "--show-toplevel"]).strip())


def collect_git_changes(
    git: GitRunner, root: Path, base: str
) -> list[FileChange]:
    """Collect committed, uncommitted, and untracked ``.py`` changes."""
    merge_base = git(["merge-base", base, "HEAD"]).strip()
    # ``--src-prefix``/``--dst-prefix`` pin the ``a/``/``b/`` prefixes that
    # :func:`parse_diff_hunks` matches on. Without them, a user's
    # ``diff.mnemonicPrefix`` or ``diff.noprefix`` config renames them and
    # every file parses as unchanged — a silent exit 0 on the blocking gate.
    diff = git(
        [
            "diff",
            "-U0",
            "--no-color",
            "--no-ext-diff",
            "--no-renames",
            "--src-prefix=a/",
            "--dst-prefix=b/",
        ]
        + [merge_base, "--", "vultron", "test"]
    )
    changed, deleted = parse_diff_hunks(diff)
    changes = [
        FileChange(p, (root / p).read_text(encoding="utf-8"), frozenset(ls))
        for p, ls in changed.items()
    ]
    changes += [
        FileChange(p, git(["show", f"{merge_base}:{p}"])) for p in deleted
    ]
    untracked = git(
        ["ls-files", "--others", "--exclude-standard", "--", "vultron", "test"]
    )
    changes += [
        FileChange(p, (root / p).read_text(encoding="utf-8"))
        for p in untracked.splitlines()
        if p.endswith(".py")
    ]
    return sorted(changes, key=lambda c: c.path)


def changes_from_paths(root: Path, paths: Iterable[str]) -> list[FileChange]:
    """Treat each of *paths* as fully changed (``--paths`` mode).

    A path that does not exist yet is not an error: ``--paths`` is how
    ``deepen-context`` runs the backstop at planning time, naming the files the
    work will touch before any of them exists. Such a file contributes no
    symbols, but its path still matches mirror tests and statements.
    """
    changes = []
    for raw in paths:
        full = (Path.cwd() / raw).resolve()
        try:
            rel = full.relative_to(root).as_posix()
        except ValueError as exc:
            raise BackstopError(f"{raw} is outside {root}: {exc}") from exc
        try:
            source = full.read_text(encoding="utf-8")
        except FileNotFoundError:
            source = ""
        except OSError as exc:
            raise BackstopError(f"cannot read {raw}: {exc}") from exc
        changes.append(FileChange(rel, source))
    return changes
