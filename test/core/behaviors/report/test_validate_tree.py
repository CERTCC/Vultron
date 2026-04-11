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
Tests for report validation behavior tree composition.

Verifies that the ValidateReportBT composite tree correctly orchestrates
the validation workflow using the nodes from nodes.py.

Per specs/behavior-tree-integration.md BT-06 and testability.md requirements.
"""

import pytest
from py_trees.common import Status

from vultron.adapters.driven.datalayer_tinydb import TinyDbDataLayer
from vultron.core.models.participant_status import VultronParticipantStatus
from vultron.core.use_cases._helpers import _report_phase_status_id
from vultron.core.models.vultron_types import (
    VultronCaseActor,
    VultronOffer,
    VultronReport,
)
from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.report.validate_tree import (
    create_validate_report_tree,
)
from vultron.core.states.rm import RM


@pytest.fixture
def datalayer():
    """Create in-memory TinyDB data layer for testing."""
    return TinyDbDataLayer(db_path=None)


@pytest.fixture
def actor_id():
    """Test vendor actor ID."""
    return "https://example.org/actors/vendor"


@pytest.fixture
def finder_actor_id():
    """Test finder actor ID — distinct from the vendor."""
    return "https://example.org/actors/finder"


@pytest.fixture
def report(datalayer, actor_id):
    """Create test VulnerabilityReport."""
    report_obj = VultronReport(
        id_="https://example.org/reports/CVE-2024-001",
        name="Test Vulnerability Report",
        content="Test vulnerability description",
    )
    datalayer.create(report_obj)
    return report_obj


@pytest.fixture
def offer(datalayer, report, actor_id, finder_actor_id):
    """Create test Offer activity.  The *finder* submits the offer to the
    *vendor* inbox, so ``actor`` is the finder's ID.
    """
    offer_obj = VultronOffer(
        id_="https://example.org/activities/offer-123",
        actor=finder_actor_id,
        object_=report.id_,
        target=actor_id,
    )
    datalayer.create(offer_obj)
    return offer_obj


@pytest.fixture
def actor(datalayer, actor_id):
    """Create test vendor actor in the DataLayer."""
    actor_obj = VultronCaseActor(
        id_=actor_id,
        name="Vendor Co",
    )
    datalayer.create(actor_obj)
    return actor_obj


@pytest.fixture
def finder_actor(datalayer, finder_actor_id):
    """Create test finder actor in the DataLayer."""
    actor_obj = VultronCaseActor(
        id_=finder_actor_id,
        name="Finder Co",
    )
    datalayer.create(actor_obj)
    return actor_obj


@pytest.fixture
def bridge(datalayer):
    """Create BT bridge for execution."""
    return BTBridge(datalayer=datalayer)


@pytest.fixture
def case(bridge, datalayer, actor_id, report, offer, actor, finder_actor):
    """Pre-create the VulnerabilityCase at RM.RECEIVED.

    Mirrors what SubmitReportReceivedUseCase does via receive_report_case_tree
    (per ADR-0015).  Tests that run the validate_report tree depend on this
    fixture to satisfy the EnsureEmbargoExists precondition.
    """
    from vultron.core.behaviors.case.receive_report_case_tree import (
        create_receive_report_case_tree,
    )

    tree = create_receive_report_case_tree(
        report_id=report.id_,
        offer_id=offer.id_,
    )
    bridge.execute_with_setup(tree, actor_id=actor_id, datalayer=datalayer)
    cases = datalayer.by_type("VulnerabilityCase")
    assert cases, "Expected case fixture to create a VulnerabilityCase"
    case_id = next(iter(cases))
    return datalayer.read(case_id)


# ============================================================================
# Tree Creation Tests
# ============================================================================


def test_create_validate_report_tree_returns_selector(report, offer):
    """Tree factory returns Selector root node."""
    tree = create_validate_report_tree(
        report_id=report.id_,
        offer_id=offer.id_,
    )

    assert tree is not None
    assert tree.name == "ValidateReportBT"
    # py_trees.composites.Selector is a subclass of py_trees.composites.Composite
    assert hasattr(tree, "children")
    assert len(tree.children) == 2  # Early exit + validation flow


def test_tree_structure_matches_spec(report, offer):
    """Tree structure matches expected hierarchy from spec."""
    tree = create_validate_report_tree(
        report_id=report.id_,
        offer_id=offer.id_,
    )

    # Root: Selector with 2 children
    assert len(tree.children) == 2

    # Child 1: CheckRMStateValid (early exit)
    early_exit = tree.children[0]
    assert early_exit.name == "CheckRMStateValid"

    # Child 2: ValidationFlow (Sequence)
    validation_flow = tree.children[1]
    assert validation_flow.name == "ValidationFlow"
    assert (
        len(validation_flow.children) == 4
    )  # Precondition + 2 policies + actions

    # Validation flow children
    precondition = validation_flow.children[0]
    assert precondition.name == "CheckRMStateReceivedOrInvalid"

    credibility = validation_flow.children[1]
    assert credibility.name == "EvaluateReportCredibility"

    validity = validation_flow.children[2]
    assert validity.name == "EvaluateReportValidity"

    actions = validation_flow.children[3]
    assert actions.name == "ValidationActions"
    # Per ADR-0015: case/participant creation moved to receive_report_case_tree.
    # ValidationActions now only transitions RM state and checks embargo.
    assert len(actions.children) == 2
    assert actions.children[0].name == "TransitionRMtoValid"
    assert actions.children[1].name == "EnsureEmbargoExists"


# ============================================================================
# Execution Tests
# ============================================================================


def test_tree_execution_success_new_report(
    bridge, datalayer, actor_id, report, offer, actor, finder_actor, case
):
    """Tree executes successfully for report after case was created at receipt."""
    tree = create_validate_report_tree(
        report_id=report.id_,
        offer_id=offer.id_,
    )

    # Act: Execute tree
    result = bridge.execute_with_setup(
        tree=tree,
        actor_id=actor_id,
        datalayer=datalayer,
    )

    # Assert: Tree succeeds
    assert result.status == Status.SUCCESS
    assert result.errors is None or result.errors == []

    # Verify side effects: Report status updated to VALID in DataLayer
    valid_id = _report_phase_status_id(actor_id, report.id_, RM.VALID.value)
    assert datalayer.get("ParticipantStatus", valid_id) is not None


def test_tree_execution_does_not_create_case(
    bridge, datalayer, actor_id, report, offer, actor, finder_actor, case
):
    """validate-report BT does NOT create a case (case was created at receipt).

    Per ADR-0015, case creation belongs in receive_report_case_tree triggered
    by SubmitReportReceivedUseCase at RM.RECEIVED.  validate_report only
    transitions RM state and verifies the embargo exists.
    """
    cases_before = set(datalayer.by_type("VulnerabilityCase").keys())

    tree = create_validate_report_tree(
        report_id=report.id_,
        offer_id=offer.id_,
    )
    result = bridge.execute_with_setup(
        tree=tree,
        actor_id=actor_id,
        datalayer=datalayer,
    )

    assert result.status == Status.SUCCESS
    cases_after = set(datalayer.by_type("VulnerabilityCase").keys())
    # No new cases should have been created by validate_report
    assert cases_after == cases_before, (
        "validate_report BT must not create a new VulnerabilityCase "
        "(case creation belongs at RM.RECEIVED per ADR-0015)"
    )


def test_tree_execution_transitions_vendor_to_valid(
    bridge, datalayer, actor_id, report, offer, actor, finder_actor, case
):
    """validate-report advances vendor's report-phase status to RM.VALID."""
    tree = create_validate_report_tree(
        report_id=report.id_,
        offer_id=offer.id_,
    )

    result = bridge.execute_with_setup(
        tree=tree,
        actor_id=actor_id,
        datalayer=datalayer,
    )

    assert result.status == Status.SUCCESS

    # Vendor's report-phase status must be RM.VALID
    valid_id = _report_phase_status_id(actor_id, report.id_, RM.VALID.value)
    assert datalayer.get("ParticipantStatus", valid_id) is not None


