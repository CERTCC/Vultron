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
"""The receiver's conversion and marking nodes fail on what they lack.

``ConvertReportToCaseProposalNode`` fails, and so nothing is sent, when the
CaseActor service is not configured or the report is not held
(CP-01-026).  ``MarkProposedClaimsNode`` fails when the report or the
claims record it marks is not held, or the record cannot take the outcomes,
and changes nothing when no reading filled the proposal (CSAF-04-004).
"""

from datetime import UTC, datetime

import pytest
from py_trees.common import Status

from test.support.act_runner import run_tree
from vultron.config.app import reload_config
from vultron.core.behaviors.act_key_scope import with_act_keys
from vultron.core.behaviors.act_keys import REPORT_ID
from vultron.core.behaviors.case.nodes import (
    ConvertReportToCaseProposalNode,
    MarkProposedClaimsNode,
)
from vultron.core.models.report_claims import (
    ClaimsReading,
    ReportClaims,
    ReportClaimsRecord,
    SchemaVerdict,
)

_URL_ENV = "VULTRON_ACTOR__CASE_ACTOR_SERVICE_URL"


@pytest.fixture
def case_actor_url(monkeypatch):
    monkeypatch.setenv(_URL_ENV, "http://case-actor:7999/api/v2")
    reload_config()
    yield
    monkeypatch.undo()
    reload_config()


def _reading(report_id: str) -> ClaimsReading:
    return ClaimsReading(
        document_id=f"{report_id}/csaf",
        document_digest="c" * 64,
        document_format="CSAF 2.1",
        schema_verdict=SchemaVerdict.SCHEMA_VALID,
        claims=ReportClaims(
            document_category="csaf_vulnerability_report", name="Title"
        ),
    )


def _convert(bridge, actor_id, report_id, readings=(), node_type=None):
    node = (node_type or ConvertReportToCaseProposalNode)(readings=readings)
    result = run_tree(
        bridge,
        tree=with_act_keys(node, {REPORT_ID: report_id}),
        actor_id=actor_id,
    )
    return result, node


@pytest.mark.spec("CP-04-005")
def test_no_case_actor_service_is_a_fault(
    monkeypatch, bridge, datalayer, actor, report
):
    monkeypatch.delenv(_URL_ENV, raising=False)
    reload_config()
    try:
        result, node = _convert(bridge, actor.id_, report.id_)
    finally:
        monkeypatch.undo()
        reload_config()

    assert result.status is Status.FAILURE
    assert "case_actor_service_url" in node.feedback_message


@pytest.mark.spec("CP-01-004")
def test_a_report_not_held_is_a_fault(case_actor_url, bridge, actor):
    result, node = _convert(
        bridge, actor.id_, "https://example.org/reports/not-held"
    )

    assert result.status is Status.FAILURE
    assert "CP-01-004" in node.feedback_message
    assert "not found" in node.feedback_message


@pytest.mark.spec("CSAF-04-004")
def test_a_claims_record_not_held_is_a_fault(bridge, datalayer, actor, report):
    """The effects that keep the report write the record first, so its
    absence is a fault: the node runs after the send, so the proposal
    stays queued and the record is left unmarked."""
    result, node = _convert(
        bridge,
        actor.id_,
        report.id_,
        readings=[_reading(report.id_)],
        node_type=MarkProposedClaimsNode,
    )

    assert result.status is Status.FAILURE
    assert "CSAF-04-004" in node.feedback_message
    assert list(datalayer.list_objects("ReportClaimsRecord")) == []


@pytest.mark.spec("CSAF-04-004")
def test_no_filling_reading_marks_nothing(bridge, datalayer, actor, report):
    other = _reading(report.id_).model_copy(
        update={
            "claims": ReportClaims(document_category="csaf_security_advisory")
        }
    )

    result, _ = _convert(
        bridge,
        actor.id_,
        report.id_,
        readings=[other],
        node_type=MarkProposedClaimsNode,
    )

    assert result.status is Status.SUCCESS
    assert list(datalayer.list_objects("ReportClaimsRecord")) == []


@pytest.mark.spec("CSAF-04-004")
def test_a_report_not_held_at_marking_is_a_fault(bridge, datalayer, actor):
    report_id = "https://example.org/reports/not-held"

    result, node = _convert(
        bridge,
        actor.id_,
        report_id,
        readings=[_reading(report_id)],
        node_type=MarkProposedClaimsNode,
    )

    assert result.status is Status.FAILURE
    assert "not found" in node.feedback_message
    assert list(datalayer.list_objects("ReportClaimsRecord")) == []


@pytest.mark.spec("CSAF-04-004")
def test_a_record_that_cannot_take_the_outcomes_is_a_fault(
    bridge, datalayer, actor, report
):
    """A record whose reading claimed no ``name`` cannot mark one, so the
    node fails and leaves the record as it was."""
    reading = _reading(report.id_)
    held = ReportClaimsRecord(
        report_id=report.id_,
        activity_id="https://example.org/activities/offer-1",
        received_at=datetime(2026, 11, 1, tzinfo=UTC),
        reading=reading.model_copy(
            update={
                "claims": ReportClaims(
                    document_category="csaf_vulnerability_report"
                )
            }
        ),
    )
    datalayer.create(held)

    result, node = _convert(
        bridge,
        actor.id_,
        report.id_,
        readings=[reading],
        node_type=MarkProposedClaimsNode,
    )

    assert result.status is Status.FAILURE
    assert "name no value the document claimed" in node.feedback_message
    assert datalayer.read(held.id_) == held
