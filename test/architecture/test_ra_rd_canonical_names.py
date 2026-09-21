"""Regression: RA and RD must use 'Report/Case Accepted' / 'Report/Case Deferred' in key reference docs.

The spec entries MSM-01-004 and MSM-01-005 use the case-qualified names because
engaging/deferring is a case-participation decision (`Join`/`Ignore` VulnerabilityCase),
not a report-validity judgment.  Every key reference page must agree.

See: GitHub issue #3467.
"""

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

from pathlib import Path

import pytest

_REPO = Path(__file__).parents[2]

_KEY_REFS = [
    _REPO / "docs/reference/formal_protocol/messages.md",
    _REPO / "docs/reference/quick_reference.md",
    _REPO / "docs/reference/glossary.md",
    _REPO / "docs/_acronyms/index.md",
]


@pytest.mark.parametrize("path", _KEY_REFS, ids=lambda p: p.name)
def test_ra_name_is_report_case_accepted(path: Path) -> None:
    assert "Report/Case Accepted" in path.read_text(), (
        f"{path.relative_to(_REPO)}: RA must be named 'Report/Case Accepted' "
        "(MSM-01-005 — acceptance is a case-participation decision)"
    )


@pytest.mark.parametrize("path", _KEY_REFS, ids=lambda p: p.name)
def test_rd_name_is_report_case_deferred(path: Path) -> None:
    assert "Report/Case Deferred" in path.read_text(), (
        f"{path.relative_to(_REPO)}: RD must be named 'Report/Case Deferred' "
        "(MSM-01-004 — deferral is a case-participation decision)"
    )