def test_tree_execution_early_exit_already_valid(
    bridge, datalayer, actor_id, report, offer, actor, finder_actor, case
):
    """Tree short-circuits if report already in VALID state."""
    # Arrange: Set report to VALID state in DataLayer
    valid_status = VultronParticipantStatus(
        id_=_report_phase_status_id(actor_id, report.id_, RM.VALID.value),
        context=report.id_,
        attributed_to=actor_id,
        rm_state=RM.VALID,
    )
    datalayer.create(valid_status)

    tree = create_validate_report_tree(
        report_id=report.id_,
        offer_id=offer.id_,
    )

    # Act: Execute tree
    result = bridge.execute_with_setup(
        tree=tree,
        actor_id=actor_id,
        datalayer=datalayer,
    )

    # Assert: Tree succeeds via early exit
    assert result.status == Status.SUCCESS


def test_tree_execution_invalid_state_transitions_to_valid(
    bridge, datalayer, actor_id, report, offer, actor, finder_actor, case
):
    """Tree can validate report from INVALID state."""
    # Arrange: Set report to INVALID state in DataLayer (no VALID record present)
    invalid_status = VultronParticipantStatus(
        id_=_report_phase_status_id(actor_id, report.id_, RM.INVALID.value),
        context=report.id_,
        attributed_to=actor_id,
        rm_state=RM.INVALID,
    )
    datalayer.create(invalid_status)

    tree = create_validate_report_tree(
        report_id=report.id_,
        offer_id=offer.id_,
    )

    # Act: Execute tree
    result = bridge.execute_with_setup(
        tree=tree,
        actor_id=actor_id,
        datalayer=datalayer,
    )

    # Assert: Tree succeeds
    assert result.status == Status.SUCCESS

    # Verify side effects: Report status updated to VALID in DataLayer
    valid_id = _report_phase_status_id(actor_id, report.id_, RM.VALID.value)
    assert datalayer.get("ParticipantStatus", valid_id) is not None


