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

"""Tests for the CaseActor-routed suggest-actor BT factories (ADR-0026/CM-16).

Covers:
- create_recommend_actor_to_case_received_tree
- create_accept_actor_recommendation_received_tree
- create_reject_actor_recommendation_received_tree
- EvaluateDefaultRolesNode (AC-1 through AC-4, CM-16-003)

Per specs/behavior-tree-integration.yaml BT-15-001, BTND-02-001 (memory=False),
ADR-0026/CM-16.
"""

from unittest.mock import MagicMock

import py_trees
from py_trees.common import Status

from vultron.core.behaviors.case.suggest_actor_tree import (
    ActorAlreadyParticipantNode,
    EmitAcceptActorRecommendationNode,
    EmitNoteDuplicateRecommendationToOwnerNode,
    EmitOfferCaseParticipantToOwnerNode,
    EmitRejectActorRecommendationNode,
    InviteInFlightNode,
    PendingOfferCaseParticipantNode,
    create_accept_actor_recommendation_received_tree,
    create_recommend_actor_to_case_received_tree,
    create_reject_actor_recommendation_received_tree,
)
from vultron.core.behaviors.case.nodes.actor import (
    EmitInviteActorToCaseNode,
    EvaluateDefaultRolesNode,
)
from vultron.core.models.protocol_pair import (
    INVITE_ACTOR_TO_CASE_REPLY_TYPES,
    OFFER_CASE_PARTICIPANT_REPLY_TYPES,
    ProtocolPair,
)
from vultron.core.states.roles import CVDRole

_REC_ID = "https://example.org/recommendations/rec-1"
_RECOMMENDER = "https://example.org/actors/recommender"
_RECOMMENDED = "https://example.org/actors/recommended"
_CASE_ID = "https://example.org/cases/case-1"


