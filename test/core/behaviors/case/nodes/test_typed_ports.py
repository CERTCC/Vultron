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

"""Typed-Ports isolation tests for case domain nodes (AC-4, issue #1883).

Covers BTND-03-011 (NoDataAvailable on missing required port) and happy-path
execution via BTTestScenario for one representative node per case sub-module.

Note: TestCheckCaseAlreadyExistsPorts, TestCollectCaseAddresseesNodeOutputPorts,
and TestCreateAndPersistCaseActivityNodeOutputPorts were removed in issue #4353
because the nodes they tested (CheckCaseAlreadyExists, CollectCaseAddresseesNode,
CreateAndPersistCaseActivityNode) were orphaned by create_create_case_tree's
removal and have been deleted.
"""

import pytest
from py_trees.ports import NoDataAvailable

from test.core.behaviors.bt_harness import BTTestScenario
from vultron.core.behaviors.case.nodes.embargo import (
    InitializeCreationEmbargoNode,
)
from vultron.core.behaviors.case.nodes.suggest_actor.conditions import (
    ActorAlreadyParticipantNode,
)
from vultron.core.behaviors.case.nodes.update import (
    BroadcastCaseUpdateNode,
)
from vultron.core.behaviors.case.nodes.vfd_role_guards import (
    CheckVendorRoleNode,
)
from vultron.core.models.case import VulnerabilityCase

ACTOR_ID = "https://example.org/actors/vendor"
CASE_ID = "https://example.org/cases/case-001"
PARTICIPANT_ID = "https://example.org/participants/p-001"


# ---------------------------------------------------------------------------
# vfd_role_guards.py — CheckVendorRoleNode
# ---------------------------------------------------------------------------


class TestCheckVendorRoleNodePorts:
    def test_missing_datalayer_raises_no_data_available(self) -> None:
        node = CheckVendorRoleNode(case_id=CASE_ID, actor_id=ACTOR_ID)
        node.setup_ports()
        with pytest.raises(NoDataAvailable):
            node.get_input("datalayer")

    def test_failure_when_case_not_found(
        self, bt_scenario: BTTestScenario
    ) -> None:
        result = bt_scenario.run(
            CheckVendorRoleNode(case_id=CASE_ID, actor_id=ACTOR_ID),
            actor_id=ACTOR_ID,
        )
        bt_scenario.assert_failure(result)


# ---------------------------------------------------------------------------
# suggest_actor/conditions.py — ActorAlreadyParticipantNode
# ---------------------------------------------------------------------------


class TestActorAlreadyParticipantNodePorts:
    def test_missing_datalayer_raises_no_data_available(self) -> None:
        node = ActorAlreadyParticipantNode(
            recommended_id=ACTOR_ID, case_id=CASE_ID
        )
        node.setup_ports()
        with pytest.raises(NoDataAvailable):
            node.get_input("datalayer")

    def test_failure_when_actor_not_participant(
        self, bt_scenario: BTTestScenario
    ) -> None:
        case = VulnerabilityCase(
            id_=CASE_ID,
            name="Test Case",
            attributed_to=ACTOR_ID,
        )
        bt_scenario.seed(case)
        result = bt_scenario.run(
            ActorAlreadyParticipantNode(
                recommended_id=ACTOR_ID, case_id=CASE_ID
            ),
            actor_id=ACTOR_ID,
        )
        bt_scenario.assert_failure(result)


# ---------------------------------------------------------------------------
# embargo.py — InitializeCreationEmbargoNode
# ---------------------------------------------------------------------------


class TestInitializeCreationEmbargoNodePorts:
    def test_missing_datalayer_raises_no_data_available(self) -> None:
        node = InitializeCreationEmbargoNode()
        node.setup_ports()
        with pytest.raises(NoDataAvailable):
            node.get_input("datalayer")

    def test_missing_case_id_raises_no_data_available(self) -> None:
        node = InitializeCreationEmbargoNode()
        node.setup_ports()
        with pytest.raises(NoDataAvailable):
            node.get_input("case_id")

    def test_missing_default_embargo_raises_no_data_available(
        self,
    ) -> None:
        node = InitializeCreationEmbargoNode()
        node.setup_ports()
        with pytest.raises(NoDataAvailable):
            node.get_input("default_embargo")


# ---------------------------------------------------------------------------
# update.py — BroadcastCaseUpdateNode
# ---------------------------------------------------------------------------


class TestBroadcastCaseUpdateNodePorts:
    def test_missing_datalayer_raises_no_data_available(self) -> None:
        node = BroadcastCaseUpdateNode(case_id=CASE_ID)
        node.setup_ports()
        with pytest.raises(NoDataAvailable):
            node.get_input("datalayer")

    def test_missing_excluded_actor_ids_raises_no_data_available(
        self,
    ) -> None:
        node = BroadcastCaseUpdateNode(case_id=CASE_ID)
        node.setup_ports()
        with pytest.raises(NoDataAvailable):
            node.get_input("excluded_actor_ids")

    def test_failure_when_case_absent(
        self, bt_scenario: BTTestScenario
    ) -> None:
        # Supply excluded_actor_ids so the tick reaches the case lookup this
        # test is named for.  Without it the node died on the missing port and
        # the assertion passed for the wrong reason (CONCERN-3019).
        result = bt_scenario.run(
            BroadcastCaseUpdateNode(case_id=CASE_ID),
            actor_id=ACTOR_ID,
            excluded_actor_ids=[],
        )
        # Pin the reason: the node also fails via _require_datalayer_and_actor,
        # so a bare assert_failure would not distinguish the absent case this
        # test is named for from that unrelated path (CONCERN-3019).
        bt_scenario.assert_failure(
            result, reason=f"case '{CASE_ID}' not found"
        )
