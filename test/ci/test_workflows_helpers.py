"""Tests for the cadence helper in ``test/ci/_workflows.py``.

A spec states how often a scheduled check must run at least, never the cron a
workflow happens to use (``notes/spec-authoring-rules.md``), so the helper
must accept any weekly-or-faster cron and refuse a slower one.
"""

from __future__ import annotations

from typing import Any

import pytest

from test.ci._workflows import runs_at_least_weekly


def _scheduled(*crons: str) -> dict[str, Any]:
    return {"on": {"schedule": [{"cron": cron} for cron in crons]}}


@pytest.mark.spec("MS-10-029", "MS-14-031")
@pytest.mark.parametrize(
    "cron",
    ["23 * * * *", "23 10 * * 1-5", "0 6 * * 1", "*/5 * * * *"],
)
@pytest.mark.spec("MS-10-029", "MS-14-031")
def test_weekly_or_faster_cron_counts(cron: str) -> None:
    assert runs_at_least_weekly(_scheduled(cron))


@pytest.mark.spec("MS-10-029", "MS-14-031")
@pytest.mark.parametrize("cron", ["0 6 1 * *", "0 6 * 1 *", "0 6 1,15 * *"])
def test_cron_pinned_to_a_day_of_month_or_month_does_not_count(
    cron: str,
) -> None:
    assert not runs_at_least_weekly(_scheduled(cron))


@pytest.mark.spec("MS-10-029", "MS-14-031")
def test_any_one_weekly_entry_is_enough() -> None:
    assert runs_at_least_weekly(_scheduled("0 6 1 * *", "0 6 * * 3"))


@pytest.mark.spec("MS-10-029", "MS-14-031")
def test_workflow_without_a_schedule_does_not_count() -> None:
    assert not runs_at_least_weekly({"on": {"push": {"branches": ["main"]}}})