class TestEvaluateDefaultRolesNode:
    """Unit tests for EvaluateDefaultRolesNode (AC-1, AC-2, AC-3, CM-16-003)."""

    def setup_method(self):
        py_trees.blackboard.Blackboard.enable_activity_stream()
        self.node = EvaluateDefaultRolesNode(
            suggested_actor_id=_RECOMMENDED,
            case_id=_CASE_ID,
            recommendation_id=_REC_ID,
        )
        self.node.setup()
        self.node.initialise()

    def teardown_method(self):
        py_trees.blackboard.Blackboard.disable_activity_stream()
        py_trees.blackboard.Blackboard.storage.clear()

    def test_node_exists(self):
        """AC-1: EvaluateDefaultRolesNode exists in the BT node library."""
        assert self.node is not None

    def test_node_name_defaults_to_class_name(self):
        assert self.node.name == "EvaluateDefaultRolesNode"

    def test_node_stores_suggested_actor_id(self):
        assert self.node.suggested_actor_id == _RECOMMENDED

    def test_node_stores_case_id(self):
        assert self.node.case_id == _CASE_ID

    def test_node_stores_recommendation_id(self):
        """AC-1: EvaluateDefaultRolesNode accepts recommendation_id."""
        assert self.node.recommendation_id == _REC_ID

    def test_returns_success_unconditionally(self):
        """returns SUCCESS unconditionally in the prototype."""
        result = self.node.update()
        assert result == Status.SUCCESS

    def test_writes_vendor_role_to_namespaced_blackboard_key(self):
        """AC-2: writes suggested_roles_{segment} = [CVDRole.VENDOR] to blackboard."""
        self.node.update()
        expected_key = f"/suggested_roles_{_REC_ID.split('/')[-1]}"
        raw = py_trees.blackboard.Blackboard.storage.get(expected_key)
        assert raw == [
            CVDRole.VENDOR
        ], f"Expected [CVDRole.VENDOR] at '{expected_key}', got {raw!r}"

    def test_does_not_write_global_suggested_roles_key(self):
        """AC-4: raw /suggested_roles key must not be written."""
        self.node.update()
        raw = py_trees.blackboard.Blackboard.storage.get("/suggested_roles")
        assert (
            raw is None
        ), f"Expected no /suggested_roles key, but found {raw!r}"

    def test_custom_name_accepted(self):
        node = EvaluateDefaultRolesNode(
            suggested_actor_id=_RECOMMENDED,
            case_id=_CASE_ID,
            recommendation_id=_REC_ID,
            name="MyCustomName",
        )
        assert node.name == "MyCustomName"

    def test_two_instances_write_different_keys(self):
        """AC-3: two tree instances with different recommendation_ids write to different keys."""
        rec_id_2 = "https://example.org/recommendations/rec-2"
        node2 = EvaluateDefaultRolesNode(
            suggested_actor_id=_RECOMMENDED,
            case_id=_CASE_ID,
            recommendation_id=rec_id_2,
        )
        node2.setup()
        node2.initialise()

        self.node.update()
        node2.update()

        key1 = f"/suggested_roles_{_REC_ID.split('/')[-1]}"
        key2 = f"/suggested_roles_{rec_id_2.split('/')[-1]}"

        assert (
            key1 != key2
        ), "Keys must differ for different recommendation_ids"
        assert py_trees.blackboard.Blackboard.storage.get(key1) == [
            CVDRole.VENDOR
        ]
        assert py_trees.blackboard.Blackboard.storage.get(key2) == [
            CVDRole.VENDOR
        ]

    def test_returns_failure_when_compute_roles_returns_empty(self):
        """AC-4: returns FAILURE when _compute_roles() returns empty list (CM-16-003).

        Guards future Evaluator overrides that substitute a custom evaluator
        returning [] — the empty list must be rejected at write time per
        ADR-0032 / BT-HELPER-01, not silently overridden by the consumer.
        """

        class _EmptyRolesNode(EvaluateDefaultRolesNode):
            def _compute_roles(self):
                return []

        node = _EmptyRolesNode(
            suggested_actor_id=_RECOMMENDED,
            case_id=_CASE_ID,
            recommendation_id=_REC_ID,
        )
        node.setup()
        node.initialise()
        result = node.update()
        assert result == Status.FAILURE
        assert node.feedback_message, "feedback_message must be set on FAILURE"
        # blackboard key must not be written
        expected_key = f"/suggested_roles_{_REC_ID.split('/')[-1]}"
        raw = py_trees.blackboard.Blackboard.storage.get(expected_key)
        assert raw is None, (
            f"Blackboard key '{expected_key}' must not be written when "
            f"_compute_roles() returns empty list, got {raw!r}"
        )


