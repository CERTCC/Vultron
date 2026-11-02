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
"""Run the targeted tests on the branch merged with its base (``merged-tree-tests``).

CI tests a PR merged into its base. After the first push the base moves, and
a fix push gated on the branch alone can pass locally and fail in CI on a
file both sides changed: a pinned id, a stale genesis hash, a test ported to
a renamed node (#5580). PAD-18-004 still forbids merging the base into the
PR branch for that, so this command tests the merge somewhere else::

    merged-tree-tests                # against origin/main
    merged-tree-tests --base B
    merged-tree-tests --no-fetch

When ``targeted-tests --overlap`` finds no path both sides changed, it
prints ``merged-tree: no overlap`` and exits 0: the branch's own gate already
covers it. Otherwise it adds a detached scratch worktree at ``HEAD``, merges
``origin/<base>`` into that worktree only, runs the ``targeted-tests --pytest``
command there, and removes the worktree with ``git worktree remove`` whatever
the result. It never runs ``git worktree prune``. The PR branch and its
checkout are not touched.

Output contract: one ``overlap_path=<path>`` line per shared path, the last
lines of the test log on a failure, then ``merged-tree exit: <code>``. Exit 0
when there is no overlap or the tests pass, 1 when they fail, 2 on a setup
error (dirty tree, unknown base, a scratch worktree that would not add or
remove), 3 when the base no longer merges cleanly. Exit 3 means the
PR conflicts with its base: rerun ``sync-decision.sh``, which calls for the
merge PAD-18-004 allows.

Requirements: specs/parallel-development.yaml PAD-18-024, PAD-18-025.
"""

from __future__ import annotations

import argparse
import os
import shlex
import subprocess
import sys
import tempfile
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path

from vultron.metadata.planning.targeted_tests import overlap
from vultron.metadata.specs.backstop import (
    BackstopError,
    base_changed_paths,
    changed_paths,
    merge_base,
    run_git,
)

#: Runs the gate in the scratch worktree and returns its exit code.
GateRunner = Callable[[Path, Path, Mapping[str, str]], int]

#: A throwaway identity for the scratch merge commit, which nothing keeps.
_MERGE_IDENTITY = (
    "-c", "user.name=merged-tree-tests",
    "-c", "user.email=merged-tree-tests@localhost",
    "-c", "commit.gpgsign=false",
)  # fmt: skip


class MergedTreeError(RuntimeError):
    """The merged tree could not be built or cleaned up."""


def _git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # nosec B603 B607 - fixed git argv
        ["git", *args], cwd=root, capture_output=True, text=True, check=False
    )


def _checked(root: Path, *args: str) -> str:
    proc = _git(root, *args)
    if proc.returncode != 0:
        detail = proc.stderr.strip() or f"exit {proc.returncode}"
        raise MergedTreeError(f"git {' '.join(args)}: {detail}")
    return proc.stdout


def shared_paths(root: Path, base_ref: str) -> list[str]:
    """The paths both the branch and *base_ref* changed since their merge base."""
    git = run_git(root)
    start = merge_base(git, base_ref)
    return overlap(
        changed_paths(git, start), base_changed_paths(git, start, base_ref)
    )


def run_targeted_gate(scratch: Path, log: Path, env: Mapping[str, str]) -> int:
    """Derive the targeted set inside *scratch* and run it, logging to *log*.

    Returns pytest's exit code. A failure to derive the set is a setup error,
    not a test failure, so it raises :class:`MergedTreeError`.
    """
    base = env.get("GITHUB_BASE_REF", "main")
    derive = subprocess.run(  # nosec B603 B607 - fixed argv
        [
            "uv",
            "run",
            "targeted-tests",
            "--base",
            f"origin/{base}",
            "--pytest",
        ],
        cwd=scratch,
        env=dict(env),
        capture_output=True,
        text=True,
        check=False,
    )
    if derive.returncode != 0:
        log.write_text(derive.stdout + derive.stderr, encoding="utf-8")
        raise MergedTreeError(
            f"targeted-tests could not derive the gate (exit "
            f"{derive.returncode}); log: {log}"
        )
    with log.open("w", encoding="utf-8") as out:
        out.write(f"[merged-tree] {derive.stdout.strip()}\n")
        out.flush()
        return subprocess.run(  # nosec B603 - the argv targeted-tests printed
            shlex.split(derive.stdout.strip()),
            cwd=scratch,
            env=dict(env),
            stdout=out,
            stderr=subprocess.STDOUT,
            check=False,
        ).returncode


