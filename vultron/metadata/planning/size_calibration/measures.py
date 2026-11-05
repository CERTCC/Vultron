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
from itertools import pairwise

from vultron.metadata.planning.size_calibration.model import (
    BandScheme,
    CalibrationData,
    ClosedIssue,
    IssuePair,
    MergedPr,
)

CALIBRATION_PERCENTILES: tuple[int, ...] = (23, 61, 87)
"""The merged-PR diff-size quantiles each bounded band's ceiling was cut at.

One per band with a ceiling, smallest first. A table in calibration puts each
ceiling near its percentile, so each band holds the share between consecutive
percentiles (:func:`target_shares`).
"""

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
    is left out, even when the other PR merged before the window. Ordered by
    Issue number.
    """
    in_window = {pr.number: pr for pr in data.prs}
    pairs: dict[int, IssuePair] = {}
    for issue in data.issues:
        closers = set(issue.merged_closing_prs)
        if not issue.closed or len(closers) != 1:
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
