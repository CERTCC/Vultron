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
"""Structural theme-fit check over open Issues (``theme-fit``).

Requirements: PAD-01-002, PAD-01-007, PAD-02-008, PAD-02-014, PAD-02-015, PAD-02-017,
PAD-02-018.

The package splits along its seams: :mod:`.fetch` owns the GraphQL query and
response shape, :mod:`.analyze` applies the rules as a pure function,
:mod:`.render` writes the Markdown report body, and :mod:`.cli` wires them.
The theme set comes from ``notes/epic-themes.md`` through
:func:`~vultron.metadata.planning.themes.load_theme_catalog`.
"""

from vultron.metadata.planning.theme_fit.analyze import analyze, nearest_epic
from vultron.metadata.planning.theme_fit.cli import main
from vultron.metadata.planning.theme_fit.fetch import (
    QUERY,
    fetch_open_issues,
    parse_issue,
    parse_pages,
)
from vultron.metadata.planning.theme_fit.model import (
    AUTO_CALVED_MARKER,
    UNSCHEDULED,
    Ancestor,
    Finding,
    FindingKind,
    OpenIssue,
    ThemeFitReport,
    TierCoherence,
)
from vultron.metadata.planning.theme_fit.render import (
    GITHUB_BODY_LIMIT,
    WORD_JOINER,
    render_coherence,
    render_markdown,
)

__all__ = [
    "AUTO_CALVED_MARKER",
    "Ancestor",
    "Finding",
    "GITHUB_BODY_LIMIT",
    "FindingKind",
    "OpenIssue",
    "QUERY",
    "ThemeFitReport",
    "TierCoherence",
    "UNSCHEDULED",
    "WORD_JOINER",
    "analyze",
    "fetch_open_issues",
    "main",
    "nearest_epic",
    "parse_issue",
    "parse_pages",
    "render_coherence",
    "render_markdown",
]
