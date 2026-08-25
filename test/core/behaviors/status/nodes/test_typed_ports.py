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

"""Typed-Ports isolation tests for status domain nodes (AC-4, issue #1883).

Covers BTND-03-011 (NoDataAvailable on missing required port) and happy-path
execution via BTTestScenario for one representative node per status sub-module.
"""

import pytest
from py_trees.ports import NoDataAvailable

from vultron.core.behaviors.status.nodes.case_status import (
    CheckCaseStatusIdempotencyNode,
)
from vultron.core.behaviors.status.nodes.conditions import (
    AllParticipantsRMClosedConditionNode,
)
from vultron.core.behaviors.status.nodes.lifecycle import (
    EmitCloseCaseNode,
    _PublicDisclosureSkipConditionNode,
)
from vultron.core.behaviors.status.nodes.rm_anomaly import EmitRMGapNoteNode
from vultron.core.behaviors.status.nodes.threat_termination import (
    _ThreatTerminationSkipConditionNode,
)
from vultron.core.models.case import VulnerabilityCase
from test.core.behaviors.bt_harness import BTTestScenario

ACTOR_ID = "https://example.org/actors/vendor"
CASE_ID = "https://example.org/cases/case-001"
STATUS_ID = "https://example.org/statuses/status-001"


# ---------------------------------------------------------------------------
# case_status.py — CheckCaseStatusIdempotencyNode
# ---------------------------------------------------------------------------


class TestCheckCaseStatusIdempotencyNodePorts:
    def test_missing_datalayer_raises_no_data_available(self) -> None:
        node = CheckCaseStatusIdempotencyNode(
            case_id=CASE_ID, status_id=STATUS_ID
        )
        node.setup_ports()
        with pytest.raises(NoDataAvailable):
            node.get_input("datalayer")

    def test_success_when_status_not_yet_present(
        self, bt_scenario: BTTestScenario
    ) -> None:
        case = VulnerabilityCase(
            id_=CASE_ID,
            name="Test Case",
            attributed_to=ACTOR_ID,
        )
        bt_scenario.seed(case)
        result = bt_scenario.run(
            CheckCaseStatusIdempotencyNode(
                case_id=CASE_ID, status_id=STATUS_ID
            ),
            actor_id=ACTOR_ID,
        )
        bt_scenario.assert_success(result)


# ---------------------------------------------------------------------------
# conditions.py — AllParticipantsRMClosedConditionNode
# ---------------------------------------------------------------------------


class TestAllParticipantsRMClosedConditionNodePorts:
    def test_missing_datalayer_raises_no_data_available(self) -> None:
        node = AllParticipantsRMClosedConditionNode(case_id=CASE_ID)
        node.setup_ports()
        with pytest.raises(NoDataAvailable):
            node.get_input("datalayer")

    def test_failure_when_no_participants(
        self, bt_scenario: BTTestScenario
    ) -> None:
        case = VulnerabilityCase(
            id_=CASE_ID,
            name="Test Case",
            attributed_to=ACTOR_ID,
        )
        bt_scenario.seed(case)
        result = bt_scenario.run(
            AllParticipantsRMClosedConditionNode(case_id=CASE_ID),
            actor_id=ACTOR_ID,
        )
        bt_scenario.assert_failure(result)


# ---------------------------------------------------------------------------
# lifecycle.py — _PublicDisclosureSkipConditionNode
# ---------------------------------------------------------------------------


class TestPublicDisclosureSkipConditionNodePorts:
    def test_missing_datalayer_raises_no_data_available(self) -> None:
        node = _PublicDisclosureSkipConditionNode(
            status_obj=None,
            sender_actor_id=ACTOR_ID,
            case_id=CASE_ID,
        )
        node.setup_ports()
        with pytest.raises(NoDataAvailable):
            node.get_input("datalayer")

    def test_success_skip_when_no_public_aware_status(
        self, bt_scenario: BTTestScenario
    ) -> None:
        """Non-public-aware status -> skip condition returns SUCCESS."""
        result = bt_scenario.run(
            _PublicDisclosureSkipConditionNode(
                status_obj=None,
                sender_actor_id=ACTOR_ID,
                case_id=CASE_ID,
            ),
            actor_id=ACTOR_ID,
        )
        bt_scenario.assert_success(result)


# ---------------------------------------------------------------------------
# threat_termination.py — _ThreatTerminationSkipConditionNode
# ---------------------------------------------------------------------------


class TestThreatTerminationSkipConditionNodePorts:
    def test_missing_datalayer_raises_no_data_available(self) -> None:
        node = _ThreatTerminationSkipConditionNode(
            status_obj=None,
            case_id=CASE_ID,
        )
        node.setup_ports()
        with pytest.raises(NoDataAvailable):
            node.get_input("datalayer")

    def test_success_skip_when_no_threat(
        self, bt_scenario: BTTestScenario
    ) -> None:
        """No threat in status -> skip returns SUCCESS."""
        result = bt_scenario.run(
            _ThreatTerminationSkipConditionNode(
                status_obj=None,
                case_id=CASE_ID,
            ),
            actor_id=ACTOR_ID,
        )
        bt_scenario.assert_success(result)


# ---------------------------------------------------------------------------
# lifecycle.py — EmitCloseCaseNode
# ---------------------------------------------------------------------------


class TestEmitCloseCaseNodePorts:
    def test_missing_datalayer_raises_no_data_available(self) -> None:
        node = EmitCloseCaseNode(case_id=CASE_ID)
        node.setup_ports()
        with pytest.raises(NoDataAvailable):
            node.get_input("datalayer")

    def test_success_when_factory_absent(
        self, bt_scenario: BTTestScenario
    ) -> None:
        result = bt_scenario.run(
            EmitCloseCaseNode(case_id=CASE_ID), actor_id=ACTOR_ID
        )
        bt_scenario.assert_success(result)


# ---------------------------------------------------------------------------
# rm_anomaly.py — EmitRMGapNoteNode
# ---------------------------------------------------------------------------


class TestEmitRMGapNoteNodePorts:
    def test_missing_datalayer_raises_no_data_available(self) -> None:
        node = EmitRMGapNoteNode(sender_actor_id=ACTOR_ID, case_id=CASE_ID)
        node.setup_ports()
        with pytest.raises(NoDataAvailable):
            node.get_input("datalayer")

    def test_success_when_no_case_id(
        self, bt_scenario: BTTestScenario
    ) -> None:
        result = bt_scenario.run(
            EmitRMGapNoteNode(sender_actor_id=ACTOR_ID, case_id=None),
            actor_id=ACTOR_ID,
        )
        bt_scenario.assert_success(result)
