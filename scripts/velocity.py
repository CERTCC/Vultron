#!/usr/bin/env python3
"""
Collect development velocity metrics from GitHub (CERTCC/Vultron).

Fetches all issues created on or after START_DATE, buckets them by week and
month, and emits a JSON document with raw counts suitable for downstream
analysis and visualization.  Unless ``--no-pipeline-cost`` is given, it also
fetches merged PRs and GitHub Actions runs and adds a ``pipeline_cost``
section: per-PR CI runs, merges from main, local suite runs, and
open-to-merge time, plus weekly failed CI runs on main (PAD-18-007) and
weekly red episodes on main with each episode's candidate partner merges.

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


# A merge from main is a merge commit (two or more parents) whose headline
# names the main branch.  Agents write these headlines by hand as often as git
# does ("Merge origin/main into ...", "merge: sync with main"), so the headline
# test is a word match, not a fixed git template.  The word boundary keeps
# branch names such as "maintenance" out.
_MAIN_REF_RE = re.compile(r"\b(?:origin/)?main\b", re.IGNORECASE)

# The line pr-execute writes (PAD-18-006): ``Suite runs: N full, M targeted``.
# Agents writing the summary by hand also bold the label
# (``**Suite runs**: N full, M targeted``) or put the counts after the words
# (``Suite runs: full N, targeted M``); both carry the same two numbers, so
# both are read rather than dropped as absent.
_SUITE_RUNS_LABEL = r"(?:\*\*|__)?Suite runs(?:\*\*|__)?:(?:\*\*|__)?\s+"
_SUITE_RUNS_RE = re.compile(
    _SUITE_RUNS_LABEL + r"(\d+)\s+full,\s+(\d+)\s+targeted"
)
_SUITE_RUNS_WORDS_FIRST_RE = re.compile(
    _SUITE_RUNS_LABEL + r"full\s+(\d+),\s+targeted\s+(\d+)"
)

# Workflow-run conclusions.  A "CI run" in this script is one CI iteration:
# the set of workflow runs GitHub started for one head commit.  Superseded
# (cancelled) and skipped runs say nothing about the commit, so a commit whose
# runs were all cancelled or skipped is not an iteration.
_FAILED_CONCLUSIONS = frozenset({"failure", "timed_out", "startup_failure"})
_IGNORED_CONCLUSIONS = frozenset({"cancelled", "skipped"})

# The REST workflow-runs endpoint returns at most this many results for any
# filtered query, whatever the page number.  Windows are split until each
# fits under it.
_REST_RESULT_CAP = 1000
_RUNS_PER_PAGE = 100

# GraphQL query to fetch merged PRs with their commits, comments, and reviews.
# Ordered by UPDATED_AT so paging can stop at the window start: a PR's
# mergedAt never follows its updatedAt.
PR_GRAPHQL_QUERY = """
query($owner: String!, $name: String!, $cursor: String) {
  repository(owner: $owner, name: $name) {
    pullRequests(
      first: 50,
      after: $cursor,
      states: [MERGED],
      orderBy: {field: UPDATED_AT, direction: DESC}
    ) {
      pageInfo { hasNextPage endCursor }
      nodes {
        number
        createdAt
        updatedAt
        mergedAt
        headRefName
        baseRefName
        mergeCommit { oid }
        commits(first: 250) {
          nodes {
            commit {
              messageHeadline
              parents { totalCount }
            }
          }
        }
        comments(first: 100) {
          nodes { body createdAt }
        }
        reviews(first: 100) {
          nodes { body createdAt }
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
    stop_after: Callable[[list[dict]], bool] | None = None,
) -> list[dict]:
    """Paginate a GitHub GraphQL query and return all nodes.

    ``page_extractor`` receives the ``data`` dict from the GraphQL response
    and must return a dict with ``nodes`` (list) and ``pageInfo`` (object with
    ``hasNextPage`` and ``endCursor``).

    ``stop_after``, when given, is called with each page's nodes; paging
    stops after the first page for which it returns ``True``.
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
            if stop_after is not None and stop_after(page["nodes"]):
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

    Returns PR dicts with ``number``, ``createdAt``, ``updatedAt``,
    ``mergedAt``, ``headRefName``, ``baseRefName``, ``mergeCommit.oid``,
    ``commits.nodes``, ``comments.nodes``, and
    ``reviews.nodes``.

    GraphQL has no server-side ``mergedAt`` filter, so PRs are paged
    newest-updated first and filtered here.  Because a PR's ``mergedAt`` is
    never later than its ``updatedAt``, paging stops after the first page
    whose oldest ``updatedAt`` predates the window.
    """
    since_date = date.fromisoformat(since)

    def _page_predates_window(nodes: list[dict]) -> bool:
        if not nodes:
            return True
        oldest = iso_to_date(nodes[-1].get("updatedAt"))
        return oldest is not None and oldest < since_date

    all_prs = _graphql_paginate(
        PR_GRAPHQL_QUERY,
        {"owner": owner, "name": name},
        token,
        lambda data: data["repository"]["pullRequests"],
        label="PRs",
        timeout=60,
        stop_after=_page_predates_window,
    )
    return [
        pr
        for pr in all_prs
        if (d := iso_to_date(pr.get("mergedAt"))) is not None
        and d >= since_date
    ]


def _iso_z(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _fetch_runs_in_window(
    client: httpx.Client,
    url: str,
    base_params: dict[str, str | int],
    lo: datetime,
    hi: datetime,
) -> list[dict]:
    """Fetch every run created in ``[lo, hi]``, splitting past the REST cap.

    The endpoint stops returning results after ``_REST_RESULT_CAP`` for any
    filtered query, so a window whose ``total_count`` exceeds the cap is
    halved and each half fetched on its own.
    """
    params: dict[str, str | int] = {
        **base_params,
        "created": f"{_iso_z(lo)}..{_iso_z(hi)}",
        "per_page": _RUNS_PER_PAGE,
        "page": 1,
    }
    resp = client.get(url, params=params)
    resp.raise_for_status()
    body = resp.json()
    total = int(body.get("total_count", 0))

    if total > _REST_RESULT_CAP:
        if hi - lo <= timedelta(seconds=1):
            raise RuntimeError(
                f"{total} workflow runs created in one second at {_iso_z(lo)};"
                f" cannot split below the {_REST_RESULT_CAP}-result cap"
            )
        mid = lo + (hi - lo) / 2
        mid = mid.replace(microsecond=0)
        return _fetch_runs_in_window(
            client, url, base_params, lo, mid
        ) + _fetch_runs_in_window(
            client, url, base_params, mid + timedelta(seconds=1), hi
        )

    runs: list[dict] = list(body.get("workflow_runs", []))
    page_num = 1
    while len(runs) < total:
        page_num += 1
        params["page"] = page_num
        resp = client.get(url, params=params)
        resp.raise_for_status()
        batch = resp.json().get("workflow_runs", [])
        if not batch:
            break
        runs.extend(batch)
    return runs


def fetch_workflow_runs(
    owner: str,
    name: str,
    since: str,
    token: str,
    event: str = "pull_request",
    branch: str | None = None,
    until: datetime | None = None,
) -> list[dict]:
    """Fetch completed GitHub Actions workflow runs created since ``since``.

    Returns run dicts (each with at least ``id``, ``head_branch``,
    ``head_sha``, ``conclusion``, ``created_at``, and ``pull_requests``) for
    runs created from ``since`` (YYYY-MM-DD, UTC midnight) up to ``until``
    (default: now).  The window is split as needed to stay under the
    endpoint's ``_REST_RESULT_CAP``; runs are de-duplicated by ``id``.
    """
    url = f"https://api.github.com/repos/{owner}/{name}/actions/runs"
    headers = {
        "Authorization": f"bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    base_params: dict[str, str | int] = {
        "event": event,
        "status": "completed",
    }
    if branch:
        base_params["branch"] = branch

    lo = datetime.combine(date.fromisoformat(since), datetime.min.time(), UTC)
    hi = (until or datetime.now(UTC)).replace(microsecond=0)
    tag = f"{event}/{branch or 'all'}"

    with httpx.Client(headers=headers, timeout=30) as client:
        fetched = _fetch_runs_in_window(client, url, base_params, lo, hi)

    by_id: dict[object, dict] = {}
    for run in fetched:
        by_id.setdefault(run.get("id"), run)
    runs = list(by_id.values())
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

    Returns ``(full, targeted)`` when the line is present and well-formed,
    including the bold-label and words-first forms agents write by hand.
    Returns ``None`` when the line is absent or malformed (PAD-18-006).
    """
    m = _SUITE_RUNS_RE.search(body) or _SUITE_RUNS_WORDS_FIRST_RE.search(body)
    if m:
        return int(m.group(1)), int(m.group(2))
    return None


def _is_merge_from_main(commit: dict) -> bool:
    """Return True if a GraphQL commit node is a merge of the main branch.

    A merge from main has two or more parents and a headline naming main.
    """
    parents = (commit.get("parents") or {}).get("totalCount", 0)
    headline = commit.get("messageHeadline") or ""
    return parents >= 2 and bool(_MAIN_REF_RE.search(headline))


def _count_merges_from_main(commits: list[dict]) -> int:
    """Count a PR's commits that merge the main branch in."""
    return sum(
        1 for c in commits if _is_merge_from_main(c.get("commit") or {})
    )


def _extract_suite_runs(pr: dict) -> tuple[int, int] | None:
    """Return the suite-run counts from the PR's latest summary, or None.

    pr-execute posts its summary as a PR review (``gh pr review --comment``),
    so both reviews and issue comments are searched.  The line records the
    PR's cumulative cost (PAD-18-006), so the most recent one wins.
    """
    posts = [
        *((pr.get("reviews") or {}).get("nodes") or []),
        *((pr.get("comments") or {}).get("nodes") or []),
    ]
    posts.sort(key=lambda p: p.get("createdAt") or "")
    for post in reversed(posts):
        result = parse_suite_runs_line(post.get("body") or "")
        if result is not None:
            return result
    return None


def _ci_iteration_counts(runs: list[dict]) -> tuple[int, int]:
    """Return ``(ci_runs, failed_ci_runs)`` for a set of workflow runs.

    One CI run is one head commit with at least one workflow run that was not
    cancelled or skipped; it failed when any of its runs concluded in
    ``_FAILED_CONCLUSIONS``.
    """
    conclusions: dict[str, set[str]] = defaultdict(set)
    for run in runs:
        sha = run.get("head_sha") or ""
        if sha:
            conclusions[sha].add(run.get("conclusion") or "")
    iterations = [c for c in conclusions.values() if c - _IGNORED_CONCLUSIONS]
    failed = sum(1 for c in iterations if c & _FAILED_CONCLUSIONS)
    return len(iterations), failed


def build_pr_pipeline_record(
    pr: dict,
    ci_runs: int,
    failed_ci_runs: int,
) -> dict:
    """Build a pipeline-cost record for a single merged PR.

    Args:
        pr: GraphQL PR dict with ``createdAt``, ``mergedAt``, ``number``,
            ``headRefName``, ``commits.nodes``, ``comments.nodes``, and
            ``reviews.nodes``.
        ci_runs: CI iterations (see ``_ci_iteration_counts``) for this PR.
        failed_ci_runs: subset of ``ci_runs`` that failed.

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


class _RunIndex:
    """Workflow runs indexed for matching against merged PRs.

    A run that names its PRs (``pull_requests``) is matched by PR number.
    A run that names none is matched by head branch, but only when it was
    created while the PR was open, so a reused branch name does not pull in
    another PR's runs.
    """

    def __init__(self, runs: list[dict]) -> None:
        self.by_number: dict[int, list[dict]] = defaultdict(list)
        self.by_branch: dict[str, list[dict]] = defaultdict(list)
        for run in runs:
            numbers = [
                p["number"]
                for p in run.get("pull_requests") or []
                if p.get("number") is not None
            ]
            if numbers:
                for n in numbers:
                    self.by_number[n].append(run)
            elif run.get("head_branch"):
                self.by_branch[run["head_branch"]].append(run)

    def runs_for(self, pr: dict) -> list[dict]:
        matched = list(self.by_number.get(pr.get("number") or -1, []))
        opened = pr.get("createdAt") or ""
        merged = pr.get("mergedAt") or ""
        matched.extend(
            r
            for r in self.by_branch.get(pr.get("headRefName") or "", [])
            if opened <= (r.get("created_at") or "") <= merged
        )
        return matched


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
    (``None``) are excluded from aggregates, and a week where no PR carried
    the line reports ``None``, not zero.  All values are ``None`` for weeks
    with no merged PRs.
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

    ``main_runs`` is a list of workflow-run dicts from the REST API.  As for
    PRs, a CI run is one head commit: a commit on main counts once, in the
    week of its first failed workflow run, however many of its workflows
    failed.
    """
    week_set = set(all_weeks)
    first_failure: dict[str, date] = {}
    for run in main_runs:
        if run.get("conclusion") not in _FAILED_CONCLUSIONS:
            continue
        d = iso_to_date(run.get("created_at"))
        sha = run.get("head_sha") or ""
        if d is None or not sha:
            continue
        if sha not in first_failure or d < first_failure[sha]:
            first_failure[sha] = d
    counts: dict[str, int] = defaultdict(int)
    for d in first_failure.values():
        w = week_key(d)
        if w in week_set:
            counts[w] += 1
    return [
        {"week": w, "failed_ci_runs_on_main": counts.get(w, 0)}
        for w in all_weeks
    ]


def _workflow_key(run: dict) -> str:
    """Return the identity of the workflow a run belongs to.

    ``path`` names the workflow file and survives a rename of the display
    ``name``; ``workflow_id`` and ``name`` are fallbacks for trimmed records.
    """
    for field in ("path", "workflow_id", "name"):
        value = run.get(field)
        if value not in (None, ""):
            return str(value)
    return ""


def _run_order(run: dict) -> tuple[str, int]:
    """Sort key for runs: creation time, then numeric run id.

    Run ids grow with creation, so they order runs that share a
    ``created_at`` second; they are compared as numbers, not strings.
    """
    run_id = run.get("id")
    return run["created_at"], run_id if isinstance(run_id, int) else -1


def _main_red_spans(main_runs: list[dict]) -> list[dict]:
    """Group consecutive failed push runs on main into episodes, per workflow.

    For each workflow, runs are walked in creation order.  An episode opens
    at a failed run that follows a green (``success``) run and closes at the
    next green run; every failed run between them belongs to it.  Cancelled
    and skipped runs say nothing about main and are passed over, as are runs
    with any other conclusion that is neither failed nor ``success`` (such
    as ``neutral``) and runs with no ``created_at``.  A red streak that is
    already under way at the first run in the window has no green run before
    it, so its start is unknown: it is returned with ``opened_after_green`` false and
    ``prior_green_sha``/``prior_green_at`` ``None``.

    Returns one dict per episode with ``workflow`` (display name),
    ``workflow_path`` (the grouping key, see ``_workflow_key``),
    ``opened_after_green``, ``prior_green_sha``, ``prior_green_at``,
    ``first_red_sha``, ``first_red_at``, ``last_red_sha``, ``red_runs``, and
    ``ended_at`` (the closing green run's ``created_at``, or ``None`` while
    the episode is still open).  Episodes are ordered by ``first_red_at``.
    """
    by_workflow: dict[str, list[dict]] = defaultdict(list)
    for run in main_runs:
        conclusion = run.get("conclusion") or ""
        if conclusion in _IGNORED_CONCLUSIONS or not run.get("created_at"):
            continue
        by_workflow[_workflow_key(run)].append(run)

    episodes: list[dict] = []
    for key, runs in by_workflow.items():
        runs.sort(key=_run_order)
        last_green: dict | None = None
        current: dict | None = None
        for run in runs:
            conclusion = run.get("conclusion")
            if conclusion in _FAILED_CONCLUSIONS:
                if current is None:
                    current = {
                        "workflow": run.get("name") or key,
                        "workflow_path": key,
                        "opened_after_green": last_green is not None,
                        "prior_green_sha": (
                            last_green.get("head_sha") if last_green else None
                        ),
                        "prior_green_at": (
                            last_green["created_at"] if last_green else None
                        ),
                        "first_red_sha": run.get("head_sha"),
                        "first_red_at": run["created_at"],
                        "last_red_sha": run.get("head_sha"),
                        "red_runs": 0,
                        "ended_at": None,
                    }
                    episodes.append(current)
                current["last_red_sha"] = run.get("head_sha")
                current["red_runs"] += 1
            elif conclusion == "success":
                if current is not None:
                    current["ended_at"] = run["created_at"]
                    current = None
                last_green = run
    episodes.sort(key=lambda e: (e["first_red_at"], e["workflow_path"]))
    return episodes


def _merged_to_main(prs: list[dict]) -> list[dict]:
    """Return the PRs merged into ``main``, leaving out other bases.

    PRs merged into an integration branch or ``publish`` are not merges to
    main: they neither count toward the merge rate nor partner a break.
    """
    return [pr for pr in prs if pr.get("baseRefName") == "main"]


def _last_green_ci_at(runs: list[dict]) -> str | None:
    """Return when a PR's last green CI run started, or ``None``.

    A CI run is one head commit (see ``_ci_iteration_counts``); it is green
    when at least one of its workflow runs succeeded and none failed.  Its
    start is its earliest workflow run's ``created_at``, the moment CI
    checked out the base it tested against.  Runs with no ``head_sha`` or
    no ``created_at`` are passed over.
    """
    by_sha: dict[str, list[dict]] = defaultdict(list)
    for run in runs:
        sha = run.get("head_sha") or ""
        if sha and run.get("created_at"):
            by_sha[sha].append(run)
    starts = [
        min(r["created_at"] for r in group)
        for group in by_sha.values()
        if "success" in {r.get("conclusion") for r in group}
        and not {r.get("conclusion") for r in group} & _FAILED_CONCLUSIONS
    ]
    return max(starts) if starts else None


def _merged_between(prs: list[dict], after: str, before: str) -> list[int]:
    """Return the numbers of PRs merged strictly between two times.

    Ordered by merge time.  The bounds are ISO-8601 UTC strings, which
    compare in time order.
    """
    window = [p for p in prs if after < (p.get("mergedAt") or "") < before]
    window.sort(key=lambda p: p.get("mergedAt") or "")
    return [p["number"] for p in window]


def _landed_at(
    by_merge_sha: dict[str, dict], sha: str | None, run_at: str
) -> str:
    """Return when a commit on main landed.

    That is the merge time of the PR whose merge commit it is, or, for a
    direct push or a merge from before the window, its run's ``created_at``.
    A run starts seconds after its commit lands, so the merge time is the
    tighter bound when it is known.
    """
    pr = by_merge_sha.get(sha or "")
    return (pr.get("mergedAt") if pr else None) or run_at


def _main_red_episodes(
    main_runs: list[dict],
    prs: list[dict],
    index: _RunIndex,
    merged_since: date,
) -> list[dict]:
    """Build the red-episode records on main, with candidate partners.

    ``prs`` are the merged PRs fetched from ``merged_since``; only those
    merged into main are used (see ``_merged_to_main``).  Each episode from
    ``_main_red_spans`` gains:

    - ``pr_number``: the PR whose merge commit is the episode's first red
      commit, or ``None`` when no PR merged to main in the window owns it
      (a direct push, or a merge from before the window).
    - ``last_green_ci_at``: that PR's last green CI run (see
      ``_last_green_ci_at``), or ``None`` when the PR or its green run is
      unknown.
    - ``candidate_partners``: the PRs merged to main after that run and
      before the PR's own merge, the merges its last green run could not
      have seen.  ``None`` when the run is unknown, or when it predates
      ``merged_since`` and so earlier partners were never fetched; ``[]``
      means no merge landed in between.
    - ``unverified_merges``: the PRs, other than ``pr_number``, merged to
      main after the prior green commit and before the first red commit.
      None of them has a completed run in this workflow: each run was
      cancelled or skipped, or never started because of a ``paths`` filter.
      Any of them may be the real breaker, and ``pr_number`` only the first
      commit to finish red.  Each bound is the merge time of the PR whose
      merge commit is that green or red commit, or the run's ``created_at``
      for a direct push, since a run starts after its commit lands.
      ``None`` when there was no prior green run.

    Classifying an episode (semantic conflict, scenario coverage gap,
    already red, infrastructure) is left to a human.
    """
    main_prs = _merged_to_main(prs)
    window_start = _iso_z(
        datetime.combine(merged_since, datetime.min.time(), UTC)
    )
    by_merge_sha = {
        oid: pr
        for pr in main_prs
        if (oid := (pr.get("mergeCommit") or {}).get("oid"))
    }
    records = []
    for span in _main_red_spans(main_runs):
        pr = by_merge_sha.get(span["first_red_sha"] or "")
        last_green = _last_green_ci_at(index.runs_for(pr)) if pr else None
        partners = (
            _merged_between(main_prs, last_green, pr.get("mergedAt") or "")
            if pr is not None
            and last_green is not None
            and last_green >= window_start
            else None
        )
        unverified = (
            _merged_between(
                main_prs,
                _landed_at(
                    by_merge_sha,
                    span["prior_green_sha"],
                    span["prior_green_at"],
                ),
                _landed_at(
                    by_merge_sha, span["first_red_sha"], span["first_red_at"]
                ),
            )
            if span["prior_green_at"] is not None
            else None
        )
        records.append(
            {
                **span,
                "pr_number": pr.get("number") if pr else None,
                "last_green_ci_at": last_green,
                "candidate_partners": partners,
                "unverified_merges": unverified,
            }
        )
    return records


def _weekly_main_episodes(
    episodes: list[dict], prs: list[dict], all_weeks: list[str]
) -> list[dict]:
    """Count red episodes opened on main, and merges to main, per week.

    Episodes are grouped per workflow, so one breaking commit that fails
    several workflows opens several episodes.  The weekly count is of
    breaks, not workflows: episodes that share a ``first_red_sha`` count
    once, in the week of their first red run, and only when they opened
    after a green run (a streak already red at the window start did not open
    in that week).  ``merges_to_main`` counts PRs merged into main by
    ``mergedAt``.  ``red_episodes_per_100_merges`` is ``None`` for a week
    with no merges, where the rate is undefined.
    """
    week_set = set(all_weeks)
    breaks: dict[str, set[str]] = defaultdict(set)
    for ep in episodes:
        d = iso_to_date(ep.get("first_red_at"))
        if ep.get("opened_after_green") and d and week_key(d) in week_set:
            breaks[week_key(d)].add(ep.get("first_red_sha") or "")
    merges: dict[str, int] = defaultdict(int)
    for pr in _merged_to_main(prs):
        d = iso_to_date(pr.get("mergedAt"))
        if d and week_key(d) in week_set:
            merges[week_key(d)] += 1
    rows = []
    for w in all_weeks:
        n_ep, n_merge = len(breaks.get(w, ())), merges.get(w, 0)
        rows.append(
            {
                "week": w,
                "red_episodes_opened_on_main": n_ep,
                "merges_to_main": n_merge,
                "red_episodes_per_100_merges": (
                    round(100 * n_ep / n_merge, 1) if n_merge else None
                ),
            }
        )
    return rows


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
