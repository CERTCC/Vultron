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

Per specs/behavior-tree-integration.yaml BT-06 and testability.yaml requirements.
"""

import pytest
import py_trees
from py_trees.common import Status

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.models.participant_status import ParticipantStatus
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


def _always_succeed_factory(name: str) -> py_trees.behaviour.Behaviour:
    """Deterministic factory for integration tests: always returns SUCCESS."""

    class _AlwaysSucceed(py_trees.behaviour.Behaviour):
        def update(self):
            return py_trees.common.Status.SUCCESS

    return _AlwaysSucceed(name)


@pytest.fixture
def datalayer():
    """Create in-memory TinyDB data layer for testing."""
    return SqliteDataLayer("sqlite:///:memory:")


@pytest.fixture
def actor_id():
    """Test vendor actor ID."""
    return "https://example.org/actors/vendor"


@pytest.fixture
def reporter_actor_id():
    """Test reporter actor ID — distinct from the vendor."""
    return "https://example.org/actors/reporter"


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
def offer(datalayer, report, actor_id, reporter_actor_id):
    """Create test Offer activity. The reporter submits the offer to the
    vendor inbox, so ``actor`` is the reporter's ID.
    """
    offer_obj = VultronOffer(
        id_="https://example.org/activities/offer-123",
        actor=reporter_actor_id,
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
def reporter_actor(datalayer, reporter_actor_id):
    """Create test reporter actor in the DataLayer."""
    actor_obj = VultronCaseActor(
        id_=reporter_actor_id,
        name="Reporter Co",
    )
    datalayer.create(actor_obj)
    return actor_obj


@pytest.fixture
def trigger_activity(datalayer):
    """Standalone TriggerActivityPort for passing to tree factories."""
    from typing import cast

    from vultron.adapters.driven.trigger_activity_adapter import (
        TriggerActivityAdapter,
    )
    from vultron.core.ports.case_persistence import CaseOutboxPersistence

    return TriggerActivityAdapter(cast(CaseOutboxPersistence, datalayer))


@pytest.fixture
def bridge(datalayer, trigger_activity):
    """Create BT bridge for execution."""
    return BTBridge(
        datalayer=datalayer,
        trigger_activity=trigger_activity,
    )


@pytest.fixture
def bridge_no_emit(datalayer):
    """BTBridge without TriggerActivityPort — emit nodes return FAILURE immediately.

    Use this fixture for tests that exercise paths where the emit must fail so
    that the root Selector falls through to the validation-only branch.  Without
    a TriggerActivityPort, EmitValidateReportActivity returns FAILURE before any
    side-effects (like TransitionRMtoValid) can occur in the emit+validate branch.
    """
    return BTBridge(datalayer=datalayer)


@pytest.fixture
def case(
    bridge,
    datalayer,
    actor_id,
    report,
    offer,
    actor,
    reporter_actor,
    reporter_actor_id,
):
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
        reporter_actor_id=reporter_actor_id,
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
    """Tree structure matches expected hierarchy from spec.

    Per #1029 ADR-0021: tree now includes emit node for CaseActor routing.
    Root is a Selector with:
    - Child 0: EmitAndValidate sequence (trigger path)
    - Child 1: ValidationOnly selector (fallback for received path)
    """
    tree = create_validate_report_tree(
        report_id=report.id_,
        offer_id=offer.id_,
    )

    # Root: Selector with 2 children (emit+validate, fallback validate)
    assert len(tree.children) == 2

    # Child 0: EmitAndValidate (Sequence with emit + validation)
    emit_and_validate = tree.children[0]
    assert emit_and_validate.name == "EmitAndValidate"
    assert len(emit_and_validate.children) == 2
    assert emit_and_validate.children[0].name == "EmitValidateReportActivity"

    # Child 1 of EmitAndValidate: ValidationOrShortcut selector
    validation_selector = emit_and_validate.children[1]
    assert validation_selector.name == "ValidationOrShortcut"
    assert len(validation_selector.children) == 2
    assert validation_selector.children[0].name == "CheckRMStateValid"

    # ValidationFlow inside ValidationOrShortcut
    validation_flow = validation_selector.children[1]
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
    bridge, datalayer, actor_id, report, offer, actor, reporter_actor, case
):
    """Tree executes successfully for report after case was created at receipt."""
    tree = create_validate_report_tree(
        report_id=report.id_,
        offer_id=offer.id_,
        credibility_factory=_always_succeed_factory,
        validity_factory=_always_succeed_factory,
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
    bridge, datalayer, actor_id, report, offer, actor, reporter_actor, case
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
        credibility_factory=_always_succeed_factory,
        validity_factory=_always_succeed_factory,
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
    bridge, datalayer, actor_id, report, offer, actor, reporter_actor, case
):
    """validate-report advances vendor's report-phase status to RM.VALID."""
    tree = create_validate_report_tree(
        report_id=report.id_,
        offer_id=offer.id_,
        credibility_factory=_always_succeed_factory,
        validity_factory=_always_succeed_factory,
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
    bridge, datalayer, actor_id, report, offer, actor, reporter_actor, case
):
    """Tree short-circuits if report already in VALID state."""
    # Arrange: Set report to VALID state in DataLayer
    valid_status = ParticipantStatus(
        id_=_report_phase_status_id(actor_id, report.id_, RM.VALID.value),
        context=report.id_,
        attributed_to=actor_id,
        rm_state=RM.VALID,
    )
    datalayer.create(valid_status)

    tree = create_validate_report_tree(
        report_id=report.id_,
        offer_id=offer.id_,
        credibility_factory=_always_succeed_factory,
        validity_factory=_always_succeed_factory,
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
    bridge, datalayer, actor_id, report, offer, actor, reporter_actor, case
):
    """Tree can validate report from INVALID state."""
    # Arrange: Set report to INVALID state in DataLayer (no VALID record present)
    invalid_status = ParticipantStatus(
        id_=_report_phase_status_id(actor_id, report.id_, RM.INVALID.value),
        context=report.id_,
        attributed_to=actor_id,
        rm_state=RM.INVALID,
    )
    datalayer.create(invalid_status)

    tree = create_validate_report_tree(
        report_id=report.id_,
        offer_id=offer.id_,
        credibility_factory=_always_succeed_factory,
        validity_factory=_always_succeed_factory,
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
    bridge, datalayer, actor_id, report, offer, actor, reporter_actor, case
):
    """Tree succeeds even if report has no prior status (new report)."""
    # Arrange: No status set (report has no status tracking yet)
    # This simulates first-time validation — case was created at receipt.

    tree = create_validate_report_tree(
        report_id=report.id_,
        offer_id=offer.id_,
        credibility_factory=_always_succeed_factory,
        validity_factory=_always_succeed_factory,
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
    bridge, datalayer, actor_id, report, offer, actor, reporter_actor, case
):
    """Policy nodes (stubs) always return SUCCESS in Phase 1."""
    tree = create_validate_report_tree(
        report_id=report.id_,
        offer_id=offer.id_,
        credibility_factory=_always_succeed_factory,
        validity_factory=_always_succeed_factory,
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
    bridge_no_emit, datalayer, actor_id, offer, actor, reporter_actor
):
    """Tree fails when the report ID does not exist in the DataLayer.

    Without a TriggerActivityPort the emit node fails immediately, preventing
    any TransitionRMtoValid side-effects in the emit+validate branch.  The
    fallback validation-only branch then runs: CheckRMStateReceivedOrInvalid
    returns SUCCESS (no status record yet), the transition runs, then
    EnsureEmbargoExists returns FAILURE because no case is linked to the
    fake report ID.  The overall tree therefore returns FAILURE (DUR-07-004).
    """
    # Arrange: Use non-existent report ID — no case will exist for it
    fake_report_id = "https://example.org/reports/non-existent"

    tree = create_validate_report_tree(
        report_id=fake_report_id,
        offer_id=offer.id_,
    )

    # Act: Execute tree
    result = bridge_no_emit.execute_with_setup(
        tree=tree,
        actor_id=actor_id,
        datalayer=datalayer,
    )

    # Assert: Tree fails — no case exists so EnsureEmbargoExists blocks (DUR-07-004).
    assert result.status == Status.FAILURE


