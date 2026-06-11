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

"""Unit tests for participant status workflow nodes (submodule path).

Verifies LoadParticipantNode, CheckStatusNotAlreadyAppendedNode,
ResolveAndPersistStatusObjectNode, ValidateRMTransitionNode,
AppendStatusAndSaveParticipantNode, PublicDisclosureBranchNode, and
AutoCloseBranchNode imported directly from the submodule.

Per DEMOMA-07-003 steps 2–5.
"""

import pytest
import py_trees
from py_trees.common import Status

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.status.nodes.participant_status import (
    AppendStatusAndSaveParticipantNode,
    AutoCloseBranchNode,
    CheckStatusNotAlreadyAppendedNode,
    LoadParticipantNode,
    PublicDisclosureBranchNode,
    ResolveAndPersistStatusObjectNode,
    ValidateRMTransitionNode,
)
from vultron.core.states.roles import CVDRole
from vultron.wire.as2.vocab.objects.case_participant import CaseParticipant
from vultron.wire.as2.vocab.objects.case_status import ParticipantStatus
from vultron.wire.as2.vocab.objects.vulnerability_case import VulnerabilityCase

ACTOR_ID = "https://example.org/actors/vendor"
CASE_MANAGER_ID = "https://example.org/actors/case-actor"
CASE_ID = "https://example.org/cases/case-01"
PARTICIPANT_ID = "https://example.org/cases/case-01/participants/vendor"
CM_PARTICIPANT_ID = "https://example.org/cases/case-01/participants/case-actor"
STATUS_ID = "https://example.org/cases/case-01/statuses/s1"


@pytest.fixture(autouse=True)
def clear_blackboard():
    py_trees.blackboard.Blackboard.storage.clear()


@pytest.fixture
def dl():
    return SqliteDataLayer("sqlite:///:memory:")


@pytest.fixture
def bridge(dl):
    return BTBridge(datalayer=dl)


@pytest.fixture
def participant():
    return CaseParticipant(
        id_=PARTICIPANT_ID,
        context=CASE_ID,
        attributed_to=ACTOR_ID,
        case_roles=[CVDRole.CASE_OWNER],
    )


@pytest.fixture
def status_obj():
    return ParticipantStatus(id_=STATUS_ID, context=CASE_ID)


@pytest.fixture
def populated_dl(dl, participant, status_obj):
    case_manager_participant = CaseParticipant(
        id_=CM_PARTICIPANT_ID,
        context=CASE_ID,
        attributed_to=CASE_MANAGER_ID,
        case_roles=[CVDRole.CASE_MANAGER],
    )
    case = VulnerabilityCase(id_=CASE_ID, name="Test Case")
    case.add_participant(participant)
    case.add_participant(case_manager_participant)
    dl.create(case)
    dl.create(participant)
    dl.create(case_manager_participant)
    dl.create(status_obj)
    return dl


@pytest.fixture
def populated_bridge(populated_dl):
    return BTBridge(datalayer=populated_dl)


# ---------------------------------------------------------------------------
# LoadParticipantNode
# ---------------------------------------------------------------------------


class TestLoadParticipantNode:
    def test_loads_participant_to_blackboard(self, populated_bridge):
        node = LoadParticipantNode(participant_id=PARTICIPANT_ID)
        result = populated_bridge.execute_with_setup(
            tree=node, actor_id=ACTOR_ID
        )
        assert result.status == Status.SUCCESS

    def test_missing_participant_fails(self, bridge):
        node = LoadParticipantNode(
            participant_id="https://example.org/cases/missing/p"
        )
        result = bridge.execute_with_setup(tree=node, actor_id=ACTOR_ID)
        assert result.status == Status.FAILURE


# ---------------------------------------------------------------------------
# CheckStatusNotAlreadyAppendedNode
# ---------------------------------------------------------------------------


class TestCheckStatusNotAlreadyAppendedNode:
    def test_not_appended_succeeds(self, populated_bridge):
        load = LoadParticipantNode(participant_id=PARTICIPANT_ID)
        check = CheckStatusNotAlreadyAppendedNode(
            status_id=STATUS_ID, participant_id=PARTICIPANT_ID
        )
        seq = py_trees.composites.Sequence(
            name="TestSeq", memory=False, children=[load, check]
        )
        result = populated_bridge.execute_with_setup(
            tree=seq, actor_id=ACTOR_ID
        )
        assert result.status == Status.SUCCESS

    def test_already_appended_fails(self, populated_dl):
        # Append the status to the participant first
        p = populated_dl.read(PARTICIPANT_ID)
        s = populated_dl.read(STATUS_ID)
        p.participant_statuses.append(s)
        populated_dl.save(p)

        bridge = BTBridge(datalayer=populated_dl)
        load = LoadParticipantNode(participant_id=PARTICIPANT_ID)
        check = CheckStatusNotAlreadyAppendedNode(
            status_id=STATUS_ID, participant_id=PARTICIPANT_ID
        )
        seq = py_trees.composites.Sequence(
            name="TestSeq", memory=False, children=[load, check]
        )
        result = bridge.execute_with_setup(tree=seq, actor_id=ACTOR_ID)
        assert result.status == Status.FAILURE


