#!/usr/bin/env python

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

"""Tests for WritePrologueLedgerEntriesNode (Issue #1688)."""

import py_trees
import pytest
from py_trees.common import Status

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.case.nodes.prologue import (
    WritePrologueLedgerEntriesNode,
    _build_add_case_status_snapshot,
    _build_add_participant_status_snapshot,
    _build_add_report_to_case_snapshot,
    _build_create_case_snapshot,
    _build_submit_report_snapshot,
    _find_offer_record_for_report,
    _obj_to_inline_dict,
)
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.case_status import CaseStatus
from vultron.core.models.offer_record import VultronOfferRecord
from vultron.core.models.report import VulnerabilityReport
from vultron.core.models.vultron_types import VultronCaseActor
from vultron.wire.as2.vocab.objects.vulnerability_case import (  # noqa: F401
    as_VulnerabilityCase,
)

VENDOR_ID = "https://example.org/actors/vendor"
CASE_ACTOR_ID = "https://example.org/actors/case-actor"
CASE_ID = "https://example.org/cases/urn:uuid:prologue-test"
REPORT_ID = "https://example.org/reports/urn:uuid:report-1"
OFFER_ID = "https://example.org/activities/urn:uuid:offer-1"
REPORTER_ID = "https://example.org/actors/reporter"


@pytest.fixture(autouse=True)
def clear_blackboard():
    py_trees.blackboard.Blackboard.storage.clear()
    yield
    py_trees.blackboard.Blackboard.storage.clear()


@pytest.fixture
def dl():
    return SqliteDataLayer("sqlite:///:memory:")


@pytest.fixture
def vendor_actor(dl):
    actor = VultronCaseActor(id_=VENDOR_ID, name="Vendor Co")
    dl.create(actor)
    return actor


@pytest.fixture
def case_actor(dl):
    actor = VultronCaseActor(id_=CASE_ACTOR_ID, name="Case Actor")
    dl.create(actor)
    return actor


@pytest.fixture
def report(dl):
    r = VulnerabilityReport(id_=REPORT_ID, name="Test Report")
    dl.create(r)
    return r


@pytest.fixture
def case(dl, vendor_actor, report):
    c = VulnerabilityCase(
        id_=CASE_ID, attributed_to=VENDOR_ID, name="Prologue Test Case"
    )
    c.vulnerability_reports.append(REPORT_ID)
    dl.save(c)
    return c


@pytest.fixture
def offer_record(dl, report):
    rec = VultronOfferRecord(
        offer_id=OFFER_ID,
        report_id=REPORT_ID,
        offer_actor_id=REPORTER_ID,
        offer_to=[VENDOR_ID],
    )
    dl.save(rec)
    return rec


@pytest.fixture
def participant(dl, case):
    p = CaseParticipant(
        id_=f"{CASE_ID}/participants/vendor",
        attributed_to=VENDOR_ID,
        context=CASE_ID,
        name="Vendor participant",
    )
    dl.create(p)
    return p


@pytest.fixture
def full_case(dl, case, participant):
    """Case with participant attached."""
    raw = dl.read(CASE_ID)
    assert isinstance(raw, VulnerabilityCase)
    raw.add_participant(participant)
    dl.save(raw)
    return raw


# ---------------------------------------------------------------------------
# Unit tests: helper functions
# ---------------------------------------------------------------------------


class TestHelpers:
    def test_obj_to_inline_dict_pydantic(self, report):
        result = _obj_to_inline_dict(report)
        assert isinstance(result, dict)
        assert result.get("type") == "VulnerabilityReport"
        assert result.get("id") == REPORT_ID

    def test_obj_to_inline_dict_dict(self):
        d = {"foo": "bar"}
        assert _obj_to_inline_dict(d) == {"foo": "bar"}

    def test_obj_to_inline_dict_none(self):
        assert _obj_to_inline_dict(None) == {}

    def test_find_offer_record_for_report_found(self, dl, offer_record):
        result = _find_offer_record_for_report(dl, REPORT_ID)
        assert isinstance(result, VultronOfferRecord)
        assert result.offer_id == OFFER_ID

    def test_find_offer_record_for_report_not_found(self, dl):
        result = _find_offer_record_for_report(dl, "https://no-such-report")
        assert result is None

    def test_build_submit_report_snapshot(self, offer_record, report):
        snap = _build_submit_report_snapshot(
            offer_record, report, VENDOR_ID, CASE_ID
        )
        assert snap["type"] == "Offer"
        assert snap["actor"] == REPORTER_ID
        assert isinstance(snap["object"], dict)
        assert snap["object"]["type"] == "VulnerabilityReport"
        assert snap["context"] == CASE_ID

    def test_build_create_case_snapshot(self, case):
        snap = _build_create_case_snapshot(case, VENDOR_ID, CASE_ID)
        assert snap["type"] == "Create"
        assert snap["actor"] == VENDOR_ID
        assert isinstance(snap["object"], dict)
        assert snap["object"]["type"] == "VulnerabilityCase"
        assert snap["context"] == CASE_ID

    def test_build_add_report_to_case_snapshot(self, report, case):
        snap = _build_add_report_to_case_snapshot(
            report, case, VENDOR_ID, CASE_ID
        )
        assert snap["type"] == "Add"
        assert snap["actor"] == VENDOR_ID
        assert snap["object"]["type"] == "VulnerabilityReport"
        assert snap["target"]["type"] == "VulnerabilityCase"
        assert snap["context"] == CASE_ID

    def test_build_add_participant_status_snapshot(self, participant):
        status = participant.participant_statuses[0]
        snap = _build_add_participant_status_snapshot(
            status, participant, VENDOR_ID, CASE_ID
        )
        assert snap["type"] == "Add"
        assert snap["actor"] == VENDOR_ID
        assert snap["object"]["type"] == "ParticipantStatus"
        assert snap["target"]["type"] == "CaseParticipant"
        assert snap["context"] == CASE_ID

    def test_build_add_case_status_snapshot(self, case):
        raw_status = case.case_statuses[0]
        assert isinstance(raw_status, CaseStatus)
        snap = _build_add_case_status_snapshot(
            raw_status, case, VENDOR_ID, CASE_ID
        )
        assert snap["type"] == "Add"
        assert snap["actor"] == VENDOR_ID
        assert snap["object"]["type"] == "CaseStatus"
        assert snap["target"]["type"] == "VulnerabilityCase"
        assert snap["context"] == CASE_ID


