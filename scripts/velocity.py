#!/usr/bin/env python3
"""
Collect development velocity metrics from GitHub Issues (CERTCC/Vultron).

Fetches all issues created on or after START_DATE, buckets them by week and
month, and emits a JSON document with raw counts suitable for downstream
analysis and visualization.

Usage:
    python scripts/velocity.py
    python scripts/velocity.py --output plan/data/velocity.json
    python scripts/velocity.py --output -          # stdout
    python scripts/velocity.py --start 2026-05-01  # override start date
    python scripts/velocity.py --repo OWNER/NAME   # override repo
"""

import argparse
import json
import re
import subprocess
import sys
from collections import defaultdict
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import httpx2 as httpx
import pandas as pd

REPO_OWNER = "CERTCC"
REPO_NAME = "Vultron"
DEFAULT_START = "2026-05-01"
DEFAULT_OUTPUT = "plan/data/velocity.json"

# Issue types that represent "discovery" work
DISCOVERY_TYPES = {"Idea", "Concern"}
# Issue types that represent structural grouping
EPIC_TYPES = {"Epic"}
# Everything else is treated as delivery work
BUG_TYPE = "Bug"

# Why an agent opened an issue (label prefix); see completeness-doctrine.md
# "Net Issues: Close More Than You Open".
OPENED_PREFIX = "opened:"
OPENED_REASONS = ("excursion", "separate-defect", "debt", "deferred")
# Reasons that add to the backlog; excursions net to zero by definition.
NET_OPENED_REASONS = ("separate-defect", "debt", "deferred")


# Pattern to identify a commit headline that merges the main branch in.
# The quotes around 'main' already prevent false matches on branch names
# like 'maintenance', so no word-boundary assertion is needed.
_MERGE_FROM_MAIN_RE = re.compile(
    r"^Merge (branch 'main'|remote-tracking branch 'origin/main')",
    re.IGNORECASE,
)

# Fixed format written by pr-execute (PAD-18-006).
_SUITE_RUNS_RE = re.compile(r"Suite runs:\s+(\d+)\s+full,\s+(\d+)\s+targeted")

# GraphQL query to fetch merged PRs with their commits and comments.
PR_GRAPHQL_QUERY = """
query($owner: String!, $name: String!, $cursor: String) {
  repository(owner: $owner, name: $name) {
    pullRequests(
      first: 50,
      after: $cursor,
      states: [MERGED],
      orderBy: {field: CREATED_AT, direction: DESC}
    ) {
      pageInfo { hasNextPage endCursor }
      nodes {
        number
        createdAt
        mergedAt
        headRefName
        commits(first: 250) {
          nodes {
            commit {
              messageHeadline
            }
          }
        }
        comments(first: 100) {
          nodes {
            body
          }
        }
      }
    }
  }
}
"""


def get_github_token() -> str:
    result = subprocess.run(
        ["gh", "auth", "token"], capture_output=True, text=True, check=True
    )
    return result.stdout.strip()


GRAPHQL_QUERY = """
query($owner: String!, $name: String!, $cursor: String) {
  repository(owner: $owner, name: $name) {
    issues(
      first: 100,
      after: $cursor,
      orderBy: {field: CREATED_AT, direction: ASC},
      filterBy: {since: $since}
    ) {
      pageInfo { hasNextPage endCursor }
      nodes {
        number
        createdAt
        closedAt
        state
        issueType { name }
      }
    }
  }
}
"""

# filterBy.since isn't a variable in the same position — use a parameterized query
GRAPHQL_QUERY = """
query($owner: String!, $name: String!, $cursor: String, $since: DateTime!) {
  repository(owner: $owner, name: $name) {
    issues(
      first: 100,
      after: $cursor,
      orderBy: {field: CREATED_AT, direction: ASC},
      filterBy: {since: $since}
    ) {
      pageInfo { hasNextPage endCursor }
      nodes {
        number
        createdAt
        closedAt
        state
        stateReason
        issueType { name }
        labels(first: 100) { nodes { name } }
      }
    }
  }
}
"""


