"""Tests for ``pr-size --calibrate`` (vultron.metadata.planning.size_calibration).

Pure: every test feeds fixture records or a fake ``gh`` runner, so nothing reads
GitHub or the clock.
"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta

import pytest

from vultron.metadata.planning import size_bands
from vultron.metadata.planning.gh import GhError
from vultron.metadata.planning.size_calibration import fetch, measures, report
from vultron.metadata.planning.size_calibration.model import (
    CalibrationData,
    ClosedIssue,
    IssuePair,
    MergedPr,
)

SCHEME = size_bands.calibration_scheme()
NOW = datetime(2026, 11, 5, tzinfo=UTC)
SINCE = NOW - timedelta(days=60)
IN_WINDOW = NOW - timedelta(days=1)


def pr(number: int, lines: int, closes: tuple[int, ...] = ()) -> MergedPr:
    return MergedPr(number, IN_WINDOW, lines, closes)


def issue(
    number: int,
    closer: int | tuple[int, ...],
    labels: tuple[str, ...] = ("size:M",),
    acs: int | None = 3,
    closed: bool = True,
) -> ClosedIssue:
    closers = (closer,) if isinstance(closer, int) else closer
    return ClosedIssue(number, closed, labels, acs, closers)


def data(
    prs: Sequence[MergedPr], issues: Sequence[ClosedIssue] = ()
) -> CalibrationData:
    return CalibrationData(SINCE, NOW, tuple(prs), tuple(issues))


class TestCountAcs:
    def test_labelled_checkboxes_count_wherever_they_sit(self):
        body = "- [ ] AC-1: one\n* [x] AC-2: two\n  - [X] AC-3: three\n"
        assert measures.count_acs(body) == 3

    def test_an_unlabelled_checkbox_outside_the_section_does_not_count(self):
        body = "- [ ] AC-1: one\n- [ ] a stray task\n"
        assert measures.count_acs(body) == 1

    def test_without_labels_it_counts_the_acceptance_criteria_section(self):
        body = (
            "## Summary\n- [ ] not an AC\n\n"
            "## Acceptance Criteria\n- [ ] first\n- [x] second\n\n"
            "## Notes\n- [ ] also not an AC\n"
        )
        assert measures.count_acs(body) == 2

    def test_the_section_may_run_to_the_end_of_the_body(self):
        body = "### acceptance criteria\n- [ ] first\n"
        assert measures.count_acs(body) == 1

    @pytest.mark.parametrize(
        "body",
        ["", "no criteria here", "## Acceptance Criteria\n\nprose only\n"],
    )
    def test_no_acceptance_criteria_is_none_not_zero(self, body):
        assert measures.count_acs(body) is None


class TestPercentile:
    def test_endpoints_are_the_minimum_and_maximum(self):
        assert measures.percentile([5, 1, 3], 0) == 1
        assert measures.percentile([5, 1, 3], 100) == 5

    def test_it_interpolates_between_ranks(self):
        assert measures.percentile([0, 10], 25) == pytest.approx(2.5)
        assert measures.percentile([1, 2, 3, 4], 50) == pytest.approx(2.5)

    def test_a_single_value_is_every_percentile(self):
        assert measures.percentile([7], 61) == 7

    def test_empty_input_is_refused(self):
        with pytest.raises(ValueError, match="empty"):
            measures.percentile([], 50)

    @pytest.mark.parametrize("p", [-1, 100.5])
    def test_out_of_range_p_is_refused(self, p):
        with pytest.raises(ValueError, match="0-100"):
            measures.percentile([1, 2], p)


class TestTargetShares:
    def test_each_band_holds_the_gap_between_its_cuts(self):
        assert measures.target_shares((23, 61, 87)) == (23, 38, 26, 13)

    def test_shares_sum_to_the_whole(self):
        assert sum(measures.target_shares()) == 100

    def test_one_percentile_per_bounded_band(self):
        """The report pairs them with ``strict=True``; this says why it holds.

        Re-cutting the table to a different band count without a matching
        percentile list would otherwise surface only when someone ran it.
        """
        bounded = [b for b in size_bands.SIZE_BANDS if b.max_lines is not None]
        assert len(measures.CALIBRATION_PERCENTILES) == len(bounded)


class TestBandShares:
    def test_counts_and_shares_follow_the_classifier(self):
        prs = [pr(1, 10), pr(2, 100), pr(3, 101), pr(4, 5000)]
        shares = measures.band_shares(prs, SCHEME)
        assert [(s.label, s.count) for s in shares] == [
            ("size:S", 2),
            ("size:M", 1),
            ("size:L", 0),
            ("size:XL", 1),
        ]
        assert [s.share for s in shares] == [50.0, 25.0, 0.0, 25.0]

    def test_no_prs_gives_every_band_a_zero_share(self):
        shares = measures.band_shares([], SCHEME)
        assert [s.label for s in shares] == list(SCHEME.labels)
        assert all(s.count == 0 and s.share == 0.0 for s in shares)


class TestDiffPercentiles:
    def test_one_value_per_requested_percentile(self):
        prs = [pr(n, n * 10) for n in range(1, 102)]
        assert measures.diff_percentiles(prs, (0, 50, 100)) == (
            (0, 10),
            (50, 510),
            (100, 1010),
        )

    def test_an_empty_window_is_refused(self):
        with pytest.raises(ValueError):
            measures.diff_percentiles([])


class TestPairedIssues:
    def test_a_closed_issue_with_one_window_closer_pairs(self):
        window = data([pr(10, 50)], [issue(1, 10)])
        assert measures.paired_issues(window) == (
            IssuePair(window.issues[0], window.prs[0]),
        )

    def test_an_open_issue_is_left_out(self):
        window = data([pr(10, 50)], [issue(1, 10, closed=False)])
        assert measures.paired_issues(window) == ()

    def test_two_merged_closers_leave_it_out_even_outside_the_window(self):
        window = data([pr(10, 50)], [issue(1, (10, 3))])
        assert measures.paired_issues(window) == ()

    def test_the_same_closer_listed_twice_is_still_one(self):
        window = data([pr(10, 50)], [issue(1, (10, 10))])
        assert len(measures.paired_issues(window)) == 1

    def test_a_closer_that_merged_before_the_window_is_left_out(self):
        window = data([pr(10, 50)], [issue(1, 3)])
        assert measures.paired_issues(window) == ()

    def test_pairs_are_ordered_by_issue_number(self):
        window = data([pr(10, 50)], [issue(5, 10), issue(2, 10)])
        assert [p.issue.number for p in measures.paired_issues(window)] == [
            2,
            5,
        ]


class TestEstimateOf:
    def test_the_largest_known_label_wins(self):
        assert (
            measures.estimate_of(issue(1, 10, ("size:L", "size:S")), SCHEME)
            == "size:L"
        )

    def test_an_unknown_size_label_is_ignored(self):
        assert (
            measures.estimate_of(issue(1, 10, ("size:XXL",)), SCHEME) is None
        )

    def test_no_label_is_no_estimate(self):
        assert measures.estimate_of(issue(1, 10, ()), SCHEME) is None


class TestEstimateAccuracy:
    def test_each_outcome_is_counted(self):
        prs = [pr(10, 50), pr(11, 300), pr(12, 300), pr(13, 5000), pr(14, 9)]
        issues = [
            issue(1, 10, ("size:S",)),  # S → S: exact
            issue(2, 11, ("size:S",)),  # S → M: too small, within one
            issue(3, 12, ("size:L",)),  # L → M: too big, within one
            issue(4, 13, ("size:S",)),  # S → XL: too small by three
            issue(5, 14, ()),  # no estimate
        ]
        pairs = measures.paired_issues(data(prs, issues))
        assert measures.estimate_accuracy(
            pairs, SCHEME
        ) == measures.EstimateAccuracy(
            estimated=4,
            exact=1,
            too_small=2,
            too_big=1,
            within_one=3,
            unestimated=1,
        )

    def test_no_pairs_counts_nothing(self):
        assert measures.estimate_accuracy([], SCHEME).estimated == 0


class TestLinesPerAc:
    def test_median_per_ac_count_smallest_count_first(self):
        prs = [pr(10, 100), pr(11, 300), pr(12, 900)]
        issues = [
            issue(1, 10, acs=2),
            issue(2, 11, acs=2),
            issue(3, 12, acs=1),
            issue(4, 10, acs=None),
        ]
        pairs = measures.paired_issues(data(prs, issues))
        assert measures.lines_by_ac_count(pairs) == (
            measures.AcCountLines(1, 1, 900),
            measures.AcCountLines(2, 2, 200),
        )
        # 900/1, 100/2, 300/2 → median of 50, 150, 900
        assert measures.median_lines_per_ac(pairs) == 150

    def test_no_criteria_anywhere_gives_no_ratio(self):
        pairs = measures.paired_issues(
            data([pr(10, 100)], [issue(1, 10, acs=None)])
        )
        assert measures.lines_by_ac_count(pairs) == ()
        assert measures.median_lines_per_ac(pairs) is None


class TestReport:
    def _window(self) -> CalibrationData:
        prs = [pr(10, 50), pr(11, 300), pr(12, 800), pr(13, 2000)]
        issues = [issue(1, 10, ("size:S",), acs=1), issue(2, 11, (), acs=4)]
        return data(prs, issues)

    def test_every_section_appears_in_order(self):
        text = report.render_report(self._window(), SCHEME)
        titles = [
            "pr-size --calibrate: 2026-09-06 to 2026-11-05",
            "Band shares — 4 PRs merged in the window",
            "Diff-size percentiles",
            "Estimate vs. measured — 2 closed Issues",
            "Median diff lines per AC count — 2 of those Issues",
        ]
        positions = [text.index(title) for title in titles]
        assert positions == sorted(positions)

    def test_band_lines_carry_share_and_target(self):
        text = report.render_report(self._window(), SCHEME)
        assert "size:S" in text and "25.0%  (target 23%)" in text
        assert "size:L ceiling 1200" in text

    def test_accuracy_names_what_the_shares_are_of(self):
        text = report.render_report(self._window(), SCHEME)
        assert "1 carry a size: estimate and 1 carry none" in text
        assert "exact               1 100.0%" in text

    def test_an_empty_window_says_so_instead_of_failing(self):
        text = report.render_report(data([]), SCHEME)
        assert "no PRs merged in the window" in text
        assert "no paired Issue has acceptance criteria" in text
        assert "    —" in text  # a share of nothing is not 0%

    def test_a_new_measure_is_one_more_builder(self):
        """The extension point the later per-band measures use."""

        def extra(window: CalibrationData, scheme) -> report.Section:
            return report.Section("Extra", (f"{len(window.prs)} PRs",))

        text = report.render_report(
            self._window(), SCHEME, (*report.SECTIONS, extra)
        )
        assert text.endswith("Extra\n  4 PRs")


def _node(
    number: int,
    merged: datetime,
    updated: datetime | None = None,
    issues: Sequence[dict] = (),
    additions: int = 7,
    deletions: int = 3,
) -> dict:
    return {
        "number": number,
        "additions": additions,
        "deletions": deletions,
        "mergedAt": merged.isoformat().replace("+00:00", "Z"),
        "updatedAt": (updated or merged).isoformat().replace("+00:00", "Z"),
        "closingIssuesReferences": {"nodes": list(issues)},
    }


def _issue_node(number: int, closers: Sequence[tuple[int, bool]]) -> dict:
    return {
        "number": number,
        "state": "CLOSED",
        "body": "- [ ] AC-1: a\n- [ ] AC-2: b\n",
        "labels": {"nodes": [{"name": "size:S"}, {"name": "theme:x"}]},
        "closedByPullRequestsReferences": {
            "nodes": [{"number": n, "merged": m} for n, m in closers]
        },
    }


def _page(nodes: Sequence[dict], cursor: str | None = None) -> dict:
    return {
        "data": {
            "repository": {
                "pullRequests": {
                    "pageInfo": {
                        "hasNextPage": cursor is not None,
                        "endCursor": cursor,
                    },
                    "nodes": list(nodes),
                }
            }
        }
    }


class TestParsePage:
    def test_a_pr_is_read_with_its_issues(self):
        page = fetch.parse_page(
            _page(
                [_node(10, IN_WINDOW, issues=[_issue_node(1, [(10, True)])])]
            ),
            SINCE,
        )
        assert page.prs == (MergedPr(10, IN_WINDOW, 10, (1,)),)
        assert page.issues == (ClosedIssue(1, True, ("size:S",), 2, (10,)),)
        assert page.next_cursor is None

    def test_an_unmerged_closer_is_not_a_closing_pr(self):
        page = fetch.parse_page(
            _page(
                [
                    _node(
                        10,
                        IN_WINDOW,
                        issues=[_issue_node(1, [(10, True), (9, False)])],
                    )
                ]
            ),
            SINCE,
        )
        assert page.issues[0].merged_closing_prs == (10,)

    def test_a_pr_merged_before_the_window_is_dropped(self):
        old = SINCE - timedelta(days=1)
        page = fetch.parse_page(
            _page([_node(10, old, updated=NOW)], "c"), SINCE
        )
        assert page.prs == ()
        assert page.next_cursor == "c"

    def test_reaching_a_pr_updated_before_the_window_stops_paging(self):
        old = SINCE - timedelta(days=1)
        page = fetch.parse_page(
            _page([_node(10, IN_WINDOW), _node(9, old)], "c"), SINCE
        )
        assert [p.number for p in page.prs] == [10]
        assert page.next_cursor is None

    def test_graphql_errors_are_raised_verbatim(self):
        with pytest.raises(GhError, match="rate limited"):
            fetch.parse_page({"errors": [{"message": "rate limited"}]}, SINCE)

    @pytest.mark.parametrize("payload", [[], {"data": {}}, {"data": None}])
    def test_an_unexpected_shape_is_a_gh_error(self, payload):
        with pytest.raises(GhError, match="could not read the PR query"):
            fetch.parse_page(payload, SINCE)


class FakeGh:
    """A runner that answers each call with the next canned page."""

    def __init__(self, *pages: object) -> None:
        self.replies = [
            p if isinstance(p, str) else json.dumps(p) for p in pages
        ]
        self.calls: list[list[str]] = []

    def __call__(self, args: Sequence[str]) -> str:
        self.calls.append(list(args))
        return self.replies.pop(0)


class TestFetchWindow:
    def test_it_follows_the_cursor_and_merges_pages(self):
        shared = _issue_node(1, [(10, True)])
        gh = FakeGh(
            _page([_node(11, IN_WINDOW, issues=[shared])], "c1"),
            _page([_node(10, IN_WINDOW, issues=[shared])]),
        )
        window = fetch.fetch_window("o/n", SINCE, NOW, gh)
        assert [p.number for p in window.prs] == [10, 11]
        assert [i.number for i in window.issues] == [1]
        assert "endCursor=c1" not in gh.calls[0]
        assert "endCursor=c1" in gh.calls[1]
        assert "owner=o" in gh.calls[0] and "name=n" in gh.calls[0]

    @pytest.mark.parametrize("repo", ["", "owner", "o/", "/n", "o/n/x"])
    def test_a_malformed_repo_is_refused_before_calling_gh(self, repo):
        gh = FakeGh()
        with pytest.raises(GhError, match="OWNER/NAME"):
            fetch.fetch_window(repo, SINCE, NOW, gh)
        assert gh.calls == []

    def test_unparseable_output_is_a_gh_error(self):
        with pytest.raises(GhError, match="could not read"):
            fetch.fetch_window("o/n", SINCE, NOW, FakeGh("not json"))


class TestCli:
    def test_calibrate_reads_the_window_ending_now(self):
        gh = FakeGh(_page([_node(10, IN_WINDOW, additions=40, deletions=2)]))
        text = size_bands.calibrate(7, run=gh, now=NOW)
        assert text.startswith("pr-size --calibrate: 2026-10-29 to 2026-11-05")
        assert "Band shares — 1 PRs merged" in text

    def test_calibrate_refuses_a_non_positive_window(self):
        with pytest.raises(ValueError, match="at least 1"):
            size_bands.calibrate(0, run=FakeGh())

    def test_main_defaults_to_sixty_days(self, monkeypatch, capsys):
        seen: list[int] = []
        monkeypatch.setattr(
            size_bands, "calibrate", lambda days: seen.append(days) or "ok"
        )
        assert size_bands.main(["--calibrate"]) == 0
        assert seen == [size_bands.DEFAULT_CALIBRATION_DAYS] == [60]
        assert capsys.readouterr().out == "ok\n"

    def test_main_passes_days_through(self, monkeypatch):
        seen: list[int] = []
        monkeypatch.setattr(
            size_bands, "calibrate", lambda days: seen.append(days) or ""
        )
        size_bands.main(["--calibrate", "--days", "14"])
        assert seen == [14]

    def test_days_zero_is_reported_not_replaced_by_the_default(self, capsys):
        assert size_bands.main(["--calibrate", "--days", "0"]) == 2
        assert "at least 1" in capsys.readouterr().err

    def test_days_without_calibrate_is_a_usage_error(self):
        with pytest.raises(SystemExit) as exc:
            size_bands.main(["--days", "5"])
        assert exc.value.code == 2

    @pytest.mark.parametrize(
        "failure",
        [
            GhError("gh is not installed"),
            subprocess.CalledProcessError(1, ["gh"], stderr="HTTP 502"),
        ],
    )
    def test_a_gh_failure_exits_one_with_its_detail(
        self, monkeypatch, capsys, failure
    ):
        def boom(days: int) -> str:
            raise failure

        monkeypatch.setattr(size_bands, "calibrate", boom)
        assert size_bands.main(["--calibrate"]) == 1
        err = capsys.readouterr().err
        assert "gh is not installed" in err or "HTTP 502" in err
