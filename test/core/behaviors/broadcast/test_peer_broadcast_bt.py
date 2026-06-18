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

"""Unit tests for the shared fail-fast peer broadcast helper (BT-14-001, BT-14-002).

Covers:
- :func:`~vultron.core.behaviors.broadcast.nodes._find_case_manager_id`
- :class:`~vultron.core.behaviors.broadcast.nodes.FindCaseManagerNode`
- :class:`~vultron.core.behaviors.broadcast.nodes.FilterPeerRecipientsNode`
- :class:`~vultron.core.behaviors.broadcast.nodes.CreateBroadcastActivityNode`
- :class:`~vultron.core.behaviors.broadcast.nodes.BroadcastQueueToOutboxNode`
- :func:`~vultron.core.behaviors.broadcast.peer_broadcast_tree.peer_broadcast_bt`

Per specs/behavior-tree-integration.yaml BT-14-001, BT-14-002.
"""

from unittest.mock import MagicMock

import py_trees
import pytest
from py_trees.common import Status

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.broadcast.nodes import (
    BroadcastQueueToOutboxNode,
    CreateBroadcastActivityNode,
    FilterPeerRecipientsNode,
    FindCaseManagerNode,
    _find_case_manager_id,
)
from vultron.core.behaviors.broadcast.peer_broadcast_tree import (
    peer_broadcast_bt,
)
from vultron.core.states.roles import CVDRole
from vultron.wire.as2.vocab.objects.case_participant import CaseParticipant
from vultron.wire.as2.vocab.objects.vulnerability_case import VulnerabilityCase

# ---------------------------------------------------------------------------
# Test fixtures
# ---------------------------------------------------------------------------

ACTOR_ID = "https://example.org/actors/vendor"
CASE_MANAGER_ID = "https://example.org/actors/case-actor"
PEER_ID = "https://example.org/actors/peer"
SECOND_PEER_ID = "https://example.org/actors/peer2"
CASE_ID = "https://example.org/cases/case-01"
PARTICIPANT_ID = "https://example.org/cases/case-01/participants/vendor"
CM_PARTICIPANT_ID = "https://example.org/cases/case-01/participants/case-actor"
PEER_PARTICIPANT_ID = "https://example.org/cases/case-01/participants/peer"
SECOND_PEER_PARTICIPANT_ID = (
    "https://example.org/cases/case-01/participants/peer2"
)


@pytest.fixture(autouse=True)
def clear_blackboard():
    py_trees.blackboard.Blackboard.storage.clear()
    yield
    py_trees.blackboard.Blackboard.storage.clear()


@pytest.fixture
def dl():
    return SqliteDataLayer("sqlite:///:memory:")


@pytest.fixture
def bridge(dl):
    return BTBridge(datalayer=dl)


@pytest.fixture
def vendor_participant():
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
def peer_participant():
    return CaseParticipant(
        id_=PEER_PARTICIPANT_ID,
        context=CASE_ID,
        attributed_to=PEER_ID,
        case_roles=[CVDRole.COORDINATOR],
    )


@pytest.fixture
def case_with_peers(
    vendor_participant, case_manager_participant, peer_participant
):
    obj = VulnerabilityCase(id_=CASE_ID, name="Test Case")
    obj.add_participant(vendor_participant)
    obj.add_participant(case_manager_participant)
    obj.add_participant(peer_participant)
    return obj


@pytest.fixture
def populated_dl(
    dl,
    case_with_peers,
    vendor_participant,
    case_manager_participant,
    peer_participant,
):
    dl.create(case_with_peers)
    dl.create(vendor_participant)
    dl.create(case_manager_participant)
    dl.create(peer_participant)
    return dl


@pytest.fixture
def populated_bridge(populated_dl):
    return BTBridge(datalayer=populated_dl)


# ---------------------------------------------------------------------------
# _find_case_manager_id helper
# ---------------------------------------------------------------------------