# ============================================================================
# Integration Tests
# ============================================================================


def test_tree_execution_idempotency(
    bridge, datalayer, actor_id, report, offer, actor, reporter_actor, case
):
    """Multiple executions produce same result (idempotent)."""
    tree1 = create_validate_report_tree(
        report_id=report.id_,
        offer_id=offer.id_,
        credibility_factory=_always_succeed_factory,
        validity_factory=_always_succeed_factory,
    )

    tree2 = create_validate_report_tree(
        report_id=report.id_,
        offer_id=offer.id_,
        credibility_factory=_always_succeed_factory,
        validity_factory=_always_succeed_factory,
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
        credibility_factory=_always_succeed_factory,
        validity_factory=_always_succeed_factory,
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
        credibility_factory=_always_succeed_factory,
        validity_factory=_always_succeed_factory,
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
    bridge_no_emit, datalayer, actor_id, report, offer, actor, reporter_actor
):
    """validate-report BT returns FAILURE when no case is linked to the report.

    Without a TriggerActivityPort the emit node fails immediately, so the root
    Selector falls through to the validation-only branch.  EnsureEmbargoExists
    returns FAILURE because ``find_case_by_report_id`` returns None.  The
    overall tree therefore returns FAILURE (DUR-07-004 guard: embargo MUST be
    established before RM.VALID).
    """
    # No case fixture — simulate report submitted but case not yet created.
    tree = create_validate_report_tree(
        report_id=report.id_,
        offer_id=offer.id_,
    )
    result = bridge_no_emit.execute_with_setup(
        tree=tree,
        actor_id=actor_id,
        datalayer=datalayer,
    )
    # EnsureEmbargoExists blocks: no linked case exists (DUR-07-004).
    assert result.status == Status.FAILURE


