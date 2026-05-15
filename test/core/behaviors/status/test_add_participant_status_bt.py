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

"""Tests for AddParticipantStatus BT nodes and tree factory.

Covers all five DEMOMA-07-003 steps:
  1. VerifySenderIsParticipantNode — unknown sender is rejected
  2. AppendParticipantStatusNode  — status appended, RM regression rejected
  3. BroadcastStatusToPeersNode   — always SUCCESS, skips without trigger_activity
  4. PublicDisclosureBranchNode   — always SUCCESS, only triggers teardown on CS.P + CASE_OWNER
  5. AutoCloseBranchNode          — always SUCCESS, logs when all RM.CLOSED

Per specs/multi-actor-demo.yaml DEMOMA-07-003.
"""

import py_trees
import pytest
from py_trees.common import Status

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.status.add_participant_status_tree import (
    add_participant_status_tree,
)
from vultron.core.behaviors.status.nodes import (
    AppendParticipantStatusNode,
    AutoCloseBranchNode,
    BroadcastStatusToPeersNode,
    PublicDisclosureBranchNode,
    VerifySenderIsParticipantNode,
)
from vultron.core.states.rm import RM
from vultron.core.states.roles import CVDRole
from vultron.wire.as2.factories import add_status_to_participant_activity
from vultron.wire.as2.vocab.objects.case_participant import CaseParticipant
from vultron.wire.as2.vocab.objects.case_status import ParticipantStatus
from vultron.wire.as2.vocab.objects.vulnerability_case import VulnerabilityCase

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ACTOR_ID = "https://example.org/actors/vendor"
OUTSIDER_ID = "https://example.org/actors/outsider"
CASE_MANAGER_ID = "https://example.org/actors/case-actor"
CASE_ID = "https://example.org/cases/case-01"
PARTICIPANT_ID = "https://example.org/cases/case-01/participants/vendor"
CM_PARTICIPANT_ID = "https://example.org/cases/case-01/participants/case-actor"
STATUS_ID = "https://example.org/cases/case-01/participants/vendor/statuses/s1"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def clear_blackboard():
    """Clear py_trees global blackboard storage between tests."""
    py_trees.blackboard.Blackboard.storage.clear()


@pytest.fixture
def dl():
    return SqliteDataLayer("sqlite:///:memory:")


@pytest.fixture
def bridge(dl):
    return BTBridge(datalayer=dl)


@pytest.fixture
def status_obj():
    return ParticipantStatus(
        id_=STATUS_ID,
        context=CASE_ID,
    )


@pytest.fixture
def participant():
    return CaseParticipant(
        id_=PARTICIPANT_ID,
        context=CASE_ID,
        attributed_to=ACTOR_ID,
        case_roles=[CVDRole.CASE_OWNER],
    )


@pytest.fixture
def case_manager_participant():
    return CaseParticipant(
        id_=CM_PARTICIPANT_ID,
        context=CASE_ID,
        attributed_to=CASE_MANAGER_ID,
        case_roles=[CVDRole.CASE_MANAGER],
    )


@pytest.fixture
def case(participant, case_manager_participant):
    """VulnerabilityCase with vendor and Case Manager participants."""
    obj = VulnerabilityCase(id_=CASE_ID, name="Test Case")
    obj.actor_participant_index[ACTOR_ID] = PARTICIPANT_ID
    obj.actor_participant_index[CASE_MANAGER_ID] = CM_PARTICIPANT_ID
    return obj


@pytest.fixture
def populated_dl(dl, case, participant, case_manager_participant, status_obj):
    """DataLayer pre-populated with case, participants, and status."""
    dl.create(case)
    dl.create(participant)
    dl.create(case_manager_participant)
    dl.create(status_obj)
    return dl


@pytest.fixture
def populated_bridge(populated_dl):
    return BTBridge(datalayer=populated_dl)


# ---------------------------------------------------------------------------
# Step 1: VerifySenderIsParticipantNode
# ---------------------------------------------------------------------------


