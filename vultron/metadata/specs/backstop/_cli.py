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
"""``spec-backstop`` command-line interface."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from vultron.metadata.base import repo_root
from vultron.metadata.specs.backstop._model import (
    HUB_THRESHOLD,
    BackstopError,
    FileChange,
    Manifest,
)
from vultron.metadata.specs.backstop._diff import (
    changes_from_paths,
    collect_git_changes,
    git_toplevel,
    _run_git,
)
from vultron.metadata.specs.backstop._symbols import build_test_index
from vultron.metadata.specs.backstop._analysis import (
    analyze,
    load_requirements,
)
from vultron.metadata.specs.backstop._manifest import (
    parse_manifest,
    unresolved_groups,
)
from vultron.metadata.specs.backstop._render import render_json, render_text


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="spec-backstop",
        description=(
            "List the spec groups that plausibly govern the changed code and "
            "check them against a Spec manifest."
        ),
    )
    parser.add_argument("--base", default="origin/main", help="base ref")
    parser.add_argument(
        "--manifest", help="Spec manifest file, or - for stdin"
    )
    parser.add_argument(
        "--paths", nargs="+", help="treat these files as fully changed"
    )
    parser.add_argument("--json", action="store_true", help="JSON output")
    parser.add_argument(
        "--hub-threshold",
        type=int,
        default=HUB_THRESHOLD,
        metavar="N",
        help=(
            "demote import hits for symbols imported by more than N test "
            f"files to INFO (default {HUB_THRESHOLD})"
        ),
    )
    return parser


def _read_manifest(source: str, topics: set[str]) -> Manifest:
    if source == "-":
        return parse_manifest(sys.stdin.read(), topics)
    try:
        text = Path(source).read_text(encoding="utf-8")
    except OSError as exc:
        raise BackstopError(f"cannot read manifest {source}: {exc}") from exc
    return parse_manifest(text, topics)


def _collect(args: argparse.Namespace) -> tuple[Path, list[FileChange]]:
    if args.paths:
        root = repo_root().resolve()
        return root, changes_from_paths(root, args.paths)
    root = git_toplevel(Path.cwd()).resolve()
    return root, collect_git_changes(_run_git(root), root, args.base)


def _run(args: argparse.Namespace) -> int:
    root, changes = _collect(args)
    requirements = load_requirements(root / "specs")
    report = analyze(
        changes, build_test_index(root), requirements, args.hub_threshold
    )
    unresolved = None
    if args.manifest:
        topics = {r.topic for r in requirements}
        manifest = _read_manifest(args.manifest, topics)
        unresolved = unresolved_groups(report.must, manifest)
    render = render_json if args.json else render_text
    print(render(report, unresolved))
    if report.no_signal:
        print(
            "spec-backstop: no deterministic signal for: "
            f"{', '.join(report.no_signal)} — rely on manifest judgment",
            file=sys.stderr,
        )
    return 1 if unresolved else 0


def main() -> int:
    """CLI entry point for ``spec-backstop``."""
    args = _build_parser().parse_args()
    try:
        return _run(args)
    except (BackstopError, FileNotFoundError) as exc:
        print(f"spec-backstop: error: {exc}", file=sys.stderr)
        return 2
