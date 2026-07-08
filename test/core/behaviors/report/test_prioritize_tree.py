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
Tests for case prioritization behavior trees (BT-2.1).

Verifies engage_case and defer_case trees correctly update the
CaseParticipant.participant_status RM state, reflecting the
participant-specific nature of the RM state machine.
"""

import pytest
from py_trees.common import Status

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.models.activity import VultronActivity
from vultron.core.models.base import VultronObject
from vultron.core.models.events import MessageSemantics
from vultron.core.models.events.case import (
    DeferCaseReceivedEvent,
    EngageCaseReceivedEvent,
)
from vultron.core.models.participant_status import ParticipantStatus
from vultron.core.models.vultron_types import (
    VultronCase,
    VultronCaseActor,
    VultronParticipant,
    VultronReport,
)
from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.report.prioritize_tree import (
    create_defer_case_tree,
    create_engage_case_tree,
    create_prioritize_subtree,
)
from vultron.core.states.rm import RM
from vultron.core.states.roles import CVDRole


def _make_participant_in_valid_state(
    id_: str, attributed_to: str, context: str
) -> VultronParticipant:
    """Create a VultronParticipant pre-seeded with RM.VALID status.

    engage_case and defer_case require the participant to be in VALID state
    (the precondition for VALID → ACCEPTED or VALID → DEFERRED transitions).
    """
    participant = VultronParticipant(
        id_=id_,
        attributed_to=attributed_to,
        context=context,
        participant_statuses=[
            ParticipantStatus(
                attributed_to=attributed_to,
                context=context,
                rm_state=RM.RECEIVED,
            ),
            ParticipantStatus(
                attributed_to=attributed_to,
                context=context,
                rm_state=RM.VALID,
            ),
        ],
    )
    return participant


def _make_engage_request(
    case: VultronCase, actor_id: str
) -> EngageCaseReceivedEvent:
    return EngageCaseReceivedEvent(
        activity_id=f"{case.id_}/activities/engage",
        actor_id=actor_id,
        object_=VultronObject(id_=case.id_),
        semantic_type=MessageSemantics.ENGAGE_CASE,
        activity=VultronActivity(
            type_="Announce",
            actor=f"{case.id_}/actor",
            object_=VultronCase(id_=case.id_),
            context=case.id_,
        ),
    )


def _make_defer_request(
    case: VultronCase, actor_id: str
) -> DeferCaseReceivedEvent:
    return DeferCaseReceivedEvent(
        activity_id=f"{case.id_}/activities/defer",
        actor_id=actor_id,
        object_=VultronObject(id_=case.id_),
        semantic_type=MessageSemantics.DEFER_CASE,
        activity=VultronActivity(
            type_="Announce",
            actor=f"{case.id_}/actor",
            object_=VultronCase(id_=case.id_),
            context=case.id_,
        ),
    )


@pytest.fixture
def datalayer():
    return SqliteDataLayer("sqlite:///:memory:")


@pytest.fixture
def actor_id():
    return "https://example.org/actors/vendor"


@pytest.fixture
def actor(datalayer, actor_id):
    obj = VultronCaseActor(id_=actor_id, name="Vendor Co")
    datalayer.create(obj)
    return obj


@pytest.fixture
def report(datalayer):
    obj = VultronReport(
        id_="https://example.org/reports/CVE-2024-001",
        name="Test Report",
        content="Buffer overflow",
    )
    datalayer.create(obj)
    return obj


@pytest.fixture
def case_with_participant(datalayer, actor_id, actor, report):
    """Case with the test actor as a CaseParticipant stored as a separate record.

    The participant is pre-seeded to RM.VALID so that engage/defer BTs can
    apply the VALID → ACCEPTED / VALID → DEFERRED transitions.
    """
    participant = _make_participant_in_valid_state(
        id_="https://example.org/participants/vendor-cp-001",
        attributed_to=actor_id,
        context="https://example.org/cases/case-001",
    )
    datalayer.create(participant)
    case = VultronCase(
        id_="https://example.org/cases/case-001",
        name="Test Case",
        vulnerability_reports=[report.id_],
        case_participants=[participant.id_],
    )
    datalayer.create(case)
    return case


@pytest.fixture
def case_without_participant(datalayer, report):
    """Case with no participants."""
    case = VultronCase(
        id_="https://example.org/cases/case-002",
        name="Test Case No Participants",
        vulnerability_reports=[report.id_],
        case_participants=[],
    )
    datalayer.create(case)
    return case


@pytest.fixture
def bridge(datalayer):
    from typing import cast

    from vultron.adapters.driven.trigger_activity_adapter import (
        TriggerActivityAdapter,
    )
    from vultron.core.ports.case_persistence import CaseOutboxPersistence

    return BTBridge(
        datalayer=datalayer,
        trigger_activity=TriggerActivityAdapter(
            cast(CaseOutboxPersistence, datalayer)
        ),
    )


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
def case_manager_actor_id():
    return "https://example.org/actors/coordinator"


@pytest.fixture
def case_with_manager(
    datalayer, actor_id, actor, report, case_manager_actor_id
):
    """Case with a vendor participant AND a CASE_MANAGER participant.

    The vendor participant is pre-seeded to RM.VALID so engage/defer BTs can
    apply the VALID → ACCEPTED / VALID → DEFERRED transitions.  The case
    manager participant is added to ``actor_participant_index`` so that
    ``ResolveCaseManagerNode`` can locate it (PCR-08-001).
    """
    vendor_participant = _make_participant_in_valid_state(
        id_="https://example.org/participants/vendor-cp-002",
        attributed_to=actor_id,
        context="https://example.org/cases/case-manager-001",
    )
    datalayer.create(vendor_participant)

    cm_actor = VultronCaseActor(id_=case_manager_actor_id, name="Coordinator")
    datalayer.create(cm_actor)

    cm_participant = VultronParticipant(
        id_="https://example.org/participants/coordinator-cp-001",
        attributed_to=case_manager_actor_id,
        context="https://example.org/cases/case-manager-001",
        case_roles=[CVDRole.CASE_MANAGER, CVDRole.COORDINATOR],
    )
    datalayer.create(cm_participant)

    case = VultronCase(
        id_="https://example.org/cases/case-manager-001",
        name="Test Case With Manager",
        vulnerability_reports=[report.id_],
        case_participants=[vendor_participant.id_, cm_participant.id_],
        actor_participant_index={
            actor_id: vendor_participant.id_,
            case_manager_actor_id: cm_participant.id_,
        },
    )
    datalayer.create(case)
    return case


# ============================================================================
# Tree structure tests
# ============================================================================


def test_create_engage_case_tree_returns_sequence(
    case_with_participant, actor_id
):
    tree = create_engage_case_tree(
        case_id=case_with_participant.id_, actor_id=actor_id
    )
    assert tree is not None
    assert tree.name == "EngageCaseBT"
    assert hasattr(tree, "children")
    assert len(tree.children) == 5


def test_create_defer_case_tree_returns_sequence(
    case_with_participant, actor_id
):
    tree = create_defer_case_tree(
        case_id=case_with_participant.id_, actor_id=actor_id
    )
    assert tree is not None
    assert tree.name == "DeferCaseBT"
    assert hasattr(tree, "children")
    assert len(tree.children) == 3


def test_engage_tree_node_names(case_with_participant, actor_id):
    tree = create_engage_case_tree(
        case_id=case_with_participant.id_, actor_id=actor_id
    )
    assert tree.children[0].name == "CheckParticipantExists"
    # Commit runs before effects (CLP-10-006)
    assert tree.children[1].name == "GuardedCommitCaseLedgerEntryBT"
    assert tree.children[2].name == "TransitionParticipantRMtoAccepted"


def test_defer_tree_node_names(case_with_participant, actor_id):
    tree = create_defer_case_tree(
        case_id=case_with_participant.id_, actor_id=actor_id
    )
    assert tree.children[0].name == "CheckParticipantExists"
    # Commit runs before effects (CLP-10-006)
    assert tree.children[1].name == "GuardedCommitCaseLedgerEntryBT"
    assert tree.children[2].name == "TransitionParticipantRMtoDeferred"


# ============================================================================
# Execution tests — engage_case
# ============================================================================


def test_engage_case_tree_success(
    bridge, datalayer, actor_id, case_with_participant
):
    """EngageCaseBT succeeds and sets participant RM to ACCEPTED."""
    request = _make_engage_request(case_with_participant, actor_id)
    tree = create_engage_case_tree(
        case_id=case_with_participant.id_, actor_id=actor_id
    )
    result = bridge.execute_with_setup(
        tree=tree, actor_id=actor_id, activity=request
    )

    assert result.status == Status.SUCCESS

    participant_id = "https://example.org/participants/vendor-cp-001"
    updated_participant = datalayer.read(participant_id)
    latest_status = updated_participant.participant_statuses[-1]
    assert latest_status.rm_state == RM.ACCEPTED


def test_engage_case_tree_fails_no_participant(
    bridge, datalayer, actor_id, case_without_participant
):
    """EngageCaseBT fails when actor has no CaseParticipant in the case."""
    request = _make_engage_request(case_without_participant, actor_id)
    tree = create_engage_case_tree(
        case_id=case_without_participant.id_, actor_id=actor_id
    )
    result = bridge.execute_with_setup(
        tree=tree, actor_id=actor_id, activity=request
    )

    assert result.status == Status.FAILURE


def test_engage_case_tree_fails_missing_case(bridge, datalayer, actor_id):
    """EngageCaseBT fails when the case does not exist in the datalayer."""
    case = VultronCase(
        id_="https://example.org/cases/nonexistent",
        name="Missing Case",
        vulnerability_reports=[],
        case_participants=[],
    )
    request = _make_engage_request(case, actor_id)
    tree = create_engage_case_tree(
        case_id="https://example.org/cases/nonexistent", actor_id=actor_id
    )
    result = bridge.execute_with_setup(
        tree=tree, actor_id=actor_id, activity=request
    )

    assert result.status == Status.FAILURE


# ============================================================================
# Execution tests — defer_case
# ============================================================================


def test_defer_case_tree_success(
    bridge, datalayer, actor_id, case_with_participant
):
    """DeferCaseBT succeeds and sets participant RM to DEFERRED."""
    request = _make_defer_request(case_with_participant, actor_id)
    tree = create_defer_case_tree(
        case_id=case_with_participant.id_, actor_id=actor_id
    )
    result = bridge.execute_with_setup(
        tree=tree, actor_id=actor_id, activity=request
    )

    assert result.status == Status.SUCCESS

    participant_id = "https://example.org/participants/vendor-cp-001"
    updated_participant = datalayer.read(participant_id)
    latest_status = updated_participant.participant_statuses[-1]
    assert latest_status.rm_state == RM.DEFERRED


def test_defer_case_tree_fails_no_participant(
    bridge, datalayer, actor_id, case_without_participant
):
    """DeferCaseBT fails when actor has no CaseParticipant in the case."""
    request = _make_defer_request(case_without_participant, actor_id)
    tree = create_defer_case_tree(
        case_id=case_without_participant.id_, actor_id=actor_id
    )
    result = bridge.execute_with_setup(
        tree=tree, actor_id=actor_id, activity=request
    )

    assert result.status == Status.FAILURE


def test_defer_case_tree_fails_missing_case(bridge, datalayer, actor_id):
    """DeferCaseBT fails when the case does not exist in the datalayer."""
    case = VultronCase(
        id_="https://example.org/cases/nonexistent",
        name="Missing Case",
        vulnerability_reports=[],
        case_participants=[],
    )
    request = _make_defer_request(case, actor_id)
    tree = create_defer_case_tree(
        case_id="https://example.org/cases/nonexistent", actor_id=actor_id
    )
    result = bridge.execute_with_setup(
        tree=tree, actor_id=actor_id, activity=request
    )

    assert result.status == Status.FAILURE


# ============================================================================
# Multiple participants — participant-specific isolation
# ============================================================================


def test_engage_only_affects_target_actor(bridge, datalayer, report):
    """Engaging updates only the target actor's RM state, not other participants."""
    actor_a = "https://example.org/actors/vendor-a"
    actor_b = "https://example.org/actors/vendor-b"

    participant_a = _make_participant_in_valid_state(
        id_="https://example.org/participants/cp-a",
        attributed_to=actor_a,
        context="https://example.org/cases/case-multi",
    )
    participant_b = _make_participant_in_valid_state(
        id_="https://example.org/participants/cp-b",
        attributed_to=actor_b,
        context="https://example.org/cases/case-multi",
    )
    datalayer.create(participant_a)
    datalayer.create(participant_b)
    case = VultronCase(
        id_="https://example.org/cases/case-multi",
        name="Multi-participant case",
        vulnerability_reports=[report.id_],
        case_participants=[participant_a.id_, participant_b.id_],
    )
    datalayer.create(case)

    request = _make_engage_request(case, actor_a)
    tree = create_engage_case_tree(case_id=case.id_, actor_id=actor_a)
    result = bridge.execute_with_setup(
        tree=tree, actor_id=actor_a, activity=request
    )
    assert result.status == Status.SUCCESS

    updated_a = datalayer.read(participant_a.id_)
    updated_b = datalayer.read(participant_b.id_)
    assert updated_a.participant_statuses[-1].rm_state == RM.ACCEPTED
    # actor_b's RM state must be unchanged (START, from default init)
    assert updated_b.participant_statuses[-1].rm_state != RM.ACCEPTED