class TestVerifySenderIsParticipantNode:
    def test_known_sender_succeeds(self, populated_bridge):
        node = VerifySenderIsParticipantNode(
            status_id=STATUS_ID,
            sender_actor_id=ACTOR_ID,
            case_id=CASE_ID,
        )
        result = populated_bridge.execute_with_setup(
            tree=node, actor_id=CASE_MANAGER_ID
        )
        assert result.status == Status.SUCCESS

    def test_unknown_sender_fails(self, populated_bridge):
        node = VerifySenderIsParticipantNode(
            status_id=STATUS_ID,
            sender_actor_id=OUTSIDER_ID,
            case_id=CASE_ID,
        )
        result = populated_bridge.execute_with_setup(
            tree=node, actor_id=CASE_MANAGER_ID
        )
        assert result.status == Status.FAILURE

    def test_missing_case_fails(self, bridge):
        """No case in DataLayer → FAILURE."""
        node = VerifySenderIsParticipantNode(
            status_id=STATUS_ID,
            sender_actor_id=ACTOR_ID,
            case_id="https://example.org/cases/nonexistent",
        )
        result = bridge.execute_with_setup(tree=node, actor_id=ACTOR_ID)
        assert result.status == Status.FAILURE

    def test_no_case_id_falls_back_to_dl_lookup(self, populated_bridge):
        """When case_id is None, node resolves case_id from status.context."""
        node = VerifySenderIsParticipantNode(
            status_id=STATUS_ID,
            sender_actor_id=ACTOR_ID,
            case_id=None,
        )
        result = populated_bridge.execute_with_setup(
            tree=node, actor_id=CASE_MANAGER_ID
        )
        assert result.status == Status.SUCCESS


# ---------------------------------------------------------------------------
# Step 2: AppendParticipantStatusNode
# ---------------------------------------------------------------------------


class TestAppendParticipantStatusNode:
    def test_appends_status(self, populated_dl, populated_bridge, status_obj):
        node = AppendParticipantStatusNode(
            status_id=STATUS_ID,
            participant_id=PARTICIPANT_ID,
            status_obj_fallback=status_obj,
        )
        result = populated_bridge.execute_with_setup(
            tree=node, actor_id=ACTOR_ID
        )
        assert result.status == Status.SUCCESS
        p = populated_dl.read(PARTICIPANT_ID)
        assert p is not None
        status_ids = [getattr(s, "id_", s) for s in p.participant_statuses]
        assert STATUS_ID in status_ids

    def test_idempotent_when_already_present(self, populated_dl, status_obj):
        """Running the node twice does not duplicate the status."""
        bridge = BTBridge(datalayer=populated_dl)

        def _make_node():
            return AppendParticipantStatusNode(
                status_id=STATUS_ID,
                participant_id=PARTICIPANT_ID,
                status_obj_fallback=status_obj,
            )

        # First call appends the status
        result1 = bridge.execute_with_setup(
            tree=_make_node(), actor_id=ACTOR_ID
        )
        assert result1.status == Status.SUCCESS
        p = populated_dl.read(PARTICIPANT_ID)
        count_after_first = len(p.participant_statuses)
        assert STATUS_ID in [
            getattr(s, "id_", s) for s in p.participant_statuses
        ]

        # Second call must be idempotent — count must not increase
        bridge2 = BTBridge(datalayer=populated_dl)
        result2 = bridge2.execute_with_setup(
            tree=_make_node(), actor_id=ACTOR_ID
        )
        assert result2.status == Status.SUCCESS
        p2 = populated_dl.read(PARTICIPANT_ID)
        assert len(p2.participant_statuses) == count_after_first

    def test_missing_participant_fails(self, bridge, status_obj):
        node = AppendParticipantStatusNode(
            status_id=STATUS_ID,
            participant_id="https://example.org/cases/case-01/participants/missing",
            status_obj_fallback=status_obj,
        )
        result = bridge.execute_with_setup(tree=node, actor_id=ACTOR_ID)
        assert result.status == Status.FAILURE

    def test_backwards_rm_transition_fails(
        self, populated_dl, populated_bridge, participant
    ):
        """A backwards RM transition (CLOSED → RECEIVED) is rejected."""
        closed_status = ParticipantStatus(
            id_=f"{STATUS_ID}/prev",
            context=CASE_ID,
            rm_state=RM.CLOSED,
        )
        participant.participant_statuses.append(closed_status)
        populated_dl.save(participant)
        populated_dl.create(closed_status)

        regressed_status = ParticipantStatus(
            id_=f"{STATUS_ID}/regressed",
            context=CASE_ID,
            rm_state=RM.RECEIVED,
        )
        populated_dl.create(regressed_status)

        node = AppendParticipantStatusNode(
            status_id=regressed_status.id_,
            participant_id=PARTICIPANT_ID,
            status_obj_fallback=regressed_status,
        )
        result = populated_bridge.execute_with_setup(
            tree=node, actor_id=ACTOR_ID
        )
        assert result.status == Status.FAILURE

    def test_forward_rm_jump_accepted(
        self, populated_dl, populated_bridge, participant
    ):
        """A non-adjacent but forward RM jump is accepted (sender authoritative)."""
        received_status = ParticipantStatus(
            id_=f"{STATUS_ID}/received",
            context=CASE_ID,
            rm_state=RM.RECEIVED,
        )
        participant.participant_statuses.append(received_status)
        populated_dl.save(participant)
        populated_dl.create(received_status)

        accepted_status = ParticipantStatus(
            id_=f"{STATUS_ID}/accepted",
            context=CASE_ID,
            rm_state=RM.ACCEPTED,
        )
        populated_dl.create(accepted_status)

        node = AppendParticipantStatusNode(
            status_id=accepted_status.id_,
            participant_id=PARTICIPANT_ID,
            status_obj_fallback=accepted_status,
        )
        result = populated_bridge.execute_with_setup(
            tree=node, actor_id=ACTOR_ID
        )
        assert result.status == Status.SUCCESS


