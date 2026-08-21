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

"""Tests for typed-Ports base classes and pilot node migrations.

Covers:
- BTND-03-009: typed port declarations replace register_key().
- BTND-03-010: setup_ports() with remappings wires BTBridge flat keys.
- BTND-03-011: get_input() reads injected values correctly.
- AC-4 (issue #1808): isolated-node port tests + early-error-detection tests.
"""

import pytest
import py_trees
from py_trees.ports import NoDataAvailable

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.behaviors.helpers import (
    DataLayerConditionWithPorts,
    DataLayerActionWithPorts,
)
from vultron.core.behaviors.report.nodes.conditions import (
    CheckRMStateValid,
    CheckRMStateReceivedOrInvalid,
    EnsureEmbargoExists,
    EvaluateReportCredibility,
)
from vultron.core.behaviors.report.nodes.rm_transitions import (
    TransitionRMtoValid,
)
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_actor import VultronCaseActor
from vultron.core.models.dimensions import RmDimension
from vultron.core.models.participant_status import ParticipantStatus
from vultron.core.models.report import VultronReport
from vultron.core.states.rm import RM
from vultron.core.models._helpers import _report_phase_status_id
from test.core.behaviors.bt_harness import BTTestScenario

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

ACTOR_ID = "https://example.org/actors/vendor"
REPORT_ID = "https://example.org/reports/CVE-2024-001"
OFFER_ID = "https://example.org/activities/offer-123"


def _fresh_dl() -> SqliteDataLayer:
    return SqliteDataLayer("sqlite:///:memory:")


def _write_btbridge_keys(
    dl: SqliteDataLayer, actor_id: str = ACTOR_ID
) -> None:
    """Simulate what BTBridge.setup_tree() writes to the flat blackboard."""
    bb = py_trees.blackboard.Client(name="test_setup")
    bb.register_key(key="datalayer", access=py_trees.common.Access.WRITE)
    bb.register_key(key="actor_id", access=py_trees.common.Access.WRITE)
    bb.datalayer = dl
    bb.actor_id = actor_id


# ---------------------------------------------------------------------------
# Base-class contract: DataLayerConditionWithPorts
# ---------------------------------------------------------------------------


class TestDataLayerConditionWithPortsContract:
    """Verify the base class declares required ports and reads via get_input."""

    def test_input_ports_declares_datalayer(self) -> None:
        ports = DataLayerConditionWithPorts.input_ports()
        assert "datalayer" in ports
        assert ports["datalayer"].required

    def test_input_ports_declares_actor_id(self) -> None:
        ports = DataLayerConditionWithPorts.input_ports()
        assert "actor_id" in ports
        assert ports["actor_id"].required

    def test_output_ports_empty(self) -> None:
        assert DataLayerConditionWithPorts.output_ports() == {}

    def test_missing_required_port_raises_at_get_input(self) -> None:
        """NoDataAvailable raised when required port not on blackboard (BTND-03-011)."""
        py_trees.blackboard.Blackboard.storage.clear()

        class _MinimalNode(DataLayerConditionWithPorts):
            def update(self):
                return py_trees.common.Status.SUCCESS

        node = _MinimalNode(name="MinimalTest")
        node.setup_ports()
        with pytest.raises(NoDataAvailable):
            node.get_input("datalayer")

    def test_get_input_reads_btbridge_flat_key(self) -> None:
        """get_input('datalayer') reads the /datalayer key written by BTBridge."""
        py_trees.blackboard.Blackboard.storage.clear()
        dl = _fresh_dl()
        _write_btbridge_keys(dl)

        class _MinimalNodeWithRemapping(DataLayerConditionWithPorts):
            def update(self):
                return py_trees.common.Status.SUCCESS

        node = _MinimalNodeWithRemapping(name="MinimalTest")
        node.setup_ports(
            port_remappings={
                "datalayer": "/datalayer",
                "actor_id": "/actor_id",
            }
        )
        assert node.get_input("datalayer") is dl
        assert node.get_input("actor_id") == ACTOR_ID