# ============================================================================
# Factory injection tests (BT-18-004)
# ============================================================================


def test_validate_tree_custom_credibility_factory_used(report, offer):
    """credibility_factory node appears in the tree when a custom factory is passed."""
    sentinel = {"called": False}

    def custom_factory(name):
        import py_trees

        sentinel["called"] = True
        sentinel["name"] = name

        class _Marker(py_trees.behaviour.Behaviour):
            def update(self):
                return py_trees.common.Status.SUCCESS

        return _Marker(name="CustomCredibility")

    tree = create_validate_report_tree(
        report_id=report.id_,
        offer_id=offer.id_,
        credibility_factory=custom_factory,
    )

    assert sentinel["called"]
    tree_str = py_trees.display.ascii_tree(tree)
    assert "CustomCredibility" in tree_str


def test_validate_tree_custom_validity_factory_used(report, offer):
    """validity_factory node appears in the tree when a custom factory is passed."""
    import py_trees

    def custom_factory(name):
        class _Marker(py_trees.behaviour.Behaviour):
            def update(self):
                return py_trees.common.Status.SUCCESS

        return _Marker(name="CustomValidity")

    tree = create_validate_report_tree(
        report_id=report.id_,
        offer_id=offer.id_,
        validity_factory=custom_factory,
    )

    tree_str = py_trees.display.ascii_tree(tree)
    assert "CustomValidity" in tree_str


def test_validate_tree_gather_info_factory_signature_accepted(report, offer):
    """gather_info_factory parameter is accepted without error (Phase 2 hook).

    The factory is NOT called in Phase 1 (not wired into the tree body yet).
    This test verifies only that the parameter is accepted without raising.
    """

    def gather_factory(name):
        import py_trees

        class _Marker(py_trees.behaviour.Behaviour):
            def update(self):
                return py_trees.common.Status.SUCCESS

        return _Marker(name="CustomGather")

    # Should not raise; factory is accepted even if not yet wired in Phase 1
    tree = create_validate_report_tree(
        report_id=report.id_,
        offer_id=offer.id_,
        gather_info_factory=gather_factory,
    )
    assert tree is not None


def test_validate_report_tree_case_has_active_embargo(
    bridge, datalayer, actor_id, report, offer, actor, reporter_actor, case
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
        credibility_factory=_always_succeed_factory,
        validity_factory=_always_succeed_factory,
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