# ---------------------------------------------------------------------------
# ResolveAndPersistStatusObjectNode
# ---------------------------------------------------------------------------


class TestResolveAndPersistStatusObjectNode:
    def test_resolves_from_dl(self, populated_bridge):
        node = ResolveAndPersistStatusObjectNode(
            status_id=STATUS_ID, status_obj_fallback=None
        )
        result = populated_bridge.execute_with_setup(
            tree=node, actor_id=ACTOR_ID
        )
        assert result.status == Status.SUCCESS

    def test_missing_without_fallback_fails(self, bridge):
        node = ResolveAndPersistStatusObjectNode(
            status_id="https://example.org/missing", status_obj_fallback=None
        )
        result = bridge.execute_with_setup(tree=node, actor_id=ACTOR_ID)
        assert result.status == Status.FAILURE


# ---------------------------------------------------------------------------
# ValidateRMTransitionNode
# ---------------------------------------------------------------------------


class TestValidateRMTransitionNode:
    def test_valid_forward_transition_succeeds(self, populated_bridge):
        load = LoadParticipantNode(participant_id=PARTICIPANT_ID)
        resolve = ResolveAndPersistStatusObjectNode(
            status_id=STATUS_ID, status_obj_fallback=None
        )
        validate = ValidateRMTransitionNode(participant_id=PARTICIPANT_ID)
        seq = py_trees.composites.Sequence(
            name="TestSeq", memory=False, children=[load, resolve, validate]
        )
        result = populated_bridge.execute_with_setup(
            tree=seq, actor_id=ACTOR_ID
        )
        assert result.status == Status.SUCCESS


# ---------------------------------------------------------------------------
# AppendStatusAndSaveParticipantNode
# ---------------------------------------------------------------------------


class TestAppendStatusAndSaveParticipantNode:
    def test_appends_status(self, populated_bridge, populated_dl):
        p_before = populated_dl.read(PARTICIPANT_ID)
        initial_count = len(p_before.participant_statuses)

        load = LoadParticipantNode(participant_id=PARTICIPANT_ID)
        resolve = ResolveAndPersistStatusObjectNode(
            status_id=STATUS_ID, status_obj_fallback=None
        )
        append = AppendStatusAndSaveParticipantNode(
            status_id=STATUS_ID, participant_id=PARTICIPANT_ID
        )
        seq = py_trees.composites.Sequence(
            name="TestSeq", memory=False, children=[load, resolve, append]
        )
        result = populated_bridge.execute_with_setup(
            tree=seq, actor_id=ACTOR_ID
        )
        assert result.status == Status.SUCCESS

        p = populated_dl.read(PARTICIPANT_ID)
        assert len(p.participant_statuses) == initial_count + 1


# ---------------------------------------------------------------------------
# PublicDisclosureBranchNode
# ---------------------------------------------------------------------------


class TestPublicDisclosureBranchNode:
    def test_always_succeeds_when_not_public_aware(
        self, populated_bridge, status_obj
    ):
        node = PublicDisclosureBranchNode(
            status_obj=status_obj,
            sender_actor_id=ACTOR_ID,
            case_id=CASE_ID,
        )
        result = populated_bridge.execute_with_setup(
            tree=node, actor_id=ACTOR_ID
        )
        assert result.status == Status.SUCCESS


# ---------------------------------------------------------------------------
# AutoCloseBranchNode
# ---------------------------------------------------------------------------


class TestAutoCloseBranchNode:
    def test_always_succeeds(self, populated_bridge):
        node = AutoCloseBranchNode(case_id=CASE_ID)
        result = populated_bridge.execute_with_setup(
            tree=node, actor_id=CASE_MANAGER_ID
        )
        assert result.status == Status.SUCCESS

    def test_succeeds_with_none_case_id(self, populated_bridge):
        node = AutoCloseBranchNode(case_id=None)
        result = populated_bridge.execute_with_setup(
            tree=node, actor_id=CASE_MANAGER_ID
        )
        assert result.status == Status.SUCCESS
