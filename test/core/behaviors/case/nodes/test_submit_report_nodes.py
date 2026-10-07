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
"""Node-level tests for the received ``Offer(Report)`` effect nodes (#3872)."""

import pytest
from py_trees.common import Status

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.case.nodes.submit_report import (
    CheckOfferAddressedToReceiverNode,
    StoreSubmitReportOfferRecordNode,
)
from vultron.core.models.offer_record import VultronOfferRecord

VENDOR = "https://example.org/actors/vendor"
OFFER = "https://example.org/activities/offer-n1"
REPORT = "https://example.org/reports/r-n1"
FINDER = "https://example.org/users/finder"


def _run(node):
    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=VENDOR)
    result = BTBridge(datalayer=dl).execute_with_setup(node, actor_id=VENDOR)
    return dl, result


def _record_node():
    return StoreSubmitReportOfferRecordNode(
        offer_id=OFFER,
        report_id=REPORT,
        offer_actor_id=FINDER,
        offer_to=[VENDOR],
    )


@pytest.mark.spec("CM-15-001")
def test_offer_record_node_writes_the_record():
    dl, result = _run(_record_node())
    assert result.status == Status.SUCCESS
    record = dl.read(VultronOfferRecord.build_id(OFFER))
    assert isinstance(record, VultronOfferRecord)
    assert record.report_id == REPORT
    assert record.offer_to == [VENDOR]


def test_offer_record_node_is_idempotent():
    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=VENDOR)
    bridge = BTBridge(datalayer=dl)
    for _ in range(2):
        result = bridge.execute_with_setup(_record_node(), actor_id=VENDOR)
        assert result.status == Status.SUCCESS


@pytest.mark.spec("HP-01-005")
@pytest.mark.parametrize(
    ("to", "cc", "status", "reason"),
    [
        ([VENDOR], [], Status.SUCCESS, None),
        ([], [VENDOR], Status.FAILURE, "cc"),
        (
            ["https://example.org/actors/other"],
            [],
            Status.FAILURE,
            "not a recipient",
        ),
    ],
)
def test_addressing_guard(to, cc, status, reason):
    node = CheckOfferAddressedToReceiverNode(to=to, cc=cc, report_id=REPORT)
    _, result = _run(node)
    assert result.status == status
    if reason:
        assert reason in node.feedback_message
