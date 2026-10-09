"""Unit tests for velocity.py pipeline-cost metrics (AC-4).

Covers ``parse_suite_runs_line`` (present, absent, malformed), merge-from-main
detection, CI-run counting and matching, ``build_pr_pipeline_record``,
``_pr_weekly_aggregates``, ``_weekly_main_failures``, and the fetchers.  The
fetchers run against recorded API responses in ``fixtures/velocity/`` through
``httpx.MockTransport``; nothing calls the live API.
"""

from __future__ import annotations

import importlib.util
import json
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType

import httpx2 as httpx
import pytest

_ROOT = Path(__file__).parents[2]
_SCRIPT = _ROOT / "scripts" / "velocity.py"
_FIXTURES = Path(__file__).parent / "fixtures" / "velocity"


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


def _commit(headline: str, parents: int = 1) -> dict:
    return {
        "commit": {
            "messageHeadline": headline,
            "parents": {"totalCount": parents},
        }
    }


@pytest.mark.parametrize(
    "headline",
    [
        "Merge branch 'main' into task/fix",
        "Merge remote-tracking branch 'origin/main' into task/feat",
        "Merge origin/main into task/4359-velocity-pipeline-cost",
        "merge: sync with main",
        "chore: merge main",
    ],
)
def test_count_merges_from_main_recognises_headline_forms(
    velocity: ModuleType, headline: str
) -> None:
    """Hand-written merge headlines on this repo count, not just git's."""
    assert velocity._count_merges_from_main([_commit(headline, 2)]) == 1


def test_count_merges_from_main_ignores_single_parent_commit(
    velocity: ModuleType,
) -> None:
    """A commit that mentions main but is not a merge does not count."""
    commits = [_commit("docs: explain why main stays green", 1)]
    assert velocity._count_merges_from_main(commits) == 0


def test_count_merges_from_main_ignores_merge_of_other_branch(
    velocity: ModuleType,
) -> None:
    commits = [
        _commit("Merge branch 'task/12-maintenance' into integration/x", 2)
    ]
    assert velocity._count_merges_from_main(commits) == 0


def test_count_merges_from_main_none(velocity: ModuleType) -> None:
    commits = [_commit("Add feature"), _commit("Fix tests")]
    assert velocity._count_merges_from_main(commits) == 0


