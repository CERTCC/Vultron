"""Issue-flow metrics: counts, backlog, cycle time, net issues and how
Concerns were resolved."""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, date, datetime, timedelta

import pandas as pd

from .github import REPO_NAME, REPO_OWNER
from .periods import (
    _period_keys,
    iso_to_date,
    iso_to_datetime,
    month_key,
    week_key,
)

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


# A Concern closed by a PR from a branch with this prefix was answered
# through ``plan-issue``, the full planning route (completeness-doctrine.md
# "Ask, Then Finish").
PLANNING_BRANCH_PREFIX = "plan/"
CONCERN_TYPE = "Concern"


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


def closer_branch(issue: dict) -> str | None:
    """Return the head branch of the PR that closed an issue, if a PR did."""
    nodes = (issue.get("timelineItems") or {}).get("nodes") or []
    if not nodes:
        return None
    closer = (nodes[-1] or {}).get("closer") or {}
    branch = closer.get("headRefName")
    return str(branch) if branch else None


def _concern_resolution(
    issues: list[dict], periods: list[str], key
) -> list[dict]:
    """Per-period Concern flow: how many were filed and how each was closed.

    ``filed`` counts Concerns created in the period.  The rest count
    Concerns closed as completed in the period: ``closed``, the subset
    ``closed_by_planning_pr`` (closing PR's branch starts with ``plan/``),
    the subset ``closed_within_1_day``, and ``median_days_to_close``
    (``None`` when none closed).  A Concern answered within a day could
    usually have been asked in the session that filed it.
    """
    rows: dict[str, dict] = {
        p: {
            "filed": 0,
            "closed": 0,
            "closed_by_planning_pr": 0,
            "closed_within_1_day": 0,
        }
        for p in periods
    }
    days: dict[str, list[float]] = defaultdict(list)
    for issue in issues:
        if classify_type(issue) != CONCERN_TYPE:
            continue
        created = iso_to_datetime(issue.get("createdAt"))
        if created and key(created.date()) in rows:
            rows[key(created.date())]["filed"] += 1
        closed = iso_to_datetime(issue.get("closedAt"))
        if (
            not created
            or not closed
            or key(closed.date()) not in rows
            or issue.get("stateReason") != "COMPLETED"
        ):
            continue
        row = rows[key(closed.date())]
        row["closed"] += 1
        branch = closer_branch(issue)
        if branch and branch.startswith(PLANNING_BRANCH_PREFIX):
            row["closed_by_planning_pr"] += 1
        elapsed = (closed - created).total_seconds() / 86400
        if elapsed <= 1:
            row["closed_within_1_day"] += 1
        days[key(closed.date())].append(elapsed)
    return [
        {
            "period": p,
            **row,
            "median_days_to_close": (
                round(float(pd.Series(days[p]).median()), 1)
                if days[p]
                else None
            ),
        }
        for p, row in rows.items()
    ]


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
        "concern_resolution_by_week": _concern_resolution(
            issues, all_weeks, week_key
        ),
    }