class TestRecommendActorToCaseReceivedTree:
    """Structural tests for create_recommend_actor_to_case_received_tree."""

    def setup_method(self):
        self.tree = create_recommend_actor_to_case_received_tree(
            recommendation_id=_REC_ID,
            recommender_id=_RECOMMENDER,
            recommended_id=_RECOMMENDED,
            case_id=_CASE_ID,
        )

    def test_root_is_sequence(self):
        assert isinstance(self.tree, py_trees.composites.Sequence)

    def test_root_name(self):
        assert self.tree.name == "RecommendActorToCaseBT"

    def test_memory_false(self):
        assert self.tree.memory is False, (
            "RecommendActorToCaseBT root Sequence must use memory=False "
            "(BTND-02-001 stateless-ticking invariant)"
        )

    def _flatten_tree_types(self):
        """Collect all node types via depth-first walk."""
        types = []
        for node in self.tree.iterate():
            types.append(type(node))
        return types

    def test_has_evaluate_default_roles_node(self):
        """AC-4 (tree wiring): EvaluateDefaultRolesNode appears in the tree."""
        all_types = self._flatten_tree_types()
        assert (
            EvaluateDefaultRolesNode in all_types
        ), "RecommendActorToCaseBT must contain EvaluateDefaultRolesNode"

    def test_evaluate_roles_node_before_emit_node(self):
        """EvaluateDefaultRolesNode must precede EmitOfferCaseParticipantToOwnerNode."""
        nodes = list(self.tree.iterate())
        types = [type(n) for n in nodes]
        eval_idx = next(
            (i for i, t in enumerate(types) if t is EvaluateDefaultRolesNode),
            None,
        )
        emit_idx = next(
            (
                i
                for i, t in enumerate(types)
                if t is EmitOfferCaseParticipantToOwnerNode
            ),
            None,
        )
        assert eval_idx is not None, "EvaluateDefaultRolesNode not found"
        assert (
            emit_idx is not None
        ), "EmitOfferCaseParticipantToOwnerNode not found"
        assert eval_idx < emit_idx, (
            "EvaluateDefaultRolesNode must appear before "
            "EmitOfferCaseParticipantToOwnerNode in tree ordering"
        )

    def test_evaluate_node_carries_recommended_id(self):
        nodes = [
            n
            for n in self.tree.iterate()
            if isinstance(n, EvaluateDefaultRolesNode)
        ]
        assert nodes, "Expected EvaluateDefaultRolesNode in tree"
        node = nodes[0]
        assert node.suggested_actor_id == _RECOMMENDED
        assert node.case_id == _CASE_ID

    def test_has_emit_offer_case_participant_node(self):
        """Effect nodes must include EmitOfferCaseParticipantToOwnerNode."""
        all_types = self._flatten_tree_types()
        assert (
            EmitOfferCaseParticipantToOwnerNode in all_types
        ), "RecommendActorToCaseBT must contain EmitOfferCaseParticipantToOwnerNode"

    def test_emit_node_carries_recommendation_id(self):
        """The emit node must carry the original recommendation ID as origin."""
        emit_nodes = [
            n
            for n in self.tree.iterate()
            if isinstance(n, EmitOfferCaseParticipantToOwnerNode)
        ]
        assert (
            emit_nodes
        ), "Expected EmitOfferCaseParticipantToOwnerNode in tree"
        node = emit_nodes[0]
        assert node.recommendation_id == _REC_ID
        assert node.recommender_id == _RECOMMENDER
        assert node.recommended_id == _RECOMMENDED
        assert node.case_id == _CASE_ID


class TestEmitOfferCaseParticipantToOwnerNodeEmptyRoles:
    """Unit tests for the empty-roles guard in EmitOfferCaseParticipantToOwnerNode."""

    def _node(self):
        dl = MagicMock()
        factory = MagicMock()
        node = EmitOfferCaseParticipantToOwnerNode(
            recommendation_id=_REC_ID,
            recommender_id=_RECOMMENDER,
            recommended_id=_RECOMMENDED,
            case_id=_CASE_ID,
        )
        # Wire datalayer and actor_id via the standard helper.
        writer = py_trees.blackboard.Client(name="test-emit-setup-writer")
        writer.register_key(
            key="datalayer", access=py_trees.common.Access.WRITE
        )
        writer.register_key(
            key="actor_id", access=py_trees.common.Access.WRITE
        )
        writer.register_key(
            key="trigger_activity_factory",
            access=py_trees.common.Access.WRITE,
        )
        writer.datalayer = dl
        writer.actor_id = _ACTOR_ID
        writer.trigger_activity_factory = factory
        node.setup()
        node.initialise()
        # Simulate a pathological writer that bypasses EvaluateDefaultRolesNode's
        # non-empty invariant by writing [] to the namespaced blackboard key.
        id_segment = _REC_ID.split("/")[-1]
        py_trees.blackboard.Blackboard.storage[
            f"/suggested_roles_{id_segment}"
        ] = []
        return node, factory

    def setup_method(self):
        py_trees.blackboard.Blackboard.enable_activity_stream()

    def teardown_method(self):
        py_trees.blackboard.Blackboard.disable_activity_stream()
        py_trees.blackboard.Blackboard.storage.clear()

    def test_returns_failure_when_roles_empty(self):
        """update() must return FAILURE when suggested_roles is [] (CM-16-003)."""
        node, _ = self._node()
        result = node.update()
        assert result == Status.FAILURE
        assert node.feedback_message, "feedback_message must be set on FAILURE"

    def test_factory_not_called_when_roles_empty(self):
        """factory.offer_actor_to_case must not be called with empty roles."""
        node, factory = self._node()
        node.update()
        factory.offer_actor_to_case.assert_not_called()


