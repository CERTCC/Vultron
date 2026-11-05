"""Tests for the ``pr-size --calibrate`` quality measures (#5835).

Later bug fixes per band (:func:`measures.fix_rates`, traced by
:mod:`~vultron.metadata.planning.size_calibration.blame`) and the heavy-review
share per band (:func:`measures.review_loads`). Pure: every test feeds fixture
records, fixture ``git`` output or a fake runner, so nothing reads GitHub, git
or the clock.
"""

from __future__ import annotations

import subprocess
from collections.abc import Sequence
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from test.metadata._fake_runner import FakeRunner
from vultron.metadata import git_runner
from vultron.metadata.base import repo_root
from vultron.metadata.git_runner import GitError
from vultron.metadata.planning import size_bands
from vultron.metadata.planning.size_calibration import (
    blame,
    measures,
    report,
)
from vultron.metadata.planning.size_calibration.model import (
    FOLLOW_UP,
    CalibrationData,
    FixTrace,
    MergedPr,
)

SCHEME = size_bands.calibration_scheme()
NOW = datetime(2026, 11, 5, tzinfo=UTC)
SINCE = NOW - timedelta(days=60)
OLD = NOW - timedelta(days=45)
"""A merge time with a full follow-up before the window ends."""


def pr(
    number: int,
    lines: int = 50,
    merged: datetime = OLD,
    head: str = "task/x",
    commits: tuple[str, ...] | None = None,
    **fields: object,
) -> MergedPr:
    ids = (f"c{number}",) if commits is None else commits
    return MergedPr(
        number,
        merged,
        lines,
        head_ref=head,
        commits=ids,
        commit_count=len(ids),
        merge_commit=f"m{number}",
        **fields,  # type: ignore[arg-type]
    )


def fix(number: int, merged: datetime, lines: int = 20) -> MergedPr:
    return pr(number, lines, merged, head=f"bug/{number}-x")


def window(
    prs: Sequence[MergedPr], traces: Sequence[FixTrace] = ()
) -> CalibrationData:
    return CalibrationData(SINCE, NOW, tuple(prs), (), tuple(traces))


def trace(fix_number: int, *commits: str) -> FixTrace:
    return FixTrace(fix_number, frozenset(commits))


class TestIsBugFix:
    @pytest.mark.parametrize(
        ("head", "expected"),
        [
            ("bug/5847-x", True),
            ("fix/typo", True),
            ("task/5835-x", False),
            ("bugfix/x", False),
            ("", False),
        ],
    )
    def test_the_head_branch_prefix_decides(self, head, expected):
        assert pr(1, head=head).is_bug_fix is expected


