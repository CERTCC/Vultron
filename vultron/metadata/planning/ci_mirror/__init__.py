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
(#5580). This command runs, on the whole branch diff, every check a
``pull_request`` run of ``.github/workflows/`` would run, except the full
suites and the container demos::

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
Exit 0 when nothing blocks, 1 when any check is ``FAIL`` or ``UNAVAILABLE``
(its tool is not on ``PATH``), 2 on a setup error (not a repository, an
unknown base, a dirty tree). ``NOT-TRIGGERED``, ``N/A`` and ``SKIPPED`` do
not block; ``--skip <id>`` is for a check the caller has satisfied another way
and must say how in the PR.

Every CI step is either mirrored here or excluded with a reason
(``_registry.py``); ``test/ci/test_prepush_ci_mirror_parity.py`` fails on one
that is neither. Requirements: specs/parallel-development.yaml PAD-18-021 to
PAD-18-025.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path

from vultron.metadata.planning.ci_mirror._parity import (
    exclusion_key,
    opaque_actions,
    parity_problems,
)
from vultron.metadata.planning.ci_mirror._registry import (
    EXCLUSIONS,
    GUARD_TESTS,
    MIRROR_CHECKS,
    CheckContext,
    MirrorCheck,
)
from vultron.metadata.planning.ci_mirror._run import (
    CheckResult,
    CheckStatus,
    PlannedCheck,
    plan,
    run_checks,
)
from vultron.metadata.planning.ci_mirror._workflows import (
    pull_request_steps,
    pull_request_workflows,
)

__all__ = [
    "EXCLUSIONS",
    "GUARD_TESTS",
    "MIRROR_CHECKS",
    "CheckResult",
    "MirrorCheck",
    "CheckStatus",
    "exclusion_key",
    "main",
    "opaque_actions",
    "parity_problems",
]


class MirrorSetupError(RuntimeError):
    """The mirror cannot decide what to check: no repository, base or clean tree."""


def _git(root: Path, *args: str) -> str:
    proc = subprocess.run(  # nosec B603 B607 - fixed git argv
        ["git", *args], cwd=root, capture_output=True, text=True, check=False
    )
    if proc.returncode != 0:
        detail = proc.stderr.strip() or f"exit {proc.returncode}"
        raise MirrorSetupError(f"git {' '.join(args)}: {detail}")
    return proc.stdout


def _branch_diff(root: Path, base_ref: str) -> tuple[str, tuple[str, ...]]:
    start = _git(root, "merge-base", base_ref, "HEAD").strip()
    names = _git(root, "diff", "--name-only", "--no-renames", start, "HEAD")
    return start, tuple(sorted(set(names.splitlines())))


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="prepush-ci-mirror",
        description="Run CI's pull-request checks on the branch diff.",
    )
    parser.add_argument("--base", default="main", help="base branch name")
    parser.add_argument("--pr", default="", help="the PR number, once open")
    parser.add_argument("--skip", action="append", default=[], metavar="ID")
    parser.add_argument("--jobs", type=int, default=4)
    parser.add_argument("--no-fetch", action="store_true")
    parser.add_argument("--list", action="store_true", help="plan only")
    parser.add_argument("--json", action="store_true")
    return parser


def _setup(args: argparse.Namespace) -> tuple[Path, CheckContext]:
    root = Path(_git(Path.cwd(), "rev-parse", "--show-toplevel").strip())
    if not args.list and _git(root, "status", "--porcelain").strip():
        raise MirrorSetupError(
            "the working tree is dirty; commit first, so what the mirror "
            "checks is what the push sends"
        )
    if not args.no_fetch:
        _git(root, "fetch", "--quiet", "origin", args.base)
    base_ref = f"origin/{args.base}"
    _git(root, "rev-parse", "--verify", "--quiet", f"{base_ref}^{{commit}}")
    start, changed = _branch_diff(root, base_ref)
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


def _tail(path: str | None, lines: int = 15) -> str:
    if path is None:
        return ""
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    return "\n".join(text.splitlines()[-lines:])


def _report(
    planned: Sequence[PlannedCheck],
    results: Sequence[CheckResult] | None,
    as_json: bool,
) -> int:
    rows = results or [
        CheckResult(
            p.check.id, p.status or CheckStatus.PASSED, p.reason or "would run", 0.0,
            None, None,
        )
        for p in planned
    ]  # fmt: skip
    code = 1 if results and any(r.status.blocks for r in results) else 0
    if as_json:
        print(
            json.dumps(
                {
                    "exit": code,
                    "checks": [
                        {
                            "id": r.id,
                            "status": r.status.value,
                            "reason": r.reason,
                            "seconds": round(r.seconds, 1),
                            "log": r.log,
                        }
                        for r in rows
                    ],
                },
                indent=2,
            )
        )
        return code
    for row in rows:
        print(_line(row) if results else f"PLAN {row.id} {row.reason}")
        if row.status is CheckStatus.FAILED and row.log:
            print(f"  log: {row.log}")
            print("  " + _tail(row.log).replace("\n", "\n  "))
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
        return _report(planned, None, args.json)
    # PYTHONPATH empty, as every CI step sets it; GITHUB_BASE_REF so the
    # merge-base guards read this base, as they do in CI.
    env = {**os.environ, "PYTHONPATH": "", "GITHUB_BASE_REF": args.base}
    results = run_checks(planned, root, jobs=args.jobs, env=env)
    return _report(planned, results, args.json)
