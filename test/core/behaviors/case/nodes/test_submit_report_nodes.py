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
"""Node-level tests for the received ``Offer(VulnerabilityReport)`` effect nodes.

Issue #3872.
"""

from types import SimpleNamespace

import pytest
from py_trees.common import Status

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.case.nodes.submit_report import (
    CheckOfferNamesReceiverInToNode,
    StoreSubmitReportOfferRecordNode,
)
from vultron.core.models.activity import VultronActivity
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


def _offer_event(to: list[str], sender: str = FINDER) -> SimpleNamespace:
    """A received event as the tree sees it: its activity carries ``to``."""
    return SimpleNamespace(
        activity=VultronActivity(id_=OFFER, type_="Offer", actor=sender, to=to)
    )


@pytest.mark.spec("HP-09-001")
@pytest.mark.parametrize(
    ("to", "status"),
    [
        ([VENDOR], Status.SUCCESS),
        # The receiver's own Offer to someone else: the addressee door admits
        # it as the sender's copy, but `to` does not name the receiver.
        (["https://example.org/actors/other"], Status.FAILURE),
        ([], Status.FAILURE),
    ],
    ids=["named-in-to", "own-copy-to-someone-else", "empty-to"],
)
def test_case_creation_eligibility_reads_to_alone(to, status):
    """Eligibility comes from ``to`` only (HP-09-001), off the blackboard."""
    node = CheckOfferNamesReceiverInToNode()
    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=VENDOR)
    result = BTBridge(datalayer=dl).execute_with_setup(
        node, actor_id=VENDOR, activity=_offer_event(to, sender=VENDOR)
    )
    assert result.status == status
    assert node.not_named_in_to is (status is Status.FAILURE)
    if status is Status.FAILURE:
        assert "not eligible to create a case" in node.feedback_message
        assert "HP-09-001" in node.feedback_message


def test_eligibility_wiring_fault_is_not_a_decline():
    """A missing DataLayer fails the node without reading as a decline."""
    node = CheckOfferNamesReceiverInToNode()
    assert node.update() is Status.FAILURE
    assert node.not_named_in_to is False
