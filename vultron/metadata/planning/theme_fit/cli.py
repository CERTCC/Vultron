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
"""``theme-fit``: report structural theme-fit findings on open Issues.

::

    theme-fit                 # the Markdown report (exit 1 on any finding)
    theme-fit --json          # the report as JSON
    theme-fit --coherence     # only the coherence-per-tier table
    theme-fit --max-chars 65536   # the report, cut to fit an Issue body
    theme-fit --no-schedule   # skip Project #24 (a token that cannot read it)

Read-only: it applies no labels and moves no Issue (``notes/epic-themes.md``
§ "Acting on a Theme-Fit Finding"). Exit codes: 0 no findings, 1 findings,
2 the catalog cannot be loaded or a ``gh`` call fails. Untriaged Issues (no
parent; PAD-01-007, PAD-02-028) are listed in the report but are not
findings, so they leave the exit code at 0.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from vultron.metadata.file_loading import MetadataLoadError
from vultron.metadata.planning.gh import (
    DEFAULT_REPO,
    GH_FAILURES,
    Runner,
    gh_failure_detail,
    run_gh,
)
from vultron.metadata.planning.theme_fit.analyze import analyze
from vultron.metadata.planning.theme_fit.fetch import fetch_open_issues
from vultron.metadata.planning.theme_fit.render import (
    GITHUB_BODY_LIMIT,
    render_coherence,
    render_markdown,
)
from vultron.metadata.planning.themes import load_theme_catalog


def main(argv: list[str] | None = None, run: Runner = run_gh) -> int:
    """CLI entry point: fetch open Issues, apply the rules, print the report."""
    parser = argparse.ArgumentParser(
        description=(
            "Report structural theme-fit findings on open Issues and "
            "coherence per Schedule tier. Read-only."
        )
    )
    parser.add_argument(
        "--repo",
        default=DEFAULT_REPO,
        help="OWNER/NAME (default: %(default)s)",
    )
    parser.add_argument(
        "--catalog",
        type=Path,
        help="the catalog note (default: notes/epic-themes.md)",
    )
    out = parser.add_mutually_exclusive_group()
    out.add_argument(
        "--json", action="store_true", help="print the report as JSON"
    )
    out.add_argument(
        "--coherence",
        action="store_true",
        help="print only the coherence-per-tier table",
    )
    parser.add_argument(
        "--max-chars",
        type=int,
        metavar="N",
        help=(
            "cut the Markdown report's finding and untriaged lists so it "
            "fits in N "
            f"characters (an Issue body takes {GITHUB_BODY_LIMIT})"
        ),
    )
    parser.add_argument(
        "--no-schedule",
        action="store_true",
        help=(
            "do not read Project #24's Schedule, for a token that cannot "
            "(such as a workflow's GITHUB_TOKEN); coherence is then shown "
            "for all tiers together"
        ),
    )
    args = parser.parse_args(argv)
    if args.max_chars is not None and args.max_chars < 1:
        parser.error("--max-chars must be a positive number")

    try:
        catalog = load_theme_catalog(args.catalog)
    except (MetadataLoadError, FileNotFoundError) as exc:
        print(f"theme-fit: {exc}", file=sys.stderr)
        return 2
    try:
        issues = fetch_open_issues(
            args.repo, run, read_schedule=not args.no_schedule
        )
    except GH_FAILURES as exc:
        print(
            f"theme-fit: gh failed: {gh_failure_detail(exc)}", file=sys.stderr
        )
        return 2

    report = analyze(issues, catalog, schedule_read=not args.no_schedule)
    if args.json:
        print(json.dumps(report.to_json(), indent=2))
    elif args.coherence:
        print("\n".join(render_coherence(report)))
    else:
        try:
            text = render_markdown(report, args.max_chars)
        except ValueError as exc:
            print(f"theme-fit: {exc}", file=sys.stderr)
            return 2
        print(text, end="")
    return 0 if report.clean else 1


if __name__ == "__main__":
    sys.exit(main())