# ============================================================================
# Idempotency tests (BT-2.0.3, BT-2.0.4, BT-2.0.5 — ID-04-004 MUST)
# ============================================================================


def test_engage_case_tree_idempotent(
    bridge, datalayer, actor_id, case_with_participant
):
    """Executing EngageCaseBT twice leaves RM state ACCEPTED, no duplicate entries."""
    request = _make_engage_request(case_with_participant, actor_id)
    tree1 = create_engage_case_tree(
        case_id=case_with_participant.id_, actor_id=actor_id
    )
    result1 = bridge.execute_with_setup(
        tree=tree1, actor_id=actor_id, activity=request
    )
    assert result1.status == Status.SUCCESS

    tree2 = create_engage_case_tree(
        case_id=case_with_participant.id_, actor_id=actor_id
    )
    result2 = bridge.execute_with_setup(
        tree=tree2, actor_id=actor_id, activity=request
    )
    assert result2.status == Status.SUCCESS

    updated_case = datalayer.read(case_with_participant.id_)
    participant_id = updated_case.case_participants[0]
    participant = datalayer.read(participant_id)
    assert participant.participant_statuses[-1].rm_state == RM.ACCEPTED
    # Second execution must NOT append a duplicate status entry
    accepted_entries = [
        s
        for s in participant.participant_statuses
        if s.rm_state == RM.ACCEPTED
    ]
    assert len(accepted_entries) == 1