# ---------------------------------------------------------------------------
# Step 3: BroadcastStatusToPeersNode
# ---------------------------------------------------------------------------


class TestBroadcastStatusToPeersNode:
    def test_skips_without_trigger_activity(self, populated_bridge):
        """No trigger_activity → returns SUCCESS silently."""
        node = BroadcastStatusToPeersNode(
            status_id=STATUS_ID,
            participant_id=PARTICIPANT_ID,
            sender_actor_id=ACTOR_ID,
            case_id=CASE_ID,
        )
        result = populated_bridge.execute_with_setup(
            tree=node, actor_id=CASE_MANAGER_ID
        )
        assert result.status == Status.SUCCESS

    def test_always_succeeds(self, bridge):
        """Even with no DataLayer data, BroadcastStatusToPeers succeeds."""
        node = BroadcastStatusToPeersNode(
            status_id=STATUS_ID,
            participant_id=PARTICIPANT_ID,
            sender_actor_id=ACTOR_ID,
            case_id=None,
        )
        result = bridge.execute_with_setup(tree=node, actor_id=ACTOR_ID)
        assert result.status == Status.SUCCESS


# ---------------------------------------------------------------------------
# Step 4: PublicDisclosureBranchNode
# ---------------------------------------------------------------------------


class TestPublicDisclosureBranchNode:
    def test_skips_when_no_pxa_state(self, populated_bridge, status_obj):
        """Status without case_status.pxa_state → skips teardown, SUCCESS."""
        node = PublicDisclosureBranchNode(
            status_obj=status_obj,
            sender_actor_id=ACTOR_ID,
            case_id=CASE_ID,
        )
        result = populated_bridge.execute_with_setup(
            tree=node, actor_id=CASE_MANAGER_ID
        )
        assert result.status == Status.SUCCESS

    def test_skips_when_status_is_none(self, populated_bridge):
        node = PublicDisclosureBranchNode(
            status_obj=None,
            sender_actor_id=ACTOR_ID,
            case_id=CASE_ID,
        )
        result = populated_bridge.execute_with_setup(
            tree=node, actor_id=CASE_MANAGER_ID
        )
        assert result.status == Status.SUCCESS