class TestEmitInviteActorToCaseNodeEmptyRoles:
    """Unit tests for the empty-roles guard in EmitInviteActorToCaseNode (CM-17-003)."""

    _CASE_ID_INVITE = "https://example.org/cases/case-invite-1"
    _INVITEE_ID = "https://example.org/actors/invitee"

    def _node(self):
        dl = MagicMock()
        factory = MagicMock()
        node = EmitInviteActorToCaseNode(
            invitee_id=self._INVITEE_ID,
            case_id=self._CASE_ID_INVITE,
        )
        writer = py_trees.blackboard.Client(
            name="test-invite-empty-roles-writer"
        )
        writer.register_key(
            key="datalayer", access=py_trees.common.Access.WRITE
        )
        writer.register_key(
            key="actor_id", access=py_trees.common.Access.WRITE
        )
        writer.register_key(
            key="trigger_activity_factory",
            access=py_trees.common.Access.WRITE,
        )
        writer.datalayer = dl
        writer.actor_id = _ACTOR_ID
        writer.trigger_activity_factory = factory
        node.setup()
        node.initialise()
        # Write empty roles list to simulate a caller passing roles=[] via
        # InviteActorToCaseTriggerRequest.roles=[] → kwargs["suggested_roles"]=[]
        py_trees.blackboard.Blackboard.storage["/suggested_roles"] = []
        return node, factory

    def setup_method(self):
        py_trees.blackboard.Blackboard.enable_activity_stream()

    def teardown_method(self):
        py_trees.blackboard.Blackboard.disable_activity_stream()
        py_trees.blackboard.Blackboard.storage.clear()

    def test_returns_failure_when_roles_empty(self):
        """update() must return FAILURE when suggested_roles is [] (CM-17-003)."""
        node, _ = self._node()
        result = node.update()
        assert result == Status.FAILURE
        assert node.feedback_message, "feedback_message must be set on FAILURE"

    def test_factory_not_called_when_roles_empty(self):
        """factory.invite_actor_to_case must not be called with empty roles."""
        node, factory = self._node()
        node.update()
        factory.invite_actor_to_case.assert_not_called()


class TestAcceptActorRecommendationReceivedTree:
    """Structural tests for create_accept_actor_recommendation_received_tree."""

    def setup_method(self):
        self.tree = create_accept_actor_recommendation_received_tree(
            recommendation_id=_REC_ID,
            recommender_id=_RECOMMENDER,
            invitee_id=_RECOMMENDED,
            case_id=_CASE_ID,
        )

    def test_root_is_sequence(self):
        assert isinstance(self.tree, py_trees.composites.Sequence)

    def test_root_name(self):
        assert self.tree.name == "AcceptActorRecommendationBT"

    def test_memory_false(self):
        assert (
            self.tree.memory is False
        ), "AcceptActorRecommendationBT root Sequence must use memory=False"

    def test_has_accept_recommendation_node(self):
        nodes = [
            c
            for c in self.tree.children
            if isinstance(c, EmitAcceptActorRecommendationNode)
        ]
        assert nodes, "Expected EmitAcceptActorRecommendationNode in tree"
        node = nodes[0]
        assert node.recommender_id == _RECOMMENDER
        assert node.recommendation_id == _REC_ID
        assert node.recommended_id == _RECOMMENDED
        assert node.case_id == _CASE_ID

    def test_has_invite_actor_node(self):
        nodes = [
            c
            for c in self.tree.children
            if isinstance(c, EmitInviteActorToCaseNode)
        ]
        assert (
            nodes
        ), "Expected EmitInviteActorToCaseNode in tree (CM-16-006 step 4)"
        node = nodes[0]
        assert node.invitee_id == _RECOMMENDED
        assert node.case_id == _CASE_ID