def test_defer_case_tree_idempotent(
    bridge, datalayer, actor_id, case_with_participant
):
    """Executing DeferCaseBT twice leaves RM state DEFERRED, no duplicate entries."""
    request = _make_defer_request(case_with_participant, actor_id)
    tree1 = create_defer_case_tree(
        case_id=case_with_participant.id_, actor_id=actor_id
    )
    result1 = bridge.execute_with_setup(
        tree=tree1, actor_id=actor_id, activity=request
    )
    assert result1.status == Status.SUCCESS

    tree2 = create_defer_case_tree(
        case_id=case_with_participant.id_, actor_id=actor_id
    )
    result2 = bridge.execute_with_setup(
        tree=tree2, actor_id=actor_id, activity=request
    )
    assert result2.status == Status.SUCCESS

    updated_case = datalayer.read(case_with_participant.id_)
    participant_id = updated_case.case_participants[0]
    participant = datalayer.read(participant_id)
    assert participant.participant_statuses[-1].rm_state == RM.DEFERRED
    # Second execution must NOT append a duplicate status entry
    deferred_entries = [
        s
        for s in participant.participant_statuses
        if s.rm_state == RM.DEFERRED
    ]
    assert len(deferred_entries) == 1


# ============================================================================
# create_prioritize_subtree tests (D5-7-BTFIX-1 / D5-7-BTFIX-2)
# ============================================================================


