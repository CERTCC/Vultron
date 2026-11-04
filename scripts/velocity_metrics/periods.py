"""Date parsing and the week/month period keys every metric buckets by."""

from __future__ import annotations

from datetime import date, datetime, timedelta


def iso_to_datetime(s: str | None) -> datetime | None:
    if not s:
        return None
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def iso_to_date(s: str | None) -> date | None:
    dt = iso_to_datetime(s)
    return dt.date() if dt else None


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


def _iso_z(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
