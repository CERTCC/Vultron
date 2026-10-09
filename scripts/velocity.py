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
import subprocess
import sys
from collections import defaultdict
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


def fetch_all_issues(
    owner: str, name: str, since: str, token: str
) -> list[dict]:
    url = "https://api.github.com/graphql"
    headers = {"Authorization": f"bearer {token}"}
    issues = []
    cursor = None

    with httpx.Client(headers=headers, timeout=30) as client:
        while True:
            variables = {
                "owner": owner,
                "name": name,
                "since": f"{since}T00:00:00Z",
                "cursor": cursor,
            }
            resp = client.post(
                url,
                json={"query": GRAPHQL_QUERY, "variables": variables},
            )
            resp.raise_for_status()
            body = resp.json()
            if "errors" in body:
                raise RuntimeError(f"GraphQL errors: {body['errors']}")

            page = body["data"]["repository"]["issues"]
            issues.extend(page["nodes"])
            print(
                f"  fetched {len(issues)} issues...", file=sys.stderr, end="\r"
            )

            if not page["pageInfo"]["hasNextPage"]:
                break
            cursor = page["pageInfo"]["endCursor"]

    print(f"  fetched {len(issues)} issues total    ", file=sys.stderr)
    return issues


def classify_type(issue: dict) -> str:
    """Return normalized issue type string."""
    itype = (issue.get("issueType") or {}).get("name")
    if not itype:
        return "Untyped"
    return itype


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

    print("Computing metrics...", file=sys.stderr)
    metrics = build_metrics(issues, start)

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
