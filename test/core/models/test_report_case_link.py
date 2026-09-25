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

"""Tests for the reporter-side ``VultronReportCaseLink`` record."""

import pytest

from vultron.core.models.report_case_link import VultronReportCaseLink

_REPORT_ID = "https://example.org/reports/r1"
_VENDOR_ID = "https://example.org/actors/vendor"
_COORDINATOR_ID = "https://example.org/actors/coordinator"


@pytest.mark.xfail(
    strict=True,
    reason=(
        "CBT-06-002: the link id is derived from the report alone, so a "
        "second recipient of the same report collides with the first. "
        "Tracked by TASK_PLACEHOLDER."
    ),
)
@pytest.mark.spec("CBT-06-002")
def test_links_for_two_recipients_of_one_report_are_distinct_records():
    """One report offered to two recipients needs one link per recipient."""
    to_vendor = VultronReportCaseLink(
        report_id=_REPORT_ID, trusted_case_creator_id=_VENDOR_ID
    )
    to_coordinator = VultronReportCaseLink(
        report_id=_REPORT_ID, trusted_case_creator_id=_COORDINATOR_ID
    )
    assert to_vendor.id_ != to_coordinator.id_