# ---------------------------------------------------------------------------
# Base-class contract: DataLayerActionWithPorts
# ---------------------------------------------------------------------------


class TestDataLayerActionWithPortsContract:
    def test_input_ports_declares_trigger_factory(self) -> None:
        ports = DataLayerActionWithPorts.input_ports()
        assert "trigger_activity_factory" in ports
        assert not ports["trigger_activity_factory"].required

    def test_output_ports_empty(self) -> None:
        assert DataLayerActionWithPorts.output_ports() == {}


# ---------------------------------------------------------------------------
# Pilot: CheckRMStateValid
# ---------------------------------------------------------------------------


class TestCheckRMStateValidPorts:
    def test_input_ports_declared(self) -> None:
        ports = CheckRMStateValid.input_ports()
        assert "datalayer" in ports
        assert "actor_id" in ports

    def test_output_ports_empty(self) -> None:
        assert CheckRMStateValid.output_ports() == {}

    def test_missing_datalayer_raises_no_data_available(self) -> None:
        py_trees.blackboard.Blackboard.storage.clear()
        node = CheckRMStateValid(report_id=REPORT_ID)
        node.setup_ports()
        with pytest.raises(NoDataAvailable):
            node.get_input("datalayer")

    def test_via_bt_scenario_when_valid(
        self, bt_scenario: BTTestScenario
    ) -> None:
        actor = VultronCaseActor(id_=ACTOR_ID, name="Vendor")
        report = VultronReport(id_=REPORT_ID, name="R1", content="c")
        status = ParticipantStatus(
            id_=_report_phase_status_id(ACTOR_ID, REPORT_ID, RM.VALID.value),
            context=REPORT_ID,
            attributed_to=ACTOR_ID,
            rm=RmDimension(state=RM.VALID),
        )
        bt_scenario.seed(actor, report, status)
        result = bt_scenario.run(
            CheckRMStateValid(report_id=REPORT_ID), actor_id=ACTOR_ID
        )
        bt_scenario.assert_success(result)

    def test_via_bt_scenario_when_not_valid(
        self, bt_scenario: BTTestScenario
    ) -> None:
        actor = VultronCaseActor(id_=ACTOR_ID, name="Vendor")
        report = VultronReport(id_=REPORT_ID, name="R1", content="c")
        bt_scenario.seed(actor, report)
        result = bt_scenario.run(
            CheckRMStateValid(report_id=REPORT_ID), actor_id=ACTOR_ID
        )
        bt_scenario.assert_failure(result)

    def test_sender_actor_id_checked_instead_of_blackboard_actor(
        self, bt_scenario: BTTestScenario
    ) -> None:
        """sender_actor_id overrides blackboard actor_id (ADR-0022 single-BT)."""
        SENDER_ID = "https://example.org/actors/reporter"
        actor = VultronCaseActor(id_=ACTOR_ID, name="Vendor")
        sender = VultronCaseActor(id_=SENDER_ID, name="Reporter")
        report = VultronReport(id_=REPORT_ID, name="R1", content="c")
        # Only the sender has a VALID status record, not the blackboard actor.
        status = ParticipantStatus(
            id_=_report_phase_status_id(SENDER_ID, REPORT_ID, RM.VALID.value),
            context=REPORT_ID,
            attributed_to=SENDER_ID,
            rm=RmDimension(state=RM.VALID),
        )
        bt_scenario.seed(actor, sender, report, status)
        # Tree runs under ACTOR_ID (blackboard actor_id = ACTOR_ID);
        # node must check SENDER_ID's RM state and return SUCCESS.
        result = bt_scenario.run(
            CheckRMStateValid(report_id=REPORT_ID, sender_actor_id=SENDER_ID),
            actor_id=ACTOR_ID,
        )
        bt_scenario.assert_success(result)


