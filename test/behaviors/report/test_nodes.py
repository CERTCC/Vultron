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
Tests for report validation behavior tree nodes.
"""

import py_trees
import pytest
from py_trees.blackboard import Client as BlackboardClient
from py_trees.common import Status

from vultron.api.v2.data.status import (
    OfferStatus,
    ReportStatus,
    get_status_layer,
    set_status,
)
from vultron.api.v2.datalayer.tinydb_backend import TinyDbDataLayer
from vultron.as_vocab.base.objects.activities.transitive import as_Offer
from vultron.as_vocab.base.objects.actors import as_Service
from vultron.as_vocab.objects.vulnerability_report import VulnerabilityReport
from vultron.behaviors.report.nodes import (
    CheckRMStateReceivedOrInvalid,
    CheckRMStateValid,
    CreateCaseActivity,
    CreateCaseNode,
    EvaluateReportCredibility,
    EvaluateReportValidity,
    TransitionRMtoInvalid,
    TransitionRMtoValid,
    UpdateActorOutbox,
)
from vultron.bt.report_management.states import RM
from vultron.enums import OfferStatusEnum


@pytest.fixture
def datalayer():
    """In-memory DataLayer for testing."""
    return TinyDbDataLayer(db_path=None)


@pytest.fixture
def actor(datalayer):
    """Create test actor."""
    actor = as_Service(
        name="Test Actor",
        url="https://example.org/actor",
    )
    datalayer.create(actor)
    return actor


@pytest.fixture
def report(datalayer):
    """Create test report."""
    report = VulnerabilityReport(
        name="TEST-001",
        content="Test vulnerability report",
    )
    datalayer.create(report)
    return report


@pytest.fixture
def offer(datalayer, report, actor):
    """Create test offer activity."""
    offer = as_Offer(actor=actor.as_id, object=report)
    datalayer.create(offer)
    return offer


@pytest.fixture
def blackboard_client(datalayer, actor):
    """Set up blackboard with DataLayer and actor_id."""
    client = BlackboardClient(name="TestClient")
    client.register_key(key="datalayer", access=py_trees.common.Access.WRITE)
    client.register_key(key="actor_id", access=py_trees.common.Access.WRITE)
    client.datalayer = datalayer
    client.actor_id = actor.as_id
    return client


def setup_node_blackboard(node, datalayer, actor_id):
    """Helper to set up node with blackboard."""
    node.setup()
    # Register and set blackboard keys with WRITE access
    node.blackboard.register_key(
        key="datalayer", access=py_trees.common.Access.WRITE
    )
    node.blackboard.register_key(
        key="actor_id", access=py_trees.common.Access.WRITE
    )
    node.blackboard.datalayer = datalayer
    node.blackboard.actor_id = actor_id
    node.initialise()


# ============================================================================
# Condition Node Tests
# ============================================================================


def test_check_rm_state_valid_when_valid(datalayer, actor, report):
    """CheckRMStateValid returns SUCCESS when report is VALID."""
    # Set report to VALID
    set_status(
        ReportStatus(
            object_type="VulnerabilityReport",
            object_id=report.as_id,
            status=RM.VALID,
            actor_id=actor.as_id,
        )
    )

    node = CheckRMStateValid(report_id=report.as_id)
    setup_node_blackboard(node, datalayer, actor.as_id)

    result = node.update()
    assert result == Status.SUCCESS


def test_check_rm_state_valid_when_received(datalayer, actor, report):
    """CheckRMStateValid returns FAILURE when report is RECEIVED."""
    set_status(
        ReportStatus(
            object_type="VulnerabilityReport",
            object_id=report.as_id,
            status=RM.RECEIVED,
            actor_id=actor.as_id,
        )
    )

    node = CheckRMStateValid(report_id=report.as_id)
    setup_node_blackboard(node, datalayer, actor.as_id)

    result = node.update()
    assert result == Status.FAILURE


def test_check_rm_state_valid_when_no_status(datalayer, actor, report):
    """CheckRMStateValid returns FAILURE when no status exists."""
    node = CheckRMStateValid(report_id=report.as_id)
    setup_node_blackboard(node, datalayer, actor.as_id)

    result = node.update()
    assert result == Status.FAILURE


def test_check_rm_state_received_or_invalid_when_received(
    datalayer, actor, report
):
    """CheckRMStateReceivedOrInvalid returns SUCCESS when RECEIVED."""
    set_status(
        ReportStatus(
            object_type="VulnerabilityReport",
            object_id=report.as_id,
            status=RM.RECEIVED,
            actor_id=actor.as_id,
        )
    )

    node = CheckRMStateReceivedOrInvalid(report_id=report.as_id)
    setup_node_blackboard(node, datalayer, actor.as_id)

    result = node.update()
    assert result == Status.SUCCESS


def test_check_rm_state_received_or_invalid_when_invalid(
    datalayer, actor, report
):
    """CheckRMStateReceivedOrInvalid returns SUCCESS when INVALID."""
    set_status(
        ReportStatus(
            object_type="VulnerabilityReport",
            object_id=report.as_id,
            status=RM.INVALID,
            actor_id=actor.as_id,
        )
    )

    node = CheckRMStateReceivedOrInvalid(report_id=report.as_id)
    setup_node_blackboard(node, datalayer, actor.as_id)

    result = node.update()
    assert result == Status.SUCCESS


def test_check_rm_state_received_or_invalid_when_valid(
    datalayer, actor, report
):
    """CheckRMStateReceivedOrInvalid returns FAILURE when VALID."""
    set_status(
        ReportStatus(
            object_type="VulnerabilityReport",
            object_id=report.as_id,
            status=RM.VALID,
            actor_id=actor.as_id,
        )
    )

    node = CheckRMStateReceivedOrInvalid(report_id=report.as_id)
    setup_node_blackboard(node, datalayer, actor.as_id)

    result = node.update()
    assert result == Status.FAILURE


def test_check_rm_state_received_or_invalid_when_no_status(
    datalayer, actor, report
):
    """CheckRMStateReceivedOrInvalid returns SUCCESS when no status (default RECEIVED)."""
    node = CheckRMStateReceivedOrInvalid(report_id=report.as_id)
    setup_node_blackboard(node, datalayer, actor.as_id)

    result = node.update()
    assert result == Status.SUCCESS


# ============================================================================
# Action Node Tests
# ============================================================================


def test_transition_rm_to_valid(datalayer, actor, report, offer):
    """TransitionRMtoValid updates statuses correctly."""
    node = TransitionRMtoValid(report_id=report.as_id, offer_id=offer.as_id)
    setup_node_blackboard(node, datalayer, actor.as_id)

    result = node.update()
    assert result == Status.SUCCESS

    # Verify statuses
    status_layer = get_status_layer()
    report_status = status_layer["VulnerabilityReport"][report.as_id][
        actor.as_id
    ]
    assert report_status["status"] == RM.VALID

    offer_status = status_layer["Offer"][offer.as_id][actor.as_id]
    assert offer_status["status"] == OfferStatusEnum.ACCEPTED


def test_transition_rm_to_invalid(datalayer, actor, report, offer):
    """TransitionRMtoInvalid updates statuses correctly."""
    node = TransitionRMtoInvalid(report_id=report.as_id, offer_id=offer.as_id)
    setup_node_blackboard(node, datalayer, actor.as_id)

    result = node.update()
    assert result == Status.SUCCESS

    # Verify statuses
    status_layer = get_status_layer()
    report_status = status_layer["VulnerabilityReport"][report.as_id][
        actor.as_id
    ]
    assert report_status["status"] == RM.INVALID

    offer_status = status_layer["Offer"][offer.as_id][actor.as_id]
    assert offer_status["status"] == OfferStatusEnum.TENTATIVELY_REJECTED


def test_create_case_node(datalayer, actor, report):
    """CreateCaseNode creates VulnerabilityCase and stores case_id."""
    node = CreateCaseNode(report_id=report.as_id)
    setup_node_blackboard(node, datalayer, actor.as_id)

    result = node.update()
    assert result == Status.SUCCESS

    # Verify case_id in blackboard
    case_id = node.blackboard.get("case_id")
    assert case_id is not None

    # Verify case exists in DataLayer
    case_obj = datalayer.read(case_id, raise_on_missing=True)
    assert case_obj.name == f"Case for Report {report.as_id}"
    assert case_obj.attributed_to == actor.as_id


def test_create_case_node_idempotency(datalayer, actor, report):
    """CreateCaseNode handles duplicate case creation gracefully."""
    node = CreateCaseNode(report_id=report.as_id)
    setup_node_blackboard(node, datalayer, actor.as_id)

    # First creation
    result1 = node.update()
    assert result1 == Status.SUCCESS

    # Second creation (should log warning but still succeed)
    result2 = node.update()
    assert result2 == Status.SUCCESS


def test_create_case_activity(datalayer, actor, report, offer):
    """CreateCaseActivity creates activity and collects addressees."""
    # First create case to populate case_id in blackboard
    case_node = CreateCaseNode(report_id=report.as_id)
    setup_node_blackboard(case_node, datalayer, actor.as_id)
    case_node.update()

    # Create activity node
    activity_node = CreateCaseActivity(
        report_id=report.as_id, offer_id=offer.as_id
    )
    activity_node.blackboard = (
        case_node.blackboard
    )  # Reuse blackboard with case_id
    activity_node.initialise()

    result = activity_node.update()
    assert result == Status.SUCCESS

    # Verify activity_id in blackboard
    activity_id = activity_node.blackboard.get("activity_id")
    assert activity_id is not None

    # Verify activity exists in DataLayer
    activity_obj = datalayer.read(activity_id, raise_on_missing=True)
    assert activity_obj.as_type == "Create"


def test_create_case_activity_missing_case_id(datalayer, actor, report, offer):
    """CreateCaseActivity fails if case_id not in blackboard."""
    node = CreateCaseActivity(report_id=report.as_id, offer_id=offer.as_id)
    setup_node_blackboard(node, datalayer, actor.as_id)

    result = node.update()
    assert result == Status.FAILURE


def test_update_actor_outbox(datalayer, actor, report, offer):
    """UpdateActorOutbox appends activity to actor's outbox."""
    # First create case and activity to populate blackboard
    case_node = CreateCaseNode(report_id=report.as_id)
    setup_node_blackboard(case_node, datalayer, actor.as_id)
    case_node.update()

    activity_node = CreateCaseActivity(
        report_id=report.as_id, offer_id=offer.as_id
    )
    activity_node.blackboard = case_node.blackboard
    activity_node.initialise()
    activity_node.update()

    # Update outbox
    outbox_node = UpdateActorOutbox()
    outbox_node.blackboard = activity_node.blackboard
    outbox_node.initialise()

    result = outbox_node.update()
    assert result == Status.SUCCESS

    # Verify activity in actor's outbox
    updated_actor = datalayer.read(actor.as_id, raise_on_missing=True)
    activity_id = outbox_node.blackboard.get("activity_id")
    assert activity_id in updated_actor.outbox.items


