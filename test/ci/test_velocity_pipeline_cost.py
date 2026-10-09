"""Unit tests for velocity.py pipeline-cost metrics (AC-4).

Covers ``parse_suite_runs_line`` (present, absent, malformed),
``_count_merges_from_main``, ``build_pr_pipeline_record``,
``_pr_weekly_aggregates``, and ``_weekly_main_failures`` — all using
crafted fixtures, never live API calls.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest

_ROOT = Path(__file__).parents[2]
_SCRIPT = _ROOT / "scripts" / "velocity.py"


@pytest.fixture(scope="module")
def velocity() -> ModuleType:
    spec = importlib.util.spec_from_file_location("velocity", _SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# ── parse_suite_runs_line ──────────────────────────────────────────────────


def test_parse_suite_runs_line_present(velocity: ModuleType) -> None:
    assert velocity.parse_suite_runs_line(
        "Suite runs: 2 full, 1 targeted"
    ) == (2, 1)


def test_parse_suite_runs_line_present_within_larger_body(
    velocity: ModuleType,
) -> None:
    body = (
        "## Execute summary\n\nSuite runs: 3 full, 0 targeted\nSome other text"
    )
    assert velocity.parse_suite_runs_line(body) == (3, 0)


def test_parse_suite_runs_line_absent_empty(velocity: ModuleType) -> None:
    assert velocity.parse_suite_runs_line("") is None


def test_parse_suite_runs_line_absent_no_keyword(velocity: ModuleType) -> None:
    assert velocity.parse_suite_runs_line("No suite info here.") is None


def test_parse_suite_runs_line_malformed_non_numeric(
    velocity: ModuleType,
) -> None:
    """Line present but numbers replaced with text → treated as absent."""
    assert (
        velocity.parse_suite_runs_line("Suite runs: abc full, xyz targeted")
        is None
    )


def test_parse_suite_runs_line_malformed_partial(velocity: ModuleType) -> None:
    """Only partial 'Suite runs:' pattern present → treated as absent."""
    assert velocity.parse_suite_runs_line("Suite runs: 1 full") is None


def test_parse_suite_runs_line_extra_whitespace(velocity: ModuleType) -> None:
    """Extra whitespace between tokens is accepted."""
    assert velocity.parse_suite_runs_line(
        "Suite runs:  4  full,  2  targeted"
    ) == (4, 2)


# ── _count_merges_from_main ────────────────────────────────────────────────


def test_count_merges_from_main_branch_headline(velocity: ModuleType) -> None:
    commits = [
        {"commit": {"messageHeadline": "Merge branch 'main' into task/fix"}},
        {"commit": {"messageHeadline": "Fix typo"}},
    ]
    assert velocity._count_merges_from_main(commits) == 1


def test_count_merges_from_main_origin_headline(velocity: ModuleType) -> None:
    commits = [
        {
            "commit": {
                "messageHeadline": (
                    "Merge remote-tracking branch 'origin/main' into task/feat"
                )
            }
        },
    ]
    assert velocity._count_merges_from_main(commits) == 1


def test_count_merges_from_main_none(velocity: ModuleType) -> None:
    commits = [
        {"commit": {"messageHeadline": "Add feature"}},
        {"commit": {"messageHeadline": "Fix tests"}},
    ]
    assert velocity._count_merges_from_main(commits) == 0


def test_count_merges_from_main_multiple(velocity: ModuleType) -> None:
    commits = [
        {"commit": {"messageHeadline": "Merge branch 'main' into task/fix"}},
        {"commit": {"messageHeadline": "Fix bug"}},
        {"commit": {"messageHeadline": "Merge branch 'main' into task/fix"}},
    ]
    assert velocity._count_merges_from_main(commits) == 2


def test_count_merges_from_main_empty(velocity: ModuleType) -> None:
    assert velocity._count_merges_from_main([]) == 0


# ── build_pr_pipeline_record ───────────────────────────────────────────────


def _make_pr(
    number: int = 100,
    created_at: str = "2026-09-01T10:00:00Z",
    merged_at: str = "2026-09-02T22:00:00Z",
    branch: str = "task/100-feature",
    merge_commit_count: int = 1,
    suite_line: str | None = "Suite runs: 2 full, 1 targeted",
) -> dict:
    """Build a minimal PR dict for fixture-based testing."""
    commits = [{"commit": {"messageHeadline": "Add feature"}}]
    for _ in range(merge_commit_count):
        commits.append(
            {
                "commit": {
                    "messageHeadline": "Merge branch 'main' into task/100-feature"
                }
            }
        )
    comments = []
    if suite_line is not None:
        comments.append({"body": f"## Execute summary\n\n{suite_line}\n"})
    return {
        "number": number,
        "createdAt": created_at,
        "mergedAt": merged_at,
        "headRefName": branch,
        "commits": {"nodes": commits},
        "comments": {"nodes": comments},
    }


def test_build_pr_pipeline_record_full(velocity: ModuleType) -> None:
    rec = velocity.build_pr_pipeline_record(
        _make_pr(), ci_runs=5, failed_ci_runs=1
    )
    assert rec["pr_number"] == 100
    assert rec["ci_runs"] == 5
    assert rec["failed_ci_runs"] == 1
    assert rec["merges_from_main"] == 1
    assert rec["full_suite_runs"] == 2
    assert rec["targeted_suite_runs"] == 1
    # 2026-09-01T10:00 → 2026-09-02T22:00 = 36.0 hours
    assert rec["open_to_merge_hours"] == 36.0


def test_build_pr_pipeline_record_suite_runs_absent(
    velocity: ModuleType,
) -> None:
    rec = velocity.build_pr_pipeline_record(
        _make_pr(suite_line=None), ci_runs=3, failed_ci_runs=0
    )
    assert rec["full_suite_runs"] is None
    assert rec["targeted_suite_runs"] is None


def test_build_pr_pipeline_record_suite_runs_malformed(
    velocity: ModuleType,
) -> None:
    rec = velocity.build_pr_pipeline_record(
        _make_pr(suite_line="Suite runs: abc full, xyz targeted"),
        ci_runs=3,
        failed_ci_runs=0,
    )
    assert rec["full_suite_runs"] is None
    assert rec["targeted_suite_runs"] is None


def test_build_pr_pipeline_record_no_merges_from_main(
    velocity: ModuleType,
) -> None:
    rec = velocity.build_pr_pipeline_record(
        _make_pr(merge_commit_count=0), ci_runs=2, failed_ci_runs=0
    )
    assert rec["merges_from_main"] == 0


def test_build_pr_pipeline_record_open_to_merge_hours(
    velocity: ModuleType,
) -> None:
    pr = _make_pr(
        created_at="2026-09-01T00:00:00Z",
        merged_at="2026-09-01T12:00:00Z",
    )
    rec = velocity.build_pr_pipeline_record(pr, ci_runs=1, failed_ci_runs=0)
    assert rec["open_to_merge_hours"] == 12.0


# ── _pr_weekly_aggregates ──────────────────────────────────────────────────

# 2026-09-07 is the Monday of ISO week 2026-W37.
_W37 = "2026-W37"
_W38 = "2026-W38"


def _make_record(
    pr_number: int,
    merged_at: str,
    ci_runs: int = 3,
    failed_ci_runs: int = 0,
    merges_from_main: int = 0,
    open_to_merge_hours: float = 24.0,
    full_suite_runs: int | None = 1,
    targeted_suite_runs: int | None = 0,
) -> dict:
    return {
        "pr_number": pr_number,
        "merged_at": merged_at,
        "ci_runs": ci_runs,
        "failed_ci_runs": failed_ci_runs,
        "merges_from_main": merges_from_main,
        "open_to_merge_hours": open_to_merge_hours,
        "full_suite_runs": full_suite_runs,
        "targeted_suite_runs": targeted_suite_runs,
    }


def test_pr_weekly_aggregates_single_pr(velocity: ModuleType) -> None:
    records = [
        _make_record(
            1,
            "2026-09-07T00:00:00Z",
            ci_runs=4,
            failed_ci_runs=1,
            open_to_merge_hours=36.0,
            full_suite_runs=2,
            targeted_suite_runs=1,
        )
    ]
    rows = velocity._pr_weekly_aggregates(records, [_W37])
    assert len(rows) == 1
    row = rows[0]
    assert row["week"] == _W37
    assert row["pr_count"] == 1
    assert row["total_ci_runs"] == 4.0
    assert row["median_ci_runs"] == 4.0
    assert row["total_failed_ci_runs"] == 1.0
    assert row["total_full_suite_runs"] == 2
    assert row["total_targeted_suite_runs"] == 1


def test_pr_weekly_aggregates_suite_runs_absent_excluded(
    velocity: ModuleType,
) -> None:
    """PRs without suite runs do not inflate or suppress the total."""
    records = [
        _make_record(
            1,
            "2026-09-07T00:00:00Z",
            full_suite_runs=None,
            targeted_suite_runs=None,
        ),
        _make_record(
            2, "2026-09-08T00:00:00Z", full_suite_runs=3, targeted_suite_runs=2
        ),
    ]
    rows = velocity._pr_weekly_aggregates(records, [_W37])
    row = rows[0]
    assert row["total_full_suite_runs"] == 3
    assert row["total_targeted_suite_runs"] == 2


def test_pr_weekly_aggregates_empty_week_returns_none(
    velocity: ModuleType,
) -> None:
    rows = velocity._pr_weekly_aggregates([], [_W37, _W38])
    assert len(rows) == 2
    assert rows[0]["pr_count"] == 0
    assert rows[0]["total_ci_runs"] is None
    assert rows[0]["median_ci_runs"] is None
    assert rows[0]["total_full_suite_runs"] is None


def test_pr_weekly_aggregates_multiple_prs_median(
    velocity: ModuleType,
) -> None:
    """Median is computed across all PRs in the week."""
    records = [
        _make_record(1, "2026-09-07T00:00:00Z", ci_runs=2),
        _make_record(2, "2026-09-08T00:00:00Z", ci_runs=4),
        _make_record(3, "2026-09-09T00:00:00Z", ci_runs=6),
    ]
    rows = velocity._pr_weekly_aggregates(records, [_W37])
    row = rows[0]
    assert row["pr_count"] == 3
    assert row["total_ci_runs"] == 12.0
    assert row["median_ci_runs"] == 4.0


def test_pr_weekly_aggregates_splits_prs_across_weeks(
    velocity: ModuleType,
) -> None:
    records = [
        _make_record(1, "2026-09-07T00:00:00Z"),  # W37
        _make_record(2, "2026-09-14T00:00:00Z"),  # W38
    ]
    rows = velocity._pr_weekly_aggregates(records, [_W37, _W38])
    w37 = next(r for r in rows if r["week"] == _W37)
    w38 = next(r for r in rows if r["week"] == _W38)
    assert w37["pr_count"] == 1
    assert w38["pr_count"] == 1


# ── _weekly_main_failures ──────────────────────────────────────────────────


def test_weekly_main_failures_counts_failures(velocity: ModuleType) -> None:
    runs = [
        {
            "head_branch": "main",
            "conclusion": "failure",
            "created_at": "2026-09-07T10:00:00Z",
        },
        {
            "head_branch": "main",
            "conclusion": "success",
            "created_at": "2026-09-08T10:00:00Z",
        },
        {
            "head_branch": "main",
            "conclusion": "failure",
            "created_at": "2026-09-10T10:00:00Z",
        },
    ]
    rows = velocity._weekly_main_failures(runs, [_W37])
    assert rows[0]["week"] == _W37
    assert rows[0]["failed_ci_runs_on_main"] == 2


def test_weekly_main_failures_zero_in_clean_week(velocity: ModuleType) -> None:
    runs = [
        {
            "head_branch": "main",
            "conclusion": "success",
            "created_at": "2026-09-07T10:00:00Z",
        },
    ]
    rows = velocity._weekly_main_failures(runs, [_W37])
    assert rows[0]["failed_ci_runs_on_main"] == 0


def test_weekly_main_failures_empty_runs(velocity: ModuleType) -> None:
    rows = velocity._weekly_main_failures([], [_W37, _W38])
    assert all(r["failed_ci_runs_on_main"] == 0 for r in rows)


def test_weekly_main_failures_out_of_window_excluded(
    velocity: ModuleType,
) -> None:
    """Runs outside the provided weeks list are not counted."""
    runs = [
        {
            "head_branch": "main",
            "conclusion": "failure",
            "created_at": "2026-08-31T10:00:00Z",
        },
    ]
    # 2026-08-31 is in W36, which is not in the provided weeks
    rows = velocity._weekly_main_failures(runs, [_W37])
    assert rows[0]["failed_ci_runs_on_main"] == 0


# ── build_pr_pipeline_metrics (end-to-end) ────────────────────────────────


def test_build_pr_pipeline_metrics_integrates_runs_and_prs(
    velocity: ModuleType,
) -> None:
    """End-to-end: correlates workflow runs with merged PRs via branch name."""
    from datetime import date

    pr = _make_pr(
        number=42,
        created_at="2026-09-07T08:00:00Z",
        merged_at="2026-09-07T20:00:00Z",
        branch="task/42-feature",
        merge_commit_count=2,
        suite_line="Suite runs: 1 full, 3 targeted",
    )

    # Two completed runs for this PR's branch; one failure, one success
    pr_runs = [
        {
            "head_branch": "task/42-feature",
            "conclusion": "failure",
            "created_at": "2026-09-07T10:00:00Z",
        },
        {
            "head_branch": "task/42-feature",
            "conclusion": "success",
            "created_at": "2026-09-07T18:00:00Z",
        },
        # A run for a different branch — must NOT be counted for PR 42
        {
            "head_branch": "task/99-other",
            "conclusion": "failure",
            "created_at": "2026-09-07T12:00:00Z",
        },
    ]

    # One failed run on main
    main_runs = [
        {
            "head_branch": "main",
            "conclusion": "failure",
            "created_at": "2026-09-08T00:00:00Z",
        },
    ]

    result = velocity.build_pr_pipeline_metrics(
        [pr], pr_runs, main_runs, date(2026, 9, 7)
    )

    assert len(result["per_pr"]) == 1
    rec = result["per_pr"][0]
    assert rec["pr_number"] == 42
    assert rec["ci_runs"] == 2
    assert rec["failed_ci_runs"] == 1
    assert rec["merges_from_main"] == 2
    assert rec["full_suite_runs"] == 1
    assert rec["targeted_suite_runs"] == 3
    assert rec["open_to_merge_hours"] == 12.0

    # PR with no matching branch in workflow runs → ci_runs = 0
    pr_no_runs = _make_pr(number=43, branch="task/43-orphan")
    result2 = velocity.build_pr_pipeline_metrics(
        [pr_no_runs], [], [], date(2026, 9, 7)
    )
    assert result2["per_pr"][0]["ci_runs"] == 0
    assert result2["per_pr"][0]["failed_ci_runs"] == 0

    # main failures wired through
    mf_rows = result["weekly_main_failures"]
    assert any(r["failed_ci_runs_on_main"] == 1 for r in mf_rows)
