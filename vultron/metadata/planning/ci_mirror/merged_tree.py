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

When no path was changed on both sides (the overlap ``targeted-tests
--overlap`` reports, from the same helper), it prints ``merged-tree: no
overlap`` and exits 0: the branch's own gate already covers it. Otherwise it
adds a detached scratch worktree at ``HEAD``, merges
``origin/<base>`` into that worktree only, runs there the tests that
``targeted-tests --paths`` selects for the shared files, and removes the
worktree with ``git worktree remove`` whatever the result. It never runs
``git worktree prune``. The PR branch and its checkout are not touched.

Output contract: one ``overlap_path=<path>`` line per shared path, the last
lines of the test log on a failure, then ``merged-tree exit: <code>``. Exit 0
when there is no overlap or the tests pass, 1 when they fail, 2 on a setup
error (dirty tree, unknown base, a scratch worktree that would not add or
remove, a merge that failed without a conflict), 3 when the base no longer
merges cleanly, 143 when SIGTERM stopped it (after removing the worktree).
Exit 3 means the PR conflicts with its base: rerun ``sync-decision.sh``,
which calls for the merge PAD-18-004 allows.

Requirements: specs/parallel-development.yaml PAD-18-024, PAD-18-025.
"""

from __future__ import annotations

import argparse
import os
import shlex
import signal
import subprocess
import sys
import tempfile
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from types import FrameType

from vultron.metadata.planning.ci_mirror._run import log_tail, run_in_session
from vultron.metadata.planning.targeted_tests import branch_overlap
from vultron.metadata.specs.backstop import (
    BackstopError,
    git_toplevel,
    merge_base,
    run_git,
)

#: Runs the gate for the shared paths in the scratch worktree; its exit code.
GateRunner = Callable[[Path, Sequence[str], Path, Mapping[str, str]], int]

#: A throwaway identity for the scratch merge commit, which nothing keeps.
_MERGE_IDENTITY = (
    "-c", "user.name=merged-tree-tests",
    "-c", "user.email=merged-tree-tests@localhost",
    "-c", "commit.gpgsign=false",
)  # fmt: skip

#: The exit status of a run stopped by SIGTERM (128 + 15), after cleanup.
SIGTERM_EXIT = 143


class MergedTreeError(RuntimeError):
    """The merged tree could not be built or cleaned up."""


class _Terminated(BaseException):
    """SIGTERM arrived; unwinding runs every ``finally`` on the way out."""


def _on_sigterm(signum: int, frame: FrameType | None) -> None:
    raise _Terminated()


def _checked(root: Path, *args: str) -> str:
    try:
        return run_git(root)(list(args))
    except BackstopError as exc:
        raise MergedTreeError(str(exc)) from exc


def shared_paths(root: Path, base_ref: str) -> list[str]:
    """The paths both the branch and *base_ref* changed since their merge base."""
    git = run_git(root)
    return branch_overlap(git, merge_base(git, base_ref), base_ref)


def run_targeted_gate(
    scratch: Path, paths: Sequence[str], log: Path, env: Mapping[str, str]
) -> int:
    """Derive the targeted set for *paths* inside *scratch* and run it.

    The set is ``targeted-tests --paths`` for the files both sides changed,
    each counted as wholly changed, as after a conflict merge (PAD-18-015).
    The branch's own lines were gated already; what the base can break is
    where the two meet. Returns pytest's exit code, logging to *log*.

    A failure to derive the set is a setup error, not a test failure, so it
    raises :class:`MergedTreeError`. The tests run in their own process
    group, so an interrupt stops their workers too.
    """
    derive = subprocess.run(  # nosec B603 B607 - fixed argv
        ["uv", "run", "targeted-tests", "--pytest", "--paths", *paths],
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
        code = run_in_session(
            shlex.split(derive.stdout.strip()),
            cwd=scratch,
            env=env,
            out=out,
            timeout=None,
        )
    return 1 if code is None else code


def _merge(scratch: Path, base: str) -> bool:
    """Merge ``origin/<base>`` in *scratch*: True when clean, False on a conflict.

    Any other failure (a bad ref, a broken repository) is a setup error.
    """
    merged = subprocess.run(  # nosec B603 B607 - fixed git argv
        ["git", *_MERGE_IDENTITY, "merge", "--no-ff", "--no-edit", "--quiet",
         f"origin/{base}"],
        cwd=scratch, capture_output=True, text=True, check=False,
    )  # fmt: skip
    if merged.returncode == 0:
        return True
    if _checked(scratch, "diff", "--name-only", "--diff-filter=U").strip():
        return False
    detail = merged.stderr.strip() or f"exit {merged.returncode}"
    raise MergedTreeError(f"git merge origin/{base}: {detail}")


def gate_merged_tree(
    root: Path,
    base: str,
    paths: Sequence[str],
    *,
    run_gate: GateRunner,
    log: Path,
    env: Mapping[str, str],
) -> int:
    """Merge ``origin/<base>`` into a scratch worktree and run the gate there.

    Returns 0 when the gate passes, 1 when it fails, 3 when the merge
    conflicts. Raises :class:`MergedTreeError` when the worktree cannot be
    added or removed, the merge fails for another reason, or the gate cannot
    be derived. Removal runs on every path out, an interrupt included, so no
    checkout is left behind.
    """
    scratch = Path(tempfile.mkdtemp(prefix=f"vultron-{root.name}-merged-"))
    scratch.rmdir()  # git worktree add creates the directory itself
    try:
        _checked(
            root,
            "worktree",
            "add",
            "--quiet",
            "--detach",
            str(scratch),
            "HEAD",
        )
        if not _merge(scratch, base):
            return 3
        return 0 if run_gate(scratch, paths, log, env) == 0 else 1
    finally:
        if scratch.exists():
            _checked(root, "worktree", "remove", "--force", str(scratch))


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="merged-tree-tests",
        description="Run the targeted tests on the branch merged with its base.",
    )
    parser.add_argument("--base", default="main", help="base branch name")
    parser.add_argument("--no-fetch", action="store_true")
    return parser


def _run(args: argparse.Namespace, run_gate: GateRunner) -> int:
    try:
        root = git_toplevel(Path.cwd())
    except BackstopError as exc:
        raise MergedTreeError(str(exc)) from exc
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
        root, args.base, both, run_gate=run_gate, log=log, env=env
    )
    if code == 3:
        print(f"merged-tree: origin/{args.base} no longer merges cleanly")
    elif code != 0:
        print(f"merged-tree: tests failed on the merged tree; log: {log}")
        print(log_tail(log, 20))
    return code


def main(
    argv: Sequence[str] | None = None,
    *,
    run_gate: GateRunner = run_targeted_gate,
) -> int:
    """Entry point for ``merged-tree-tests``.

    SIGTERM (``timeout`` sends it first) unwinds through the cleanup instead
    of killing the process where it stands, so the scratch worktree is
    removed and the run exits :data:`SIGTERM_EXIT`.
    """
    args = _build_parser().parse_args(argv)
    previous = signal.signal(signal.SIGTERM, _on_sigterm)
    try:
        code = _run(args, run_gate)
    except MergedTreeError as exc:
        print(f"merged-tree-tests: {exc}", file=sys.stderr)
        code = 2
    except _Terminated:
        print("merged-tree-tests: terminated; scratch worktree removed")
        code = SIGTERM_EXIT
    finally:
        signal.signal(signal.SIGTERM, previous)
    print(f"merged-tree exit: {code}")
    return code