class TestCountTriageFindings:
    def test_no_triage_record_is_none_not_zero(self):
        bodies = ["## PR Verify: #1\n\nphase8-x-0 verified", "LGTM"]
        assert measures.count_triage_findings(bodies) is None

    def test_a_triage_that_found_nothing_is_zero(self):
        body = "## PR Triage: #1 — t\n\n**Total**: 0 FAIL · 0 IMPROVE · 0 NEW-ISSUE"
        assert measures.count_triage_findings([body]) == 0

    def test_finding_ids_count_once_across_records(self):
        prepush = (
            "## Pre-push review (fresh agent)\n"
            "1. **`phase8-untested-branch-0`** fixed\n"
            "2. **`phase9-stale-note-0`** fixed, and `phase8-untested-branch-0`"
        )
        triage = (
            "## PR Triage: #1 — t\n| phase8-untested-branch-0 | carried |\n"
            "| phase5-missing-guard-1 | new |\n"
            "**Total**: 9 FAIL · 9 IMPROVE · 0 NEW-ISSUE"
        )
        assert measures.count_triage_findings([prepush, triage]) == 3

    @pytest.mark.parametrize(
        ("body", "expected"),
        [
            (
                "## PR Triage: #1\n**Total**: 1 FAIL · 3 IMPROVE · 2 NEW-ISSUE",
                6,
            ),
            (
                "## PR triage — #1\n**Findings: 1 FAIL, 0 IMPROVE, 0 NEW-ISSUE**",
                1,
            ),
            (
                "## Pre-push review\nIt reported **13 findings**: 2 FAIL, "
                "10 IMPROVE, 1 NEW-ISSUE.\nLater: 4 FAIL",
                13,
            ),
            (
                "## PR Triage: #1\nAll 16 pre-push findings (3 FAIL, 13 "
                "IMPROVE) confirmed\n**Total**: 0 FAIL · 1 IMPROVE",
                1,
            ),
            ("## PR Triage: #1\nnothing to report", 0),
            (
                "## Pre-push review\nThe review raised 16 findings, all fixed",
                16,
            ),
            (
                "## PR Triage: #1\n**Total**: see below\n4 pre-push findings",
                4,
            ),
            ("## PR Triage: #1\n**Total**: 3 findings\n1 FAIL", 3),
        ],
    )
    def test_a_record_without_ids_counts_what_it_states(self, body, expected):
        assert measures.count_triage_findings([body]) == expected

    def test_records_without_ids_add_to_the_pooled_ids(self):
        with_ids = "## PR Triage: #1\n| phase8-a-0 |\n| phase8-b-0 |"
        stated = "## Pre-push review\n**Total**: 2 FAIL · 3 IMPROVE"
        assert measures.count_triage_findings([with_ids, stated]) == 7

    @pytest.mark.parametrize(
        "heading",
        [
            "## PR Triage: #1 — t",
            "## PR triage (delta mode) — #1",
            "## Pre-push review (fresh agent)",
            "**Pre-push review (fresh agent)**: 1 finding",
            "## pr-ship review (triage, execute, verify): PR #1",
            "## Fresh review — PR #1 (triage + execute)",
            "## 🔍 pr-triage",
            "### Post-push review (fresh agent, full mode)",
        ],
    )
    def test_triage_and_review_headings_are_records(self, heading):
        assert measures.is_triage_record(f"\n{heading}\n| phase8-a-0 |")

    @pytest.mark.parametrize(
        "body",
        [
            "## PR Verify: #1 — READY-TO-MERGE",
            "## PR Execute: #1",
            "## pr-execute: fixed all 3 triage findings",
            "## Post-push verify (fresh review agent)",
            "## Review verdict — READY-TO-MERGE",
            "## pr-ship verdict — verification",
            "## Addendum",
            "Thanks for the review",
            "",
        ],
    )
    def test_other_comments_are_not_records(self, body):
        assert not measures.is_triage_record(body)

    def test_the_heading_must_open_the_body(self):
        quoted = "> ## PR Triage: #1\n| phase8-a-0 |"
        assert measures.count_triage_findings([quoted]) is None


class TestCommitOwners:
    def test_each_commit_and_the_merge_commit_map_to_their_pr(self):
        owners = measures.commit_owners([pr(10, commits=("a", "b"))])
        assert owners == {"a": 10, "b": 10, "m10": 10}

    def test_a_shared_commit_belongs_to_the_pr_that_merged_first(self):
        stacked = pr(20, merged=OLD, commits=("a", "b"))
        base = pr(30, merged=OLD - timedelta(hours=1), commits=("a",))
        owners = measures.commit_owners([stacked, base])
        assert owners["a"] == 30 and owners["b"] == 20


class TestLaterFixes:
    def test_a_fix_within_the_follow_up_counts_against_the_blamed_pr(self):
        later = fix(11, OLD + timedelta(days=3))
        data = window([pr(10), later], [trace(11, "c10")])
        assert measures.later_fixes(data) == {10: frozenset({11})}

    def test_a_fix_through_the_merge_commit_counts(self):
        data = window(
            [pr(10), fix(11, OLD + timedelta(days=1))], [trace(11, "m10")]
        )
        assert measures.later_fixes(data) == {10: frozenset({11})}

    def test_a_fix_exactly_at_the_follow_up_edge_counts(self):
        data = window([pr(10), fix(11, OLD + FOLLOW_UP)], [trace(11, "c10")])
        assert measures.later_fixes(data) == {10: frozenset({11})}

    def test_a_fix_past_the_follow_up_does_not_count(self):
        late = fix(11, OLD + FOLLOW_UP + timedelta(seconds=1))
        data = window([pr(10), late], [trace(11, "c10")])
        assert measures.later_fixes(data) == {}

    def test_a_fix_merged_first_does_not_count(self):
        early = fix(11, OLD - timedelta(hours=1))
        data = window([pr(10), early], [trace(11, "c10")])
        assert measures.later_fixes(data) == {}

    def test_a_fix_blaming_its_own_or_unknown_commits_counts_nothing(self):
        data = window(
            [pr(10), fix(11, OLD + timedelta(days=1))],
            [trace(11, "c11", "m11", "from-before-the-window")],
        )
        assert measures.later_fixes(data) == {}

    def test_a_trace_of_a_pr_outside_the_window_is_ignored(self):
        data = window([pr(10)], [trace(99, "c10")])
        assert measures.later_fixes(data) == {}

    def test_one_fix_counts_once_per_pr_and_against_each_pr(self):
        prs = [
            pr(10, commits=("a", "b")),
            pr(12),
            fix(11, OLD + timedelta(days=2)),
        ]
        data = window(prs, [trace(11, "a", "b", "c12")])
        assert measures.later_fixes(data) == {
            10: frozenset({11}),
            12: frozenset({11}),
        }


