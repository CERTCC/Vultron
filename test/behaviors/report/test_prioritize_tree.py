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

from vultron.api.v2.datalayer.tinydb_backend import TinyDbDataLayer
from vultron.as_vocab.base.objects.actors import as_Service
from vultron.as_vocab.objects.case_participant import CaseParticipant
from vultron.as_vocab.objects.vulnerability_case import VulnerabilityCase
from vultron.as_vocab.objects.vulnerability_report import VulnerabilityReport
from vultron.behaviors.bridge import BTBridge
from vultron.behaviors.report.prioritize_tree import (
    create_defer_case_tree,
    create_engage_case_tree,
)
from vultron.bt.report_management.states import RM


@pytest.fixture
def datalayer():
    return TinyDbDataLayer(db_path=None)


@pytest.fixture
def actor_id():
    return "https://example.org/actors/vendor"


@pytest.fixture
def actor(datalayer, actor_id):
    obj = as_Service(as_id=actor_id, name="Vendor Co")
    datalayer.create(obj)
    return obj


@pytest.fixture
def report(datalayer):
    obj = VulnerabilityReport(
        as_id="https://example.org/reports/CVE-2024-001",
        name="Test Report",
        content="Buffer overflow",
    )
    datalayer.create(obj)
    return obj


@pytest.fixture
def case_with_participant(datalayer, actor_id, actor, report):
    """Case with the test actor as a CaseParticipant."""
    participant = CaseParticipant(
        as_id="https://example.org/participants/vendor-cp-001",
        attributed_to=actor_id,
        context="https://example.org/cases/case-001",
    )
    case = VulnerabilityCase(
        as_id="https://example.org/cases/case-001",
        name="Test Case",
        vulnerability_reports=[report],
        case_participants=[participant],
    )
    datalayer.create(case)
    return case


@pytest.fixture
def case_without_participant(datalayer, report):
    """Case with no participants."""
    case = VulnerabilityCase(
        as_id="https://example.org/cases/case-002",
        name="Test Case No Participants",
        vulnerability_reports=[report],
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
        case_id=case_with_participant.as_id, actor_id=actor_id
    )
    assert tree is not None
    assert tree.name == "EngageCaseBT"
    assert hasattr(tree, "children")
    assert len(tree.children) == 2


def test_create_defer_case_tree_returns_sequence(
    case_with_participant, actor_id
):
    tree = create_defer_case_tree(
        case_id=case_with_participant.as_id, actor_id=actor_id
    )
    assert tree is not None
    assert tree.name == "DeferCaseBT"
    assert hasattr(tree, "children")
    assert len(tree.children) == 2


def test_engage_tree_node_names(case_with_participant, actor_id):
    tree = create_engage_case_tree(
        case_id=case_with_participant.as_id, actor_id=actor_id
    )
    assert tree.children[0].name == "CheckParticipantExists"
    assert tree.children[1].name == "TransitionParticipantRMtoAccepted"


def test_defer_tree_node_names(case_with_participant, actor_id):
    tree = create_defer_case_tree(
        case_id=case_with_participant.as_id, actor_id=actor_id
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
        case_id=case_with_participant.as_id, actor_id=actor_id
    )
    result = bridge.execute_with_setup(tree=tree, actor_id=actor_id)

    assert result.status == Status.SUCCESS

    updated_case = datalayer.read(case_with_participant.as_id)
    participant = updated_case.case_participants[0]
    latest_status = participant.participant_status[-1]
    assert latest_status.rm_state == RM.ACCEPTED


def test_engage_case_tree_fails_no_participant(
    bridge, datalayer, actor_id, case_without_participant
):
    """EngageCaseBT fails when actor has no CaseParticipant in the case."""
    tree = create_engage_case_tree(
        case_id=case_without_participant.as_id, actor_id=actor_id
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
        case_id=case_with_participant.as_id, actor_id=actor_id
    )
    result = bridge.execute_with_setup(tree=tree, actor_id=actor_id)

    assert result.status == Status.SUCCESS

    updated_case = datalayer.read(case_with_participant.as_id)
    participant = updated_case.case_participants[0]
    latest_status = participant.participant_status[-1]
    assert latest_status.rm_state == RM.DEFERRED


