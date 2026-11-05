#  Copyright (c) 2026 Carnegie Mellon University and Contributors.
#  - see Contributors.md for a full list of Contributors
#  - see ContributionInstructions.md for information on how you can Contribute to this project
#  Vultron Multiparty Coordinated Vulnerability Disclosure Protocol Prototype is
#  licensed under a MIT (SEI)-style license, please see LICENSE.md distributed
#  with this Software or contact permission@sei.cmu.edu for full terms.
#  Created, in part, with funding and support from the United States Government
#  (see Acknowledgments file). This program may include and/or can make use of
#  certain third party source code, object code, documentation and other files
#  ("Third Party Software"). See LICENSE.md for more details.
#  Carnegie Mellon®, CERT® and CERT Coordination Center® are registered in the
#  U.S. Patent and Trademark Office by Carnegie Mellon University
"""The arithmetic behind ``pr-size --calibrate``, as pure functions.

Nothing here reads GitHub or the clock: every function takes the records in
:mod:`.model` and returns numbers, so tests feed fixture data.
"""

from __future__ import annotations

import math
import re
import statistics
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import timedelta
from itertools import pairwise

from vultron.metadata.planning.size_calibration.model import (
    CALIBRATION_PERCENTILES,
    FOLLOW_UP,
    BandScheme,
    CalibrationData,
    ClosedIssue,
    IssuePair,
    MergedPr,
)

_AC_ITEM = re.compile(r"^[ \t]*[-*+][ \t]+\[[ xX]\][ \t]+AC-\d+\b", re.M)
_CHECKBOX = re.compile(r"^[ \t]*[-*+][ \t]+\[[ xX]\][ \t]+\S", re.M)
_AC_HEADING = re.compile(r"^#{1,6}[ \t]+Acceptance Criteria\b.*$", re.M | re.I)
_HEADING = re.compile(r"^#{1,6}[ \t]", re.M)


def count_acs(body: str) -> int | None:
    """The acceptance-criteria checkbox count of an Issue body (PAD-05-001).

    Checkboxes labelled ``AC-N`` count wherever they sit, which is the form the
    Issue templates write. A body with none falls back to the checkboxes under
    an ``Acceptance Criteria`` heading. ``None`` means the body has no
    acceptance criteria at all, which is not the same as a count of zero.
    """
    labelled = len(_AC_ITEM.findall(body))
    if labelled:
        return labelled
    heading = _AC_HEADING.search(body)
    if heading is None:
        return None
    rest = body[heading.end() :]
    following = _HEADING.search(rest)
    section = rest if following is None else rest[: following.start()]
    return len(_CHECKBOX.findall(section)) or None


def percentile(values: Sequence[float], p: float) -> float:
    """The ``p``-th percentile of ``values``, linearly interpolated.

    The inclusive method: ``p=0`` is the minimum, ``p=100`` the maximum.

    Raises:
        ValueError: If ``values`` is empty or ``p`` is outside 0-100.
    """
    if not values:
        raise ValueError("percentile of an empty sequence is undefined")
    if not 0 <= p <= 100:
        raise ValueError(f"percentile must be within 0-100, got {p}")
    ordered = sorted(values)
    position = (len(ordered) - 1) * p / 100
    low, high = math.floor(position), math.ceil(position)
    return ordered[low] + (ordered[high] - ordered[low]) * (position - low)


def target_shares(
    percentiles: Sequence[int] = CALIBRATION_PERCENTILES,
) -> tuple[float, ...]:
    """The share of PRs, in percent, each band holds when in calibration.

    One more share than percentiles: the last band holds everything above the
    last cut.
    """
    cuts = (0, *percentiles, 100)
    return tuple(float(upper - lower) for lower, upper in pairwise(cuts))


@dataclass(frozen=True)
class BandShare:
    """How many window PRs one band measured, and their share in percent."""

    label: str
    count: int
    share: float


def band_shares(
    prs: Sequence[MergedPr], scheme: BandScheme
) -> tuple[BandShare, ...]:
    """Each band's count and share of ``prs``, smallest band first.

    Every band appears, including empty ones; with no PRs every share is 0.
    """
    counts = dict.fromkeys(scheme.labels, 0)
    for pr in prs:
        counts[scheme.classify(pr.diff_lines).label] += 1
    total = len(prs)
    return tuple(
        BandShare(label, count, 100 * count / total if total else 0.0)
        for label, count in counts.items()
    )


