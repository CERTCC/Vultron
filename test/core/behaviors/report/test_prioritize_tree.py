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
from vultron.core.models.participant_status import VultronParticipantStatus
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
            VultronParticipantStatus(
                attributed_to=attributed_to,
                context=context,
                rm_state=RM.RECEIVED,
            ),
            VultronParticipantStatus(
                attributed_to=attributed_to,
                context=context,
                rm_state=RM.VALID,
            ),
        ],
    )
    return participant


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
    return BTBridge(datalayer=datalayer)


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
    assert len(tree.children) == 3


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
    assert tree.children[1].name == "TransitionParticipantRMtoAccepted"


def test_defer_tree_node_names(case_with_participant, actor_id):
    tree = create_defer_case_tree(
        case_id=case_with_participant.id_, actor_id=actor_id
    )
    assert tree.children[0].name == "CheckParticipantExists"
    assert tree.children[1].name == "TransitionParticipantRMtoDeferred"


# ============================================================================
# Execution tests — engage_case
# ============================================================================


def test_engage_case_tree_success(
    bridge, datalayer, actor_id, case_with_participant
):
    """EngageCaseBT succeeds and sets participant RM to ACCEPTED."""
    tree = create_engage_case_tree(
        case_id=case_with_participant.id_, actor_id=actor_id
    )
    result = bridge.execute_with_setup(tree=tree, actor_id=actor_id)

    assert result.status == Status.SUCCESS

    participant_id = "https://example.org/participants/vendor-cp-001"
    updated_participant = datalayer.read(participant_id)
    latest_status = updated_participant.participant_statuses[-1]
    assert latest_status.rm_state == RM.ACCEPTED


def test_engage_case_tree_fails_no_participant(
    bridge, datalayer, actor_id, case_without_participant
):
    """EngageCaseBT fails when actor has no CaseParticipant in the case."""
    tree = create_engage_case_tree(
        case_id=case_without_participant.id_, actor_id=actor_id
    )
    result = bridge.execute_with_setup(tree=tree, actor_id=actor_id)

    assert result.status == Status.FAILURE


def test_engage_case_tree_fails_missing_case(bridge, datalayer, actor_id):
    """EngageCaseBT fails when the case does not exist in the datalayer."""
    tree = create_engage_case_tree(
        case_id="https://example.org/cases/nonexistent", actor_id=actor_id
    )
    result = bridge.execute_with_setup(tree=tree, actor_id=actor_id)

    assert result.status == Status.FAILURE


# ============================================================================
# Execution tests — defer_case
# ============================================================================


def test_defer_case_tree_success(
    bridge, datalayer, actor_id, case_with_participant
):
    """DeferCaseBT succeeds and sets participant RM to DEFERRED."""
    tree = create_defer_case_tree(
        case_id=case_with_participant.id_, actor_id=actor_id
    )
    result = bridge.execute_with_setup(tree=tree, actor_id=actor_id)

    assert result.status == Status.SUCCESS

    participant_id = "https://example.org/participants/vendor-cp-001"
    updated_participant = datalayer.read(participant_id)
    latest_status = updated_participant.participant_statuses[-1]
    assert latest_status.rm_state == RM.DEFERRED


def test_defer_case_tree_fails_no_participant(
    bridge, datalayer, actor_id, case_without_participant
):
    """DeferCaseBT fails when actor has no CaseParticipant in the case."""
    tree = create_defer_case_tree(
        case_id=case_without_participant.id_, actor_id=actor_id
    )
    result = bridge.execute_with_setup(tree=tree, actor_id=actor_id)

    assert result.status == Status.FAILURE


def test_defer_case_tree_fails_missing_case(bridge, datalayer, actor_id):
    """DeferCaseBT fails when the case does not exist in the datalayer."""
    tree = create_defer_case_tree(
        case_id="https://example.org/cases/nonexistent", actor_id=actor_id
    )
    result = bridge.execute_with_setup(tree=tree, actor_id=actor_id)

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

    tree = create_engage_case_tree(case_id=case.id_, actor_id=actor_a)
    result = bridge.execute_with_setup(tree=tree, actor_id=actor_a)
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
    tree1 = create_engage_case_tree(
        case_id=case_with_participant.id_, actor_id=actor_id
    )
    result1 = bridge.execute_with_setup(tree=tree1, actor_id=actor_id)
    assert result1.status == Status.SUCCESS

    tree2 = create_engage_case_tree(
        case_id=case_with_participant.id_, actor_id=actor_id
    )
    result2 = bridge.execute_with_setup(tree=tree2, actor_id=actor_id)
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
    tree1 = create_defer_case_tree(
        case_id=case_with_participant.id_, actor_id=actor_id
    )
    result1 = bridge.execute_with_setup(tree=tree1, actor_id=actor_id)
    assert result1.status == Status.SUCCESS

    tree2 = create_defer_case_tree(
        case_id=case_with_participant.id_, actor_id=actor_id
    )
    result2 = bridge.execute_with_setup(tree=tree2, actor_id=actor_id)
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
    case_with_participant, actor_id
):
    """create_prioritize_subtree returns a Selector named PrioritizeBT."""
    tree = create_prioritize_subtree(
        case_id=case_with_participant.id_, actor_id=actor_id
    )
    assert tree is not None
    assert tree.name == "PrioritizeBT"
    assert hasattr(tree, "children")
    assert len(tree.children) == 2

    engage_path = tree.children[0]
    assert engage_path.name == "EngagePath"
    assert len(engage_path.children) == 3
    assert engage_path.children[0].name == "EvaluateCasePriority"
    assert engage_path.children[1].name == "EmitEngageCaseActivity"
    assert engage_path.children[2].name == "TransitionParticipantRMtoAccepted"

    defer_path = tree.children[1]
    assert defer_path.name == "DeferPath"
    assert len(defer_path.children) == 2
    assert defer_path.children[0].name == "EmitDeferCaseActivity"
    assert defer_path.children[1].name == "TransitionParticipantRMtoDeferred"


def test_prioritize_subtree_engages_by_default(
    bridge, datalayer, actor_id, case_with_participant
):
    """PrioritizeBT engages by default (EvaluateCasePriority is always SUCCESS).

    Verifies:
    - Tree returns SUCCESS
    - Participant RM state transitions to ACCEPTED
    - An RmEngageCaseActivity (Join type) is created in the datalayer
    - The activity appears in the actor's outbox (D5-7-BTFIX-1)
    """
    tree = create_prioritize_subtree(
        case_id=case_with_participant.id_, actor_id=actor_id
    )
    result = bridge.execute_with_setup(tree=tree, actor_id=actor_id)

    assert result.status == Status.SUCCESS

    # Participant RM state must be ACCEPTED
    participant_id = "https://example.org/participants/vendor-cp-001"
    updated_participant = datalayer.read(participant_id)
    assert updated_participant.participant_statuses[-1].rm_state == RM.ACCEPTED

    # An engage activity must have been created and added to outbox
    updated_actor = datalayer.read(actor_id)
    assert updated_actor is not None
    assert len(updated_actor.outbox.items) == 1

    engage_activity_id = updated_actor.outbox.items[0]
    engage_activity = datalayer.read(engage_activity_id)
    assert engage_activity is not None
    assert str(engage_activity.type_) == "Join"
    assert engage_activity.actor == actor_id
    assert engage_activity.object_.id_ == case_with_participant.id_
