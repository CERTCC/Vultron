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

"""
Tests for communication behavior tree nodes.

Covers SendOfferCaseManagerRoleNode.

Per DEMOMA-08-002, DEMOMA-08-003; Issue #469.
"""

import py_trees
import pytest

from vultron.core.behaviors.case.nodes import (
    CollectCaseAddresseesNode,
    CreateAndPersistCaseActivityNode,
    CreateOfferCaseManagerActivityNode,
    CreateCaseActorNode,
    EmitCreateCaseActivity,
    ResolveCaseManagerOfferContextNode,
    SendOfferCaseManagerRoleNode,
)
from vultron.core.models.vultron_types import (
    VultronCase,
    VultronCaseActor,
    VultronReport,
)
from test.core.behaviors.bt_harness import BTTestScenario

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def actor_id() -> str:
    return "https://example.org/actors/vendor"


@pytest.fixture
def actor(bt_scenario: BTTestScenario, actor_id: str) -> VultronCaseActor:
    obj = VultronCaseActor(id_=actor_id, name="Vendor Co")
    bt_scenario.dl.create(obj)
    return obj


@pytest.fixture
def report(bt_scenario: BTTestScenario) -> VultronReport:
    obj = VultronReport(name="TEST-001", content="Test vulnerability report")
    bt_scenario.dl.create(obj)
    return obj


@pytest.fixture
def case_obj(
    bt_scenario: BTTestScenario, report: VultronReport
) -> VultronCase:
    case = VultronCase(
        id_="https://example.org/cases/case-001",
        name="Test Case",
        vulnerability_reports=[report.id_],
    )
    bt_scenario.dl.create(case)
    return case


# ---------------------------------------------------------------------------
# TestEmitCreateCaseActivity
# ---------------------------------------------------------------------------


class TestEmitCreateCaseActivity:
    """EmitCreateCaseActivity composes create-case activity emission leaves."""

    def test_tree_is_sequence_with_named_leaf_nodes(self) -> None:
        tree = EmitCreateCaseActivity()
        assert isinstance(tree, py_trees.composites.Sequence)
        assert len(tree.children) == 2
        assert isinstance(tree.children[0], CollectCaseAddresseesNode)
        assert isinstance(tree.children[1], CreateAndPersistCaseActivityNode)

    def test_collect_case_addressees_filters_sender(
        self,
        bt_scenario: BTTestScenario,
        actor: VultronCaseActor,
        actor_id: str,
        case_obj: VultronCase,
    ) -> None:
        case_obj.actor_participant_index[actor_id] = (
            "https://example.org/participants/vendor"
        )
        case_obj.actor_participant_index["https://example.org/actors/peer"] = (
            "https://example.org/participants/peer"
        )
        bt_scenario.dl.save(case_obj)

        result = bt_scenario.run(
            CollectCaseAddresseesNode(),
            actor_id=actor_id,
            case_id=case_obj.id_,
        )
        bt_scenario.assert_success(result)
        addressees = py_trees.blackboard.Blackboard.storage.get(
            "/create_case_addressees"
        )
        assert addressees == ["https://example.org/actors/peer"]

    def test_create_and_persist_case_activity_writes_activity_id(
        self,
        bt_scenario: BTTestScenario,
        actor: VultronCaseActor,
        actor_id: str,
        case_obj: VultronCase,
    ) -> None:
        result = bt_scenario.run(
            CreateAndPersistCaseActivityNode(),
            actor_id=actor_id,
            case_id=case_obj.id_,
            create_case_obj=case_obj,
            create_case_addressees=[],
        )
        bt_scenario.assert_success(result)
        activity_id = py_trees.blackboard.Blackboard.storage.get(
            "/activity_id"
        )
        assert isinstance(activity_id, str)
        assert bt_scenario.dl.read(activity_id) is not None


# ---------------------------------------------------------------------------
# TestSendOfferCaseManagerRoleNode
# ---------------------------------------------------------------------------


class TestSendOfferCaseManagerRoleNode:
    """SendOfferCaseManagerRoleNode queues Offer(CaseManagerRole) to Case Actor."""

    def test_tree_is_sequence_with_named_leaf_nodes(self) -> None:
        tree = SendOfferCaseManagerRoleNode()
        assert isinstance(tree, py_trees.composites.Sequence)
        assert len(tree.children) == 2
        assert isinstance(tree.children[0], ResolveCaseManagerOfferContextNode)
        assert isinstance(tree.children[1], CreateOfferCaseManagerActivityNode)

    def test_queues_offer_and_writes_activity_id(
        self,
        bt_scenario: BTTestScenario,
        actor: VultronCaseActor,
        actor_id: str,
        case_obj: VultronCase,
    ) -> None:
        """SendOfferCaseManagerRoleNode writes activity_id to blackboard after Offer."""
        # Run CreateCaseActorNode first to populate the DataLayer with the
        # Case Actor entity and participant.
        bt_scenario.run(
            CreateCaseActorNode(),
            actor_id=actor_id,
            case_id=case_obj.id_,
        )

        # Retrieve the case_actor_id that was written to the blackboard.
        case_actor_id = py_trees.blackboard.Blackboard.storage.get(
            "/case_actor_id"
        )
        assert (
            case_actor_id is not None
        ), "CreateCaseActorNode must write case_actor_id"

        case_actor_participant_id = py_trees.blackboard.Blackboard.storage.get(
            "/case_actor_participant_id"
        )
        assert (
            case_actor_participant_id is not None
        ), "CreateCaseActorNode must write case_actor_participant_id"

        # Now run SendOfferCaseManagerRoleNode with the needed blackboard context.
        result = bt_scenario.run(
            SendOfferCaseManagerRoleNode(),
            actor_id=actor_id,
            case_id=case_obj.id_,
            case_actor_id=case_actor_id,
            case_actor_participant_id=case_actor_participant_id,
        )
        bt_scenario.assert_success(result)

        activity_id = py_trees.blackboard.Blackboard.storage.get(
            "/activity_id"
        )
        assert activity_id is not None

    def test_fails_without_case_actor_id_in_blackboard(
        self,
        bt_scenario: BTTestScenario,
        actor: VultronCaseActor,
        actor_id: str,
        case_obj: VultronCase,
    ) -> None:
        """SendOfferCaseManagerRoleNode fails if case_actor_id is not in blackboard."""
        # Provide case_id but no case_actor_id — the participant exists in DL
        # but the blackboard is missing the case_actor_id key.
        result = bt_scenario.run(
            SendOfferCaseManagerRoleNode(),
            actor_id=actor_id,
            case_id=case_obj.id_,
            # case_actor_id intentionally omitted
        )
        assert result.status == py_trees.common.Status.FAILURE
