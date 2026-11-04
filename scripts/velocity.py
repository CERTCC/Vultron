#!/usr/bin/env python3
"""
Collect development velocity metrics from GitHub (CERTCC/Vultron).

Fetches all issues created on or after START_DATE, buckets them by week and
month, and emits a JSON document with raw counts suitable for downstream
analysis and visualization, including how Concerns were closed.  Unless
``--no-pipeline-cost`` is given, it also fetches merged PRs and GitHub Actions
runs and adds a ``pipeline_cost`` section: per-PR CI runs, merges from main,
local suite runs, questions asked and filed, and open-to-merge time, plus
weekly failed CI runs on main (PAD-18-007) and weekly red episodes on main
with each episode's candidate partner merges.

Usage:
    python scripts/velocity.py
    python scripts/velocity.py --output plan/data/velocity.json
    python scripts/velocity.py --output -          # stdout
    python scripts/velocity.py --start 2026-05-01  # override start date
    python scripts/velocity.py --repo OWNER/NAME   # override repo
    python scripts/velocity.py --no-pipeline-cost  # issues only
"""

import argparse
import json
import sys
from datetime import date
from pathlib import Path

from velocity_metrics.github import (
    REPO_NAME,
    REPO_OWNER,
    fetch_all_issues,
    get_github_token,
)
from velocity_metrics.issues import build_metrics
from velocity_metrics.pipeline_cost import collect_pipeline_cost

DEFAULT_START = "2026-05-01"
DEFAULT_OUTPUT = "plan/data/velocity.json"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        default=DEFAULT_OUTPUT,
        help=f"Output path (default: {DEFAULT_OUTPUT}). Use '-' for stdout.",
    )
    parser.add_argument(
        "--start",
        default=DEFAULT_START,
        help=f"Start date ISO 8601 (default: {DEFAULT_START})",
    )
    parser.add_argument(
        "--repo",
        default=f"{REPO_OWNER}/{REPO_NAME}",
        help="GitHub repo as OWNER/NAME",
    )
    parser.add_argument(
        "--no-pipeline-cost",
        action="store_true",
        help=(
            "Skip the per-PR pipeline-cost section (needs a token with "
            "Actions read access); the output then has no pipeline_cost key."
        ),
    )
    args = parser.parse_args()

    owner, name = args.repo.split("/", 1)
    start = date.fromisoformat(args.start)

    print(
        f"Fetching issues from {owner}/{name} since {start}...",
        file=sys.stderr,
    )
    token = get_github_token()
    issues = fetch_all_issues(owner, name, args.start, token)

    print("Computing issue metrics...", file=sys.stderr)
    metrics = build_metrics(issues, start)

    if not args.no_pipeline_cost:
        metrics["pipeline_cost"] = collect_pipeline_cost(
            owner, name, start, token
        )

    output = json.dumps(metrics, indent=2)

    if args.output == "-":
        print(output)
    else:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(output)
        print(f"Written to {out_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
