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
from datetime import date, datetime, timedelta, timezone
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
        issueType { name }
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


def build_metrics(issues: list[dict], start: date) -> dict:
    # Collect all weeks and months in range up to today
    today = date.today()
    all_weeks = []
    all_months = set()
    cursor = start - timedelta(days=start.weekday())  # Monday of start week
    while cursor <= today:
        all_weeks.append(week_key(cursor))
        all_months.add(month_key(cursor))
        cursor += timedelta(weeks=1)
    all_months_sorted = sorted(all_months)

    all_types = sorted({classify_type(i) for i in issues} | {"Untyped"})

    # --- Per-period counts ---
    # created[period][type] = count
    created_week: dict[str, dict[str, int]] = defaultdict(
        lambda: defaultdict(int)
    )
    created_month: dict[str, dict[str, int]] = defaultdict(
        lambda: defaultdict(int)
    )
    closed_week: dict[str, dict[str, int]] = defaultdict(
        lambda: defaultdict(int)
    )
    closed_month: dict[str, dict[str, int]] = defaultdict(
        lambda: defaultdict(int)
    )

    cycle_days_by_type: dict[str, list[float]] = defaultdict(list)

    for issue in issues:
        created = iso_to_date(issue["createdAt"])
        closed = iso_to_date(issue.get("closedAt"))
        itype = classify_type(issue)

        if created and created >= start:
            created_week[week_key(created)][itype] += 1
            created_month[month_key(created)][itype] += 1

        if closed and closed >= start:
            closed_week[week_key(closed)][itype] += 1
            closed_month[month_key(closed)][itype] += 1

        if created and closed:
            cycle_days_by_type[itype].append((closed - created).days)

    # --- Cycle time (median days to close, by type) ---
    cycle_time = {}
    for itype, days in cycle_days_by_type.items():
        s = pd.Series(days)
        cycle_time[itype] = {
            "median_days": round(float(s.median()), 1),
            "p25_days": round(float(s.quantile(0.25)), 1),
            "p75_days": round(float(s.quantile(0.75)), 1),
            "n": len(days),
        }

    # --- Running open backlog per type per period ---
    # For each period end, count issues open at that moment
    # (created <= period_end AND (not closed OR closed > period_end))
    def backlog_at(period_end: date) -> dict[str, int]:
        counts: dict[str, int] = defaultdict(int)
        for issue in issues:
            created = iso_to_date(issue["createdAt"])
            closed = iso_to_date(issue.get("closedAt"))
            if created is None:
                continue
            if created <= period_end and (
                closed is None or closed > period_end
            ):
                counts[classify_type(issue)] += 1
        return dict(counts)

    # Weekly backlog snapshots (end of each week = Sunday)
    weekly_backlog = {}
    for w in all_weeks:
        year, wnum = int(w[:4]), int(w[6:])
        week_start = date.fromisocalendar(year, wnum, 1)
        week_end = week_start + timedelta(days=6)
        if week_end <= today:
            weekly_backlog[w] = backlog_at(week_end)

    # Monthly backlog snapshots (last day of month)
    monthly_backlog = {}
    for m in all_months_sorted:
        year, mon = int(m[:4]), int(m[5:])
        last_day = (
            date(year, mon + 1, 1) - timedelta(days=1)
            if mon < 12
            else date(year, 12, 31)
        )
        if last_day <= today:
            monthly_backlog[m] = backlog_at(last_day)

    # --- Serialize with zero-filled periods for all known types ---
    def fill_zeros(period_dict: dict, periods: list) -> list[dict]:
        rows = []
        for p in periods:
            row = {"period": p}
            for t in all_types:
                row[t] = period_dict.get(p, {}).get(t, 0)
            rows.append(row)
        return rows

    return {
        "meta": {
            "repo": f"{REPO_OWNER}/{REPO_NAME}",
            "start_date": start.isoformat(),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "total_issues_fetched": len(issues),
            "issue_types": all_types,
        },
        "created_by_week": fill_zeros(created_week, all_weeks),
        "created_by_month": fill_zeros(created_month, all_months_sorted),
        "closed_by_week": fill_zeros(closed_week, all_weeks),
        "closed_by_month": fill_zeros(closed_month, all_months_sorted),
        "open_backlog_by_week": fill_zeros(weekly_backlog, all_weeks),
        "open_backlog_by_month": fill_zeros(
            monthly_backlog, all_months_sorted
        ),
        "cycle_time_by_type": cycle_time,
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