def gate_merged_tree(
    root: Path,
    base: str,
    *,
    run_gate: GateRunner,
    log: Path,
    env: Mapping[str, str],
) -> int:
    """Merge ``origin/<base>`` into a scratch worktree and run the gate there.

    Returns 0 when the gate passes, 1 when it fails, 3 when the merge
    conflicts. Raises :class:`MergedTreeError` when the worktree cannot be
    added or removed, or the gate cannot be derived. Removal runs on every
    path out, so no checkout is left behind.
    """
    scratch = Path(tempfile.mkdtemp(prefix=f"vultron-{root.name}-merged-"))
    scratch.rmdir()  # git worktree add creates the directory itself
    _checked(
        root, "worktree", "add", "--quiet", "--detach", str(scratch), "HEAD"
    )
    try:
        merged = _git(
            scratch, *_MERGE_IDENTITY, "merge", "--no-ff", "--no-edit",
            "--quiet", f"origin/{base}",
        )  # fmt: skip
        if merged.returncode != 0:
            return 3
        code = run_gate(scratch, log, env)
        return 0 if code == 0 else 1
    finally:
        _checked(root, "worktree", "remove", "--force", str(scratch))


def _tail(log: Path, lines: int = 20) -> str:
    if not log.is_file():
        return ""
    text = log.read_text(encoding="utf-8", errors="replace")
    return "\n".join(text.splitlines()[-lines:])


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="merged-tree-tests",
        description="Run the targeted tests on the branch merged with its base.",
    )
    parser.add_argument("--base", default="main", help="base branch name")
    parser.add_argument("--no-fetch", action="store_true")
    return parser


def _run(args: argparse.Namespace, run_gate: GateRunner) -> int:
    root = Path(_checked(Path.cwd(), "rev-parse", "--show-toplevel").strip())
    if _checked(root, "status", "--porcelain").strip():
        raise MergedTreeError("the working tree is dirty; commit first")
    if not args.no_fetch:
        _checked(root, "fetch", "--quiet", "origin", args.base)
    base_ref = f"origin/{args.base}"
    try:
        both = shared_paths(root, base_ref)
    except BackstopError as exc:
        raise MergedTreeError(str(exc)) from exc
    if not both:
        print("merged-tree: no overlap")
        return 0
    for path in both:
        print(f"overlap_path={path}")
    log = Path(tempfile.gettempdir()) / f"vultron-{root.name}-merged-tree.log"
    # The scratch worktree gets its own uv environment; an inherited
    # VIRTUAL_ENV names this checkout's, which uv would warn about and ignore.
    env = {k: v for k, v in os.environ.items() if k != "VIRTUAL_ENV"}
    env |= {"PYTHONPATH": "", "GITHUB_BASE_REF": args.base}
    code = gate_merged_tree(
        root, args.base, run_gate=run_gate, log=log, env=env
    )
    if code == 3:
        print(f"merged-tree: origin/{args.base} no longer merges cleanly")
    elif code != 0:
        print(f"merged-tree: tests failed on the merged tree; log: {log}")
        print(_tail(log))
    return code


def main(
    argv: Sequence[str] | None = None,
    *,
    run_gate: GateRunner = run_targeted_gate,
) -> int:
    """Entry point for ``merged-tree-tests``."""
    args = _build_parser().parse_args(argv)
    try:
        code = _run(args, run_gate)
    except MergedTreeError as exc:
        print(f"merged-tree-tests: {exc}", file=sys.stderr)
        code = 2
    print(f"merged-tree exit: {code}")
    return code
