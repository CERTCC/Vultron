"""``scripts/velocity.py`` question and Concern-resolution metrics.

Pins the ``Questions: asked N, filed M`` PR-body line and the weekly Concern
flow (completeness-doctrine.md "Ask, Then Finish"): how many Concerns were
filed, how many closed through a planning PR, and how many within a day.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.velocity_metrics import (
    issues as issue_metrics,
    periods,
    pr_pipeline,
)

_ROOT = Path(__file__).parents[2]

# 2026-09-07 is the Monday of ISO week 2026-W37.
_W37 = "2026-W37"


def _pr(body: str) -> dict:
    return {
        "number": 1,
        "createdAt": "2026-09-07T00:00:00Z",
        "mergedAt": "2026-09-07T12:00:00Z",
        "body": body,
        "headRefName": "task/1-x",
        "baseRefName": "main",
        "commits": {"nodes": []},
        "comments": {"nodes": []},
        "reviews": {"nodes": []},
    }


def _concern(
    created: str,
    closed: str | None = None,
    branch: str | None = None,
    state_reason: str = "COMPLETED",
    issue_type: str = "Concern",
) -> dict:
    closer = {"headRefName": branch} if branch else None
    return {
        "createdAt": created,
        "closedAt": closed,
        "stateReason": state_reason if closed else None,
        "issueType": {"name": issue_type},
        "labels": {"nodes": []},
        "timelineItems": {"nodes": [{"closer": closer}] if closed else []},
    }


# ── parse_questions_line ───────────────────────────────────────────────────


@pytest.mark.parametrize(
    "body",
    [
        "Questions: asked 2, filed 1",
        "## Summary\n\nDoes a thing.\n\nIssues: closed 1, opened 0\n"
        "Questions: asked 2, filed 1\n",
        "**Questions**: asked 2, filed 1",
    ],
)
def test_parse_questions_line_present(body):
    assert pr_pipeline.parse_questions_line(body) == (2, 1)


@pytest.mark.parametrize(
    "body",
    [
        "",
        "Issues: closed 1, opened 0",
        "Questions: asked 2",
        "Questions: none",
    ],
)
def test_parse_questions_line_absent_or_malformed(body):
    assert pr_pipeline.parse_questions_line(body) is None


def test_parse_questions_line_skips_a_quoted_example():
    body = (
        "## Summary\n\nDocuments the `Questions: asked 1, filed 1` line.\n\n"
        "Issues: closed 0, opened 0\nQuestions: asked 0, filed 0\n"
    )
    assert pr_pipeline.parse_questions_line(body) == (0, 0)


# ── per-PR record and weekly totals ────────────────────────────────────────


def test_pr_record_reads_questions_from_body():
    rec = pr_pipeline.build_pr_pipeline_record(
        _pr("Questions: asked 3, filed 0"), ci_runs=1, failed_ci_runs=0
    )
    assert (rec["questions_asked"], rec["questions_filed"]) == (3, 0)


def test_pr_record_without_questions_line_is_unknown_not_zero():
    rec = pr_pipeline.build_pr_pipeline_record(
        _pr("no line here"), ci_runs=1, failed_ci_runs=0
    )
    assert rec["questions_asked"] is None
    assert rec["questions_filed"] is None


def test_weekly_question_totals_skip_prs_without_the_line():
    records = [
        pr_pipeline.build_pr_pipeline_record(_pr(body), 1, 0)
        for body in (
            "Questions: asked 2, filed 1",
            "Questions: asked 1, filed 0",
            "no line here",
        )
    ]
    row = pr_pipeline._pr_weekly_aggregates(records, [_W37])[0]
    assert row["total_questions_asked"] == 3
    assert row["total_questions_filed"] == 1


def test_weekly_question_totals_none_when_no_pr_reports():
    records = [pr_pipeline.build_pr_pipeline_record(_pr(""), 1, 0)]
    row = pr_pipeline._pr_weekly_aggregates(records, [_W37])[0]
    assert row["total_questions_asked"] is None
    assert row["total_questions_filed"] is None


# ── closer_branch ──────────────────────────────────────────────────────────


def test_closer_branch_reads_closing_pr_branch():
    issue = _concern("2026-09-07T00:00:00Z", "2026-09-08T00:00:00Z", "plan/x")
    assert issue_metrics.closer_branch(issue) == "plan/x"


def test_closer_branch_none_when_closed_by_hand():
    assert (
        issue_metrics.closer_branch(
            _concern("2026-09-07T00:00:00Z", "2026-09-08T00:00:00Z")
        )
        is None
    )
    assert issue_metrics.closer_branch({"createdAt": "2026-09-07"}) is None


# ── _concern_resolution ────────────────────────────────────────────────────


def test_concern_resolution_counts_route_and_speed():
    issues = [
        # Planning PR, closed in 12 hours.
        _concern("2026-09-07T00:00:00Z", "2026-09-07T12:00:00Z", "plan/a"),
        # Task PR, closed in 3 days.
        _concern("2026-09-05T00:00:00Z", "2026-09-08T00:00:00Z", "task/b"),
        # Closed by hand in 1 day exactly.
        _concern("2026-09-08T00:00:00Z", "2026-09-09T00:00:00Z"),
        # Not planned: filed this week, but not a resolution.
        _concern(
            "2026-09-09T00:00:00Z",
            "2026-09-09T01:00:00Z",
            state_reason="NOT_PLANNED",
        ),
        # Still open.
        _concern("2026-09-10T00:00:00Z"),
        # Not a Concern.
        _concern(
            "2026-09-07T00:00:00Z",
            "2026-09-07T01:00:00Z",
            "plan/c",
            issue_type="Idea",
        ),
    ]
    row = issue_metrics._concern_resolution(issues, [_W37], periods.week_key)[
        0
    ]
    assert row["period"] == _W37
    assert row["filed"] == 4
    assert row["closed"] == 3
    assert row["closed_by_planning_pr"] == 1
    assert row["closed_within_1_day"] == 2
    assert row["median_days_to_close"] == 1.0


def test_concern_resolution_median_none_without_closes():
    row = issue_metrics._concern_resolution(
        [_concern("2026-09-07T00:00:00Z")], [_W37], periods.week_key
    )[0]
    assert row["filed"] == 1
    assert row["closed"] == 0
    assert row["median_days_to_close"] is None