def test_create_prioritize_subtree_returns_selector(
    case_with_participant, actor_id, trigger_activity
):
    """create_prioritize_subtree returns a Selector named PrioritizeBT.

    Verifies the canonical sender-side pattern (PCR-08-001): each path uses
    engage_case_trigger_bt / defer_case_trigger_bt, which compose
    TransitionParticipantRM* → SenderSideBT(ResolveCaseManagerNode →
    ConstructActivitiesNode → QueueToOutboxNode).
    """
    tree = create_prioritize_subtree(
        case_id=case_with_participant.id_,
        actor_id=actor_id,
        trigger_activity=trigger_activity,
    )
    assert tree is not None
    assert tree.name == "PrioritizeBT"
    assert hasattr(tree, "children")
    assert len(tree.children) == 2

    # Engage path: EvaluateCasePriority → EngageCaseTriggerBT → OnAccept
    engage_path = tree.children[0]
    assert engage_path.name == "EngagePath"
    assert len(engage_path.children) == 3
    assert engage_path.children[0].name == "EvaluateCasePriority"
    engage_trigger_bt = engage_path.children[1]
    assert engage_trigger_bt.name == "EngageCaseTriggerBT"
    assert len(engage_trigger_bt.children) == 2
    assert (
        engage_trigger_bt.children[0].name
        == "TransitionParticipantRMtoAccepted"
    )
    engage_sender = engage_trigger_bt.children[1]
    assert engage_sender.name == "SenderSideBT"
    assert len(engage_sender.children) == 3
    assert engage_sender.children[0].name == "ResolveCaseManagerNode"
    assert engage_sender.children[1].name == "ConstructActivitiesNode"
    assert engage_sender.children[2].name == "QueueToOutboxNode"
    assert engage_path.children[2].name == "OnAccept"

    # Defer path: DeferPath (Sequence) wrapping DeferCaseTriggerBT → OnDefer
    defer_path = tree.children[1]
    assert defer_path.name == "DeferPath"
    assert len(defer_path.children) == 2
    defer_trigger_bt = defer_path.children[0]
    assert defer_trigger_bt.name == "DeferCaseTriggerBT"
    assert len(defer_trigger_bt.children) == 2
    assert (
        defer_trigger_bt.children[0].name
        == "TransitionParticipantRMtoDeferred"
    )
    defer_sender = defer_trigger_bt.children[1]
    assert defer_sender.name == "SenderSideBT"
    assert len(defer_sender.children) == 3
    assert defer_sender.children[0].name == "ResolveCaseManagerNode"
    assert defer_sender.children[1].name == "ConstructActivitiesNode"
    assert defer_sender.children[2].name == "QueueToOutboxNode"
    assert defer_path.children[1].name == "OnDefer"