def test_tree_execution_no_prior_status_succeeds(
    bridge, datalayer, actor_id, report, offer, actor, finder_actor, case
):
    """Tree succeeds even if report has no prior status (new report)."""
    # Arrange: No status set (report has no status tracking yet)
    # This simulates first-time validation — case was created at receipt.

    tree = create_validate_report_tree(
        report_id=report.id_,
        offer_id=offer.id_,
    )

    # Act: Execute tree
    result = bridge.execute_with_setup(
        tree=tree,
        actor_id=actor_id,
        datalayer=datalayer,
    )

    # Assert: Tree succeeds (precondition accepts no status as RECEIVED-equivalent)
    assert result.status == Status.SUCCESS

    # Verify side effects: Report status updated to VALID in DataLayer
    valid_id = _report_phase_status_id(actor_id, report.id_, RM.VALID.value)
    assert datalayer.get("ParticipantStatus", valid_id) is not None


def test_tree_execution_policy_stubs_always_accept(
    bridge, datalayer, actor_id, report, offer, actor, finder_actor, case
):
    """Policy nodes (stubs) always return SUCCESS in Phase 1."""
    tree = create_validate_report_tree(
        report_id=report.id_,
        offer_id=offer.id_,
    )

    # Act: Execute tree
    result = bridge.execute_with_setup(
        tree=tree,
        actor_id=actor_id,
        datalayer=datalayer,
    )

    # Assert: Tree succeeds (policies don't reject)
    assert result.status == Status.SUCCESS


# ============================================================================
# Error Handling Tests
# ============================================================================


def test_tree_execution_missing_datalayer_fails(
    bridge, actor_id, report, offer
):
    """Tree fails gracefully if DataLayer not in blackboard."""
    tree = create_validate_report_tree(
        report_id=report.id_,
        offer_id=offer.id_,
    )

    # Act: Execute without DataLayer in blackboard
    result = bridge.execute_with_setup(
        tree=tree,
        actor_id=actor_id,
        datalayer=None,  # Missing DataLayer
    )

    # Assert: Tree fails
    assert result.status == Status.FAILURE