class TestRejectActorRecommendationReceivedTree:
    """Structural tests for create_reject_actor_recommendation_received_tree."""

    def setup_method(self):
        self.tree = create_reject_actor_recommendation_received_tree(
            recommendation_id=_REC_ID,
            recommender_id=_RECOMMENDER,
            recommended_id=_RECOMMENDED,
            case_id=_CASE_ID,
        )

    def test_root_is_sequence(self):
        assert isinstance(self.tree, py_trees.composites.Sequence)

    def test_root_name(self):
        assert self.tree.name == "RejectActorRecommendationBT"

    def test_memory_false(self):
        assert (
            self.tree.memory is False
        ), "RejectActorRecommendationBT root Sequence must use memory=False"

    def test_has_reject_recommendation_node(self):
        nodes = [
            c
            for c in self.tree.children
            if isinstance(c, EmitRejectActorRecommendationNode)
        ]
        assert nodes, "Expected EmitRejectActorRecommendationNode in tree"
        node = nodes[0]
        assert node.recommender_id == _RECOMMENDER
        assert node.recommendation_id == _REC_ID
        assert node.recommended_id == _RECOMMENDED
        assert node.case_id == _CASE_ID


# ---------------------------------------------------------------------------
# Duplicate-detection precondition node tests (CM-16-008, CM-16-009)
# ---------------------------------------------------------------------------


_ACTOR_ID = "https://example.org/actors/case-actor"


def _make_node_with_datalayer(node, dl, actor_id=_ACTOR_ID):
    """Wire a datalayer mock onto a DataLayerAction node via the blackboard."""
    # Populate the blackboard storage so initialise() can read datalayer/actor_id.
    writer = py_trees.blackboard.Client(name="test-setup-writer")
    writer.register_key(key="datalayer", access=py_trees.common.Access.WRITE)
    writer.register_key(key="actor_id", access=py_trees.common.Access.WRITE)
    writer.datalayer = dl
    writer.actor_id = actor_id
    node.setup()
    node.initialise()
    return node


class TestActorAlreadyParticipantNode:
    """Unit tests for ActorAlreadyParticipantNode (AC-7b, CM-16-009)."""

    def setup_method(self):
        py_trees.blackboard.Blackboard.enable_activity_stream()

    def teardown_method(self):
        py_trees.blackboard.Blackboard.disable_activity_stream()
        py_trees.blackboard.Blackboard.storage.clear()

    def _node(self, participant_index=None):
        dl = MagicMock()
        case_obj = MagicMock()
        case_obj.actor_participant_index = participant_index or {}
        dl.read.return_value = case_obj
        node = ActorAlreadyParticipantNode(
            recommended_id=_RECOMMENDED,
            case_id=_CASE_ID,
        )
        return _make_node_with_datalayer(node, dl)

    def test_returns_success_when_actor_in_index(self):
        node = self._node(
            participant_index={
                _RECOMMENDED: "https://example.org/participants/p1"
            }
        )
        assert node.update() == Status.SUCCESS

    def test_returns_failure_when_actor_not_in_index(self):
        node = self._node(participant_index={})
        assert node.update() == Status.FAILURE

    def test_returns_failure_when_datalayer_not_available(self):
        node = ActorAlreadyParticipantNode(
            recommended_id=_RECOMMENDED, case_id=_CASE_ID
        )
        # node.datalayer is None by default — no setup/initialise needed
        assert node.update() == Status.FAILURE

    def test_name_defaults_to_class_name(self):
        node = ActorAlreadyParticipantNode(
            recommended_id=_RECOMMENDED, case_id=_CASE_ID
        )
        assert node.name == "ActorAlreadyParticipantNode"

    def test_custom_name_accepted(self):
        node = ActorAlreadyParticipantNode(
            recommended_id=_RECOMMENDED, case_id=_CASE_ID, name="MyName"
        )
        assert node.name == "MyName"