def test_prioritize_subtree_engages_by_default(
    bridge, datalayer, actor_id, trigger_activity, case_with_manager
):
    """PrioritizeBT engages by default (EvaluateCasePriority is always SUCCESS).

    Verifies:
    - Tree returns SUCCESS
    - Participant RM state transitions to ACCEPTED
    - An RmEngageCaseActivity (Join type) is created in the datalayer
      addressed to the Case Manager (PCR-08-001)
    - The activity appears in the actor's outbox (D5-7-BTFIX-1)
    """
    tree = create_prioritize_subtree(
        case_id=case_with_manager.id_,
        actor_id=actor_id,
        trigger_activity=trigger_activity,
    )
    result = bridge.execute_with_setup(tree=tree, actor_id=actor_id)

    assert result.status == Status.SUCCESS

    # Participant RM state must be ACCEPTED
    participant_id = "https://example.org/participants/vendor-cp-002"
    updated_participant = datalayer.read(participant_id)
    assert updated_participant.participant_statuses[-1].rm_state == RM.ACCEPTED

    # An engage activity must have been created and added to outbox
    outbox_items = datalayer.clone_for_actor(actor_id).outbox_list()
    assert len(outbox_items) == 1

    engage_activity_id = outbox_items[0]
    engage_activity = datalayer.read(engage_activity_id)
    assert engage_activity is not None
    assert str(engage_activity.type_) == "Join"
    assert engage_activity.actor == actor_id
    assert engage_activity.object_.id_ == case_with_manager.id_


