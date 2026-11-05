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
calibrate against any table.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from vultron.metadata.planning.size_bands import SizeBand


@dataclass(frozen=True)
class BandScheme:
    """The band table to calibrate, and the classifier that applies it.

    ``bands`` is ordered smallest first, as ``SIZE_BANDS`` is; ``classify`` is
    ``band_for_diff``. They are passed together so the report ranks bands in the
    same order the classifier assigns them.
    """

    bands: tuple[SizeBand, ...]
    classify: Callable[[int], SizeBand]

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
    """

    number: int
    merged_at: datetime
    diff_lines: int
    closes: tuple[int, ...] = ()


@dataclass(frozen=True)
class ClosedIssue:
    """An Issue some window PR closes, reduced to what calibration reads.

    ``size_labels`` is every ``size:`` label the Issue carries — the estimate
    PAD-05-010 keeps there. ``ac_count`` is its acceptance-criteria
    checkbox count, ``None`` when the body has no acceptance criteria.
    ``merged_closing_prs`` is every *merged* PR that closes it, inside the
    window or not, so a second PR outside the window still disqualifies it.
    """

    number: int
    closed: bool
    size_labels: tuple[str, ...]
    ac_count: int | None
    merged_closing_prs: tuple[int, ...]


@dataclass(frozen=True)
class CalibrationData:
    """One window of merged PRs and the Issues they close."""

    since: datetime
    until: datetime
    prs: tuple[MergedPr, ...]
    issues: tuple[ClosedIssue, ...] = ()


@dataclass(frozen=True)
class IssuePair:
    """A closed Issue and the single merged PR that closed it."""

    issue: ClosedIssue
    pr: MergedPr
