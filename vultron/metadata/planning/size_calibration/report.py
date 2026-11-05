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
"""The ``pr-size --calibrate`` report: one section per measure.

Each section is a :data:`SectionBuilder` that turns a window of data into a
titled block of lines. :data:`SECTIONS` is the report, in order; a new measure
is a new builder appended there, and :func:`render_report` needs no change.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass

from vultron.metadata.planning.size_calibration.measures import (
    CALIBRATION_PERCENTILES,
    band_shares,
    diff_percentiles,
    estimate_accuracy,
    lines_by_ac_count,
    median_lines_per_ac,
    paired_issues,
    target_shares,
)
from vultron.metadata.planning.size_calibration.model import (
    BandScheme,
    CalibrationData,
)


@dataclass(frozen=True)
class Section:
    """One titled block of the report."""

    title: str
    lines: tuple[str, ...]

    def render(self) -> str:
        """The title, then each line indented under it."""
        return "\n".join([self.title, *(f"  {line}" for line in self.lines)])


SectionBuilder = Callable[[CalibrationData, BandScheme], Section]
"""Builds one report section from a window of data and the band table."""


def _percent(part: int, whole: int) -> str:
    return f"{100 * part / whole:5.1f}%" if whole else "    —"


def band_share_section(data: CalibrationData, scheme: BandScheme) -> Section:
    """Each band's share of the window's PRs, against its target share."""
    title = f"Band shares — {len(data.prs)} PRs merged in the window"
    if not data.prs:
        return Section(title, ("no PRs merged in the window",))
    lines = [
        f"{share.label:<8} {band.lines_range:>10} {share.count:>5} "
        f"{share.share:5.1f}%  (target {target:.0f}%)"
        for share, band, target in zip(
            band_shares(data.prs, scheme),
            scheme.bands,
            target_shares(),
            strict=True,
        )
    ]
    return Section(title, tuple(lines))


def percentile_section(data: CalibrationData, scheme: BandScheme) -> Section:
    """The diff size at each calibration percentile, beside its ceiling."""
    title = (
        "Diff-size percentiles — where each band's ceiling would sit if "
        "recut today"
    )
    if not data.prs:
        return Section(title, ("no PRs merged in the window",))
    bounded = [band for band in scheme.bands if band.max_lines is not None]
    lines = [
        f"p{p:<3} {value:>8.0f} lines   {band.label} ceiling {band.max_lines}"
        for (p, value), band in zip(
            diff_percentiles(data.prs, CALIBRATION_PERCENTILES),
            bounded,
            strict=True,
        )
    ]
    return Section(title, tuple(lines))


def estimate_accuracy_section(
    data: CalibrationData, scheme: BandScheme
) -> Section:
    """How often the Issue estimate matched the measured PR band."""
    pairs = paired_issues(data)
    accuracy = estimate_accuracy(pairs, scheme)
    title = (
        f"Estimate vs. measured — {len(pairs)} closed Issues whose single "
        "closing PR merged in the window"
    )
    whole = accuracy.estimated
    lines = [
        f"{whole} carry a size: estimate and {accuracy.unestimated} carry "
        "none; the shares below are of the estimated ones",
        f"exact           {accuracy.exact:>5} {_percent(accuracy.exact, whole)}",
        f"too small       {accuracy.too_small:>5} "
        f"{_percent(accuracy.too_small, whole)}  (estimate below the "
        "measured band)",
        f"too big         {accuracy.too_big:>5} "
        f"{_percent(accuracy.too_big, whole)}  (estimate above the "
        "measured band)",
        f"within one band {accuracy.within_one:>5} "
        f"{_percent(accuracy.within_one, whole)}  (includes exact)",
    ]
    return Section(title, tuple(lines))


def lines_per_ac_section(data: CalibrationData, scheme: BandScheme) -> Section:
    """The median diff for each acceptance-criteria count."""
    pairs = paired_issues(data)
    rows = lines_by_ac_count(pairs)
    title = (
        f"Median diff lines per AC count — {sum(r.issues for r in rows)} "
        "of those Issues have acceptance criteria"
    )
    if not rows:
        return Section(title, ("no paired Issue has acceptance criteria",))
    lines = ["ACs  Issues  Median lines"]
    lines.extend(
        f"{row.ac_count:>3}  {row.issues:>6}  {row.median_lines:>12.0f}"
        for row in rows
    )
    per_ac = median_lines_per_ac(pairs)
    if per_ac is not None:
        lines.append(f"median lines per AC: {per_ac:.0f}")
    return Section(title, tuple(lines))


SECTIONS: tuple[SectionBuilder, ...] = (
    band_share_section,
    percentile_section,
    estimate_accuracy_section,
    lines_per_ac_section,
)
"""The report, in print order. Add a measure by appending its builder."""


def render_report(
    data: CalibrationData,
    scheme: BandScheme,
    sections: Sequence[SectionBuilder] = SECTIONS,
) -> str:
    """The whole report: a window header, then every section in order."""
    header = (
        f"pr-size --calibrate: {data.since:%Y-%m-%d} to {data.until:%Y-%m-%d}"
    )
    blocks = [header, *(build(data, scheme).render() for build in sections)]
    return "\n\n".join(blocks)
