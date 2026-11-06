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
"""The records ``pr-size --calibrate`` reads and measures.

:class:`MergedPr` and :class:`ClosedIssue` are what the GraphQL query returns,
already reduced to what the measures need; :class:`CalibrationData` is one
window of them. :class:`BandScheme` carries the band table in, so this package
never imports ``size_bands`` (which imports it for the CLI) and a test can
calibrate against any table whose cut quantiles it also names.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from itertools import pairwise
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from vultron.metadata.planning.size_bands import SizeBand


CALIBRATION_PERCENTILES: tuple[int, ...] = (23, 61, 87)
"""The merged-PR diff-size quantiles each bounded band's ceiling was cut at.

One per band with a ceiling, smallest first. A table in calibration puts each
ceiling near its percentile, so each band holds the share between consecutive
percentiles (:func:`.measures.target_shares`).
"""


FOLLOW_UP = timedelta(days=30)
"""How long after a PR merges a bug fix still counts as a later fix of it.

Only a PR merged at least this long before the window ends has had its whole
follow-up observed, so only those PRs enter the later-fix rate
(:func:`.measures.fix_rates`).
"""

BUG_FIX_PREFIXES: tuple[str, ...] = ("bug/", "fix/")
"""The head-branch prefixes that mark a PR as a bug fix."""


@dataclass(frozen=True)
class BandScheme:
    """The band table to calibrate, the classifier, and the quantiles it was cut at.

    ``bands`` is ordered smallest first, as ``SIZE_BANDS`` is; ``classify`` is
    ``band_for_diff``. They are passed together so the report ranks bands in the
    same order the classifier assigns them. ``percentiles`` holds one cut
    quantile per band with a line ceiling, smallest first; the report pairs
    them with those bands and derives each band's target share from them.

    Raises:
        ValueError: If ``percentiles`` does not hold one strictly increasing
            value inside 0-100 per bounded band.
    """

    bands: tuple[SizeBand, ...]
    classify: Callable[[int], SizeBand]
    percentiles: tuple[int, ...] = CALIBRATION_PERCENTILES

    def __post_init__(self) -> None:
        bounded = sum(1 for band in self.bands if band.max_lines is not None)
        if len(self.percentiles) != bounded:
            raise ValueError(
                f"a scheme with {bounded} bounded bands needs {bounded} cut "
                f"percentiles, got {len(self.percentiles)}"
            )
        cuts = (0, *self.percentiles, 100)
        if any(lower >= upper for lower, upper in pairwise(cuts)):
            raise ValueError(
                "cut percentiles must increase strictly inside 0-100, got "
                f"{self.percentiles}"
            )

    @property
    def labels(self) -> tuple[str, ...]:
        """The band labels, smallest first."""
        return tuple(band.label for band in self.bands)

    def rank(self, label: str) -> int:
        """The position of ``label`` in the table, smallest band at 0.

        Raises:
            ValueError: If ``label`` is not one of the scheme's bands.
        """
        return self.labels.index(label)


@dataclass(frozen=True)
class MergedPr:
    """One PR merged in the calibration window.

    ``diff_lines`` is additions plus deletions, the number ``pr-size-label``
    measures (PAD-05-002). ``closes`` is the Issues it closes by keyword.

    The rest feeds the quality measures. ``head_ref`` is the head branch name,
    which marks a bug fix (:data:`BUG_FIX_PREFIXES`). ``open_for`` is the time
    from opening to merge. ``commit_count`` is how many commits the PR has, and
    ``commits`` the ids of those read, which may be fewer
    (:attr:`commits_complete`); ``merge_commit`` is the commit its merge put on
    the base branch (``None`` when unknown). A later fix's blame maps back to
    the PR through either.
    ``triage_findings`` is the review findings its triage records raise, and
    ``None`` when it carries no triage record at all
    (:func:`.measures.count_triage_findings`).
    """

    number: int
    merged_at: datetime
    diff_lines: int
    closes: tuple[int, ...] = ()
    head_ref: str = ""
    open_for: timedelta = timedelta(0)
    commit_count: int = 0
    commits: tuple[str, ...] = ()
    merge_commit: str | None = None
    triage_findings: int | None = None

    @property
    def is_bug_fix(self) -> bool:
        """Whether the head branch marks this PR as a bug fix."""
        return self.head_ref.startswith(BUG_FIX_PREFIXES)

    @property
    def commits_complete(self) -> bool:
        """Whether ``commits`` holds the id of every commit on the PR."""
        return len(self.commits) >= self.commit_count


@dataclass(frozen=True)
class ClosedIssue:
    """An Issue some window PR closes, reduced to what calibration reads.

    ``size_labels`` is every ``size:`` label the Issue carries — the estimate
    PAD-05-010 keeps there. ``ac_count`` is its acceptance-criteria
    checkbox count, ``None`` when the body has no acceptance criteria.
    ``merged_closing_prs`` is every *merged* PR that closes it, inside the
    window or not, so a second PR outside the window still disqualifies it.
    ``closers_complete`` is false when GitHub listed more linked PRs than the
    query read, so a second merged closer may be among the unread ones.
    """

    number: int
    closed: bool
    size_labels: tuple[str, ...]
    ac_count: int | None
    merged_closing_prs: tuple[int, ...]
    closers_complete: bool = True


@dataclass(frozen=True)
class FixTrace:
    """The commits a bug-fix PR's changed lines were last written by.

    ``blamed`` is every distinct commit that ``git blame`` names, at the first
    parent of the fix's merge, for the ``vultron/`` lines the fix deletes or
    rewrites.
    """

    fix: int
    blamed: frozenset[str]


@dataclass(frozen=True)
class CalibrationData:
    """One window of merged PRs, the Issues they close, and the fix traces.

    ``fix_traces`` holds one :class:`FixTrace` per bug-fix PR traced, so a
    window read without tracing reports no later fixes rather than failing.
    """

    since: datetime
    until: datetime
    prs: tuple[MergedPr, ...]
    issues: tuple[ClosedIssue, ...] = ()
    fix_traces: tuple[FixTrace, ...] = ()


@dataclass(frozen=True)
class IssuePair:
    """A closed Issue and the single merged PR that closed it."""

    issue: ClosedIssue
    pr: MergedPr