def test_prioritize_subtree_custom_on_accept_factory_used(
    case_with_participant, actor_id, trigger_activity
):
    """on_accept_factory node appears in the engage path when custom factory is passed."""
    import py_trees

    def custom_on_accept(name):
        class _Marker(py_trees.behaviour.Behaviour):
            def update(self):
                return py_trees.common.Status.SUCCESS

        return _Marker(name="CustomOnAccept")

    tree = create_prioritize_subtree(
        case_id=case_with_participant.id_,
        actor_id=actor_id,
        trigger_activity=trigger_activity,
        on_accept_factory=custom_on_accept,
    )

    engage_path = tree.children[0]
    assert engage_path.children[2].name == "CustomOnAccept"


def test_prioritize_subtree_custom_on_defer_factory_used(
    case_with_participant, actor_id, trigger_activity
):
    """on_defer_factory node appears in the defer path when custom factory is passed."""
    import py_trees

    def custom_on_defer(name):
        class _Marker(py_trees.behaviour.Behaviour):
            def update(self):
                return py_trees.common.Status.SUCCESS

        return _Marker(name="CustomOnDefer")

    tree = create_prioritize_subtree(
        case_id=case_with_participant.id_,
        actor_id=actor_id,
        trigger_activity=trigger_activity,
        on_defer_factory=custom_on_defer,
    )

    defer_path = tree.children[1]
    assert defer_path.children[1].name == "CustomOnDefer"


def test_prioritize_subtree_defers_when_engage_path_fails(
    monkeypatch,
    bridge,
    datalayer,
    actor_id,
    trigger_activity,
    case_with_manager,
):
    """PrioritizeBT falls back to defer when engage preconditions fail."""
    from vultron.core.behaviors.report import prioritize_tree

    monkeypatch.setattr(
        prioritize_tree.EvaluateCasePriority,
        "update",
        lambda self: Status.FAILURE,
    )

    tree = create_prioritize_subtree(
        case_id=case_with_manager.id_,
        actor_id=actor_id,
        trigger_activity=trigger_activity,
    )
    result = bridge.execute_with_setup(tree=tree, actor_id=actor_id)

    assert result.status == Status.SUCCESS

    participant_id = "https://example.org/participants/vendor-cp-002"
    updated_participant = datalayer.read(participant_id)
    assert updated_participant.participant_statuses[-1].rm_state == RM.DEFERRED

    outbox_items = datalayer.clone_for_actor(actor_id).outbox_list()
    assert len(outbox_items) == 1

    defer_activity_id = outbox_items[0]
    defer_activity = datalayer.read(defer_activity_id)
    assert defer_activity is not None
    assert str(defer_activity.type_) == "Ignore"
    assert defer_activity.actor == actor_id
    assert defer_activity.object_.id_ == case_with_manager.id_