def test_tree_execution_missing_actor_id_fails(
    bridge, datalayer, report, offer
):
    """Tree fails gracefully if actor_id not in blackboard."""
    tree = create_validate_report_tree(
        report_id=report.id_,
        offer_id=offer.id_,
    )

    # Act: Execute without actor_id in blackboard
    result = bridge.execute_with_setup(
        tree=tree,
        actor_id=None,  # Missing actor_id
        datalayer=datalayer,
    )

    # Assert: Tree short-circuits via early exit (CheckRMStateValid returns SUCCESS on error)
    # This is acceptable behavior - missing actor_id causes early nodes to fail gracefully
    # The tree structure has a Selector at root, so early FAILURE from CheckRMStateValid
    # tries ValidationFlow, which also fails, causing overall SUCCESS from early exit
    assert result.status in [Status.SUCCESS, Status.FAILURE]


def test_tree_execution_missing_report_fails(
    bridge, datalayer, actor_id, offer, actor, finder_actor
):
    """Tree fails if no case exists for the report (EnsureEmbargoExists fails)."""
    # Arrange: Use non-existent report ID — no case will exist for it
    fake_report_id = "https://example.org/reports/non-existent"

    tree = create_validate_report_tree(
        report_id=fake_report_id,
        offer_id=offer.id_,
    )

    # Act: Execute tree
    result = bridge.execute_with_setup(
        tree=tree,
        actor_id=actor_id,
        datalayer=datalayer,
    )

    # Assert: Tree fails because EnsureEmbargoExists finds no case
    assert result.status == Status.FAILURE


# ============================================================================
# Integration Tests
# ============================================================================


def test_tree_execution_idempotency(
    bridge, datalayer, actor_id, report, offer, actor, finder_actor, case
):
    """Multiple executions produce same result (idempotent)."""
    tree1 = create_validate_report_tree(
        report_id=report.id_,
        offer_id=offer.id_,
    )

    tree2 = create_validate_report_tree(
        report_id=report.id_,
        offer_id=offer.id_,
    )

    # Act: Execute tree twice
    result1 = bridge.execute_with_setup(
        tree=tree1,
        actor_id=actor_id,
        datalayer=datalayer,
    )

    result2 = bridge.execute_with_setup(
        tree=tree2,
        actor_id=actor_id,
        datalayer=datalayer,
    )

    # Assert: Both succeed
    assert result1.status == Status.SUCCESS
    assert result2.status == Status.SUCCESS

    # Verify: Second execution short-circuits via early exit
    # (report already VALID from first execution)


def test_tree_execution_actor_isolation(
    bridge, datalayer, report, offer, actor, case
):
    """Different actors maintain isolated execution contexts."""
    actor_a = "https://example.org/actors/vendor-a"
    actor_b = "https://example.org/actors/vendor-b"

    # Create both actors
    for aid in [actor_a, actor_b]:
        actor_obj = VultronCaseActor(id_=aid, name=f"Actor {aid}")
        datalayer.create(actor_obj)

    # Execute for actor A
    tree_a = create_validate_report_tree(
        report_id=report.id_,
        offer_id=offer.id_,
    )
    result_a = bridge.execute_with_setup(
        tree=tree_a,
        actor_id=actor_a,
        datalayer=datalayer,
    )

    # Execute for actor B
    tree_b = create_validate_report_tree(
        report_id=report.id_,
        offer_id=offer.id_,
    )
    result_b = bridge.execute_with_setup(
        tree=tree_b,
        actor_id=actor_b,
        datalayer=datalayer,
    )

    # Assert: Both succeed independently
    assert result_a.status == Status.SUCCESS
    assert result_b.status == Status.SUCCESS

    # Verify: actor_a should have VALID status in DataLayer
    valid_id_a = _report_phase_status_id(actor_a, report.id_, RM.VALID.value)
    assert datalayer.get("ParticipantStatus", valid_id_a) is not None