class TestFollowedUp:
    def test_only_prs_with_a_full_follow_up_are_kept(self):
        edge = NOW - FOLLOW_UP
        prs = [
            pr(1, merged=edge),
            pr(2, merged=edge + timedelta(seconds=1)),
        ]
        assert [p.number for p in measures.followed_up(window(prs))] == [1]


class TestFixRates:
    def test_per_pr_and_per_thousand_lines_by_band(self):
        prs = [
            pr(10, 50),
            pr(11, 50),
            pr(20, 1000),
            fix(30, OLD + timedelta(days=1), lines=20),
            fix(31, OLD + timedelta(days=2), lines=20),
        ]
        traces = [trace(30, "c10", "c20"), trace(31, "c20")]
        rates = {
            r.label: r for r in measures.fix_rates(window(prs, traces), SCHEME)
        }
        small = rates["size:S"]
        assert (small.prs, small.lines, small.fixes) == (4, 140, 1)
        assert small.per_pr == pytest.approx(0.25)
        assert small.per_kloc == pytest.approx(1000 / 140)
        large = rates["size:L"]
        assert (large.prs, large.lines, large.fixes) == (1, 1000, 2)
        assert large.per_pr == 2.0 and large.per_kloc == 2.0

    def test_prs_without_a_full_follow_up_are_left_out(self):
        recent = pr(10, merged=NOW - timedelta(days=5))
        fixer = fix(11, NOW - timedelta(days=4))
        rates = measures.fix_rates(
            window([recent, fixer], [trace(11, "c10")]), SCHEME
        )
        assert all(r.prs == 0 and r.fixes == 0 for r in rates)

    def test_every_band_appears_and_an_empty_one_has_no_rate(self):
        rates = measures.fix_rates(window([]), SCHEME)
        assert [r.label for r in rates] == list(SCHEME.labels)
        assert all(r.per_pr is None and r.per_kloc is None for r in rates)


class TestHeavyReview:
    @pytest.mark.parametrize(
        ("fields", "expected"),
        [
            ({"triage_findings": 7}, (False, False, False)),
            ({"triage_findings": 8}, (True, False, False)),
            ({"triage_findings": None}, (False, False, False)),
            ({"commit_count": 6}, (False, False, False)),
            ({"commit_count": 7}, (False, True, False)),
            (
                {"open_for": timedelta(hours=23, minutes=59)},
                (False, False, False),
            ),
            ({"open_for": timedelta(days=1)}, (False, False, True)),
        ],
    )
    def test_each_threshold_is_inclusive(self, fields, expected):
        verdict = measures.heavy_review(
            replace(MergedPr(1, OLD, 50), **fields)
        )
        assert (
            verdict.findings,
            verdict.commits,
            verdict.open_long,
        ) == expected
        assert verdict.heavy is any(expected)

    def test_review_loads_count_each_test_and_the_heavy_ones_once(self):
        prs = [
            MergedPr(1, OLD, 50, triage_findings=9, commit_count=8),
            MergedPr(2, OLD, 60, open_for=timedelta(days=2)),
            MergedPr(3, OLD, 70),
            MergedPr(4, OLD, 2000, commit_count=12),
        ]
        loads = {r.label: r for r in measures.review_loads(prs, SCHEME)}
        small = loads["size:S"]
        assert (small.prs, small.heavy) == (3, 2)
        assert (small.by_findings, small.by_commits, small.by_open) == (
            1,
            1,
            1,
        )
        assert (loads["size:XL"].prs, loads["size:XL"].heavy) == (1, 1)
        assert (loads["size:M"].prs, loads["size:M"].heavy) == (0, 0)