def diff_percentiles(
    prs: Sequence[MergedPr],
    percentiles: Sequence[int] = CALIBRATION_PERCENTILES,
) -> tuple[tuple[int, float], ...]:
    """``(p, diff lines)`` for each calibration percentile of ``prs``.

    Raises:
        ValueError: If ``prs`` is empty.
    """
    sizes = [pr.diff_lines for pr in prs]
    return tuple((p, percentile(sizes, p)) for p in percentiles)


def paired_issues(data: CalibrationData) -> tuple[IssuePair, ...]:
    """Closed Issues whose single merged closing PR merged in the window.

    An Issue closed by two merged PRs has no one diff that measures it, so it
    is left out, even when the other PR merged before the window, and so is an
    Issue whose closer list the query could not read in full. Ordered by Issue
    number.
    """
    in_window = {pr.number: pr for pr in data.prs}
    pairs: dict[int, IssuePair] = {}
    for issue in data.issues:
        closers = set(issue.merged_closing_prs)
        if not (issue.closed and issue.closers_complete) or len(closers) != 1:
            continue
        pr = in_window.get(next(iter(closers)))
        if pr is not None:
            pairs[issue.number] = IssuePair(issue, pr)
    return tuple(pairs[number] for number in sorted(pairs))


def estimate_of(issue: ClosedIssue, scheme: BandScheme) -> str | None:
    """The Issue's estimate band, or ``None`` when it carries none.

    The largest known ``size:`` label wins, as in ``weight_of``; a label the
    scheme does not know is ignored.
    """
    known = [label for label in issue.size_labels if label in scheme.labels]
    return max(known, key=scheme.rank) if known else None


@dataclass(frozen=True)
class EstimateAccuracy:
    """How the Issue estimates compared with the measured PR bands.

    ``estimated`` counts the pairs that carry an estimate, and the four
    outcome counts are out of it. ``within_one`` includes ``exact``.
    ``unestimated`` is the pairs left out for having no ``size:`` label.
    """

    estimated: int
    exact: int
    too_small: int
    too_big: int
    within_one: int
    unestimated: int


def estimate_accuracy(
    pairs: Sequence[IssuePair], scheme: BandScheme
) -> EstimateAccuracy:
    """Compare each pair's estimate band with its PR's measured band.

    "Too small" means the estimate is a smaller band than the PR measured.
    """
    exact = too_small = too_big = within_one = unestimated = 0
    for pair in pairs:
        estimate = estimate_of(pair.issue, scheme)
        if estimate is None:
            unestimated += 1
            continue
        gap = scheme.rank(estimate) - scheme.rank(
            scheme.classify(pair.pr.diff_lines).label
        )
        exact += gap == 0
        too_small += gap < 0
        too_big += gap > 0
        within_one += abs(gap) <= 1
    return EstimateAccuracy(
        estimated=len(pairs) - unestimated,
        exact=exact,
        too_small=too_small,
        too_big=too_big,
        within_one=within_one,
        unestimated=unestimated,
    )


@dataclass(frozen=True)
class AcCountLines:
    """The median PR diff for the Issues with one acceptance-criteria count."""

    ac_count: int
    issues: int
    median_lines: float


def lines_by_ac_count(pairs: Sequence[IssuePair]) -> tuple[AcCountLines, ...]:
    """Median diff lines per AC count, smallest count first.

    Pairs whose Issue has no acceptance criteria are left out.
    """
    groups: dict[int, list[int]] = {}
    for pair in pairs:
        if pair.issue.ac_count is not None:
            groups.setdefault(pair.issue.ac_count, []).append(
                pair.pr.diff_lines
            )
    return tuple(
        AcCountLines(count, len(sizes), statistics.median(sizes))
        for count, sizes in sorted(groups.items())
    )


def median_lines_per_ac(pairs: Sequence[IssuePair]) -> float | None:
    """The median of each pair's diff lines divided by its AC count.

    The one number the "lines per AC moved" drift check compares across runs.
    ``None`` when no pair has acceptance criteria.
    """
    ratios = [
        pair.pr.diff_lines / pair.issue.ac_count
        for pair in pairs
        if pair.issue.ac_count
    ]
    return statistics.median(ratios) if ratios else None