class TestInviteInFlightNode:
    """Unit tests for InviteInFlightNode (AC-7a, CM-16-009)."""

    def setup_method(self):
        py_trees.blackboard.Blackboard.enable_activity_stream()

    def teardown_method(self):
        py_trees.blackboard.Blackboard.disable_activity_stream()
        py_trees.blackboard.Blackboard.storage.clear()

    def _node(self, pair):
        dl = MagicMock()
        dl.find_protocol_pair.return_value = pair
        node = InviteInFlightNode(
            recommended_id=_RECOMMENDED,
            case_id=_CASE_ID,
        )
        return _make_node_with_datalayer(node, dl)

    def _pending_pair(self):
        return ProtocolPair(
            case_id=_CASE_ID,
            request_event_type="invite_actor_to_case",
            object_id=_RECOMMENDED,
            reply_event_types=INVITE_ACTOR_TO_CASE_REPLY_TYPES,
            request_found=True,
        )

    def _fresh_pair(self):
        return ProtocolPair(
            case_id=_CASE_ID,
            request_event_type="invite_actor_to_case",
            object_id=_RECOMMENDED,
            reply_event_types=INVITE_ACTOR_TO_CASE_REPLY_TYPES,
            request_found=False,
        )

    def _closed_pair(self):
        return ProtocolPair(
            case_id=_CASE_ID,
            request_event_type="invite_actor_to_case",
            object_id=_RECOMMENDED,
            reply_event_types=INVITE_ACTOR_TO_CASE_REPLY_TYPES,
            request_found=True,
            reply_object_id="https://example.org/activities/accept-1",
            reply_event_type="accept_invite_actor_to_case",
        )

    def test_returns_success_when_invite_in_flight(self):
        node = self._node(self._pending_pair())
        assert node.update() == Status.SUCCESS

    def test_returns_failure_when_no_prior_invite(self):
        node = self._node(self._fresh_pair())
        assert node.update() == Status.FAILURE

    def test_returns_failure_when_invite_closed(self):
        node = self._node(self._closed_pair())
        assert node.update() == Status.FAILURE

    def test_queries_correct_event_type(self):
        dl = MagicMock()
        dl.find_protocol_pair.return_value = self._fresh_pair()
        node = InviteInFlightNode(
            recommended_id=_RECOMMENDED, case_id=_CASE_ID
        )
        _make_node_with_datalayer(node, dl)
        node.update()
        dl.find_protocol_pair.assert_called_once_with(
            case_id=_CASE_ID,
            request_event_type="invite_actor_to_case",
            object_id=_RECOMMENDED,
            reply_event_types=INVITE_ACTOR_TO_CASE_REPLY_TYPES,
        )

    def test_returns_failure_when_datalayer_not_available(self):
        node = InviteInFlightNode(
            recommended_id=_RECOMMENDED, case_id=_CASE_ID
        )
        assert node.update() == Status.FAILURE