class TestReportSections:
    def test_both_quality_sections_follow_the_survey(self):
        assert report.SECTIONS[-2:] == (
            report.later_fix_section,
            report.heavy_review_section,
        )

    def test_the_later_fix_section_reports_each_band(self):
        prs = [pr(10, 50), fix(30, OLD + timedelta(days=1))]
        text = report.render_report(window(prs, [trace(30, "c10")]), SCHEME)
        assert (
            "Later bug fixes within 30 days — 2 PRs merged at least 30" in text
        )
        assert "1 bug-fix PRs (bug/ and fix/ branches) traced" in text
        assert "size:S       2      70      1    0.50           14.29" in text
        assert "size:M       0       0      0       —               —" in text

    def test_without_a_full_follow_up_it_says_so(self):
        recent = pr(10, merged=NOW - timedelta(days=1))
        text = report.later_fix_section(window([recent]), SCHEME).render()
        assert "no PR in the window has a full 30-day follow-up" in text

    def test_the_heavy_review_section_reports_share_and_coverage(self):
        prs = [
            MergedPr(1, OLD, 50, triage_findings=8),
            MergedPr(2, OLD, 50, triage_findings=0),
            MergedPr(3, OLD, 50),
            MergedPr(4, OLD, 50),
        ]
        text = report.heavy_review_section(window(prs), SCHEME).render()
        assert text.startswith(
            "Heavy review — 8+ triage findings, 7+ commits, or open 1+ day"
        )
        assert "2 of 4 PRs carry a triage record" in text
        assert "size:S       4      1   25.0%         1        0     0" in text
        assert "size:M       0      0       —" in text

    def test_an_empty_window_says_so(self):
        text = report.heavy_review_section(window([]), SCHEME).render()
        assert "no PRs merged in the window" in text


DIFF = """\
diff --git a/vultron/a.py b/vultron/a.py
index 1..2 100644
--- a/vultron/a.py
+++ b/vultron/a.py
@@ -3,2 +3,3 @@ def f():
-old
-old
+new
@@ -10 +11 @@
-one
+one'
@@ -20,0 +22,4 @@
+added only
diff --git a/vultron/old.py b/vultron/new.py
similarity index 90%
rename from vultron/old.py
rename to vultron/new.py
--- a/vultron/old.py
+++ b/vultron/new.py
@@ -7,3 +7,0 @@
-gone
diff --git a/vultron/created.py b/vultron/created.py
new file mode 100644
--- /dev/null
+++ b/vultron/created.py
@@ -0,0 +1,2 @@
+x
diff --git a/vultron/added_only.py b/vultron/added_only.py
--- a/vultron/added_only.py
+++ b/vultron/added_only.py
@@ -4,0 +5 @@
+y
"""

SHA_A = "a" * 40
SHA_B = "b" * 40

PORCELAIN = f"""\
{SHA_A} 3 3 2
author Someone
summary first
filename vultron/a.py
\told
{SHA_A} 4 4
\told
{SHA_B} 10 10 1
author Other
filename vultron/a.py
\t{SHA_A} 1 1 looks like a header but is content
"""


class TestOldRanges:
    def test_deleted_and_rewritten_lines_are_read_by_old_path(self):
        assert blame.old_ranges(DIFF) == {
            "vultron/a.py": ((3, 2), (10, 1)),
            "vultron/old.py": ((7, 3),),
        }

    def test_an_empty_diff_has_no_ranges(self):
        assert blame.old_ranges("") == {}

    def test_a_deleted_line_that_looks_like_a_header_is_not_one(self):
        diff = (
            "diff --git a/vultron/a.py b/vultron/a.py\n"
            "--- a/vultron/a.py\n+++ b/vultron/a.py\n"
            "@@ -3,2 +3,0 @@\n"
            "-- a/elsewhere.py\n"
            '-- "quoted"\n'
            "@@ -9 +7 @@\n-x\n+y\n"
        )
        assert blame.old_ranges(diff) == {"vultron/a.py": ((3, 2), (9, 1))}

    def test_a_trailing_tab_after_the_path_is_dropped(self):
        diff = (
            "diff --git a/vultron/a b.py b/vultron/a b.py\n"
            "--- a/vultron/a b.py\t\n+++ b/vultron/a b.py\t\n"
            "@@ -1 +1 @@\n-x\n+y\n"
        )
        assert blame.old_ranges(diff) == {"vultron/a b.py": ((1, 1),)}

    def test_a_header_path_without_the_a_prefix_is_not_traced(self):
        diff = (
            "diff --git vultron/a.py vultron/a.py\n"
            "--- vultron/a.py\n+++ vultron/a.py\n"
            "@@ -1 +1 @@\n-x\n+y\n"
        )
        assert blame.old_ranges(diff) == {}

    def test_a_quoted_path_is_refused(self):
        quoted = 'diff --git "a/vultron/\\tx" "b/vultron/\\tx"\n--- "a/vultron/\\tx"\n'
        with pytest.raises(GitError, match="quoted path"):
            blame.old_ranges(quoted)


