"""The ``targeted-tests`` command line."""

from __future__ import annotations

import argparse
import json
import shlex
import sys
from collections.abc import Callable
from pathlib import Path

from vultron.metadata.planning.targeted_tests.index import build_index
from vultron.metadata.planning.targeted_tests.selection import (
    Selection,
    branch_overlap,
    conflict_suite_trigger,
    pytest_argv,
    select_tests,
)
from vultron.metadata.specs.backstop import (
    BackstopError,
    GitRunner,
    changed_paths,
    changes_from_paths,
    collect_git_changes,
    git_toplevel,
    merge_base,
    run_git,
)

# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="targeted-tests",
        description=(
            "Derive the local test gate for the branch diff (PAD-18-002, "
            "PAD-18-003), or list the files the base and the branch both "
            "changed (PAD-18-004)."
        ),
    )
    parser.add_argument(
        "--base", default="origin/main", help="base ref (default origin/main)"
    )
    parser.add_argument(
        "--overlap",
        action="store_true",
        help=(
            "list files changed on both the base and this branch since the "
            "merge base; exit 1 when there are any"
        ),
    )
    parser.add_argument(
        "--paths",
        nargs="+",
        metavar="PATH",
        help=(
            "derive the gate for these files (the conflicted files after a "
            "base merge) instead of the branch diff; each counts as wholly "
            "changed"
        ),
    )
    output = parser.add_mutually_exclusive_group()
    output.add_argument("--json", action="store_true", help="JSON output")
    output.add_argument(
        "--pytest",
        action="store_true",
        help="print the pytest command line instead of the file list",
    )
    return parser


def _render_selection(selection: Selection, args: argparse.Namespace) -> str:
    argv = pytest_argv(selection)
    if args.json:
        return json.dumps(
            {
                "mode": "full" if selection.full else "targeted",
                "tests": selection.tests,
                "triggers": [
                    {"path": t.path, "reason": t.reason}
                    for t in selection.triggers
                ],
                "unmapped": selection.unmapped,
                "pytest": argv,
            },
            indent=2,
        )
    if args.pytest:
        return shlex.join(argv)
    if selection.full:
        lines = [f"{t.path}: {t.reason}" for t in selection.triggers]
        return "\n".join(["full", *lines])
    return "\n".join(selection.tests)


def _source_at(git: GitRunner, commit: str) -> Callable[[str], str | None]:
    """A reader of a file's source at *commit*; ``None`` when it is absent."""

    def read(path: str) -> str | None:
        if not git(["ls-tree", "--name-only", commit, "--", path]).strip():
            return None
        return git(["show", f"{commit}:{path}"])

    return read


def _run_selection(args: argparse.Namespace, root: Path) -> int:
    git = run_git(root)
    # One merge base for both reads, so a fetch between them cannot split
    # the diff across two starting points.
    start = merge_base(git, args.base)
    selection = select_tests(
        changed_paths(git, start),
        collect_git_changes(git, root, start),
        build_index(root),
        lambda p: (root / p).is_file(),
        _source_at(git, start),
    )
    return _report_selection(selection, args)


def _report_selection(selection: Selection, args: argparse.Namespace) -> int:
    print(_render_selection(selection, args))
    if args.pytest and selection.full:
        for trigger in selection.triggers:
            print(
                f"targeted-tests: full suite: {trigger.path}: "
                f"{trigger.reason}",
                file=sys.stderr,
            )
    if selection.unmapped:
        print(
            "targeted-tests: no test maps to: "
            f"{', '.join(selection.unmapped)} — CI covers these",
            file=sys.stderr,
        )
    return 0


def _run_paths(args: argparse.Namespace, root: Path) -> int:
    changes = changes_from_paths(root, args.paths)
    selection = select_tests(
        [c.path for c in changes],
        [c for c in changes if c.path.endswith(".py")],
        build_index(root),
        lambda p: (root / p).is_file(),
        trigger=conflict_suite_trigger,
    )
    return _report_selection(selection, args)


def _run_overlap(args: argparse.Namespace, root: Path) -> int:
    git = run_git(root)
    start = merge_base(git, args.base)
    both = branch_overlap(git, start, args.base)
    if args.json:
        payload = {"base": args.base, "merge_base": start, "overlap": both}
        print(json.dumps(payload, indent=2))
    elif both:
        print("\n".join(both))
    if both:
        print(
            f"targeted-tests: {len(both)} file(s) changed on both "
            f"{args.base} and this branch since {start[:12]}",
            file=sys.stderr,
        )
    return 1 if both else 0


def main() -> int:
    """CLI entry point for ``targeted-tests``."""
    parser = _build_parser()
    args = parser.parse_args()
    if args.overlap and args.pytest:
        parser.error("--pytest does not apply to --overlap")
    if args.overlap and args.paths:
        parser.error("--paths does not apply to --overlap")
    try:
        root = git_toplevel(Path.cwd()).resolve()
        if args.overlap:
            return _run_overlap(args, root)
        if args.paths:
            return _run_paths(args, root)
        return _run_selection(args, root)
    except (BackstopError, OSError) as exc:
        print(f"targeted-tests: error: {exc}", file=sys.stderr)
        return 2