# ---------------------------------------------------------------------------
# Pilot: CheckRMStateReceivedOrInvalid
# ---------------------------------------------------------------------------


class TestCheckRMStateReceivedOrInvalidPorts:
    def test_input_ports_declared(self) -> None:
        ports = CheckRMStateReceivedOrInvalid.input_ports()
        assert "datalayer" in ports
        assert "actor_id" in ports

    def test_missing_datalayer_raises_no_data_available(self) -> None:
        py_trees.blackboard.Blackboard.storage.clear()
        node = CheckRMStateReceivedOrInvalid(report_id=REPORT_ID)
        node.setup_ports()
        with pytest.raises(NoDataAvailable):
            node.get_input("datalayer")

    def test_success_when_no_valid_status(
        self, bt_scenario: BTTestScenario
    ) -> None:
        actor = VultronCaseActor(id_=ACTOR_ID, name="Vendor")
        report = VultronReport(id_=REPORT_ID, name="R1", content="c")
        bt_scenario.seed(actor, report)
        result = bt_scenario.run(
            CheckRMStateReceivedOrInvalid(report_id=REPORT_ID),
            actor_id=ACTOR_ID,
        )
        bt_scenario.assert_success(result)

    def test_failure_when_already_valid(
        self, bt_scenario: BTTestScenario
    ) -> None:
        actor = VultronCaseActor(id_=ACTOR_ID, name="Vendor")
        report = VultronReport(id_=REPORT_ID, name="R1", content="c")
        status = ParticipantStatus(
            id_=_report_phase_status_id(ACTOR_ID, REPORT_ID, RM.VALID.value),
            context=REPORT_ID,
            attributed_to=ACTOR_ID,
            rm=RmDimension(state=RM.VALID),
        )
        bt_scenario.seed(actor, report, status)
        result = bt_scenario.run(
            CheckRMStateReceivedOrInvalid(report_id=REPORT_ID),
            actor_id=ACTOR_ID,
        )
        bt_scenario.assert_failure(result)


# ---------------------------------------------------------------------------
# Pilot: EnsureEmbargoExists
# ---------------------------------------------------------------------------


class TestEnsureEmbargoExistsPorts:
    def test_input_ports_declared(self) -> None:
        ports = EnsureEmbargoExists.input_ports()
        assert "datalayer" in ports
        assert "actor_id" in ports

    def test_missing_datalayer_raises_no_data_available(self) -> None:
        py_trees.blackboard.Blackboard.storage.clear()
        node = EnsureEmbargoExists(report_id=REPORT_ID)
        node.setup_ports()
        with pytest.raises(NoDataAvailable):
            node.get_input("datalayer")

    def test_failure_when_no_case(self, bt_scenario: BTTestScenario) -> None:
        actor = VultronCaseActor(id_=ACTOR_ID, name="Vendor")
        report = VultronReport(id_=REPORT_ID, name="R1", content="c")
        bt_scenario.seed(actor, report)
        result = bt_scenario.run(
            EnsureEmbargoExists(report_id=REPORT_ID), actor_id=ACTOR_ID
        )
        bt_scenario.assert_failure(result)

    def test_success_when_case_has_active_embargo(
        self, bt_scenario: BTTestScenario
    ) -> None:
        actor = VultronCaseActor(id_=ACTOR_ID, name="Vendor")
        report = VultronReport(id_=REPORT_ID, name="R1", content="c")
        # active_embargo is a str | None URI field on VulnerabilityCase
        case = VulnerabilityCase(
            name="Test Case",
            vulnerability_reports=[REPORT_ID],
            attributed_to=ACTOR_ID,
        )
        case.active_embargo = "https://example.org/embargos/em-001"
        bt_scenario.seed(actor, report, case)
        result = bt_scenario.run(
            EnsureEmbargoExists(report_id=REPORT_ID), actor_id=ACTOR_ID
        )
        bt_scenario.assert_success(result)

    def test_failure_when_case_has_no_active_embargo(
        self, bt_scenario: BTTestScenario
    ) -> None:
        actor = VultronCaseActor(id_=ACTOR_ID, name="Vendor")
        report = VultronReport(id_=REPORT_ID, name="R1", content="c")
        case = VulnerabilityCase(
            name="Test Case",
            vulnerability_reports=[REPORT_ID],
            attributed_to=ACTOR_ID,
        )
        # active_embargo defaults to None — no explicit assignment needed
        bt_scenario.seed(actor, report, case)
        result = bt_scenario.run(
            EnsureEmbargoExists(report_id=REPORT_ID), actor_id=ACTOR_ID
        )
        bt_scenario.assert_failure(result)