def test_update_actor_outbox_missing_activity_id(datalayer, actor):
    """UpdateActorOutbox fails if activity_id not in blackboard."""
    node = UpdateActorOutbox()
    setup_node_blackboard(node, datalayer, actor.as_id)

    result = node.update()
    assert result == Status.FAILURE


# ============================================================================
# Policy Node Tests (Stubs)
# ============================================================================


def test_evaluate_report_credibility(datalayer, actor, report):
    """EvaluateReportCredibility always returns SUCCESS (stub)."""
    node = EvaluateReportCredibility(report_id=report.as_id)
    setup_node_blackboard(node, datalayer, actor.as_id)

    result = node.update()
    assert result == Status.SUCCESS


def test_evaluate_report_validity(datalayer, actor, report):
    """EvaluateReportValidity always returns SUCCESS (stub)."""
    node = EvaluateReportValidity(report_id=report.as_id)
    setup_node_blackboard(node, datalayer, actor.as_id)

    result = node.update()
    assert result == Status.SUCCESS


# ============================================================================
# Integration Test
# ============================================================================


def test_full_validation_workflow(datalayer, actor, report, offer):
    """Test full validation workflow using all nodes in sequence."""
    # 1. Check if already valid (should fail initially)
    check_valid = CheckRMStateValid(report_id=report.as_id)
    setup_node_blackboard(check_valid, datalayer, actor.as_id)
    assert check_valid.update() == Status.FAILURE

    # 2. Check preconditions (should succeed)
    check_precond = CheckRMStateReceivedOrInvalid(report_id=report.as_id)
    setup_node_blackboard(check_precond, datalayer, actor.as_id)
    assert check_precond.update() == Status.SUCCESS

    # 3. Evaluate credibility (stub: always succeeds)
    eval_cred = EvaluateReportCredibility(report_id=report.as_id)
    setup_node_blackboard(eval_cred, datalayer, actor.as_id)
    assert eval_cred.update() == Status.SUCCESS

    # 4. Evaluate validity (stub: always succeeds)
    eval_valid = EvaluateReportValidity(report_id=report.as_id)
    setup_node_blackboard(eval_valid, datalayer, actor.as_id)
    assert eval_valid.update() == Status.SUCCESS

    # 5. Transition to VALID
    transition = TransitionRMtoValid(
        report_id=report.as_id, offer_id=offer.as_id
    )
    setup_node_blackboard(transition, datalayer, actor.as_id)
    assert transition.update() == Status.SUCCESS

    # 6. Create case
    create_case = CreateCaseNode(report_id=report.as_id)
    create_case.blackboard = transition.blackboard
    create_case.initialise()
    assert create_case.update() == Status.SUCCESS

    # 7. Create activity
    create_activity = CreateCaseActivity(
        report_id=report.as_id, offer_id=offer.as_id
    )
    create_activity.blackboard = create_case.blackboard
    create_activity.initialise()
    assert create_activity.update() == Status.SUCCESS

    # 8. Update outbox
    update_outbox = UpdateActorOutbox()
    update_outbox.blackboard = create_activity.blackboard
    update_outbox.initialise()
    assert update_outbox.update() == Status.SUCCESS

    # 9. Verify final state
    check_valid_final = CheckRMStateValid(report_id=report.as_id)
    setup_node_blackboard(check_valid_final, datalayer, actor.as_id)
    assert check_valid_final.update() == Status.SUCCESS