def _graphql_paginate(
    query: str,
    variables: dict,
    token: str,
    page_extractor: Callable[[dict], dict],
    label: str = "items",
    timeout: int = 30,
) -> list[dict]:
    """Paginate a GitHub GraphQL query and return all nodes.

    ``page_extractor`` receives the ``data`` dict from the GraphQL response
    and must return a dict with ``nodes`` (list) and ``pageInfo`` (object with
    ``hasNextPage`` and ``endCursor``).
    """
    url = "https://api.github.com/graphql"
    headers = {"Authorization": f"bearer {token}"}
    nodes: list[dict] = []
    cursor = None

    with httpx.Client(headers=headers, timeout=timeout) as client:
        while True:
            resp = client.post(
                url,
                json={
                    "query": query,
                    "variables": {**variables, "cursor": cursor},
                },
            )
            resp.raise_for_status()
            body = resp.json()
            if "errors" in body:
                raise RuntimeError(f"GraphQL errors: {body['errors']}")

            page = page_extractor(body["data"])
            nodes.extend(page["nodes"])
            print(
                f"  fetched {len(nodes)} {label}...",
                file=sys.stderr,
                end="\r",
            )

            if not page["pageInfo"]["hasNextPage"]:
                break
            cursor = page["pageInfo"]["endCursor"]

    print(f"  fetched {len(nodes)} {label} total    ", file=sys.stderr)
    return nodes


def fetch_all_issues(
    owner: str, name: str, since: str, token: str
) -> list[dict]:
    return _graphql_paginate(
        GRAPHQL_QUERY,
        {"owner": owner, "name": name, "since": f"{since}T00:00:00Z"},
        token,
        lambda data: data["repository"]["issues"],
        label="issues",
    )


def fetch_merged_prs(
    owner: str, name: str, since: str, token: str
) -> list[dict]:
    """Fetch merged PRs with mergedAt >= since (YYYY-MM-DD).

    Returns PR dicts with ``number``, ``createdAt``, ``mergedAt``,
    ``headRefName``, ``commits.nodes``, and ``comments.nodes``.

    All merged PRs are fetched and filtered client-side; no server-side date
    predicate is available for ``mergedAt`` in the GitHub GraphQL API.  This
    is acceptable for a project where the total number of merged PRs is in
    the hundreds, not tens of thousands.
    """
    since_date = date.fromisoformat(since)
    all_prs = _graphql_paginate(
        PR_GRAPHQL_QUERY,
        {"owner": owner, "name": name},
        token,
        lambda data: data["repository"]["pullRequests"],
        label="PRs",
        timeout=60,
    )
    return [
        pr
        for pr in all_prs
        if (d := iso_to_date(pr.get("mergedAt"))) is not None
        and d >= since_date
    ]