# ---------------------------------------------------------------------------
# Pilot: TransitionRMtoValid
# ---------------------------------------------------------------------------


class TestTransitionRMtoValidPorts:
    def test_input_ports_declared(self) -> None:
        ports = TransitionRMtoValid.input_ports()
        assert "datalayer" in ports
        assert "actor_id" in ports
        assert "trigger_activity_factory" in ports

    def test_output_ports_empty(self) -> None:
        assert TransitionRMtoValid.output_ports() == {}

    def test_missing_datalayer_raises_no_data_available(self) -> None:
        py_trees.blackboard.Blackboard.storage.clear()
        node = TransitionRMtoValid(report_id=REPORT_ID, offer_id=OFFER_ID)
        node.setup_ports()
        with pytest.raises(NoDataAvailable):
            node.get_input("datalayer")

    def test_creates_rm_valid_status_record(
        self, bt_scenario: BTTestScenario
    ) -> None:
        from vultron.core.models.activity import VultronOffer

        actor = VultronCaseActor(id_=ACTOR_ID, name="Vendor")
        report = VultronReport(id_=REPORT_ID, name="R1", content="c")
        offer = VultronOffer(
            id_=OFFER_ID, actor=ACTOR_ID, object_=REPORT_ID, target=ACTOR_ID
        )
        case = VulnerabilityCase(
            name="Test Case",
            vulnerability_reports=[REPORT_ID],
            attributed_to=ACTOR_ID,
        )
        bt_scenario.seed(actor, report, offer, case)
        result = bt_scenario.run(
            TransitionRMtoValid(report_id=REPORT_ID, offer_id=OFFER_ID),
            actor_id=ACTOR_ID,
        )
        bt_scenario.assert_success(result)
        bt_scenario.assert_rm_state(REPORT_ID, RM.VALID, actor_id=ACTOR_ID)

    def test_failure_when_datalayer_not_available(self) -> None:
        """_require_datalayer() guard returns FAILURE when datalayer is None."""
        py_trees.blackboard.Blackboard.storage.clear()
        node = TransitionRMtoValid(report_id=REPORT_ID, offer_id=OFFER_ID)
        # setup_ports() with no remappings → ports namespace keys; blackboard empty
        node.setup_ports()
        # initialise() would raise NoDataAvailable; set datalayer=None manually
        # to test the _require_datalayer() guard path directly.
        node.datalayer = None
        node.actor_id = ACTOR_ID
        from py_trees.common import Status

        result = node.update()
        assert result == Status.FAILURE


# ---------------------------------------------------------------------------
# AC-4 (issue #1884): isolated-port NoDataAvailable tests for newly migrated
# report-domain nodes.
# ---------------------------------------------------------------------------


class TestEvaluateReportCredibilityPorts:
    """EvaluateReportCredibility — Type-A migration NoDataAvailable tests."""

    def test_missing_datalayer_raises_no_data_available(self) -> None:
        """BTND-03-011: get_input('datalayer') raises NoDataAvailable when absent."""
        node = EvaluateReportCredibility(report_id=REPORT_ID)
        node.setup_ports()
        with pytest.raises(NoDataAvailable):
            node.get_input("datalayer")