_HEADING_LINE = re.compile(r"\A\s*(?:#{1,6}\s|\*\*)")
_ROLE_WORD = re.compile(
    r"\b(?:pre-push review|triage|review|verify|execute|verdict)\b", re.I
)
_FINDING_ID = re.compile(r"\bphase\d+-[a-z0-9]+(?:-[a-z0-9]+)*-\d+\b")
_SEVERITY_COUNT = re.compile(r"(\d+)\s+(FAIL|IMPROVE|NEW-ISSUE)\b")
_FINDINGS_COUNT = re.compile(r"(\d+)\s+(?:[\w-]+\s+){0,2}findings?\b", re.I)


def is_triage_record(body: str) -> bool:
    """Whether a review or comment body is a triage record.

    Its first non-blank line must be a heading, either a markdown ``#``
    heading or a line opening in bold, so the name it carries is the
    comment's own. A heading naming a ``verdict`` is a verification report,
    not a review. Otherwise the first of the words triage, review, verify and
    execute in the heading decides: triage or review makes it a record. That
    takes in ``## PR Triage``, ``**Pre-push review**``, ``## pr-ship review
    (triage, execute, verify)`` and ``## 🔍 pr-triage``, and leaves out ``## PR
    Verify``, ``## PR Execute`` and ``## pr-execute: fixed all 3 triage
    findings``, whose findings the triage record already counted.
    """
    heading = next((line for line in body.splitlines() if line.strip()), "")
    if not _HEADING_LINE.match(heading):
        return False
    words = [word.lower() for word in _ROLE_WORD.findall(heading)]
    if not words or "verdict" in words:
        return False
    return words[0] in {"pre-push review", "triage", "review"}


def _line_count(line: str) -> int | None:
    """The findings one line states, or ``None`` when it states none.

    Each severity's first number on the line is summed, so ``2 FAIL, 10
    IMPROVE, 1 NEW-ISSUE`` is 13. A line naming no severity may still state a
    total, as ``16 findings`` or ``16 pre-push findings``.
    """
    counts: dict[str, int] = {}
    for number, severity in _SEVERITY_COUNT.findall(line):
        counts.setdefault(severity, int(number))
    if counts:
        return sum(counts.values())
    total = _FINDINGS_COUNT.search(line)
    return None if total is None else int(total.group(1))


def _stated_count(body: str) -> int:
    """The findings a record states in words, for one that lists no ids.

    A ``**Total**`` line that states a count wins; otherwise the first line
    that states one (:func:`_line_count`). A record stating none counts 0.
    """
    lines = body.splitlines()
    totals = [line for line in lines if line.lstrip().startswith("**Total**")]
    for line in (*totals, *lines):
        count = _line_count(line)
        if count is not None:
            return count
    return 0


def count_triage_findings(bodies: Sequence[str]) -> int | None:
    """The review findings a PR's triage records raise, or ``None`` if none.

    A triage record is a review or comment :func:`is_triage_record` accepts:
    the comments ``pr-triage`` and ``pr-ship`` post and the pre-push review
    ``build`` posts. A record's findings are the distinct finding ids
    (``phase8-slug-0``) it names, and the ids are pooled across records, so a
    finding carried forward from the pre-push review into the post-push
    triage counts once. A record that names no ids counts what it states in
    words (:func:`_stated_count`). ``None`` means the PR carries no triage
    record, which is not the same as a triage that found nothing.
    """
    records = [body for body in bodies if is_triage_record(body)]
    if not records:
        return None
    ids: set[str] = set()
    stated = 0
    for body in records:
        found = set(_FINDING_ID.findall(body))
        if found:
            ids |= found
        else:
            stated += _stated_count(body)
    return len(ids) + stated


def commit_owners(prs: Sequence[MergedPr]) -> dict[str, int]:
    """Each commit on a window PR, mapped to the PR that landed it.

    A commit can sit on two PRs, as when one branch is stacked on another;
    it belongs to the one that merged first, since that merge is what put it on
    the base branch. A PR's merge commit is its own.
    """
    owners: dict[str, int] = {}
    for pr in sorted(prs, key=lambda pr: (pr.merged_at, pr.number)):
        merge = () if pr.merge_commit is None else (pr.merge_commit,)
        for commit in (*pr.commits, *merge):
            owners.setdefault(commit, pr.number)
    return owners


