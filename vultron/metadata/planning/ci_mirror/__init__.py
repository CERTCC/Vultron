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
"""Run CI's pull-request checks locally before a push (``prepush-ci-mirror``).

About one PR in seven spent a push and a CI round on something CI found that
needs no suite run: an overlong line, a line ceiling, a link, an ADR epoch
(#5580). This command runs, on the whole branch diff, the checks of a
``pull_request`` run of ``.github/workflows/`` that answer in seconds to a
couple of minutes. It leaves the full suites, the container demos, pyright,
the spec-corpus suite, the guard tests and the site build to CI, which the
required ``CI gate`` judges (PAD-18-023, PAD-18-031)::

    prepush-ci-mirror                 # run, against origin/main
    prepush-ci-mirror --base B        # another base branch
    prepush-ci-mirror --pr N          # also the checks that need a PR number
    prepush-ci-mirror --list          # the plan, without running anything
    prepush-ci-mirror --json

A check runs when its workflow's ``pull_request`` filter matches the branch
diff, as in CI, unless the registry narrows it further and says why. The
diff runs from the merge base with ``origin/<base>`` to ``HEAD``; the command
fetches the base first (``--no-fetch`` skips that) and refuses a dirty tree,
because what it checks must be what the push sends.

Output contract (stable; pipeline skills parse it): one line per check,
``<STATUS> <id> (<seconds>s) <reason>``, then ``mirror exit: <code>``.
Exit 0 when nothing blocks, 1 when any check is ``FAIL``, ``NO-VERDICT`` (its
environment stopped it: a ``--timeout`` trip, a kill with no output, or no
heavy-check slot; the reason names the remedy) or ``UNAVAILABLE``
(its tool is not on ``PATH``), 2 on a setup error (not a repository, an
unknown base, a dirty tree). ``--list`` prints ``PLAN`` for a check that would
run, and exits 1 when its plan already holds a block. ``NOT-TRIGGERED``, ``N/A``
and ``SKIPPED`` do not block. ``--skip <id>`` is for a check the caller has
satisfied another way, and must say how in the PR.

Every CI step is either mirrored here or excluded with a reason
(``_registry.py``); ``test/ci/test_prepush_ci_mirror_parity.py`` fails on one
that is neither. Requirements: specs/parallel-development.yaml PAD-18-021 to
PAD-18-023 and PAD-18-031.
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import sys
from collections.abc import Sequence
from pathlib import Path
from types import FrameType

from vultron.metadata.planning.ci_mirror._parity import (
    exclusion_key,
    opaque_actions,
    parity_problems,
)
from vultron.metadata.planning.ci_mirror._registry import (
    EXCLUSIONS,
    MIRROR_CHECKS,
    CheckContext,
    MirrorCheck,
)
from vultron.metadata.planning.ci_mirror._run import (
    DEFAULT_TIMEOUT,
    CheckResult,
    CheckStatus,
    PlannedCheck,
    log_tail,
    plan,
    run_checks,
    stop_running,
)
from vultron.metadata.planning.ci_mirror._workflows import (
    pull_request_steps,
    pull_request_workflows,
)
from vultron.metadata.specs.backstop import (
    BackstopError,
    changed_paths,
    git_toplevel,
    merge_base,
    run_git,
)

__all__ = [
    "EXCLUSIONS",
    "MIRROR_CHECKS",
    "CheckResult",
    "MirrorCheck",
    "CheckStatus",
    "exclusion_key",
    "main",
    "opaque_actions",
    "parity_problems",
    "print_report",
]


#: The exit status of a mirror stopped by SIGTERM (128 + 15).
SIGTERM_EXIT = 143


def _on_sigterm(_signum: int, _frame: FrameType | None) -> None:
    """Stop every running check, then exit: none keeps its heavy-check slot."""
    stop_running()
    raise SystemExit(SIGTERM_EXIT)


class MirrorSetupError(RuntimeError):
    """The mirror cannot decide what to check: no repository, base or clean tree."""


def _seconds(text: str) -> int:
    value = int(text)
    if value <= 0:
        raise argparse.ArgumentTypeError(
            "must be a positive number of seconds"
        )
    return value


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="prepush-ci-mirror",
        description="Run CI's pull-request checks on the branch diff.",
    )
    parser.add_argument("--base", default="main", help="base branch name")
    parser.add_argument("--pr", default="", help="the PR number, once open")
    parser.add_argument("--skip", action="append", default=[], metavar="ID")
    parser.add_argument("--jobs", type=int, default=4)
    parser.add_argument(
        "--timeout",
        type=_seconds,
        default=DEFAULT_TIMEOUT,
        metavar="SECONDS",
        help=f"per-check ceiling (default {DEFAULT_TIMEOUT})",
    )
    parser.add_argument("--no-fetch", action="store_true")
    parser.add_argument("--list", action="store_true", help="plan only")
    parser.add_argument("--json", action="store_true")
    return parser


def _setup(args: argparse.Namespace) -> tuple[Path, CheckContext]:
    try:
        root = git_toplevel(Path.cwd())
        git = run_git(root)
        if not args.list and git(["status", "--porcelain"]).strip():
            raise MirrorSetupError(
                "the working tree is dirty; commit first, so what the mirror "
                "checks is what the push sends"
            )
        if not args.no_fetch:
            git(["fetch", "--quiet", "origin", args.base])
        base_ref = f"origin/{args.base}"
        start = merge_base(git, base_ref)
        # The diff runs to the working tree; the clean-tree check above makes
        # that HEAD on a real run, and --list may plan uncommitted work.
        changed = tuple(changed_paths(git, start))
    except BackstopError as exc:
        raise MirrorSetupError(str(exc)) from exc
    placeholders = {
        "base": args.base,
        "base_ref": base_ref,
        "merge_base": start,
        "pr": str(args.pr),
    }
    return root, CheckContext(placeholders, changed, root)


def _line(result: CheckResult) -> str:
    seconds = f"({result.seconds:.1f}s) " if result.seconds else ""
    return (
        f"{result.status.value} {result.id} {seconds}{result.reason}".rstrip()
    )


def _planned_rows(planned: Sequence[PlannedCheck]) -> list[CheckResult]:
    return [
        CheckResult(
            p.check.id, p.status or CheckStatus.PLANNED,
            p.reason or "would run", 0.0, None, None,
        )
        for p in planned
    ]  # fmt: skip


def print_report(rows: Sequence[CheckResult], as_json: bool) -> int:
    """Print *rows* in the output contract; return the exit code they give."""
    code = 1 if any(r.status.blocks for r in rows) else 0
    if as_json:
        checks = [
            {
                "id": r.id,
                "status": r.status.value,
                "reason": r.reason,
                "seconds": round(r.seconds, 1),
                "log": r.log,
            }
            for r in rows
        ]
        print(json.dumps({"exit": code, "checks": checks}, indent=2))
        return code
    for row in rows:
        print(_line(row))
        if row.status.blocks and row.log:
            print(f"  log: {row.log}")
            print("  " + log_tail(row.log).replace("\n", "\n  "))
    total = sum(r.seconds for r in rows)
    print(f"mirror total: {total:.1f}s of check time")
    print(f"mirror exit: {code}")
    return code


def main(argv: Sequence[str] | None = None) -> int:
    """Entry point for ``prepush-ci-mirror``."""
    args = _build_parser().parse_args(argv)
    unknown = set(args.skip) - {c.id for c in MIRROR_CHECKS}
    if unknown:
        print(
            f"unknown check id: {', '.join(sorted(unknown))}", file=sys.stderr
        )
        return 2
    try:
        root, context = _setup(args)
    except MirrorSetupError as exc:
        print(f"prepush-ci-mirror: {exc}", file=sys.stderr)
        print("mirror exit: 2")
        return 2
    planned = plan(
        MIRROR_CHECKS,
        pull_request_steps(root, opaque_actions(EXCLUSIONS)),
        pull_request_workflows(root),
        context,
        base=args.base,
        skip=args.skip,
    )
    if args.list:
        return print_report(_planned_rows(planned), args.json)
    # PYTHONPATH empty, as every CI step sets it; GITHUB_BASE_REF so the
    # merge-base guards read this base, as they do in CI.
    env = {**os.environ, "PYTHONPATH": "", "GITHUB_BASE_REF": args.base}
    previous = signal.signal(signal.SIGTERM, _on_sigterm)
    try:
        results = run_checks(
            planned, root, jobs=args.jobs, timeout=args.timeout, env=env
        )
    finally:
        signal.signal(signal.SIGTERM, previous)
    return print_report(results, args.json)
