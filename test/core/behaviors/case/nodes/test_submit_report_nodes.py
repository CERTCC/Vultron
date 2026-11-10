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

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from py_trees.common import Status

from test.support.act_runner import run_tree
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.case.nodes.submit_report import (
    CheckOfferNamesReceiverInToNode,
    StoreReportClaimsRecordsNode,
    StoreSubmitReportOfferRecordNode,
)
from vultron.core.models.activity import VultronActivity
from vultron.core.models.offer_record import VultronOfferRecord
from vultron.core.models.report_claims import (
    ClaimsReading,
    ReportClaims,
    ReportClaimsRecord,
    SchemaError,
    SchemaVerdict,
    SkippedClaim,
)

VENDOR = "https://example.org/actors/vendor"
OFFER = "https://example.org/activities/offer-n1"
_AT = datetime(2026, 11, 1, 12, tzinfo=UTC)
REPORT = "https://example.org/reports/r-n1"
FINDER = "https://example.org/users/finder"


def _run(node):
    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=VENDOR)
    result = run_tree(BTBridge(datalayer=dl), node, actor_id=VENDOR)
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
        result = run_tree(bridge, _record_node(), actor_id=VENDOR)
        assert result.status == Status.SUCCESS


def _claims_node() -> StoreReportClaimsRecordsNode:
    reading = ClaimsReading(
        document_id=f"{REPORT}/csaf",
        document_digest="b" * 64,
        document_format="CSAF 2.1",
        schema_verdict=SchemaVerdict.SCHEMA_INVALID,
        schema_errors=[SchemaError(path="$.document.title", message="bad")],
        claims=ReportClaims(document_category="csaf_vulnerability_report"),
        skipped=[SkippedClaim(path="$.document.title", reason="not a string")],
    )
    return StoreReportClaimsRecordsNode(
        report_id=REPORT,
        activity_id=OFFER,
        sender_id=FINDER,
        readings=[reading],
    )


@pytest.mark.spec("CSAF-04-004")
def test_claims_node_stores_one_record_per_reading_and_logs_each_skip(caplog):
    actor = f"{VENDOR}/{uuid.uuid4()}"  # a store no other test has written
    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=actor)
    with caplog.at_level("INFO"):
        result = BTBridge(datalayer=dl).execute_with_setup(
            _claims_node(), actor_id=actor, at=_AT
        )

    assert result.status == Status.SUCCESS
    record = dl.read(ReportClaimsRecord.build_id(REPORT, "b" * 64))
    assert isinstance(record, ReportClaimsRecord)
    assert record.activity_id == OFFER
    assert record.received_at == _AT, "the act's instant, never a clock read"
    assert record.reading.schema_verdict is SchemaVerdict.SCHEMA_INVALID
    [skip] = [r for r in caplog.records if "(CSAF-04-003)" in r.getMessage()]
    assert skip.levelname == "INFO"
    assert OFFER in skip.getMessage() and FINDER in skip.getMessage()


def test_claims_node_keeps_a_record_it_already_holds(caplog):
    # A store of its own: in-memory stores are shared per actor id, and a
    # record another test left behind would make the first run a no-op.
    actor = f"{VENDOR}/{uuid.uuid4()}"
    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=actor)
    bridge = BTBridge(datalayer=dl)
    bridge.execute_with_setup(_claims_node(), actor_id=actor, at=_AT)
    first = dl.list_objects("ReportClaimsRecord")
    assert len(first) == 1

    with caplog.at_level("INFO"):
        result = bridge.execute_with_setup(
            _claims_node(), actor_id=actor, at=_AT
        )

    assert result.status == Status.SUCCESS
    assert dl.list_objects("ReportClaimsRecord") == first
    assert not [r for r in caplog.records if "(CSAF-04-003)" in r.getMessage()]


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
    result = run_tree(
        BTBridge(datalayer=dl),
        node,
        actor_id=VENDOR,
        activity=_offer_event(to, sender=VENDOR),
    )
    assert result.status == status
    assert node.not_named_in_to is (status is Status.FAILURE)
    if status is Status.FAILURE:
        assert "not eligible to create a case" in node.feedback_message
        assert "HP-09-001" in node.feedback_message


def test_eligibility_without_a_received_event_is_not_a_decline(caplog):
    """No event on the blackboard is a wiring fault, never a decline."""
    node = CheckOfferNamesReceiverInToNode()
    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=VENDOR)
    with caplog.at_level("ERROR"):
        result = run_tree(BTBridge(datalayer=dl), node, actor_id=VENDOR)
    assert result.status == Status.FAILURE
    assert node.not_named_in_to is False
    assert "no received event" in node.feedback_message
    assert any(
        r.levelname == "ERROR" and "no received event" in r.getMessage()
        for r in caplog.records
    )


def test_eligibility_wiring_fault_is_not_a_decline():
    """A missing DataLayer fails the node without reading as a decline,
    even when an earlier tick of the same node declined."""
    node = CheckOfferNamesReceiverInToNode()
    node.not_named_in_to = True
    assert node.update() is Status.FAILURE
    assert node.not_named_in_to is False