def later_fixes(data: CalibrationData) -> dict[int, frozenset[int]]:
    """The bug-fix PRs that rewrote each window PR's lines within the follow-up.

    A fix counts against a PR when its traced lines blame to one of the PR's
    commits and it merged after the PR, within :data:`.model.FOLLOW_UP` of
    the PR's merge. Each fix counts once per PR however many of its lines
    blame there. A blamed commit no window PR carries, and a trace of a PR
    outside the window, are ignored. PRs no fix rewrote are absent.
    """
    by_number = {pr.number: pr for pr in data.prs}
    owners = commit_owners(data.prs)
    fixes: dict[int, set[int]] = {}
    for trace in data.fix_traces:
        fix = by_number.get(trace.fix)
        if fix is None:
            continue
        for commit in trace.blamed:
            owner = owners.get(commit)
            if owner is None or owner == fix.number:
                continue
            gap = fix.merged_at - by_number[owner].merged_at
            if timedelta(0) < gap <= FOLLOW_UP:
                fixes.setdefault(owner, set()).add(fix.number)
    return {number: frozenset(found) for number, found in fixes.items()}


def followed_up(data: CalibrationData) -> tuple[MergedPr, ...]:
    """The window PRs merged at least :data:`.model.FOLLOW_UP` before its end."""
    return tuple(
        pr for pr in data.prs if pr.merged_at + FOLLOW_UP <= data.until
    )


@dataclass(frozen=True)
class BandFixRate:
    """One band's later bug fixes, over the PRs with a full follow-up.

    ``fixes`` sums, over the band's PRs, the distinct fix PRs that rewrote
    each one, so a fix that rewrote two PRs counts once for each.
    """

    label: str
    prs: int
    lines: int
    fixes: int

    @property
    def per_pr(self) -> float | None:
        """Later fixes per PR; ``None`` for a band with no PRs."""
        return self.fixes / self.prs if self.prs else None

    @property
    def per_kloc(self) -> float | None:
        """Later fixes per 1,000 diff lines; ``None`` with no lines."""
        return 1000 * self.fixes / self.lines if self.lines else None


def fix_rates(
    data: CalibrationData, scheme: BandScheme
) -> tuple[BandFixRate, ...]:
    """Each band's later-fix rate over the window PRs with a full follow-up.

    Every band appears, smallest first, including empty ones.
    """
    fixes = later_fixes(data)
    tally = {label: [0, 0, 0] for label in scheme.labels}
    for pr in followed_up(data):
        row = tally[scheme.classify(pr.diff_lines).label]
        row[0] += 1
        row[1] += pr.diff_lines
        row[2] += len(fixes.get(pr.number, ()))
    return tuple(
        BandFixRate(label, prs, lines, found)
        for label, (prs, lines, found) in tally.items()
    )


HEAVY_FINDINGS = 8
"""Triage findings at or above which a PR counts as heavily reviewed."""

HEAVY_COMMITS = 7
"""Commits at or above which a PR counts as heavily reviewed."""

HEAVY_OPEN = timedelta(days=1)
"""Time open at or above which a PR counts as heavily reviewed."""


@dataclass(frozen=True)
class HeavyReview:
    """Which of the three heavy-review tests one PR meets."""

    findings: bool
    commits: bool
    open_long: bool

    @property
    def heavy(self) -> bool:
        """Whether the PR meets any of the three."""
        return self.findings or self.commits or self.open_long


def heavy_review(pr: MergedPr) -> HeavyReview:
    """Test ``pr`` against each heavy-review threshold.

    A PR with no triage record meets the findings test only if it has
    findings, so it never does.
    """
    return HeavyReview(
        findings=(pr.triage_findings or 0) >= HEAVY_FINDINGS,
        commits=pr.commit_count >= HEAVY_COMMITS,
        open_long=pr.open_for >= HEAVY_OPEN,
    )


@dataclass(frozen=True)
class BandReviewLoad:
    """One band's heavy-review count, and how many PRs met each test.

    A PR meeting two tests counts under both, so the three test counts may
    sum past ``heavy``.
    """

    label: str
    prs: int
    heavy: int
    by_findings: int
    by_commits: int
    by_open: int


def review_loads(
    prs: Sequence[MergedPr], scheme: BandScheme
) -> tuple[BandReviewLoad, ...]:
    """Each band's heavy-review share of ``prs``, smallest band first.

    Every band appears, including empty ones.
    """
    tally = {label: [0, 0, 0, 0, 0] for label in scheme.labels}
    for pr in prs:
        row = tally[scheme.classify(pr.diff_lines).label]
        verdict = heavy_review(pr)
        for index, met in enumerate(
            (
                True,
                verdict.heavy,
                verdict.findings,
                verdict.commits,
                verdict.open_long,
            )
        ):
            row[index] += met
    return tuple(BandReviewLoad(label, *row) for label, row in tally.items())
