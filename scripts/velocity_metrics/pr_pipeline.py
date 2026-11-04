"""Per-PR pipeline cost: PR-body summary lines, merges from main, CI
iterations, the per-PR record and its weekly aggregates."""

from __future__ import annotations

import re
from collections import defaultdict

import pandas as pd

from .periods import iso_to_date, iso_to_datetime, week_key

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


def _bold_label(name: str) -> str:
    """Regex for ``name:`` as a line label, bolded by hand or not."""
    return rf"(?:\*\*|__)?{name}(?:\*\*|__)?:(?:\*\*|__)?\s+"


_SUITE_RUNS_LABEL = _bold_label("Suite runs")
_SUITE_RUNS_RE = re.compile(
    _SUITE_RUNS_LABEL + r"(\d+)\s+full,\s+(\d+)\s+targeted"
)
_SUITE_RUNS_WORDS_FIRST_RE = re.compile(
    _SUITE_RUNS_LABEL + r"full\s+(\d+),\s+targeted\s+(\d+)"
)

# The line an implementation PR body carries (pr-body-guide.md, "Questions"):
# ``Questions: asked N, filed M``.  The label may be bolded by hand.  Like
# PRB-13, it is read only at the start of a line, so a body that quotes the
# guide's example mid-sentence is not counted by it.
_QUESTIONS_RE = re.compile(
    r"^[ \t]*" + _bold_label("Questions") + r"asked\s+(\d+),\s+filed\s+(\d+)",
    re.MULTILINE,
)


# Workflow-run conclusions.  A "CI run" in this script is one CI iteration:
# the set of workflow runs GitHub started for one head commit.  Superseded
# (cancelled) and skipped runs say nothing about the commit, so a commit whose
# runs were all cancelled or skipped is not an iteration.
_FAILED_CONCLUSIONS = frozenset({"failure", "timed_out", "startup_failure"})
_IGNORED_CONCLUSIONS = frozenset({"cancelled", "skipped"})


def parse_questions_line(body: str) -> tuple[int, int] | None:
    """Parse the ``Questions: asked N, filed M`` line from a PR body.

    Returns ``(asked, filed)`` when the line is present and well-formed,
    including a bolded label.  Returns ``None`` when it is absent or
    malformed.
    """
    m = _QUESTIONS_RE.search(body)
    if m:
        return int(m.group(1)), int(m.group(2))
    return None


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
            ``body``, ``headRefName``, ``commits.nodes``, ``comments.nodes``, and
            ``reviews.nodes``.
        ci_runs: CI iterations (see ``_ci_iteration_counts``) for this PR.
        failed_ci_runs: subset of ``ci_runs`` that failed.

    Returns a flat dict suitable for per-PR output and weekly aggregation.
    """
    created_str = pr.get("createdAt")
    merged_str = pr.get("mergedAt")

    open_to_merge_hours: float | None = None
    created_dt = iso_to_datetime(created_str)
    merged_dt = iso_to_datetime(merged_str)
    if created_dt and merged_dt:
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

    questions = parse_questions_line(pr.get("body") or "")
    questions_asked: int | None = None
    questions_filed: int | None = None
    if questions is not None:
        questions_asked, questions_filed = questions

    return {
        "pr_number": pr.get("number"),
        "merged_at": merged_str,
        "open_to_merge_hours": open_to_merge_hours,
        "ci_runs": ci_runs,
        "failed_ci_runs": failed_ci_runs,
        "merges_from_main": merges_from_main,
        "full_suite_runs": full_suite_runs,
        "targeted_suite_runs": targeted_suite_runs,
        "questions_asked": questions_asked,
        "questions_filed": questions_filed,
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
    ``total_<field>`` for each numeric field.  Suite-run and question totals
    are included only for PRs that carried the ``Suite runs:`` or
    ``Questions:`` line; absent values
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

        for suite_field in (
            "full_suite_runs",
            "targeted_suite_runs",
            "questions_asked",
            "questions_filed",
        ):
            values_s = [
                r[suite_field] for r in recs if r.get(suite_field) is not None
            ]
            row[f"total_{suite_field}"] = sum(values_s) if values_s else None

        rows.append(row)
    return rows