# ---------------------------------------------------------------------------
# Unit tests: WritePrologueLedgerEntriesNode
# ---------------------------------------------------------------------------


class TestWritePrologueLedgerEntriesNode:
    def test_succeeds_when_case_not_found(self, dl, case_actor):
        """Best-effort: node succeeds with warning when case is not in DataLayer."""
        node = WritePrologueLedgerEntriesNode(
            case_id="https://no-such-case",
            vendor_id=VENDOR_ID,
        )
        bridge = BTBridge(datalayer=dl)
        result = bridge.execute_with_setup(
            tree=node,
            actor_id=CASE_ACTOR_ID,
        )
        assert result.status == Status.SUCCESS

    def test_succeeds_with_minimal_case_no_reports(self, dl, case_actor):
        """Succeeds when case has no reports or participants."""
        c = VulnerabilityCase(
            id_=CASE_ID, attributed_to=VENDOR_ID, name="Empty Case"
        )
        dl.save(c)

        node = WritePrologueLedgerEntriesNode(
            case_id=CASE_ID,
            vendor_id=VENDOR_ID,
        )
        bridge = BTBridge(datalayer=dl)
        result = bridge.execute_with_setup(
            tree=node,
            actor_id=CASE_ACTOR_ID,
        )
        assert result.status == Status.SUCCESS

    def test_commits_prologue_entries_for_full_case(
        self, dl, case_actor, full_case, report, offer_record
    ):
        """All prologue entries are committed for a well-populated case."""
        node = WritePrologueLedgerEntriesNode(
            case_id=CASE_ID,
            vendor_id=VENDOR_ID,
        )
        bridge = BTBridge(datalayer=dl)
        result = bridge.execute_with_setup(
            tree=node,
            actor_id=CASE_ACTOR_ID,
        )
        assert result.status == Status.SUCCESS

        entries = list(dl.list_objects("CaseLedgerEntry"))
        event_types = {getattr(e, "event_type", None) for e in entries}
        assert "submit_report" in event_types
        assert "create_case" in event_types
        assert "add_report_to_case" in event_types
        assert "add_participant_status_to_participant" in event_types
        assert "add_case_status_to_case" in event_types

    def test_idempotent_second_run_succeeds(
        self, dl, case_actor, full_case, report, offer_record
    ):
        """Running the node twice commits no duplicate entries."""
        node1 = WritePrologueLedgerEntriesNode(
            case_id=CASE_ID,
            vendor_id=VENDOR_ID,
        )
        bridge = BTBridge(datalayer=dl)
        bridge.execute_with_setup(tree=node1, actor_id=CASE_ACTOR_ID)

        entries_after_first = list(dl.list_objects("CaseLedgerEntry"))

        node2 = WritePrologueLedgerEntriesNode(
            case_id=CASE_ID,
            vendor_id=VENDOR_ID,
        )
        result = bridge.execute_with_setup(tree=node2, actor_id=CASE_ACTOR_ID)
        assert result.status == Status.SUCCESS

        entries_after_second = list(dl.list_objects("CaseLedgerEntry"))
        assert len(entries_after_first) == len(entries_after_second)

    def test_best_effort_submit_report_without_offer_record(
        self, dl, case_actor, full_case, report
    ):
        """Succeeds with synthetic submit_report entry when no OfferRecord found."""
        node = WritePrologueLedgerEntriesNode(
            case_id=CASE_ID,
            vendor_id=VENDOR_ID,
        )
        bridge = BTBridge(datalayer=dl)
        result = bridge.execute_with_setup(
            tree=node,
            actor_id=CASE_ACTOR_ID,
        )
        assert result.status == Status.SUCCESS

        entries = list(dl.list_objects("CaseLedgerEntry"))
        event_types = {getattr(e, "event_type", None) for e in entries}
        assert "submit_report" in event_types