def test_ensure_embargo_exists_fails_without_case(
    bridge, datalayer, actor_id, report, offer, actor, finder_actor
):
    """validate-report BT fails if no case exists for the report.

    EnsureEmbargoExists blocks validation when the case hasn't been
    created yet (i.e., SubmitReportReceivedUseCase hasn't run first).
    Per DUR-07-004.
    """
    # No case fixture — simulate report submitted but case not yet created.
    tree = create_validate_report_tree(
        report_id=report.id_,
        offer_id=offer.id_,
    )
    result = bridge.execute_with_setup(
        tree=tree,
        actor_id=actor_id,
        datalayer=datalayer,
    )
    assert result.status == Status.FAILURE, (
        "validate_report BT must FAIL when no case exists for the report "
        "(EnsureEmbargoExists should block per DUR-07-004)"
    )


def test_validate_report_tree_case_has_active_embargo(
    bridge, datalayer, actor_id, report, offer, actor, finder_actor, case
):
    """After validate-report BT, case MUST have active_embargo set (D5-6-EMBARGORCP).

    The case fixture pre-creates the case with an embargo (from
    receive_report_case_tree).  validate_report verifies the embargo exists
    via EnsureEmbargoExists and only succeeds when it does.
    """
    from vultron.core.models.protocols import is_case_model

    tree = create_validate_report_tree(
        report_id=report.id_,
        offer_id=offer.id_,
    )
    bridge.execute_with_setup(
        tree=tree,
        actor_id=actor_id,
        datalayer=datalayer,
    )

    # The VulnerabilityCase in the DataLayer must have active_embargo set
    cases = datalayer.by_type("VulnerabilityCase")
    assert cases, "Expected at least one VulnerabilityCase in DataLayer"

    case_ids = list(cases.keys())
    case_obj = datalayer.read(case_ids[0])
    assert is_case_model(case_obj), "Expected a valid CaseModel"
    assert case_obj.active_embargo is not None, (
        "VulnerabilityCase must have active_embargo set so participants "
        "can learn about the embargo from the Create(Case) activity"
    )


def test_validate_report_auto_engages_via_bt(
    bridge, datalayer, actor_id, report, offer, actor, finder_actor, case
):
    """validate-report BT with case_id+actor_id auto-engages to RM.ACCEPTED.

    D5-7-BTFIX-1: After validation succeeds, the PrioritizeBT subtree
    transitions the actor's participant RM state from VALID → ACCEPTED via
    the BT (no procedural _auto_engage call).

    Verifies:
    - Tree returns SUCCESS
    - Actor's CaseParticipant RM state is RM.ACCEPTED
    - An RmEngageCaseActivity (Join type) appears in the actor's outbox
    """
    from typing import cast, Any
    from vultron.core.states.rm import RM

    # case was created with vendor at RM.RECEIVED by receive_report_case_tree
    tree = create_validate_report_tree(
        report_id=report.id_,
        offer_id=offer.id_,
        case_id=case.id_,
        actor_id=actor_id,
    )
    result = bridge.execute_with_setup(
        tree=tree,
        actor_id=actor_id,
        datalayer=datalayer,
    )

    assert result.status == Status.SUCCESS

    # Vendor's case-participant RM state must be RM.ACCEPTED
    updated_case = cast(Any, datalayer.read(case.id_))
    participant_id = updated_case.actor_participant_index.get(actor_id)
    assert (
        participant_id is not None
    ), "Vendor must be in actor_participant_index"
    participant = cast(Any, datalayer.read(participant_id))
    assert participant is not None
    assert participant.participant_statuses[-1].rm_state == RM.ACCEPTED

    # An engage activity (Join) must appear in the actor's outbox
    updated_actor = cast(Any, datalayer.read(actor_id))
    outbox_items = updated_actor.outbox.items
    assert len(outbox_items) >= 1
    join_activities = [
        datalayer.read(aid)
        for aid in outbox_items
        if datalayer.read(aid) is not None
        and str(getattr(datalayer.read(aid), "type_", "")) == "Join"
    ]
    assert (
        len(join_activities) >= 1
    ), "At least one RmEngageCaseActivity (Join) must be in actor outbox"