class TestPendingOfferCaseParticipantNode:
    """Unit tests for PendingOfferCaseParticipantNode (AC-6, CM-16-008)."""

    def setup_method(self):
        py_trees.blackboard.Blackboard.enable_activity_stream()

    def teardown_method(self):
        py_trees.blackboard.Blackboard.disable_activity_stream()
        py_trees.blackboard.Blackboard.storage.clear()

    def _node(self, pair):
        dl = MagicMock()
        dl.find_protocol_pair.return_value = pair
        node = PendingOfferCaseParticipantNode(
            recommended_id=_RECOMMENDED,
            case_id=_CASE_ID,
        )
        return _make_node_with_datalayer(node, dl)

    def _pending_pair(self):
        return ProtocolPair(
            case_id=_CASE_ID,
            request_event_type="offer_case_participant",
            object_id=_RECOMMENDED,
            reply_event_types=OFFER_CASE_PARTICIPANT_REPLY_TYPES,
            request_found=True,
        )

    def _fresh_pair(self):
        return ProtocolPair(
            case_id=_CASE_ID,
            request_event_type="offer_case_participant",
            object_id=_RECOMMENDED,
            reply_event_types=OFFER_CASE_PARTICIPANT_REPLY_TYPES,
            request_found=False,
        )

    def _closed_pair(self):
        return ProtocolPair(
            case_id=_CASE_ID,
            request_event_type="offer_case_participant",
            object_id=_RECOMMENDED,
            reply_event_types=OFFER_CASE_PARTICIPANT_REPLY_TYPES,
            request_found=True,
            reply_object_id="https://example.org/activities/accept-1",
            reply_event_type="accept_offer_case_participant",
        )

    def test_returns_success_when_offer_pending(self):
        node = self._node(self._pending_pair())
        assert node.update() == Status.SUCCESS

    def test_returns_failure_when_no_prior_offer(self):
        node = self._node(self._fresh_pair())
        assert node.update() == Status.FAILURE

    def test_returns_failure_when_offer_closed(self):
        node = self._node(self._closed_pair())
        assert node.update() == Status.FAILURE

    def test_queries_correct_event_type(self):
        dl = MagicMock()
        dl.find_protocol_pair.return_value = self._fresh_pair()
        node = PendingOfferCaseParticipantNode(
            recommended_id=_RECOMMENDED, case_id=_CASE_ID
        )
        _make_node_with_datalayer(node, dl)
        node.update()
        dl.find_protocol_pair.assert_called_once_with(
            case_id=_CASE_ID,
            request_event_type="offer_case_participant",
            object_id=_RECOMMENDED,
            reply_event_types=OFFER_CASE_PARTICIPANT_REPLY_TYPES,
        )

    def test_returns_failure_when_datalayer_not_available(self):
        node = PendingOfferCaseParticipantNode(
            recommended_id=_RECOMMENDED, case_id=_CASE_ID
        )
        assert node.update() == Status.FAILURE