def test_count_merges_from_main_multiple(velocity: ModuleType) -> None:
    commits = [
        _commit("Merge branch 'main' into task/fix", 2),
        _commit("Fix bug"),
        _commit("Merge branch 'main' into task/fix", 2),
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
    """Build a minimal PR dict for fixture-based testing.

    The suite line, when given, sits in a PR review, which is where
    pr-execute posts its summary (``gh pr review --comment``).
    """
    commits = [_commit("Add feature")]
    for _ in range(merge_commit_count):
        commits.append(_commit(f"Merge branch 'main' into {branch}", 2))
    reviews = []
    if suite_line is not None:
        reviews.append(
            {
                "body": f"## PR Execute: #{number}\n\n{suite_line}\n",
                "createdAt": created_at,
            }
        )
    return {
        "number": number,
        "createdAt": created_at,
        "mergedAt": merged_at,
        "headRefName": branch,
        "commits": {"nodes": commits},
        "comments": {"nodes": []},
        "reviews": {"nodes": reviews},
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


def test_build_pr_pipeline_record_reads_suite_line_from_issue_comment(
    velocity: ModuleType,
) -> None:
    pr = _make_pr(suite_line=None)
    pr["comments"]["nodes"].append(
        {"body": "Suite runs: 4 full, 0 targeted", "createdAt": "2026-09-01"}
    )
    rec = velocity.build_pr_pipeline_record(pr, ci_runs=1, failed_ci_runs=0)
    assert (rec["full_suite_runs"], rec["targeted_suite_runs"]) == (4, 0)


def test_build_pr_pipeline_record_latest_suite_line_wins(
    velocity: ModuleType,
) -> None:
    """The line is cumulative, so a later summary supersedes an earlier one."""
    pr = _make_pr(suite_line=None)
    pr["reviews"]["nodes"] = [
        {
            "body": "## PR Execute\n\nSuite runs: 3 full, 2 targeted",
            "createdAt": "2026-09-02T09:00:00Z",
        },
        {
            "body": "## PR Execute\n\nSuite runs: 1 full, 0 targeted",
            "createdAt": "2026-09-01T09:00:00Z",
        },
        {"body": "## PR Verify", "createdAt": "2026-09-02T10:00:00Z"},
    ]
    rec = velocity.build_pr_pipeline_record(pr, ci_runs=1, failed_ci_runs=0)
    assert (rec["full_suite_runs"], rec["targeted_suite_runs"]) == (3, 2)


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


# ── _ci_iteration_counts ───────────────────────────────────────────────────


def _run(
    sha: str,
    conclusion: str,
    created_at: str = "2026-09-07T10:00:00Z",
    branch: str = "task/42-feature",
    pull_requests: list[int] | None = None,
) -> dict:
    return {
        "head_sha": sha,
        "head_branch": branch,
        "conclusion": conclusion,
        "created_at": created_at,
        "pull_requests": [{"number": n} for n in pull_requests or []],
    }


def test_ci_iteration_counts_one_per_head_commit(velocity: ModuleType) -> None:
    """Several workflows on one push are one CI run, not several."""
    runs = [_run("a", "success"), _run("a", "success"), _run("b", "success")]
    assert velocity._ci_iteration_counts(runs) == (2, 0)


def test_ci_iteration_counts_any_failed_workflow_fails_the_run(
    velocity: ModuleType,
) -> None:
    runs = [
        _run("a", "success"),
        _run("a", "failure"),
        _run("b", "timed_out"),
        _run("c", "startup_failure"),
        _run("d", "success"),
    ]
    assert velocity._ci_iteration_counts(runs) == (4, 3)


def test_ci_iteration_counts_ignores_cancelled_and_skipped(
    velocity: ModuleType,
) -> None:
    """A commit whose runs were all superseded is not a CI run."""
    runs = [
        _run("a", "cancelled"),
        _run("a", "skipped"),
        _run("b", "cancelled"),
        _run("b", "success"),
    ]
    assert velocity._ci_iteration_counts(runs) == (1, 0)


def test_ci_iteration_counts_empty(velocity: ModuleType) -> None:
    assert velocity._ci_iteration_counts([]) == (0, 0)


# ── _RunIndex ──────────────────────────────────────────────────────────────


def test_run_index_matches_by_pr_number(velocity: ModuleType) -> None:
    pr = _make_pr(number=42, branch="task/42-feature")
    runs = [
        _run("a", "success", branch="other-branch", pull_requests=[42]),
        _run("b", "success", branch="task/42-feature", pull_requests=[7]),
    ]
    matched = velocity._RunIndex(runs).runs_for(pr)
    assert [r["head_sha"] for r in matched] == ["a"]


def test_run_index_branch_fallback_limited_to_open_window(
    velocity: ModuleType,
) -> None:
    """A reused branch name does not pull in another PR's runs."""
    pr = _make_pr(
        number=42,
        branch="task/42-feature",
        created_at="2026-09-07T08:00:00Z",
        merged_at="2026-09-07T20:00:00Z",
    )
    runs = [
        _run("before", "failure", created_at="2026-09-01T10:00:00Z"),
        _run("during", "success", created_at="2026-09-07T10:00:00Z"),
        _run("after", "failure", created_at="2026-09-08T10:00:00Z"),
    ]
    matched = velocity._RunIndex(runs).runs_for(pr)
    assert [r["head_sha"] for r in matched] == ["during"]


def test_pr_runs_window_start_reaches_back_to_earliest_open(
    velocity: ModuleType,
) -> None:
    from datetime import date

    prs = [
        _make_pr(created_at="2026-08-20T10:00:00Z"),
        _make_pr(created_at="2026-09-10T10:00:00Z"),
    ]
    start = date(2026, 9, 1)
    assert velocity.pr_runs_window_start(prs, start) == date(2026, 8, 20)
    assert velocity.pr_runs_window_start([], start) == start


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


def test_pr_weekly_aggregates_suite_runs_all_absent_is_none_not_zero(
    velocity: ModuleType,
) -> None:
    """A week whose PRs all lack the line reports None, never zero."""
    records = [
        _make_record(
            1,
            "2026-09-07T00:00:00Z",
            ci_runs=2,
            full_suite_runs=None,
            targeted_suite_runs=None,
        ),
        _make_record(
            2,
            "2026-09-08T00:00:00Z",
            ci_runs=6,
            full_suite_runs=None,
            targeted_suite_runs=None,
        ),
    ]
    row = velocity._pr_weekly_aggregates(records, [_W37])[0]
    assert row["pr_count"] == 2
    assert row["total_full_suite_runs"] is None
    assert row["total_targeted_suite_runs"] is None
    # Absent suite counts do not disturb the other fields' aggregates.
    assert row["median_ci_runs"] == 4.0
    assert row["total_ci_runs"] == 8.0


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


def _main_run(sha: str, conclusion: str, created_at: str) -> dict:
    return _run(sha, conclusion, created_at=created_at, branch="main")


def test_weekly_main_failures_counts_failed_commits(
    velocity: ModuleType,
) -> None:
    runs = [
        _main_run("a", "failure", "2026-09-07T10:00:00Z"),
        _main_run("b", "success", "2026-09-08T10:00:00Z"),
        _main_run("c", "timed_out", "2026-09-10T10:00:00Z"),
    ]
    rows = velocity._weekly_main_failures(runs, [_W37])
    assert rows[0]["week"] == _W37
    assert rows[0]["failed_ci_runs_on_main"] == 2


def test_weekly_main_failures_one_commit_counts_once(
    velocity: ModuleType,
) -> None:
    """One bad merge that breaks three workflows is one failure on main."""
    runs = [
        _main_run("a", "failure", "2026-09-07T10:00:00Z"),
        _main_run("a", "failure", "2026-09-07T10:00:01Z"),
        _main_run("a", "timed_out", "2026-09-07T10:00:02Z"),
    ]
    rows = velocity._weekly_main_failures(runs, [_W37])
    assert rows[0]["failed_ci_runs_on_main"] == 1


def test_weekly_main_failures_ignores_cancelled(velocity: ModuleType) -> None:
    runs = [_main_run("a", "cancelled", "2026-09-07T10:00:00Z")]
    rows = velocity._weekly_main_failures(runs, [_W37])
    assert rows[0]["failed_ci_runs_on_main"] == 0


def test_weekly_main_failures_zero_in_clean_week(velocity: ModuleType) -> None:
    runs = [_main_run("a", "success", "2026-09-07T10:00:00Z")]
    rows = velocity._weekly_main_failures(runs, [_W37])
    assert rows[0]["failed_ci_runs_on_main"] == 0


def test_weekly_main_failures_empty_runs(velocity: ModuleType) -> None:
    rows = velocity._weekly_main_failures([], [_W37, _W38])
    assert [r["failed_ci_runs_on_main"] for r in rows] == [0, 0]


def test_weekly_main_failures_out_of_window_excluded(
    velocity: ModuleType,
) -> None:
    """Runs outside the provided weeks list are not counted."""
    # 2026-08-31 is in W36, which is not in the provided weeks
    runs = [_main_run("a", "failure", "2026-08-31T10:00:00Z")]
    rows = velocity._weekly_main_failures(runs, [_W37])
    assert rows[0]["failed_ci_runs_on_main"] == 0


# ── build_pr_pipeline_metrics (end-to-end) ────────────────────────────────


def test_build_pr_pipeline_metrics_integrates_runs_and_prs(
    velocity: ModuleType,
) -> None:
    """End-to-end: correlates workflow runs with merged PRs."""
    from datetime import date

    pr = _make_pr(
        number=42,
        created_at="2026-09-07T08:00:00Z",
        merged_at="2026-09-07T20:00:00Z",
        branch="task/42-feature",
        merge_commit_count=2,
        suite_line="Suite runs: 1 full, 3 targeted",
    )

    pr_runs = [
        # Push 1: two workflows, one failed → one failed CI run
        _run("s1", "failure", created_at="2026-09-07T10:00:00Z"),
        _run("s1", "success", created_at="2026-09-07T10:00:00Z"),
        # Push 2: green
        _run("s2", "success", created_at="2026-09-07T18:00:00Z"),
        # Another branch — must NOT be counted for PR 42
        _run(
            "x1",
            "failure",
            created_at="2026-09-07T12:00:00Z",
            branch="task/99-other",
        ),
    ]
    main_runs = [_main_run("m1", "failure", "2026-09-08T00:00:00Z")]

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

    w37 = next(r for r in result["weekly_main_failures"] if r["week"] == _W37)
    assert w37["failed_ci_runs_on_main"] == 1

    # PR with no matching runs → ci_runs = 0
    pr_no_runs = _make_pr(number=43, branch="task/43-orphan")
    result2 = velocity.build_pr_pipeline_metrics(
        [pr_no_runs], [], [], date(2026, 9, 7)
    )
    assert result2["per_pr"][0]["ci_runs"] == 0
    assert result2["per_pr"][0]["failed_ci_runs"] == 0


# ── fetchers, driven by recorded API responses ────────────────────────────
#
# test/ci/fixtures/velocity/ holds trimmed real responses: a GraphQL page of
# merged PRs #4387, #4372, #4374 (review and comment bodies cut to their
# heading line) and the REST workflow runs for PR #4387's branch.


def _load_fixture(name: str) -> dict:
    loaded: dict = json.loads((_FIXTURES / name).read_text())
    return loaded


def _patch_client(
    monkeypatch: pytest.MonkeyPatch,
    velocity: ModuleType,
    handler: Callable[[httpx.Request], httpx.Response],
) -> None:
    real_client = velocity.httpx.Client

    def factory(*args: object, **kwargs: object) -> httpx.Client:
        client: httpx.Client = real_client(
            *args, transport=httpx.MockTransport(handler), **kwargs
        )
        return client

    monkeypatch.setattr(velocity.httpx, "Client", factory)


def test_fetch_merged_prs_parses_recorded_page(
    velocity: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    page = _load_fixture("graphql_merged_prs_page.json")
    _patch_client(
        monkeypatch, velocity, lambda req: httpx.Response(200, json=page)
    )
    prs = velocity.fetch_merged_prs("CERTCC", "Vultron", "2026-10-09", "t")
    assert [p["number"] for p in prs] == [4387, 4372, 4374]

    recs = {
        p["number"]: velocity.build_pr_pipeline_record(p, 0, 0) for p in prs
    }
    # Real merge headlines: "Merge remote-tracking branch 'origin/main' ..."
    assert recs[4387]["merges_from_main"] == 1
    assert recs[4372]["merges_from_main"] == 2
    # pr-execute's summary review exists but predates the Suite runs line.
    assert recs[4372]["full_suite_runs"] is None
    assert recs[4372]["targeted_suite_runs"] is None


def test_fetch_merged_prs_filters_and_stops_at_window_start(
    velocity: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Paging stops once a page's oldest updatedAt predates the window."""
    page = _load_fixture("graphql_merged_prs_page.json")
    conn = page["data"]["repository"]["pullRequests"]
    conn["pageInfo"]["hasNextPage"] = True
    for node in conn["nodes"]:
        if node["number"] == 4374:
            node["mergedAt"] = node["updatedAt"] = "2026-10-01T00:00:00Z"
    calls: list[httpx.Request] = []

    def handler(req: httpx.Request) -> httpx.Response:
        calls.append(req)
        return httpx.Response(200, json=page)

    _patch_client(monkeypatch, velocity, handler)
    prs = velocity.fetch_merged_prs("CERTCC", "Vultron", "2026-10-05", "t")
    assert len(calls) == 1
    assert [p["number"] for p in prs] == [4387, 4372]


def test_fetch_workflow_runs_reads_recorded_runs(
    velocity: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    runs_body = _load_fixture("rest_runs_pr4387.json")
    _patch_client(
        monkeypatch, velocity, lambda req: httpx.Response(200, json=runs_body)
    )
    runs = velocity.fetch_workflow_runs(
        "CERTCC",
        "Vultron",
        "2026-10-09",
        "t",
        until=datetime(2026, 10, 9, 23, 59, 59, tzinfo=UTC),
    )
    assert len(runs) == runs_body["total_count"]

    page = _load_fixture("graphql_merged_prs_page.json")
    pr = next(
        n
        for n in page["data"]["repository"]["pullRequests"]["nodes"]
        if n["number"] == 4387
    )
    # Recorded runs for a merged PR carry no pull_requests: the branch
    # fallback within the open window matches them.  Two pushes, both green.
    matched = velocity._RunIndex(runs).runs_for(pr)
    assert velocity._ci_iteration_counts(matched) == (2, 0)


def test_fetch_workflow_runs_splits_windows_past_result_cap(
    velocity: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A window over the REST cap is halved; no run is silently dropped."""
    lo = datetime(2026, 10, 1, tzinfo=UTC)
    hi = datetime(2026, 10, 2, tzinfo=UTC)
    # 1500 runs spread evenly over the day: over the 1000 cap as a whole.
    all_runs: list[dict[str, str | int]] = [
        {
            "id": i,
            "head_sha": f"s{i}",
            "conclusion": "success",
            "created_at": (lo + (hi - lo) * i / 1500).strftime(
                "%Y-%m-%dT%H:%M:%SZ"
            ),
        }
        for i in range(1500)
    ]

    def handler(req: httpx.Request) -> httpx.Response:
        a, b = req.url.params["created"].split("..")
        in_window = [r for r in all_runs if a <= str(r["created_at"]) <= b]
        per_page = int(req.url.params["per_page"])
        page = int(req.url.params["page"])
        visible = in_window[: velocity._REST_RESULT_CAP]
        batch = visible[(page - 1) * per_page : page * per_page]
        return httpx.Response(
            200, json={"total_count": len(in_window), "workflow_runs": batch}
        )

    _patch_client(monkeypatch, velocity, handler)
    runs = velocity.fetch_workflow_runs(
        "CERTCC", "Vultron", "2026-10-01", "t", until=hi
    )
    assert sorted(r["id"] for r in runs) == list(range(1500))
