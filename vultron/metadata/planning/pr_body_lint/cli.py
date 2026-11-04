"""The ``pr-body-lint`` command line: argument parsing, ``main`` and ``cli``."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from vultron.metadata.planning.pr_body_lint.checks import lint_body
from vultron.metadata.planning.pr_body_lint.facts import (
    _PAYLOAD_FIELDS,
    Runner,
    SetupError,
    _gather,
    _run,
)
from vultron.metadata.planning.pr_body_lint.rules import RULES, PrType, Stage
from vultron.metadata.specs.backstop import (
    BackstopError,
    git_toplevel,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pr-body-lint",
        description="Check a PR body against the mechanical rules of "
        "pr-body-guide.md.",
    )
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--body", help="Body file, or - for stdin")
    source.add_argument(
        "--pr-json",
        help=f"The `gh pr view --json {_PAYLOAD_FIELDS}` payload of an open "
        "PR, or - for stdin; the changed files and spec amendments are read "
        "from the local checkout, which must be at the PR's head commit",
    )
    parser.add_argument(
        "--base",
        help="Diff base (default origin/main, or origin/<base branch> with "
        "--pr-json)",
    )
    parser.add_argument(
        "--type",
        choices=[t.value for t in PrType],
        help="Body template; default: implementation when .py changed",
    )
    parser.add_argument(
        "--stage",
        choices=[s.value for s in Stage],
        default=Stage.PRE_PUSH.value,
        help="pre-push accepts create-pr's placeholders; final refuses them",
    )
    parser.add_argument(
        "--manifest", help="The resolved Spec manifest file (PRB-06)"
    )
    parser.add_argument(
        "--closes-work-item",
        action="store_true",
        help="The PR closes a Task, Feature or Bug: require a Docs: line "
        "even on a docs PR (PD-03-013)",
    )
    parser.add_argument(
        "--list-rules", action="store_true", help="Print the rules and exit"
    )
    return parser


def main(argv: Sequence[str] | None = None, run: Runner = _run) -> int:
    """CLI entry point; returns the exit code (see the module docstring)."""
    parser = _parser()
    args = parser.parse_args(argv)
    if args.list_rules:
        for rule in RULES:
            print(f"{rule.rule_id} {rule.name}: {rule.summary}")
        return 0
    if args.body is None and args.pr_json is None:
        parser.error("one of --body or --pr-json is required")
    try:
        root = git_toplevel(Path.cwd())
        text, facts = _gather(args, root, run)
    except (SetupError, BackstopError) as exc:
        print(f"pr-body-lint: {exc}", file=sys.stderr)
        return 2
    findings = lint_body(text, facts)
    for finding in findings:
        print(finding.render())
    print(
        f"pr-body-lint: {len(findings)} finding(s) "
        f"({facts.pr_type.value} PR, {facts.stage.value} stage)",
        file=sys.stderr,
    )
    return 1 if findings else 0


def cli() -> None:
    """Console-script wrapper: ``sys.exit(main())``."""
    sys.exit(main())
