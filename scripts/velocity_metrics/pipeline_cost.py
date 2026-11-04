"""Assembly of the ``pipeline_cost`` section from the fetched PRs and runs."""

from __future__ import annotations

import sys
from datetime import UTC, date, datetime

from .github import fetch_merged_prs, fetch_workflow_runs
from .main_health import (
    _main_red_episodes,
    _weekly_main_episodes,
    _weekly_main_failures,
)
from .periods import _period_keys, iso_to_date
from .pr_pipeline import (
    _ci_iteration_counts,
    _pr_weekly_aggregates,
    _RunIndex,
    build_pr_pipeline_record,
)


def pr_runs_window_start(prs: list[dict], start: date) -> date:
    """Return the date from which PR workflow runs must be fetched.

    A PR merged inside the window may have been opened before it; its runs
    from before ``start`` still count toward its cost.
    """
    opened = [d for pr in prs if (d := iso_to_date(pr.get("createdAt")))]
    return min([start, *opened])


def build_pr_pipeline_metrics(
    prs: list[dict],
    pr_workflow_runs: list[dict],
    main_workflow_runs: list[dict],
    start: date,
) -> dict:
    """Compute per-PR pipeline cost and weekly aggregates.

    Args:
        prs: merged PR dicts from ``fetch_merged_prs``.
        pr_workflow_runs: completed ``pull_request`` workflow run dicts from
            ``fetch_workflow_runs``, fetched from ``pr_runs_window_start``.
        main_workflow_runs: completed ``push`` workflow run dicts on ``main``
            from ``fetch_workflow_runs``.
        start: window start date.

    Returns a dict with keys ``per_pr``, ``weekly_pr_cost``,
    ``weekly_main_failures``, and ``main_red_episodes``.  Each
    ``weekly_main_failures`` row carries the failed-commit count beside the
    week's red episodes opened, merges to main, and episodes per 100 merges
    (see ``_weekly_main_episodes``).
    """
    today = datetime.now(UTC).date()
    all_weeks, _ = _period_keys(start, today)

    index = _RunIndex(pr_workflow_runs)

    pr_records = []
    for pr in prs:
        ci_total, ci_failed = _ci_iteration_counts(index.runs_for(pr))
        pr_records.append(build_pr_pipeline_record(pr, ci_total, ci_failed))

    episodes = _main_red_episodes(main_workflow_runs, prs, index, start)
    episode_rows = {
        row["week"]: row
        for row in _weekly_main_episodes(episodes, prs, all_weeks)
    }
    weekly_main = [
        {**row, **episode_rows[row["week"]]}
        for row in _weekly_main_failures(main_workflow_runs, all_weeks)
    ]

    return {
        "per_pr": pr_records,
        "weekly_pr_cost": _pr_weekly_aggregates(pr_records, all_weeks),
        "weekly_main_failures": weekly_main,
        "main_red_episodes": episodes,
    }


def collect_pipeline_cost(
    owner: str, name: str, start: date, token: str
) -> dict:
    """Fetch merged PRs and workflow runs, then build the pipeline-cost section."""
    print(
        f"Fetching merged PRs from {owner}/{name} since {start}...",
        file=sys.stderr,
    )
    merged_prs = fetch_merged_prs(owner, name, start.isoformat(), token)

    runs_since = pr_runs_window_start(merged_prs, start)
    print(f"Fetching PR workflow runs since {runs_since}...", file=sys.stderr)
    pr_runs = fetch_workflow_runs(
        owner, name, runs_since.isoformat(), token, event="pull_request"
    )

    print("Fetching main-branch workflow runs...", file=sys.stderr)
    main_runs = fetch_workflow_runs(
        owner, name, start.isoformat(), token, event="push", branch="main"
    )

    print("Computing pipeline cost metrics...", file=sys.stderr)
    return build_pr_pipeline_metrics(merged_prs, pr_runs, main_runs, start)