# ---------------------------------------------------------------------------
# Step 5: AutoCloseBranchNode
# ---------------------------------------------------------------------------


class TestAutoCloseBranchNode:
    def test_skips_when_participants_not_closed(self, populated_bridge):
        node = AutoCloseBranchNode(case_id=CASE_ID)
        result = populated_bridge.execute_with_setup(
            tree=node, actor_id=CASE_MANAGER_ID
        )
        assert result.status == Status.SUCCESS

    def test_logs_auto_close_when_all_closed(
        self,
        populated_dl,
        populated_bridge,
        participant,
        case_manager_participant,
    ):
        """When all CVD participants have RM.CLOSED, auto-close branch logs it."""
        closed_status = ParticipantStatus(
            id_=f"{STATUS_ID}/closed",
            context=CASE_ID,
            rm_state=RM.CLOSED,
        )
        populated_dl.create(closed_status)
        participant.participant_statuses.append(closed_status)
        populated_dl.save(participant)

        node = AutoCloseBranchNode(case_id=CASE_ID)
        result = populated_bridge.execute_with_setup(
            tree=node, actor_id=CASE_MANAGER_ID
        )
        assert result.status == Status.SUCCESS

    def test_skips_when_no_case_id(self, bridge):
        node = AutoCloseBranchNode(case_id=None)
        result = bridge.execute_with_setup(tree=node, actor_id=ACTOR_ID)
        assert result.status == Status.SUCCESS


# ---------------------------------------------------------------------------
# Full tree: add_participant_status_tree
# ---------------------------------------------------------------------------


class TestAddParticipantStatusTree:
    def test_full_tree_succeeds_for_known_sender(
        self,
        populated_dl,
        make_payload,
    ):
        """End-to-end: known sender → all five steps succeed."""
        activity = add_status_to_participant_activity(
            status=ParticipantStatus(id_=STATUS_ID, context=CASE_ID),
            target=CaseParticipant(
                id_=PARTICIPANT_ID, context=CASE_ID, attributed_to=ACTOR_ID
            ),
            actor=ACTOR_ID,
            context=VulnerabilityCase(id_=CASE_ID, name="Test"),
        )
        event = make_payload(activity)
        bridge = BTBridge(datalayer=populated_dl)
        tree = add_participant_status_tree(request=event)
        result = bridge.execute_with_setup(tree=tree, actor_id=ACTOR_ID)
        assert result.status == Status.SUCCESS

        p = populated_dl.read(PARTICIPANT_ID)
        assert p is not None
        status_ids = [getattr(s, "id_", s) for s in p.participant_statuses]
        assert STATUS_ID in status_ids

    def test_full_tree_fails_for_unknown_sender(
        self,
        populated_dl,
        make_payload,
    ):
        """Unknown sender → VerifySenderIsParticipantNode fails, tree halts."""
        activity = add_status_to_participant_activity(
            status=ParticipantStatus(id_=STATUS_ID, context=CASE_ID),
            target=CaseParticipant(
                id_=PARTICIPANT_ID, context=CASE_ID, attributed_to=OUTSIDER_ID
            ),
            actor=OUTSIDER_ID,
            context=VulnerabilityCase(id_=CASE_ID, name="Test"),
        )
        event = make_payload(activity)
        bridge = BTBridge(datalayer=populated_dl)
        tree = add_participant_status_tree(request=event)
        result = bridge.execute_with_setup(tree=tree, actor_id=OUTSIDER_ID)
        assert result.status == Status.FAILURE

        p = populated_dl.read(PARTICIPANT_ID)
        assert p is not None
        # STATUS_ID was NOT appended; only the auto-initialised default status exists
        status_ids = [getattr(s, "id_", s) for s in p.participant_statuses]
        assert STATUS_ID not in status_ids