class TestFindCaseManagerIdHelper:
    def test_finds_case_manager(self, populated_dl, case_with_peers):
        result = _find_case_manager_id(populated_dl, case_with_peers)
        assert result == CASE_MANAGER_ID

    def test_returns_none_when_no_case_manager(self, dl):
        case = VulnerabilityCase(id_=CASE_ID, name="Test Case")
        p = CaseParticipant(
            id_=PARTICIPANT_ID,
            context=CASE_ID,
            attributed_to=ACTOR_ID,
            case_roles=[CVDRole.CASE_OWNER],
        )
        case.add_participant(p)
        dl.create(case)
        dl.create(p)
        result = _find_case_manager_id(dl, case)
        assert result is None


# ---------------------------------------------------------------------------
# FindCaseManagerNode
# ---------------------------------------------------------------------------


class TestFindCaseManagerNode:
    def test_success_writes_blackboard(self, populated_bridge):
        node = FindCaseManagerNode(case_id=CASE_ID)
        result = populated_bridge.execute_with_setup(
            tree=node, actor_id=ACTOR_ID
        )
        assert result.status == Status.SUCCESS
        assert (
            py_trees.blackboard.Blackboard.storage[
                "/broadcast_case_manager_id"
            ]
            == CASE_MANAGER_ID
        )

    def test_none_case_id_fails(self, populated_bridge):
        node = FindCaseManagerNode(case_id=None)
        result = populated_bridge.execute_with_setup(
            tree=node, actor_id=ACTOR_ID
        )
        assert result.status == Status.FAILURE

    def test_missing_case_fails(self, bridge):
        node = FindCaseManagerNode(case_id="https://example.org/cases/missing")
        result = bridge.execute_with_setup(tree=node, actor_id=ACTOR_ID)
        assert result.status == Status.FAILURE

    def test_no_case_manager_participant_fails(self, dl):
        case = VulnerabilityCase(id_=CASE_ID, name="No CM")
        p = CaseParticipant(
            id_=PARTICIPANT_ID,
            context=CASE_ID,
            attributed_to=ACTOR_ID,
            case_roles=[CVDRole.CASE_OWNER],
        )
        case.actor_participant_index[ACTOR_ID] = PARTICIPANT_ID
        dl.create(case)
        dl.create(p)
        b = BTBridge(datalayer=dl)
        node = FindCaseManagerNode(case_id=CASE_ID)
        result = b.execute_with_setup(tree=node, actor_id=ACTOR_ID)
        assert result.status == Status.FAILURE


# ---------------------------------------------------------------------------
# FilterPeerRecipientsNode
# ---------------------------------------------------------------------------


class TestFilterPeerRecipientsNode:
    def _run_find_then_filter(
        self,
        dl,
        actor_id,
        sender_actor_id=ACTOR_ID,
        case_id=CASE_ID,
    ):
        seq = py_trees.composites.Sequence(
            name="TestSeq",
            memory=False,
            children=[
                FindCaseManagerNode(case_id=CASE_ID),
                FilterPeerRecipientsNode(
                    sender_actor_id=sender_actor_id,
                    case_id=case_id,
                ),
            ],
        )
        b = BTBridge(datalayer=dl)
        return b.execute_with_setup(tree=seq, actor_id=actor_id)

    def test_success_with_eligible_peer(self, populated_dl):
        result = self._run_find_then_filter(
            populated_dl,
            actor_id=CASE_MANAGER_ID,
            sender_actor_id=ACTOR_ID,
        )
        assert result.status == Status.SUCCESS
        assert py_trees.blackboard.Blackboard.storage[
            "/broadcast_peer_recipient_ids"
        ] == [PEER_ID]

    def test_success_with_empty_list_when_no_eligible_recipients(
        self, populated_dl
    ):
        """No peers after filtering → empty list, SUCCESS (no-op, BT-14-001)."""
        # Remove PEER from the case so only vendor+CM remain
        case = populated_dl.read(CASE_ID)
        del case.actor_participant_index[PEER_ID]
        populated_dl.save(case)
        result = self._run_find_then_filter(
            populated_dl,
            actor_id=CASE_MANAGER_ID,
            sender_actor_id=ACTOR_ID,
        )
        assert result.status == Status.SUCCESS
        assert (
            py_trees.blackboard.Blackboard.storage[
                "/broadcast_peer_recipient_ids"
            ]
            == []
        )

    def test_fails_on_missing_case(self, populated_dl):
        result = self._run_find_then_filter(
            populated_dl,
            actor_id=CASE_MANAGER_ID,
            case_id="https://example.org/cases/missing",
        )
        assert result.status == Status.FAILURE

    def test_excludes_sender(self, populated_dl):
        """Sender is excluded from recipient list."""
        result = self._run_find_then_filter(
            populated_dl,
            actor_id=CASE_MANAGER_ID,
            sender_actor_id=PEER_ID,
        )
        # ACTOR_ID is not sender, not self (CASE_MANAGER_ID), not CM
        assert result.status == Status.SUCCESS
        assert py_trees.blackboard.Blackboard.storage[
            "/broadcast_peer_recipient_ids"
        ] == [ACTOR_ID]

    def test_excludes_self(self, populated_dl):
        """Executing actor is excluded from recipients; empty list → SUCCESS."""
        result = self._run_find_then_filter(
            populated_dl,
            actor_id=PEER_ID,
            sender_actor_id=ACTOR_ID,
        )
        assert result.status == Status.SUCCESS
        assert (
            py_trees.blackboard.Blackboard.storage[
                "/broadcast_peer_recipient_ids"
            ]
            == []
        )