def test_defer_case_tree_fails_no_participant(
    bridge, datalayer, actor_id, case_without_participant
):
    """DeferCaseBT fails when actor has no CaseParticipant in the case."""
    tree = create_defer_case_tree(
        case_id=case_without_participant.as_id, actor_id=actor_id
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

    participant_a = CaseParticipant(
        as_id="https://example.org/participants/cp-a",
        attributed_to=actor_a,
        context="https://example.org/cases/case-multi",
    )
    participant_b = CaseParticipant(
        as_id="https://example.org/participants/cp-b",
        attributed_to=actor_b,
        context="https://example.org/cases/case-multi",
    )
    case = VulnerabilityCase(
        as_id="https://example.org/cases/case-multi",
        name="Multi-participant case",
        vulnerability_reports=[report],
        case_participants=[participant_a, participant_b],
    )
    datalayer.create(case)

    tree = create_engage_case_tree(case_id=case.as_id, actor_id=actor_a)
    result = bridge.execute_with_setup(tree=tree, actor_id=actor_a)
    assert result.status == Status.SUCCESS

    updated_case = datalayer.read(case.as_id)
    for p in updated_case.case_participants:
        p_actor = (
            p.attributed_to
            if isinstance(p.attributed_to, str)
            else p.attributed_to.as_id
        )
        latest_rm = p.participant_status[-1].rm_state
        if p_actor == actor_a:
            assert latest_rm == RM.ACCEPTED
        else:
            # actor_b's RM state must be unchanged (START, from default init)
            assert latest_rm != RM.ACCEPTED


# ============================================================================
# Idempotency tests (BT-2.0.3, BT-2.0.4, BT-2.0.5 — ID-04-004 MUST)
# ============================================================================


def test_engage_case_tree_idempotent(
    bridge, datalayer, actor_id, case_with_participant
):
    """Executing EngageCaseBT twice leaves RM state ACCEPTED, no duplicate entries."""
    tree1 = create_engage_case_tree(
        case_id=case_with_participant.as_id, actor_id=actor_id
    )
    result1 = bridge.execute_with_setup(tree=tree1, actor_id=actor_id)
    assert result1.status == Status.SUCCESS

    tree2 = create_engage_case_tree(
        case_id=case_with_participant.as_id, actor_id=actor_id
    )
    result2 = bridge.execute_with_setup(tree=tree2, actor_id=actor_id)
    assert result2.status == Status.SUCCESS

    updated_case = datalayer.read(case_with_participant.as_id)
    participant = updated_case.case_participants[0]
    assert participant.participant_status[-1].rm_state == RM.ACCEPTED
    # Second execution must NOT append a duplicate status entry
    accepted_entries = [
        s for s in participant.participant_status if s.rm_state == RM.ACCEPTED
    ]
    assert len(accepted_entries) == 1


def test_defer_case_tree_idempotent(
    bridge, datalayer, actor_id, case_with_participant
):
    """Executing DeferCaseBT twice leaves RM state DEFERRED, no duplicate entries."""
    tree1 = create_defer_case_tree(
        case_id=case_with_participant.as_id, actor_id=actor_id
    )
    result1 = bridge.execute_with_setup(tree=tree1, actor_id=actor_id)
    assert result1.status == Status.SUCCESS

    tree2 = create_defer_case_tree(
        case_id=case_with_participant.as_id, actor_id=actor_id
    )
    result2 = bridge.execute_with_setup(tree=tree2, actor_id=actor_id)
    assert result2.status == Status.SUCCESS

    updated_case = datalayer.read(case_with_participant.as_id)
    participant = updated_case.case_participants[0]
    assert participant.participant_status[-1].rm_state == RM.DEFERRED
    # Second execution must NOT append a duplicate status entry
    deferred_entries = [
        s for s in participant.participant_status if s.rm_state == RM.DEFERRED
    ]
    assert len(deferred_entries) == 1
