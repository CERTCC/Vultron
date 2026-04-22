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

from vultron.core.models.participant_status import VultronParticipantStatus
from vultron.core.use_cases._helpers import _report_phase_status_id
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.models.vultron_types import (
    VultronCaseActor,
    VultronOffer,
    VultronReport,
)
from vultron.core.behaviors.report.nodes import (
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
from vultron.core.states.rm import RM


@pytest.fixture
def datalayer():
    """In-memory DataLayer for testing."""
    return SqliteDataLayer("sqlite:///:memory:")


@pytest.fixture
def actor(datalayer):
    """Create test actor."""
    actor = VultronCaseActor(
        name="Test Actor",
    )
    datalayer.create(actor)
    return actor


@pytest.fixture
def report(datalayer):
    """Create test report."""
    report = VultronReport(
        name="TEST-001",
        content="Test vulnerability report",
    )
    datalayer.create(report)
    return report


@pytest.fixture
def offer(datalayer, report, actor):
    """Create test offer activity."""
    offer = VultronOffer(actor=actor.id_, object_=report.id_)
    datalayer.create(offer)
    return offer


@pytest.fixture
def blackboard_client(datalayer, actor):
    """Set up blackboard with DataLayer and actor_id."""
    client = BlackboardClient(name="TestClient")
    client.register_key(key="datalayer", access=py_trees.common.Access.WRITE)
    client.register_key(key="actor_id", access=py_trees.common.Access.WRITE)
    client.datalayer = datalayer
    client.actor_id = actor.id_
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
    status = VultronParticipantStatus(
        id_=_report_phase_status_id(actor.id_, report.id_, RM.VALID.value),
        context=report.id_,
        attributed_to=actor.id_,
        rm_state=RM.VALID,
    )
    datalayer.create(status)

    node = CheckRMStateValid(report_id=report.id_)
    setup_node_blackboard(node, datalayer, actor.id_)

    result = node.update()
    assert result == Status.SUCCESS


def test_check_rm_state_valid_when_received(datalayer, actor, report):
    """CheckRMStateValid returns FAILURE when report is RECEIVED (no VALID record)."""
    status = VultronParticipantStatus(
        id_=_report_phase_status_id(actor.id_, report.id_, RM.RECEIVED.value),
        context=report.id_,
        attributed_to=actor.id_,
        rm_state=RM.RECEIVED,
    )
    datalayer.create(status)

    node = CheckRMStateValid(report_id=report.id_)
    setup_node_blackboard(node, datalayer, actor.id_)

    result = node.update()
    assert result == Status.FAILURE


def test_check_rm_state_valid_when_no_status(datalayer, actor, report):
    """CheckRMStateValid returns FAILURE when no status exists."""
    node = CheckRMStateValid(report_id=report.id_)
    setup_node_blackboard(node, datalayer, actor.id_)

    result = node.update()
    assert result == Status.FAILURE


def test_check_rm_state_received_or_invalid_when_received(
    datalayer, actor, report
):
    """CheckRMStateReceivedOrInvalid returns SUCCESS when RECEIVED."""
    status = VultronParticipantStatus(
        id_=_report_phase_status_id(actor.id_, report.id_, RM.RECEIVED.value),
        context=report.id_,
        attributed_to=actor.id_,
        rm_state=RM.RECEIVED,
    )
    datalayer.create(status)

    node = CheckRMStateReceivedOrInvalid(report_id=report.id_)
    setup_node_blackboard(node, datalayer, actor.id_)

    result = node.update()
    assert result == Status.SUCCESS


def test_check_rm_state_received_or_invalid_when_invalid(
    datalayer, actor, report
):
    """CheckRMStateReceivedOrInvalid returns SUCCESS when INVALID."""
    status = VultronParticipantStatus(
        id_=_report_phase_status_id(actor.id_, report.id_, RM.INVALID.value),
        context=report.id_,
        attributed_to=actor.id_,
        rm_state=RM.INVALID,
    )
    datalayer.create(status)

    node = CheckRMStateReceivedOrInvalid(report_id=report.id_)
    setup_node_blackboard(node, datalayer, actor.id_)

    result = node.update()
    assert result == Status.SUCCESS


def test_check_rm_state_received_or_invalid_when_valid(
    datalayer, actor, report
):
    """CheckRMStateReceivedOrInvalid returns FAILURE when VALID."""
    status = VultronParticipantStatus(
        id_=_report_phase_status_id(actor.id_, report.id_, RM.VALID.value),
        context=report.id_,
        attributed_to=actor.id_,
        rm_state=RM.VALID,
    )
    datalayer.create(status)

    node = CheckRMStateReceivedOrInvalid(report_id=report.id_)
    setup_node_blackboard(node, datalayer, actor.id_)

    result = node.update()
    assert result == Status.FAILURE


def test_check_rm_state_received_or_invalid_when_no_status(
    datalayer, actor, report
):
    """CheckRMStateReceivedOrInvalid returns SUCCESS when no status (default RECEIVED)."""
    node = CheckRMStateReceivedOrInvalid(report_id=report.id_)
    setup_node_blackboard(node, datalayer, actor.id_)

    result = node.update()
    assert result == Status.SUCCESS


# ============================================================================
# Action Node Tests
# ============================================================================


def test_transition_rm_to_valid(datalayer, actor, report, offer):
    """TransitionRMtoValid updates statuses correctly."""
    node = TransitionRMtoValid(report_id=report.id_, offer_id=offer.id_)
    setup_node_blackboard(node, datalayer, actor.id_)

    result = node.update()
    assert result == Status.SUCCESS

    valid_id = _report_phase_status_id(actor.id_, report.id_, RM.VALID.value)
    assert datalayer.get("ParticipantStatus", valid_id) is not None


def test_transition_rm_to_invalid(datalayer, actor, report, offer):
    """TransitionRMtoInvalid updates report status to INVALID in DataLayer."""
    node = TransitionRMtoInvalid(report_id=report.id_, offer_id=offer.id_)
    setup_node_blackboard(node, datalayer, actor.id_)

    result = node.update()
    assert result == Status.SUCCESS

    invalid_id = _report_phase_status_id(
        actor.id_, report.id_, RM.INVALID.value
    )
    assert datalayer.get("ParticipantStatus", invalid_id) is not None


def test_create_case_node(datalayer, actor, report):
    """CreateCaseNode creates VulnerabilityCase and stores case_id."""
    node = CreateCaseNode(report_id=report.id_)
    setup_node_blackboard(node, datalayer, actor.id_)

    result = node.update()
    assert result == Status.SUCCESS

    # Verify case_id in blackboard
    case_id = node.blackboard.get("case_id")
    assert case_id is not None

    # Verify case exists in DataLayer
    case_obj = datalayer.read(case_id, raise_on_missing=True)
    assert case_obj.name == f"Case for Report {report.id_}"
    assert case_obj.attributed_to == actor.id_


def test_create_case_node_idempotency(datalayer, actor, report):
    """CreateCaseNode handles duplicate case creation gracefully."""
    node = CreateCaseNode(report_id=report.id_)
    setup_node_blackboard(node, datalayer, actor.id_)

    # First creation
    result1 = node.update()
    assert result1 == Status.SUCCESS

    # Second creation (should log warning but still succeed)
    result2 = node.update()
    assert result2 == Status.SUCCESS


def test_create_case_activity(datalayer, actor, report, offer):
    """CreateCaseActivity creates activity with recipients and embedded case."""
    # Add a finder actor whose ID will be collected as an addressee.
    from vultron.core.models.case_actor import VultronCaseActor

    finder = VultronCaseActor(name="Finder Actor")
    datalayer.create(finder)

    # Set report.attributed_to so the finder appears in the addressees list.
    report.attributed_to = finder.id_
    datalayer.save(report)

    # First create case to populate case_id in blackboard
    case_node = CreateCaseNode(report_id=report.id_)
    setup_node_blackboard(case_node, datalayer, actor.id_)
    case_node.update()

    # Create activity node
    activity_node = CreateCaseActivity(
        report_id=report.id_, offer_id=offer.id_
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

    # VultronCreateCaseActivity (type_="Create") cannot be round-tripped via
    # datalayer.read() because the "Create" wire class is not imported in the
    # test environment.  Use by_type("Create") to get the raw stored data dict.
    create_activities = datalayer.by_type("Create")
    assert (
        activity_id in create_activities
    ), f"Expected Create activity {activity_id!r} in DataLayer"
    activity_data = create_activities[activity_id]
    assert activity_data.get("type_") == "Create"

    # Verify the activity carries recipients (to field) excluding the sender.
    assert activity_data.get(
        "to"
    ), "CreateCaseActivity should have 'to' recipients"
    assert (
        actor.id_ not in activity_data["to"]
    ), "Sender actor should be excluded from 'to' recipients"
    assert (
        finder.id_ in activity_data["to"]
    ), "Finder (report.attributed_to) should be in 'to' recipients"

    # object_ is dehydrated to the case ID string at storage time; re-expansion
    # to the full case happens in outbox_handler at delivery time.
    assert isinstance(
        activity_data.get("object_"), str
    ), "CreateCaseActivity object_ should be stored as the case ID string"


def test_create_case_activity_missing_case_id(datalayer, actor, report, offer):
    """CreateCaseActivity fails if case_id not in blackboard."""
    node = CreateCaseActivity(report_id=report.id_, offer_id=offer.id_)
    setup_node_blackboard(node, datalayer, actor.id_)
    # Register case_id with WRITE access for testing
    node.blackboard.register_key(
        key="case_id", access=py_trees.common.Access.WRITE
    )
    # Explicitly set case_id to None to test error handling
    node.blackboard.set("case_id", None, overwrite=True)

    result = node.update()
    assert result == Status.FAILURE


def test_update_actor_outbox(datalayer, actor, report, offer):
    """UpdateActorOutbox appends activity to actor's outbox."""
    # First create case and activity to populate blackboard
    case_node = CreateCaseNode(report_id=report.id_)
    setup_node_blackboard(case_node, datalayer, actor.id_)
    case_node.update()

    activity_node = CreateCaseActivity(
        report_id=report.id_, offer_id=offer.id_
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
    updated_actor = datalayer.read(actor.id_, raise_on_missing=True)
    activity_id = outbox_node.blackboard.get("activity_id")
    assert activity_id in updated_actor.outbox.items


def test_update_actor_outbox_missing_activity_id(datalayer, actor):
    """UpdateActorOutbox fails if activity_id not in blackboard."""
    node = UpdateActorOutbox()
    setup_node_blackboard(node, datalayer, actor.id_)
    # Register activity_id with WRITE access for testing
    node.blackboard.register_key(
        key="activity_id", access=py_trees.common.Access.WRITE
    )
    # Explicitly set activity_id to None to test error handling
    node.blackboard.set("activity_id", None, overwrite=True)

    result = node.update()
    assert result == Status.FAILURE


# ============================================================================
# Policy Node Tests (Stubs)
# ============================================================================


def test_evaluate_report_credibility(datalayer, actor, report):
    """EvaluateReportCredibility always returns SUCCESS (stub)."""
    node = EvaluateReportCredibility(report_id=report.id_)
    setup_node_blackboard(node, datalayer, actor.id_)

    result = node.update()
    assert result == Status.SUCCESS


def test_evaluate_report_validity(datalayer, actor, report):
    """EvaluateReportValidity always returns SUCCESS (stub)."""
    node = EvaluateReportValidity(report_id=report.id_)
    setup_node_blackboard(node, datalayer, actor.id_)

    result = node.update()
    assert result == Status.SUCCESS


# ============================================================================
# Integration Test
# ============================================================================


def test_full_validation_workflow(datalayer, actor, report, offer):
    """Test full validation workflow using all nodes in sequence."""
    # 1. Check if already valid (should fail initially)
    check_valid = CheckRMStateValid(report_id=report.id_)
    setup_node_blackboard(check_valid, datalayer, actor.id_)
    assert check_valid.update() == Status.FAILURE

    # 2. Check preconditions (should succeed)
    check_precond = CheckRMStateReceivedOrInvalid(report_id=report.id_)
    setup_node_blackboard(check_precond, datalayer, actor.id_)
    assert check_precond.update() == Status.SUCCESS

    # 3. Evaluate credibility (stub: always succeeds)
    eval_cred = EvaluateReportCredibility(report_id=report.id_)
    setup_node_blackboard(eval_cred, datalayer, actor.id_)
    assert eval_cred.update() == Status.SUCCESS

    # 4. Evaluate validity (stub: always succeeds)
    eval_valid = EvaluateReportValidity(report_id=report.id_)
    setup_node_blackboard(eval_valid, datalayer, actor.id_)
    assert eval_valid.update() == Status.SUCCESS

    # 5. Transition to VALID
    transition = TransitionRMtoValid(report_id=report.id_, offer_id=offer.id_)
    setup_node_blackboard(transition, datalayer, actor.id_)
    assert transition.update() == Status.SUCCESS

    # 6. Create case
    create_case = CreateCaseNode(report_id=report.id_)
    create_case.blackboard = transition.blackboard
    create_case.initialise()
    assert create_case.update() == Status.SUCCESS

    # 7. Create activity
    create_activity = CreateCaseActivity(
        report_id=report.id_, offer_id=offer.id_
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
    check_valid_final = CheckRMStateValid(report_id=report.id_)
    setup_node_blackboard(check_valid_final, datalayer, actor.id_)
    assert check_valid_final.update() == Status.SUCCESS


# ============================================================================
# D5-6-LOGCTX: UpdateActorOutbox log content tests
# ============================================================================


def test_update_actor_outbox_logs_create_activity_type(
    datalayer, actor, report, offer, caplog
):
    """UpdateActorOutbox MUST log 'Create' activity type (D5-6-LOGCTX)."""
    case_node = CreateCaseNode(report_id=report.id_)
    setup_node_blackboard(case_node, datalayer, actor.id_)
    case_node.update()

    activity_node = CreateCaseActivity(
        report_id=report.id_, offer_id=offer.id_
    )
    activity_node.blackboard = case_node.blackboard
    activity_node.initialise()
    activity_node.update()

    outbox_node = UpdateActorOutbox()
    outbox_node.blackboard = activity_node.blackboard
    outbox_node.initialise()

    with caplog.at_level("INFO"):
        outbox_node.update()

    assert "Create" in caplog.text


def test_update_actor_outbox_logs_case_id_in_message(
    datalayer, actor, report, offer, caplog
):
    """UpdateActorOutbox MUST log the case ID in the outbox message (D5-6-LOGCTX)."""
    case_node = CreateCaseNode(report_id=report.id_)
    setup_node_blackboard(case_node, datalayer, actor.id_)
    case_node.update()

    # Capture case_id from blackboard
    case_node.blackboard.register_key(
        key="case_id", access=py_trees.common.Access.READ
    )
    case_id = case_node.blackboard.get("case_id")

    activity_node = CreateCaseActivity(
        report_id=report.id_, offer_id=offer.id_
    )
    activity_node.blackboard = case_node.blackboard
    activity_node.initialise()
    activity_node.update()

    outbox_node = UpdateActorOutbox()
    outbox_node.blackboard = activity_node.blackboard
    outbox_node.initialise()

    with caplog.at_level("INFO"):
        outbox_node.update()

    assert case_id in caplog.text
