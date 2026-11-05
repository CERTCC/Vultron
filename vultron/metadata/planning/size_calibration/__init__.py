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
"""``pr-size --calibrate``: re-run the survey the ``size:`` bands rest on.

Requirements: PAD-05-011 (one band table, applied through ``pr-size``).

The bands were cut at quantiles of a one-off survey of merged PRs. This package
recomputes those numbers for any window: each band's share, the diff size at
each cut quantile, how often Issue estimates matched the measured band, and the
median diff per acceptance-criteria count. :mod:`.measures` does the
arithmetic as pure functions, :mod:`.report` lays it out one section per
measure, and :mod:`.fetch` is the thin ``gh`` read. ``size_bands`` wires them
into its CLI and passes its own table in as a :class:`.model.BandScheme`, so
this package never imports it.
"""

from vultron.metadata.planning.size_calibration.fetch import (
    fetch_window,
    parse_search_pages,
)
from vultron.metadata.planning.size_calibration.model import (
    BandScheme,
    CalibrationData,
    ClosedIssue,
    IssuePair,
    MergedPr,
)
from vultron.metadata.planning.size_calibration.report import (
    SECTIONS,
    Section,
    SectionBuilder,
    render_report,
)

__all__ = [
    "SECTIONS",
    "BandScheme",
    "CalibrationData",
    "ClosedIssue",
    "IssuePair",
    "MergedPr",
    "Section",
    "SectionBuilder",
    "fetch_window",
    "parse_search_pages",
    "render_report",
]