# ---------------------------------------------------------------------------
# CreateBroadcastActivityNode
# ---------------------------------------------------------------------------


class TestCreateBroadcastActivityNode:
    def _make_seq(self, activity_builder, sender_actor_id=ACTOR_ID):
        return py_trees.composites.Sequence(
            name="TestSeq",
            memory=False,
            children=[
                FindCaseManagerNode(case_id=CASE_ID),
                FilterPeerRecipientsNode(
                    sender_actor_id=sender_actor_id, case_id=CASE_ID
                ),
                CreateBroadcastActivityNode(activity_builder=activity_builder),
            ],
        )

    def test_success_calls_builder_with_correct_args(self, populated_dl):
        mock_factory = MagicMock()
        mock_factory.some_method.return_value = "urn:uuid:activity-1"

        def builder(factory, cm_id, recipient_ids):
            return factory.some_method(actor=cm_id, to=recipient_ids)

        bridge = BTBridge(
            datalayer=populated_dl, trigger_activity=mock_factory
        )
        result = bridge.execute_with_setup(
            tree=self._make_seq(builder), actor_id=CASE_MANAGER_ID
        )
        assert result.status == Status.SUCCESS
        mock_factory.some_method.assert_called_once_with(
            actor=CASE_MANAGER_ID, to=[PEER_ID]
        )
        assert (
            py_trees.blackboard.Blackboard.storage["/broadcast_activity_id"]
            == "urn:uuid:activity-1"
        )

    def test_failure_when_no_factory_and_recipients_exist(
        self, populated_bridge
    ):
        """Recipients exist but no factory → FAILURE (BT-14-001)."""
        builder = MagicMock()

        result = populated_bridge.execute_with_setup(
            tree=self._make_seq(builder), actor_id=CASE_MANAGER_ID
        )
        assert result.status == Status.FAILURE
        builder.assert_not_called()

    def test_success_skips_builder_when_empty_recipients(self, populated_dl):
        """No eligible recipients → SUCCESS without calling builder."""
        case = populated_dl.read(CASE_ID)
        del case.actor_participant_index[PEER_ID]
        populated_dl.save(case)

        builder = MagicMock()
        bridge = BTBridge(datalayer=populated_dl)
        result = bridge.execute_with_setup(
            tree=self._make_seq(builder), actor_id=CASE_MANAGER_ID
        )
        assert result.status == Status.SUCCESS
        builder.assert_not_called()

    def test_failure_on_vultron_error_from_builder(self, populated_dl):
        from vultron.errors import VultronError

        mock_factory = MagicMock()
        mock_factory.some_method.side_effect = VultronError("factory failure")

        def builder(factory, cm_id, recipient_ids):
            return factory.some_method(actor=cm_id, to=recipient_ids)

        bridge = BTBridge(
            datalayer=populated_dl, trigger_activity=mock_factory
        )
        result = bridge.execute_with_setup(
            tree=self._make_seq(builder), actor_id=CASE_MANAGER_ID
        )
        assert result.status == Status.FAILURE


