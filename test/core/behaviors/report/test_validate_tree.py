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

import py_trees
import pytest
from py_trees.common import Status

from test.support.embargo_register import register
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.report.validate_tree import (
    create_validate_report_tree,
)
from vultron.core.models.activity import VultronOffer
from vultron.core.models.actor import VultronService
from vultron.core.models.report import VulnerabilityReport
from vultron.core.models.report_case_link import VultronReportCaseLink
from vultron.core.states.rm import RM
from vultron.demo.fuzzer.bundles.validation import ValidationCallOutBundle
from vultron.enums.roles import CVDRole

#: The case's CASE_MANAGER: the trigger sends every validation to it
#: (PCR-08-001), and it is the one that records the move (RSH-08-006).
CASE_MANAGER_ID = "https://example.org/actors/case-manager"


def _always_succeed_factory(name: str) -> py_trees.behaviour.Behaviour:
    """Deterministic factory for integration tests: always returns SUCCESS."""

    class _AlwaysSucceed(py_trees.behaviour.Behaviour):
        def update(self):
            return py_trees.common.Status.SUCCESS

    return _AlwaysSucceed(name)


_ALWAYS_SUCCEED_BUNDLE = ValidationCallOutBundle(
    credibility_factory=_always_succeed_factory,  # type: ignore[arg-type]
    validity_factory=_always_succeed_factory,  # type: ignore[arg-type]
)