class TestBlamedCommits:
    def test_every_header_commit_and_no_content_line(self):
        assert blame.blamed_commits(PORCELAIN) == {SHA_A, SHA_B}

    def test_empty_output_names_nothing(self):
        assert blame.blamed_commits("") == frozenset()


class TestTraceFixes:
    def test_a_bug_fix_is_diffed_then_blamed_per_file_at_the_first_parent(
        self,
    ):
        git = FakeRunner("", DIFF, f"{SHA_A} 3 3 2\n\tx\n", f"{SHA_B} 7 7 3\n")
        traces = blame.trace_fixes([pr(1), fix(2, OLD)], git)
        assert traces == (FixTrace(2, frozenset({SHA_A, SHA_B})),)
        cat, diff, first, second = git.calls
        assert cat == ["cat-file", "-e", "m2^1^{commit}"]
        assert diff[-4:] == ["m2^1", "m2", "--", "vultron/"]
        assert "--unified=0" in diff
        assert {"--src-prefix=a/", "--dst-prefix=b/"} <= set(diff)
        assert first == [
            "blame",
            "--porcelain",
            "-L",
            "3,+2",
            "-L",
            "10,+1",
            "m2^1",
            "--",
            "vultron/a.py",
        ]
        assert second[-3:] == ["m2^1", "--", "vultron/old.py"]

    def test_a_fix_with_no_old_lines_blames_nothing(self):
        git = FakeRunner("", "")
        assert blame.trace_fixes([fix(2, OLD)], git) == (
            FixTrace(2, frozenset()),
        )
        assert len(git.calls) == 2

    def test_a_window_without_bug_fixes_calls_no_git(self):
        git = FakeRunner("unused")
        assert blame.trace_fixes([pr(1)], git) == ()
        assert git.calls == []

    def test_a_merge_commit_missing_from_the_clone_names_the_fix(self):
        git = FakeRunner(GitError("fatal: Not a valid object name"))
        with pytest.raises(
            GitError,
            match=r"PR #2's merge commit m2, or its first parent, is not in.*--unshallow",
        ):
            blame.trace_fixes([fix(2, OLD)], git)

    def test_a_fix_without_a_merge_commit_is_refused(self):
        bare = MergedPr(2, OLD, 10, head_ref="fix/x")
        with pytest.raises(GitError, match="PR #2 has no merge commit"):
            blame.trace_fixes([bare], FakeRunner("unused"))


class TestCompleteCommits:
    def test_a_short_commit_list_is_read_from_the_clone(self):
        short = MergedPr(
            5, OLD, 10, commit_count=3, commits=("a",), merge_commit="m5"
        )
        git = FakeRunner("", "m5\nb\na\n")
        (done,) = blame.complete_commits([short], git)
        assert done.commits == ("m5", "b", "a")
        assert git.calls[-1] == ["rev-list", "m5^1..m5"]

    def test_complete_lists_pass_through_without_git(self):
        git = FakeRunner("unused")
        prs = (pr(1), pr(2))
        assert blame.complete_commits(prs, git) == prs
        assert git.calls == []


class TestRunGit:
    """The trace's default runner, with ``subprocess.run`` replaced."""

    def test_it_runs_in_the_repository_root(self, monkeypatch):
        seen: dict[str, object] = {}

        def ran(args, **kwargs):
            seen.update(kwargs, args=args)
            return subprocess.CompletedProcess(args, 0, "out\n", "")

        monkeypatch.setattr(git_runner.subprocess, "run", ran)
        assert blame.run_git(["status"]) == "out\n"
        assert seen["args"] == ["git", "status"]
        assert seen["cwd"] == repo_root()

    def test_a_failure_is_a_git_error(self, monkeypatch):
        def failed(args, **kwargs):
            return subprocess.CompletedProcess(args, 128, "", "fatal: bad\n")

        monkeypatch.setattr(git_runner.subprocess, "run", failed)
        with pytest.raises(GitError, match=r"^git blame x: fatal: bad$"):
            blame.run_git(["blame", "x"])