class TestDuplicateDetectionTreeStructure:
    """Structural tests for duplicate-detection arms in create_recommend_actor_to_case_received_tree.

    CM-16-008, CM-16-009, ADR-0026 Duplicate Recommendation Handling table.
    """

    def setup_method(self):
        self.tree = create_recommend_actor_to_case_received_tree(
            recommendation_id=_REC_ID,
            recommender_id=_RECOMMENDER,
            recommended_id=_RECOMMENDED,
            case_id=_CASE_ID,
        )
        self.all_nodes = list(self.tree.iterate())
        self.all_types = [type(n) for n in self.all_nodes]

    def test_has_actor_already_participant_node(self):
        assert ActorAlreadyParticipantNode in self.all_types

    def test_has_invite_in_flight_node(self):
        assert InviteInFlightNode in self.all_types

    def test_has_pending_offer_case_participant_node(self):
        assert PendingOfferCaseParticipantNode in self.all_types

    def test_has_emit_note_duplicate_node(self):
        assert EmitNoteDuplicateRecommendationToOwnerNode in self.all_types

    def test_has_emit_accept_actor_recommendation_node(self):
        assert EmitAcceptActorRecommendationNode in self.all_types

    def _duplicate_selector(self):
        """Find the DuplicateOrFreshSelector by name."""
        return next(
            n
            for n in self.all_nodes
            if isinstance(n, py_trees.composites.Selector)
            and n.name == "DuplicateOrFreshSelector"
        )

    def test_has_selector_for_duplicate_or_fresh(self):
        assert (
            self._duplicate_selector() is not None
        ), "DuplicateOrFreshSelector must exist in the tree"

    def test_selector_has_four_children(self):
        assert len(self._duplicate_selector().children) == 4

    def test_ac7b_sequence_structure(self):
        """AC-7b arm: Sequence(ActorAlreadyParticipantNode, EmitAcceptActorRecommendationNode)."""
        ac7b = self._duplicate_selector().children[0]
        assert isinstance(ac7b, py_trees.composites.Sequence)
        child_types = [type(c) for c in ac7b.children]
        assert ActorAlreadyParticipantNode in child_types
        assert EmitAcceptActorRecommendationNode in child_types

    def test_ac7a_sequence_structure(self):
        """AC-7a arm: Sequence(InviteInFlightNode, EmitAcceptActorRecommendationNode)."""
        ac7a = self._duplicate_selector().children[1]
        assert isinstance(ac7a, py_trees.composites.Sequence)
        child_types = [type(c) for c in ac7a.children]
        assert InviteInFlightNode in child_types
        assert EmitAcceptActorRecommendationNode in child_types

    def test_ac6_sequence_structure(self):
        """AC-6 arm: Sequence(PendingOfferCaseParticipantNode, EmitNoteDuplicateRecommendationToOwnerNode)."""
        ac6 = self._duplicate_selector().children[2]
        assert isinstance(ac6, py_trees.composites.Sequence)
        child_types = [type(c) for c in ac6.children]
        assert PendingOfferCaseParticipantNode in child_types
        assert EmitNoteDuplicateRecommendationToOwnerNode in child_types

    def test_fresh_path_structure(self):
        """Fresh path arm: Sequence(EvaluateDefaultRolesNode, EmitOfferCaseParticipantToOwnerNode)."""
        fresh = self._duplicate_selector().children[3]
        assert isinstance(fresh, py_trees.composites.Sequence)
        child_types = [type(c) for c in fresh.children]
        assert EvaluateDefaultRolesNode in child_types
        assert EmitOfferCaseParticipantToOwnerNode in child_types

    def test_selector_memory_false(self):
        assert self._duplicate_selector().memory is False


class TestProtocolPairIsPending:
    """Unit tests for ProtocolPair.is_pending() (added for AC-6/AC-7)."""

    def test_is_pending_true_when_request_found_and_no_reply(self):
        pair = ProtocolPair(
            case_id=_CASE_ID,
            request_event_type="offer_case_participant",
            object_id=_RECOMMENDED,
            request_found=True,
        )
        assert pair.is_pending() is True

    def test_is_pending_false_when_request_not_found(self):
        pair = ProtocolPair(
            case_id=_CASE_ID,
            request_event_type="offer_case_participant",
            object_id=_RECOMMENDED,
            request_found=False,
        )
        assert pair.is_pending() is False

    def test_is_pending_false_when_reply_found(self):
        pair = ProtocolPair(
            case_id=_CASE_ID,
            request_event_type="offer_case_participant",
            object_id=_RECOMMENDED,
            request_found=True,
            reply_object_id="https://example.org/activities/reply",
            reply_event_type="accept_offer_case_participant",
        )
        assert pair.is_pending() is False

    def test_is_open_still_true_for_fresh_pair(self):
        """is_open() returns True for fresh pair (no request found). is_pending() should not."""
        pair = ProtocolPair(
            case_id=_CASE_ID,
            request_event_type="offer_case_participant",
            object_id=_RECOMMENDED,
            request_found=False,
        )
        assert pair.is_open() is True
        assert pair.is_pending() is False

    def test_request_found_defaults_to_false(self):
        pair = ProtocolPair(
            case_id=_CASE_ID,
            request_event_type="offer_case_participant",
            object_id=_RECOMMENDED,
        )
        assert pair.request_found is False