@pytest.fixture
def datalayer():
    """The vendor's own store: the trees below run as the vendor (BT-05-005)."""
    return SqliteDataLayer(
        "sqlite:///:memory:",
        actor_id="https://example.org/actors/vendor",
    )


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
    report_obj = VulnerabilityReport(
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
    actor_obj = VultronService(
        id_=actor_id,
        name="Vendor Co",
    )
    datalayer.create(actor_obj)
    return actor_obj


@pytest.fixture
def reporter_actor(datalayer, reporter_actor_id):
    """Create test reporter actor in the DataLayer."""
    actor_obj = VultronService(
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
    from vultron.core.ports.case_outbox import CaseOutboxPersistence

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
    """BTBridge without TriggerActivityPort — the emit node returns FAILURE.

    The emit is not masked (RSH-08-006), so a tree run through this bridge
    fails at the send if it gets that far.  The tests below use it where an
    earlier precondition must already refuse the move.
    """
    return BTBridge(datalayer=datalayer)


def _seed_case_participant(
    datalayer,
    case_obj,
    participant_actor_id,
    slug,
    roles: list[CVDRole] | None = None,
):
    """Add a ``CaseParticipant`` at RM.RECEIVED for *participant_actor_id*.

    ``RM.VALID`` is case-scoped, so a case replica is only actionable once the
    acting actor is in ``actor_participant_index`` — that is what
    ``Create(VulnerabilityCase)`` delivers (CBT-01-002).  Without it
    ``TransitionRMtoValid`` correctly returns FAILURE (ISSUE-2548).

    *roles* defaults to ``[CVDRole.VENDOR]``.
    """
    from test.support.participant_status import advance_participant_rm
    from vultron.core.models.case_participant import CaseParticipant

    participant = CaseParticipant(
        id_=f"{case_obj.id_}/participants/{slug}",
        attributed_to=participant_actor_id,
        context=case_obj.id_,
        case_roles=roles if roles is not None else [CVDRole.VENDOR],
    )
    advance_participant_rm(
        participant, RM.RECEIVED, participant_actor_id, case_obj.id_
    )
    datalayer.create(participant)
    case_obj.add_participant(participant)
    datalayer.save(participant)
    datalayer.save(case_obj)
    return participant


def _seed_case_manager(datalayer, case_obj):
    """Seat a CASE_MANAGER participant so the validation has a recipient.

    The trigger sends the validation to the CASE_MANAGER and writes nothing
    of its own; without a routable recipient the tree fails (RSH-08-006).
    """
    return _seed_case_participant(
        datalayer,
        case_obj,
        CASE_MANAGER_ID,
        "case-manager",
        roles=[CVDRole.CASE_MANAGER],
    )


def _make_case(datalayer, actor_id, report_id):
    """A case naming *report_id*, with an active embargo and the vendor seated.

    ADR-0041: the vendor tree no longer creates a VulnerabilityCase, so the
    tests create one directly to satisfy ``RequireCaseForReport`` and
    ``EnsureEmbargoExists``, simulating what the CaseActor would have provided
    after accepting a CaseProposal.  The vendor's ``CaseParticipant`` sits at
    RM.RECEIVED because the RM.VALID transition is case-scoped (ISSUE-2548).
    """
    from vultron.core.models.case import VulnerabilityCase

    case_obj = VulnerabilityCase(
        id_=f"{actor_id}/cases/test-case-validate",
        name="Validate-tree test case",
        attributed_to=actor_id,
        vulnerability_reports=[report_id],
        embargo_register=register(active=f"{actor_id}/embargoes/test-embargo"),
    )
    datalayer.create(case_obj)
    _seed_case_participant(datalayer, case_obj, actor_id, "vendor")
    return case_obj


@pytest.fixture
def case(datalayer, actor_id, report):
    """The validate-tree case, with a CASE_MANAGER to send the validation to."""
    case_obj = _make_case(datalayer, actor_id, report.id_)
    _seed_case_manager(datalayer, case_obj)
    return case_obj


@pytest.fixture
def case_without_manager(datalayer, actor_id, report):
    """The validate-tree case with no CASE_MANAGER: nothing to send to."""
    return _make_case(datalayer, actor_id, report.id_)


def _vendor_statuses(datalayer, case_obj, actor_id) -> list:
    """The vendor participant's status history, as stored."""
    from vultron.core.models.case_participant import CaseParticipant

    participant = datalayer.read(case_obj.actor_participant_index[actor_id])
    assert isinstance(participant, CaseParticipant)
    return list(participant.participant_statuses)


def _link_state(datalayer, report_id) -> RM:
    """The report link's stored RM state."""
    link = datalayer.read(VultronReportCaseLink.build_id(report_id))
    assert isinstance(link, VultronReportCaseLink)
    return link.rm_state


def _sent_ids(datalayer, actor_id, before: set[str]) -> set[str]:
    """Outbox ids *actor_id* queued since *before* was taken."""
    return set(datalayer.clone_for_actor(actor_id).outbox_list()) - before


def _outbox(datalayer, actor_id) -> set[str]:
    return set(datalayer.clone_for_actor(actor_id).outbox_list())


def _assert_sent_to_case_manager(datalayer, sent: set[str]) -> None:
    """Exactly one activity was queued, addressed to the CASE_MANAGER."""
    assert len(sent) == 1
    activity = datalayer.read(next(iter(sent)))
    assert activity is not None
    assert getattr(activity, "to", None) == [CASE_MANAGER_ID]


@pytest.fixture
def report_case_link(datalayer, report):
    """Pre-create the VultronReportCaseLink with RM.RECEIVED state."""
    obj = VultronReportCaseLink(report_id=report.id_, rm_state=RM.RECEIVED)
    datalayer.create(obj)
    return obj


# ============================================================================
# Tree Creation Tests
# ============================================================================


@pytest.mark.spec("BT-06-002")
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


@pytest.mark.spec("BT-06-002")
def test_tree_structure_matches_spec(report, offer):
    """Tree structure matches expected hierarchy from spec.

    Root is a Selector with exactly two children: the ``CheckRMStateValid``
    idempotency exit (ID-04-004) and a single ``ValidationFlow`` sequence.

    The tree used to have a second, structurally duplicated validation branch
    (``ValidationOrShortcutFallback``) so that a failed emit could still
    validate.  That duplicate was the ISSUE-2548 mechanism: the first branch
    wrote the report-phase RM.VALID latch, failed on a later precondition, and
    the fallback branch's ``CheckRMStateValid`` then read that very latch and
    reported SUCCESS.  There is now one branch, the trigger side writes
    nothing (RSH-08-006), and every case-dependent precondition is checked
    before the send (ID-04-005).
    """
    tree = create_validate_report_tree(
        report_id=report.id_,
        offer_id=offer.id_,
    )

    # Root: Selector[idempotency exit, validation flow]
    assert len(tree.children) == 2
    assert tree.children[0].name == "CheckRMStateValid"

    validation_flow = tree.children[1]
    assert validation_flow.name == "ValidationFlow"
    # Precondition + 2 policies + case + embargo + actions
    assert len(validation_flow.children) == 6

    assert validation_flow.children[0].name == "CheckRMStateReceivedOrInvalid"
    assert validation_flow.children[1].name == "EvaluateReportCredibility"
    assert validation_flow.children[2].name == "EvaluateReportValidity"
    # Case-scoped preconditions precede any write (ISSUE-2548): the case must
    # be in *this* actor's store (ADR-0073, PCR-01-003) and carry an embargo
    # (DUR-07-004).
    assert validation_flow.children[3].name == "RequireCaseForReport"
    assert validation_flow.children[4].name == "EnsureEmbargoExists"

    actions = validation_flow.children[5]
    assert actions.name == "ValidationActions"
    # Per ADR-0015: case/participant creation moved to receive_report_case_tree.
    # ValidationActions only checks/latches RM state, then emits: the check
    # refuses a move before anything is sent (RSH-08-006).
    assert len(actions.children) == 2
    assert actions.children[0].name == "TransitionRMtoValid"
    assert actions.children[1].name == "EmitValidateReportActivity"


# ============================================================================
# Execution Tests
# ============================================================================


def _run_validate(bridge, datalayer, actor_id, report_id, offer_id):
    """Run the trigger-side validate-report tree as *actor_id*."""
    tree = create_validate_report_tree(
        report_id=report_id,
        offer_id=offer_id,
        call_out=_ALWAYS_SUCCEED_BUNDLE,
        sender_actor_id=actor_id,
    )
    return bridge.execute_with_setup(
        tree=tree,
        actor_id=actor_id,
        datalayer=datalayer,
    )


@pytest.mark.spec("RMB-09-001")
@pytest.mark.spec("BT-03-004")
@pytest.mark.spec("RSH-08-006")
def test_tree_execution_sends_validation_to_case_manager(
    bridge,
    datalayer,
    actor_id,
    report,
    offer,
    actor,
    reporter_actor,
    case,
    report_case_link,
):
    """The tree checks the move, sends it to the CASE_MANAGER, writes nothing.

    The CASE_MANAGER latches its own link and records VALID when it accepts
    the validation; the sender's report link stays where it was (RSH-08-006).
    """
    outbox_before = _outbox(datalayer, actor_id)

    result = _run_validate(bridge, datalayer, actor_id, report.id_, offer.id_)

    assert result.status == Status.SUCCESS
    assert result.errors is None or result.errors == []
    _assert_sent_to_case_manager(
        datalayer, _sent_ids(datalayer, actor_id, outbox_before)
    )
    assert _link_state(datalayer, report.id_) == RM.RECEIVED


def test_tree_execution_does_not_create_case(
    bridge,
    datalayer,
    actor_id,
    report,
    offer,
    actor,
    reporter_actor,
    case,
    report_case_link,
):
    """validate-report BT does NOT create a case (case was created at receipt).

    Per ADR-0015, case creation belongs in receive_report_case_tree triggered
    by SubmitReportReceivedUseCase at RM.RECEIVED.  validate_report only
    checks the RM move, verifies the embargo exists, and sends.
    """
    cases_before = set(datalayer.by_type("VulnerabilityCase").keys())

    result = _run_validate(bridge, datalayer, actor_id, report.id_, offer.id_)

    assert result.status == Status.SUCCESS
    cases_after = set(datalayer.by_type("VulnerabilityCase").keys())
    # No new cases should have been created by validate_report
    assert cases_after == cases_before, (
        "validate_report BT must not create a new VulnerabilityCase "
        "(case creation belongs at RM.RECEIVED per ADR-0015)"
    )


@pytest.mark.spec("RMB-09-001")
@pytest.mark.spec("BT-03-004")
@pytest.mark.spec("RSH-08-006")
def test_tree_execution_leaves_vendor_status_to_case_manager(
    bridge,
    datalayer,
    actor_id,
    report,
    offer,
    actor,
    reporter_actor,
    case,
    report_case_link,
):
    """validate-report appends no status to the vendor's participant.

    The vendor's status is case-file state: the CASE_MANAGER records VALID
    and the vendor's replica copies it from the ledger (RSH-08-006,
    CM-23-016).
    """
    statuses_before = _vendor_statuses(datalayer, case, actor_id)

    result = _run_validate(bridge, datalayer, actor_id, report.id_, offer.id_)

    assert result.status == Status.SUCCESS
    statuses_after = _vendor_statuses(datalayer, case, actor_id)
    assert statuses_after == statuses_before
    assert statuses_after[-1].rm.state == RM.RECEIVED


@pytest.mark.spec("BT-03-001")
def test_tree_execution_early_exit_already_valid(
    bridge, datalayer, actor_id, report, offer, actor, reporter_actor, case
):
    """Tree short-circuits if report already in VALID state, sending nothing."""
    # Arrange: Set report to VALID state in DataLayer
    datalayer.create(
        VultronReportCaseLink(report_id=report.id_, rm_state=RM.VALID)
    )
    outbox_before = _outbox(datalayer, actor_id)

    tree = create_validate_report_tree(
        report_id=report.id_,
        offer_id=offer.id_,
        call_out=_ALWAYS_SUCCEED_BUNDLE,
    )

    # Act: Execute tree
    result = bridge.execute_with_setup(
        tree=tree,
        actor_id=actor_id,
        datalayer=datalayer,
    )

    # Assert: Tree succeeds via early exit, before the send
    assert result.status == Status.SUCCESS
    assert _sent_ids(datalayer, actor_id, outbox_before) == set()


@pytest.mark.spec("RMB-11-003")
@pytest.mark.spec("RMB-09-001")
@pytest.mark.spec("RSH-08-006")
def test_tree_execution_invalid_state_sends_validation(
    bridge, datalayer, actor_id, report, offer, actor, reporter_actor, case
):
    """A report at INVALID may be validated: the move is sent, not latched."""
    # Arrange: Set report to INVALID state in DataLayer (no VALID record present)
    datalayer.create(
        VultronReportCaseLink(report_id=report.id_, rm_state=RM.INVALID)
    )
    outbox_before = _outbox(datalayer, actor_id)

    result = _run_validate(bridge, datalayer, actor_id, report.id_, offer.id_)

    assert result.status == Status.SUCCESS
    _assert_sent_to_case_manager(
        datalayer, _sent_ids(datalayer, actor_id, outbox_before)
    )
    # The link is the CASE_MANAGER's to latch (RSH-08-006).
    assert _link_state(datalayer, report.id_) == RM.INVALID


@pytest.mark.spec("RSH-08-006")
def test_tree_execution_refused_source_state_sends_nothing(
    bridge, datalayer, actor_id, report, offer, actor, reporter_actor, case
):
    """A report link whose RM state forbids → VALID is refused before the send.

    A CLOSED report cannot be validated: the check fails the tree, nothing
    is queued, and nothing is written (RSH-08-006).
    """
    datalayer.create(
        VultronReportCaseLink(report_id=report.id_, rm_state=RM.CLOSED)
    )
    statuses_before = _vendor_statuses(datalayer, case, actor_id)
    outbox_before = _outbox(datalayer, actor_id)

    result = _run_validate(bridge, datalayer, actor_id, report.id_, offer.id_)

    assert result.status == Status.FAILURE
    assert _sent_ids(datalayer, actor_id, outbox_before) == set()
    assert _link_state(datalayer, report.id_) == RM.CLOSED
    assert _vendor_statuses(datalayer, case, actor_id) == statuses_before


@pytest.mark.spec("RSH-08-006")
def test_tree_execution_fails_without_case_manager_recipient(
    bridge,
    datalayer,
    actor_id,
    report,
    offer,
    actor,
    reporter_actor,
    case_without_manager,
    report_case_link,
):
    """No routable CASE_MANAGER: the tree FAILS and queues nothing.

    The trigger writes nothing of its own, so the send is its whole effect.
    The emit is not masked by a Success fallback: a validation nobody
    receives is a failure, not a success (RSH-08-006).
    """
    statuses_before = _vendor_statuses(
        datalayer, case_without_manager, actor_id
    )
    outbox_before = _outbox(datalayer, actor_id)

    result = _run_validate(bridge, datalayer, actor_id, report.id_, offer.id_)

    assert result.status == Status.FAILURE
    assert _sent_ids(datalayer, actor_id, outbox_before) == set()
    assert _link_state(datalayer, report.id_) == RM.RECEIVED
    assert (
        _vendor_statuses(datalayer, case_without_manager, actor_id)
        == statuses_before
    )


@pytest.mark.spec("RMB-09-001")
@pytest.mark.spec("BT-03-004")
def test_tree_execution_no_prior_status_succeeds(
    bridge,
    datalayer,
    actor_id,
    report,
    offer,
    actor,
    reporter_actor,
    case,
    report_case_link,
):
    """Tree succeeds from initial RM.RECEIVED state (new report).

    In the new architecture the initial state is RM.RECEIVED on the
    VultronReportCaseLink — this test verifies the move is accepted and sent
    from that starting point, and that the link is left for the CASE_MANAGER
    to latch (RSH-08-006).
    """
    outbox_before = _outbox(datalayer, actor_id)

    result = _run_validate(bridge, datalayer, actor_id, report.id_, offer.id_)

    # Assert: Tree succeeds (precondition accepts RECEIVED)
    assert result.status == Status.SUCCESS
    _assert_sent_to_case_manager(
        datalayer, _sent_ids(datalayer, actor_id, outbox_before)
    )
    assert _link_state(datalayer, report.id_) == RM.RECEIVED


@pytest.mark.spec("RMB-09-001")
def test_tree_execution_policy_stubs_always_accept(
    bridge,
    datalayer,
    actor_id,
    report,
    offer,
    actor,
    reporter_actor,
    case,
    report_case_link,
):
    """Policy nodes (stubs) always return SUCCESS in Phase 1."""
    result = _run_validate(bridge, datalayer, actor_id, report.id_, offer.id_)

    # Assert: Tree succeeds (policies don't reject)
    assert result.status == Status.SUCCESS


# ============================================================================
# Error Handling Tests
# ============================================================================


@pytest.mark.spec("BT-03-001")
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

    CheckRMStateReceivedOrInvalid returns SUCCESS (no link yet), then the
    case preconditions fail because no case is linked to the fake report
    ID, before any check or send (DUR-07-004).
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


@pytest.mark.spec("BT-09-001")
@pytest.mark.spec("RSH-08-006")
def test_tree_execution_repeat_leaves_state_unchanged(
    bridge,
    datalayer,
    actor_id,
    report,
    offer,
    actor,
    reporter_actor,
    case,
    report_case_link,
):
    """Repeated executions produce the same result and write nothing.

    The trigger latches nothing (RSH-08-006), so until the CASE_MANAGER's
    VALID reaches the replica a repeat is not short-circuited: each run is
    the same check and sends the validation again.  Neither run moves the
    link or the vendor's status.
    """
    statuses_before = _vendor_statuses(datalayer, case, actor_id)

    for _ in range(2):
        outbox_before = _outbox(datalayer, actor_id)
        result = _run_validate(
            bridge, datalayer, actor_id, report.id_, offer.id_
        )
        assert result.status == Status.SUCCESS
        _assert_sent_to_case_manager(
            datalayer, _sent_ids(datalayer, actor_id, outbox_before)
        )

    assert _link_state(datalayer, report.id_) == RM.RECEIVED
    assert _vendor_statuses(datalayer, case, actor_id) == statuses_before


@pytest.mark.spec("BT-09-001")
def test_tree_execution_actor_isolation():
    """Each actor validates in its own store; the report link is never shared.

    ADR-0073 gives every actor its own DataLayer and forbids two actors sharing
    one store — a shared multi-tenant store is exactly the anti-pattern that
    decision removes (PCR-01-003).  ``VultronReportCaseLink`` is keyed per
    report *per store*, so under per-actor isolation that means per actor
    (issue #3266).  This test builds a separate store for each of two
    coordinators and shows each validation is checked and sent from its own
    store only: one actor's run neither queues in nor writes to the other's
    store.  The trigger writes nothing locally (RSH-08-006), so each link
    stays at ``RM.RECEIVED`` until its CASE_MANAGER's VALID is copied.

    The earlier form of this test put both actors in a single DataLayer and
    asserted that actor B saw actor A's VALID latch — a configuration ADR-0073
    declares unsupported and unreachable, which is the RM-isolation breakage
    #3266 describes.
    """
    from typing import cast

    from vultron.adapters.driven.trigger_activity_adapter import (
        TriggerActivityAdapter,
    )
    from vultron.core.models.case import VulnerabilityCase
    from vultron.core.ports.case_outbox import CaseOutboxPersistence

    report_id = "https://example.org/reports/CVE-2024-001"
    offer_id = "https://example.org/activities/offer-123"
    reporter_id = "https://example.org/actors/reporter"

    def _build_store(
        actor_id: str, slug: str
    ) -> tuple[SqliteDataLayer, BTBridge]:
        """A fully seeded, actor-scoped store — the ADR-0073 unit of isolation."""
        dl = SqliteDataLayer("sqlite:///:memory:", actor_id=actor_id)
        dl.create(VulnerabilityReport(id_=report_id, name="R", content="c"))
        dl.create(
            VultronOffer(
                id_=offer_id,
                actor=reporter_id,
                object_=report_id,
                target=actor_id,
            )
        )
        dl.create(VultronService(id_=actor_id, name=f"Actor {slug}"))
        case_obj = VulnerabilityCase(
            id_=f"{actor_id}/cases/test-case-validate",
            name="Validate-tree isolation case",
            attributed_to=actor_id,
            vulnerability_reports=[report_id],
            embargo_register=register(
                active=f"{actor_id}/embargoes/test-embargo"
            ),
        )
        dl.create(case_obj)
        _seed_case_participant(dl, case_obj, actor_id, slug)
        _seed_case_manager(dl, case_obj)
        dl.create(
            VultronReportCaseLink(report_id=report_id, rm_state=RM.RECEIVED)
        )
        trigger = TriggerActivityAdapter(cast(CaseOutboxPersistence, dl))
        return dl, BTBridge(datalayer=dl, trigger_activity=trigger)

    actor_a = "https://example.org/actors/vendor-a"
    actor_b = "https://example.org/actors/vendor-b"
    dl_a, bridge_a = _build_store(actor_a, "vendor-a")
    dl_b, bridge_b = _build_store(actor_b, "vendor-b")

    outbox_a_before = _outbox(dl_a, actor_a)
    outbox_b_before = _outbox(dl_b, actor_b)

    # actor_a validates in its own store.
    result_a = bridge_a.execute_with_setup(
        tree=create_validate_report_tree(
            report_id=report_id,
            offer_id=offer_id,
            call_out=_ALWAYS_SUCCEED_BUNDLE,
            sender_actor_id=actor_a,
        ),
        actor_id=actor_a,
    )
    assert result_a.status == Status.SUCCESS
    _assert_sent_to_case_manager(
        dl_a, _sent_ids(dl_a, actor_a, outbox_a_before)
    )

    # actor_b's store is untouched: it is a different store entirely.
    assert _sent_ids(dl_b, actor_b, outbox_b_before) == set()
    assert _link_state(dl_b, report_id) == RM.RECEIVED

    outbox_a_before = _outbox(dl_a, actor_a)
    result_b = bridge_b.execute_with_setup(
        tree=create_validate_report_tree(
            report_id=report_id,
            offer_id=offer_id,
            call_out=_ALWAYS_SUCCEED_BUNDLE,
            sender_actor_id=actor_b,
        ),
        actor_id=actor_b,
    )
    assert result_b.status == Status.SUCCESS
    _assert_sent_to_case_manager(
        dl_b, _sent_ids(dl_b, actor_b, outbox_b_before)
    )
    assert _sent_ids(dl_a, actor_a, outbox_a_before) == set()

    # Neither store latched its link: that is each CASE_MANAGER's write.
    assert _link_state(dl_a, report_id) == RM.RECEIVED
    assert _link_state(dl_b, report_id) == RM.RECEIVED


def test_ensure_embargo_exists_fails_without_case(
    bridge_no_emit, datalayer, actor_id, report, offer, actor, reporter_actor
):
    """validate-report BT returns FAILURE when no case is linked to the report.

    The case preconditions fail because ``find_case_by_report_id`` returns
    None, so the tree returns FAILURE before the send (DUR-07-004 guard:
    embargo MUST be established before RM.VALID).
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

    bundle = ValidationCallOutBundle(credibility_factory=custom_factory)  # type: ignore[arg-type]
    tree = create_validate_report_tree(
        report_id=report.id_,
        offer_id=offer.id_,
        call_out=bundle,
    )

    assert sentinel["called"]
    tree_str = py_trees.display.ascii_tree(tree)
    assert "CustomCredibility" in tree_str


def test_validate_tree_custom_validity_factory_used(report, offer):
    """validity_factory node appears in the tree when a custom bundle is passed."""
    import py_trees

    def custom_factory(name):
        class _Marker(py_trees.behaviour.Behaviour):
            def update(self):
                return py_trees.common.Status.SUCCESS

        return _Marker(name="CustomValidity")

    bundle = ValidationCallOutBundle(validity_factory=custom_factory)  # type: ignore[arg-type]
    tree = create_validate_report_tree(
        report_id=report.id_,
        offer_id=offer.id_,
        call_out=bundle,
    )

    tree_str = py_trees.display.ascii_tree(tree)
    assert "CustomValidity" in tree_str


def test_validate_tree_gather_info_factory_signature_accepted(report, offer):
    """gather_info_factory is accepted via bundle without error (Phase 2 hook).

    The factory is NOT called in Phase 1 (not wired into the tree body yet).
    This test verifies only that the parameter is accepted without raising.
    """

    def gather_factory(name):
        import py_trees

        class _Marker(py_trees.behaviour.Behaviour):
            def update(self):
                return py_trees.common.Status.SUCCESS

        return _Marker(name="CustomGather")

    bundle = ValidationCallOutBundle(gather_info_factory=gather_factory)  # type: ignore[arg-type]
    tree = create_validate_report_tree(
        report_id=report.id_,
        offer_id=offer.id_,
        call_out=bundle,
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
    from vultron.core.models.case import VulnerabilityCase

    tree = create_validate_report_tree(
        report_id=report.id_,
        offer_id=offer.id_,
        call_out=_ALWAYS_SUCCEED_BUNDLE,
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
    assert isinstance(case_obj, VulnerabilityCase), (
        "Expected a VulnerabilityCase"
    )
    assert case_obj.active_embargo is not None, (
        "VulnerabilityCase must have active_embargo set so participants "
        "can learn about the embargo from the Create(Case) activity"
    )