# ---------------------------------------------------------------------------
# BroadcastQueueToOutboxNode
# ---------------------------------------------------------------------------


class TestBroadcastQueueToOutboxNode:
    def _run_full_seq(self, dl, actor_id, factory=None):
        mock_factory = factory or MagicMock()
        if factory is None:
            mock_factory.some_method.return_value = "urn:uuid:activity-1"

        def builder(f, cm_id, recipient_ids):
            return f.some_method(actor=cm_id, to=recipient_ids)

        seq = py_trees.composites.Sequence(
            name="TestSeq",
            memory=False,
            children=[
                FindCaseManagerNode(case_id=CASE_ID),
                FilterPeerRecipientsNode(
                    sender_actor_id=ACTOR_ID, case_id=CASE_ID
                ),
                CreateBroadcastActivityNode(activity_builder=builder),
                BroadcastQueueToOutboxNode(),
            ],
        )
        bridge = BTBridge(datalayer=dl, trigger_activity=mock_factory)
        return bridge.execute_with_setup(tree=seq, actor_id=actor_id)

    def test_full_sequence_success(self, populated_dl):
        result = self._run_full_seq(populated_dl, actor_id=CASE_MANAGER_ID)
        assert result.status == Status.SUCCESS

    def test_success_skips_when_no_activity_id(self, populated_dl):
        """No broadcast_activity_id on blackboard → no-op SUCCESS (BT-14-001)."""
        node = BroadcastQueueToOutboxNode()
        # We need broadcast_case_manager_id to be set but no activity_id
        # Pre-populate only the case_manager key via FindCaseManagerNode
        seq = py_trees.composites.Sequence(
            name="TestSeq",
            memory=False,
            children=[
                FindCaseManagerNode(case_id=CASE_ID),
                node,
            ],
        )
        bridge = BTBridge(datalayer=populated_dl)
        result = bridge.execute_with_setup(tree=seq, actor_id=CASE_MANAGER_ID)
        # broadcast_peer_recipient_ids is missing → FAILURE on that key
        # Actually BroadcastQueueToOutboxNode tries broadcast_activity_id first,
        # gets KeyError → SUCCESS (no-op).  Then tries recipient_ids → KeyError
        # but we only test that the no-activity-id path exits SUCCESS.
        # The actual status depends on whether recipient_ids key exists.
        # We just confirm the node handles missing broadcast_activity_id.
        assert result.status == Status.SUCCESS

    def test_failure_when_case_manager_id_missing(self, dl):
        """No broadcast_case_manager_id in blackboard → FAILURE."""
        node = BroadcastQueueToOutboxNode()
        bridge = BTBridge(datalayer=dl)
        result = bridge.execute_with_setup(tree=node, actor_id=CASE_MANAGER_ID)
        assert result.status == Status.FAILURE


# ---------------------------------------------------------------------------
# peer_broadcast_bt integration
# ---------------------------------------------------------------------------