def fetch_workflow_runs(
    owner: str,
    name: str,
    since: str,
    token: str,
    event: str = "pull_request",
    branch: str | None = None,
) -> list[dict]:
    """Fetch completed GitHub Actions workflow runs since ``since``.

    Returns a list of run dicts (each with at least ``head_branch``,
    ``conclusion``, and ``created_at``) for runs whose ``created_at`` falls
    on or after ``since`` (YYYY-MM-DD).  The REST API returns runs
    newest-first; pagination stops when the oldest run on the current page
    predates the window.
    """
    url = f"https://api.github.com/repos/{owner}/{name}/actions/runs"
    headers = {
        "Authorization": f"bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    since_date = date.fromisoformat(since)
    params: dict[str, str | int] = {
        "event": event,
        "per_page": 100,
        "status": "completed",
    }
    if branch:
        params["branch"] = branch

    runs: list[dict] = []
    page_num = 1
    tag = f"{event}/{branch or 'all'}"

    with httpx.Client(headers=headers, timeout=30) as client:
        while True:
            params["page"] = page_num
            resp = client.get(url, params=params)
            resp.raise_for_status()
            body = resp.json()

            batch: list[dict] = body.get("workflow_runs", [])
            if not batch:
                break

            for run in batch:
                run_date = iso_to_date(run.get("created_at"))
                if run_date and run_date >= since_date:
                    runs.append(run)

            print(
                f"  fetched {len(runs)} workflow runs ({tag})...",
                file=sys.stderr,
                end="\r",
            )

            # Runs arrive newest-first; stop once the page's oldest predates window.
            oldest = iso_to_date(batch[-1].get("created_at"))
            if (oldest and oldest < since_date) or len(batch) < 100:
                break
            page_num += 1

    print(
        f"  fetched {len(runs)} workflow runs ({tag}) total    ",
        file=sys.stderr,
    )
    return runs


def classify_type(issue: dict) -> str:
    """Return normalized issue type string."""
    itype = (issue.get("issueType") or {}).get("name")
    if not itype:
        return "Untyped"
    return str(itype)


def delivery_type(issue: dict) -> bool:
    """True if this issue is delivery work (not discovery, epic, or bug)."""
    t = classify_type(issue)
    return t not in DISCOVERY_TYPES | EPIC_TYPES | {BUG_TYPE, "Untyped"}


def iso_to_date(s: str | None) -> date | None:
    if not s:
        return None
    return datetime.fromisoformat(s.replace("Z", "+00:00")).date()


def week_key(d: date) -> str:
    """ISO week string: YYYY-Www"""
    return f"{d.isocalendar().year}-W{d.isocalendar().week:02d}"


def month_key(d: date) -> str:
    return f"{d.year}-{d.month:02d}"


def _period_keys(start: date, today: date) -> tuple[list[str], list[str]]:
    """Return (weeks, sorted months) from the week of start up to today."""
    all_weeks = []
    all_months = set()
    cursor = start - timedelta(days=start.weekday())  # Monday of start week
    while cursor <= today:
        all_weeks.append(week_key(cursor))
        all_months.add(month_key(cursor))
        cursor += timedelta(weeks=1)
    # A week's Monday can fall in the previous month, so add the end points.
    all_months.update({month_key(start), month_key(today)})
    return all_weeks, sorted(all_months)


def _period_counter() -> dict[str, dict[str, int]]:
    """Return an empty counts[period][type] mapping."""
    return defaultdict(lambda: defaultdict(int))


def _count_issues(
    issues: list[dict], start: date
) -> tuple[dict[str, dict[str, dict[str, int]]], dict[str, list[float]]]:
    """Count created/closed issues per week and month, and collect cycle days.

    Returns (counts, cycle_days_by_type) where counts is keyed by
    "created_week", "created_month", "closed_week", "closed_month".
    """
    # counts[bucket][period][type] = count
    counts = {
        "created_week": _period_counter(),
        "created_month": _period_counter(),
        "closed_week": _period_counter(),
        "closed_month": _period_counter(),
    }
    cycle_days_by_type: dict[str, list[float]] = defaultdict(list)

    for issue in issues:
        created = iso_to_date(issue["createdAt"])
        closed = iso_to_date(issue.get("closedAt"))
        itype = classify_type(issue)

        if created and created >= start:
            counts["created_week"][week_key(created)][itype] += 1
            counts["created_month"][month_key(created)][itype] += 1

        if closed and closed >= start:
            counts["closed_week"][week_key(closed)][itype] += 1
            counts["closed_month"][month_key(closed)][itype] += 1

        if created and closed:
            cycle_days_by_type[itype].append((closed - created).days)

    return counts, cycle_days_by_type


def _cycle_time_summary(
    cycle_days_by_type: dict[str, list[float]],
) -> dict[str, dict]:
    """Return median/p25/p75 days to close and sample size, by type."""
    cycle_time = {}
    for itype, days in cycle_days_by_type.items():
        s = pd.Series(days)
        cycle_time[itype] = {
            "median_days": round(float(s.median()), 1),
            "p25_days": round(float(s.quantile(0.25)), 1),
            "p75_days": round(float(s.quantile(0.75)), 1),
            "n": len(days),
        }
    return cycle_time


def _backlog_at(issues: list[dict], period_end: date) -> dict[str, int]:
    """Count issues open at period_end, by type.

    Open means created <= period_end AND (not closed OR closed > period_end).
    """
    counts: dict[str, int] = defaultdict(int)
    for issue in issues:
        created = iso_to_date(issue["createdAt"])
        closed = iso_to_date(issue.get("closedAt"))
        if created is None:
            continue
        if created <= period_end and (closed is None or closed > period_end):
            counts[classify_type(issue)] += 1
    return dict(counts)


def _weekly_backlog(
    issues: list[dict], all_weeks: list[str], today: date
) -> dict[str, dict[str, int]]:
    """Backlog snapshot at the end (Sunday) of each completed week."""
    weekly_backlog = {}
    for w in all_weeks:
        year, wnum = int(w[:4]), int(w[6:])
        week_start = date.fromisocalendar(year, wnum, 1)
        week_end = week_start + timedelta(days=6)
        if week_end <= today:
            weekly_backlog[w] = _backlog_at(issues, week_end)
    return weekly_backlog


def _monthly_backlog(
    issues: list[dict], all_months: list[str], today: date
) -> dict[str, dict[str, int]]:
    """Backlog snapshot on the last day of each completed month."""
    monthly_backlog = {}
    for m in all_months:
        year, mon = int(m[:4]), int(m[5:])
        last_day = (
            date(year, mon + 1, 1) - timedelta(days=1)
            if mon < 12
            else date(year, 12, 31)
        )
        if last_day <= today:
            monthly_backlog[m] = _backlog_at(issues, last_day)
    return monthly_backlog


def _fill_zeros(
    period_dict: dict, periods: list, all_types: list[str]
) -> list[dict]:
    """Serialize period_dict with zero-filled periods for all known types."""
    rows = []
    for p in periods:
        row = {"period": p}
        for t in all_types:
            row[t] = period_dict.get(p, {}).get(t, 0)
        rows.append(row)
    return rows


def opened_reason(issue: dict) -> str | None:
    """Return the ``opened:`` reason label on an issue, if it has one."""
    names = [n["name"] for n in (issue.get("labels") or {}).get("nodes", [])]
    for name in names:
        if name.startswith(OPENED_PREFIX):
            reason: str = name[len(OPENED_PREFIX) :]
            if reason in OPENED_REASONS:
                return reason
    return None


def _net_issues(issues: list[dict], periods: list[str], key) -> list[dict]:
    """Per-period net issues: closed minus opened, by reason.

    ``closed`` counts completed non-Epic issues that are not excursions.
    Duplicate and not-planned closures are reported apart in ``closed_other``
    and do not count toward the net. ``net`` is ``closed`` minus the
    separate-defect, debt, and deferred issues opened in the period.
    """
    rows: dict[str, dict[str, int]] = {
        p: {
            "closed": 0,
            "closed_other": 0,
            **{f"opened_{r}": 0 for r in OPENED_REASONS},
        }
        for p in periods
    }
    for issue in issues:
        reason = opened_reason(issue)
        created = iso_to_date(issue.get("createdAt"))
        if reason and created and key(created) in rows:
            rows[key(created)][f"opened_{reason}"] += 1
        closed = iso_to_date(issue.get("closedAt"))
        if not closed or key(closed) not in rows:
            continue
        if classify_type(issue) in EPIC_TYPES or reason == "excursion":
            continue
        row = rows[key(closed)]
        if issue.get("stateReason") == "COMPLETED":
            row["closed"] += 1
        else:
            row["closed_other"] += 1
    for row in rows.values():
        row["net"] = row["closed"] - sum(
            row[f"opened_{r}"] for r in NET_OPENED_REASONS
        )
    return [{"period": p, **row} for p, row in rows.items()]


def parse_suite_runs_line(body: str) -> tuple[int, int] | None:
    """Parse the ``Suite runs: N full, M targeted`` line from a comment body.

    Returns ``(full, targeted)`` when the line is present and well-formed.
    Returns ``None`` when the line is absent or malformed (PAD-18-006).
    """
    m = _SUITE_RUNS_RE.search(body)
    if m:
        return int(m.group(1)), int(m.group(2))
    return None


def _is_merge_from_main(headline: str) -> bool:
    """Return True if a commit headline indicates a merge from the main branch."""
    return bool(_MERGE_FROM_MAIN_RE.match(headline))


def _count_merges_from_main(commits: list[dict]) -> int:
    """Count commits whose headline indicates a merge from the main branch."""
    return sum(
        1
        for c in commits
        if _is_merge_from_main(
            (c.get("commit") or {}).get("messageHeadline", "")
        )
    )


def _extract_suite_runs(pr: dict) -> tuple[int, int] | None:
    """Search a PR's comments for the Suite runs line; return counts or None."""
    for comment in (pr.get("comments") or {}).get("nodes", []):
        result = parse_suite_runs_line(comment.get("body", ""))
        if result is not None:
            return result
    return None


def build_pr_pipeline_record(
    pr: dict,
    ci_runs: int,
    failed_ci_runs: int,
) -> dict:
    """Build a pipeline-cost record for a single merged PR.

    Args:
        pr: GraphQL PR dict with ``createdAt``, ``mergedAt``, ``number``,
            ``headRefName``, ``commits.nodes``, and ``comments.nodes``.
        ci_runs: total completed CI workflow runs triggered for this PR's branch.
        failed_ci_runs: subset of ``ci_runs`` whose conclusion was ``failure``.

    Returns a flat dict suitable for per-PR output and weekly aggregation.
    """
    created_str = pr.get("createdAt")
    merged_str = pr.get("mergedAt")

    open_to_merge_hours: float | None = None
    if created_str and merged_str:
        created_dt = datetime.fromisoformat(created_str.replace("Z", "+00:00"))
        merged_dt = datetime.fromisoformat(merged_str.replace("Z", "+00:00"))
        open_to_merge_hours = round(
            (merged_dt - created_dt).total_seconds() / 3600, 1
        )

    merges_from_main = _count_merges_from_main(
        (pr.get("commits") or {}).get("nodes", [])
    )

    suite = _extract_suite_runs(pr)
    full_suite_runs: int | None = None
    targeted_suite_runs: int | None = None
    if suite is not None:
        full_suite_runs, targeted_suite_runs = suite

    return {
        "pr_number": pr.get("number"),
        "merged_at": merged_str,
        "open_to_merge_hours": open_to_merge_hours,
        "ci_runs": ci_runs,
        "failed_ci_runs": failed_ci_runs,
        "merges_from_main": merges_from_main,
        "full_suite_runs": full_suite_runs,
        "targeted_suite_runs": targeted_suite_runs,
    }


def _index_runs_by_branch(
    runs: list[dict],
) -> dict[str, tuple[int, int]]:
    """Build a branch → (total_runs, failed_runs) index from workflow run dicts."""
    by_branch: dict[str, list[dict]] = defaultdict(list)
    for run in runs:
        b = run.get("head_branch", "")
        if b:
            by_branch[b].append(run)
    return {
        branch: (
            len(run_list),
            sum(1 for r in run_list if r.get("conclusion") == "failure"),
        )
        for branch, run_list in by_branch.items()
    }


# Numeric fields included in weekly median + total aggregates.
_PR_NUMERIC_FIELDS = (
    "ci_runs",
    "failed_ci_runs",
    "merges_from_main",
    "open_to_merge_hours",
)


def _pr_weekly_aggregates(
    pr_records: list[dict], all_weeks: list[str]
) -> list[dict]:
    """Aggregate per-PR pipeline cost fields by week of mergedAt.

    For each week, reports ``pr_count``, plus ``median_<field>`` and
    ``total_<field>`` for each numeric field.  Suite-run totals are included
    only for PRs that carried the ``Suite runs:`` line; absent values
    (``None``) are excluded from aggregates.  All values are ``None`` for
    weeks with no merged PRs.
    """
    week_set = set(all_weeks)
    by_week: dict[str, list[dict]] = defaultdict(list)
    for rec in pr_records:
        d = iso_to_date(rec.get("merged_at"))
        if d:
            w = week_key(d)
            if w in week_set:
                by_week[w].append(rec)

    rows = []
    for w in all_weeks:
        recs = by_week.get(w, [])
        row: dict = {"week": w, "pr_count": len(recs)}

        for field in _PR_NUMERIC_FIELDS:
            values = [r[field] for r in recs if r.get(field) is not None]
            if values:
                s = pd.Series(values)
                row[f"median_{field}"] = round(float(s.median()), 1)
                row[f"total_{field}"] = round(float(s.sum()), 1)
            else:
                row[f"median_{field}"] = None
                row[f"total_{field}"] = None

        for suite_field in ("full_suite_runs", "targeted_suite_runs"):
            values_s = [
                r[suite_field] for r in recs if r.get(suite_field) is not None
            ]
            row[f"total_{suite_field}"] = sum(values_s) if values_s else None

        rows.append(row)
    return rows


def _weekly_main_failures(
    main_runs: list[dict], all_weeks: list[str]
) -> list[dict]:
    """Count failed CI runs on the main branch per week.

    ``main_runs`` is a list of workflow-run dicts from the REST API
    (``created_at`` key, snake_case).
    """
    week_set = set(all_weeks)
    counts: dict[str, int] = defaultdict(int)
    for run in main_runs:
        if run.get("conclusion") == "failure":
            ts = run.get("created_at") or run.get("createdAt")
            d = iso_to_date(ts)
            if d:
                w = week_key(d)
                if w in week_set:
                    counts[w] += 1
    return [
        {"week": w, "failed_ci_runs_on_main": counts.get(w, 0)}
        for w in all_weeks
    ]


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
            ``fetch_workflow_runs``.
        main_workflow_runs: completed ``push`` workflow run dicts on ``main``
            from ``fetch_workflow_runs``.
        start: window start date.

    Returns a dict with keys ``per_pr``, ``weekly_pr_cost``, and
    ``weekly_main_failures``.
    """
    today = datetime.now(UTC).date()
    all_weeks, _ = _period_keys(start, today)

    runs_by_branch = _index_runs_by_branch(pr_workflow_runs)

    pr_records = []
    for pr in prs:
        branch = pr.get("headRefName", "")
        ci_total, ci_failed = runs_by_branch.get(branch, (0, 0))
        pr_records.append(build_pr_pipeline_record(pr, ci_total, ci_failed))

    return {
        "per_pr": pr_records,
        "weekly_pr_cost": _pr_weekly_aggregates(pr_records, all_weeks),
        "weekly_main_failures": _weekly_main_failures(
            main_workflow_runs, all_weeks
        ),
    }


def build_metrics(issues: list[dict], start: date) -> dict:
    # Collect all weeks and months in range up to today
    today = datetime.now(UTC).date()
    all_weeks, all_months_sorted = _period_keys(start, today)

    all_types = sorted({classify_type(i) for i in issues} | {"Untyped"})

    counts, cycle_days_by_type = _count_issues(issues, start)
    weekly_backlog = _weekly_backlog(issues, all_weeks, today)
    monthly_backlog = _monthly_backlog(issues, all_months_sorted, today)

    def by_week(period_dict: dict) -> list[dict]:
        return _fill_zeros(period_dict, all_weeks, all_types)

    def by_month(period_dict: dict) -> list[dict]:
        return _fill_zeros(period_dict, all_months_sorted, all_types)

    return {
        "meta": {
            "repo": f"{REPO_OWNER}/{REPO_NAME}",
            "start_date": start.isoformat(),
            "generated_at": datetime.now(UTC).isoformat(),
            "total_issues_fetched": len(issues),
            "issue_types": all_types,
        },
        "created_by_week": by_week(counts["created_week"]),
        "created_by_month": by_month(counts["created_month"]),
        "closed_by_week": by_week(counts["closed_week"]),
        "closed_by_month": by_month(counts["closed_month"]),
        "open_backlog_by_week": by_week(weekly_backlog),
        "open_backlog_by_month": by_month(monthly_backlog),
        "cycle_time_by_type": _cycle_time_summary(cycle_days_by_type),
        "net_issues_by_week": _net_issues(issues, all_weeks, week_key),
        "net_issues_by_month": _net_issues(
            issues, all_months_sorted, month_key
        ),
    }


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

    print(
        f"Fetching merged PRs from {owner}/{name} since {start}...",
        file=sys.stderr,
    )
    merged_prs = fetch_merged_prs(owner, name, args.start, token)

    print("Fetching PR workflow runs...", file=sys.stderr)
    pr_runs = fetch_workflow_runs(
        owner, name, args.start, token, event="pull_request"
    )

    print("Fetching main-branch workflow runs...", file=sys.stderr)
    main_runs = fetch_workflow_runs(
        owner, name, args.start, token, event="push", branch="main"
    )

    print("Computing pipeline cost metrics...", file=sys.stderr)
    metrics["pipeline_cost"] = build_pr_pipeline_metrics(
        merged_prs, pr_runs, main_runs, start
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