class TestPeerBroadcastBt:
    def _make_bt(
        self,
        activity_builder,
        sender_actor_id: str = ACTOR_ID,
        case_id: str | None = CASE_ID,
    ):
        return peer_broadcast_bt(
            case_id=case_id,
            sender_actor_id=sender_actor_id,
            activity_builder=activity_builder,
        )

    def test_success_end_to_end(self, populated_dl):
        """Full happy-path: factory called, activity queued. (BT-14-002)"""
        mock_factory = MagicMock()
        mock_factory.deliver.return_value = "urn:uuid:broadcast-1"

        def builder(factory, cm_id, recipient_ids):
            return factory.deliver(actor=cm_id, to=recipient_ids)

        bridge = BTBridge(
            datalayer=populated_dl, trigger_activity=mock_factory
        )
        tree = self._make_bt(builder)
        result = bridge.execute_with_setup(tree=tree, actor_id=CASE_MANAGER_ID)
        assert result.status == Status.SUCCESS
        mock_factory.deliver.assert_called_once_with(
            actor=CASE_MANAGER_ID, to=[PEER_ID]
        )

    def test_failure_when_no_case_manager(self, dl):
        """No CASE_MANAGER in case → FAILURE (BT-14-001)."""
        case = VulnerabilityCase(id_=CASE_ID, name="No CM")
        p = CaseParticipant(
            id_=PARTICIPANT_ID,
            context=CASE_ID,
            attributed_to=ACTOR_ID,
            case_roles=[CVDRole.CASE_OWNER],
        )
        case.actor_participant_index[ACTOR_ID] = PARTICIPANT_ID
        dl.create(case)
        dl.create(p)
        builder = MagicMock()
        bridge = BTBridge(datalayer=dl)
        tree = self._make_bt(builder)
        result = bridge.execute_with_setup(tree=tree, actor_id=ACTOR_ID)
        assert result.status == Status.FAILURE
        builder.assert_not_called()

    def test_failure_when_factory_unavailable_and_recipients_exist(
        self, populated_bridge
    ):
        """Recipients exist but no factory → FAILURE (BT-14-001)."""
        builder = MagicMock()
        tree = self._make_bt(builder)
        result = populated_bridge.execute_with_setup(
            tree=tree, actor_id=CASE_MANAGER_ID
        )
        assert result.status == Status.FAILURE
        builder.assert_not_called()

    def test_failure_when_factory_raises_vultron_error(self, populated_dl):
        """Factory raises VultronError → FAILURE (BT-14-001)."""
        from vultron.errors import VultronError

        mock_factory = MagicMock()
        mock_factory.deliver.side_effect = VultronError("delivery error")

        def builder(factory, cm_id, recipient_ids):
            return factory.deliver(actor=cm_id, to=recipient_ids)

        bridge = BTBridge(
            datalayer=populated_dl, trigger_activity=mock_factory
        )
        tree = self._make_bt(builder)
        result = bridge.execute_with_setup(tree=tree, actor_id=CASE_MANAGER_ID)
        assert result.status == Status.FAILURE

    def test_success_when_no_eligible_recipients(self, populated_dl):
        """No peers after filtering → empty list → SUCCESS (no-op, BT-14-001)."""
        case = populated_dl.read(CASE_ID)
        del case.actor_participant_index[PEER_ID]
        populated_dl.save(case)

        builder = MagicMock()
        bridge = BTBridge(datalayer=populated_dl)
        tree = self._make_bt(builder)
        result = bridge.execute_with_setup(tree=tree, actor_id=CASE_MANAGER_ID)
        assert result.status == Status.SUCCESS
        builder.assert_not_called()

    def test_failure_when_none_case_id(self, populated_bridge):
        """case_id=None → FindCaseManagerNode FAILURE (BT-14-001)."""
        builder = MagicMock()
        tree = self._make_bt(builder, case_id=None)
        result = populated_bridge.execute_with_setup(
            tree=tree, actor_id=CASE_MANAGER_ID
        )
        assert result.status == Status.FAILURE
        builder.assert_not_called()

    def test_no_guaranteed_success_fallback(self, populated_dl):
        """Verify there is no Selector+Success anti-pattern (BT-14-001).

        A plain Sequence must propagate FAILURE; if a Selector-with-Success
        were present, the tree would return SUCCESS even when the factory is
        unavailable.  This test confirms the FAILURE is NOT masked.
        """
        builder = MagicMock()
        # populated_dl has a peer, so the factory WILL be called — but we
        # have no factory → FAILURE must propagate to the root.
        bridge = BTBridge(datalayer=populated_dl)
        tree = self._make_bt(builder)
        result = bridge.execute_with_setup(tree=tree, actor_id=CASE_MANAGER_ID)
        assert result.status == Status.FAILURE, (
            "peer_broadcast_bt must NOT have a guaranteed-SUCCESS fallback "
            "(BT-14-001): got SUCCESS when factory was unavailable"
        )
