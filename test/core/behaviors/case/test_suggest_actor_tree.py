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
- EvaluateDefaultRolesNode (AC-1 through AC-3, CM-15-003)

Per specs/behavior-tree-integration.yaml BT-15-001, BTND-02-001 (memory=False),
ADR-0026/CM-16.
"""

import py_trees
from py_trees.common import Status

from vultron.core.behaviors.case.suggest_actor_tree import (
    EmitAcceptActorRecommendationNode,
    EmitOfferCaseParticipantToOwnerNode,
    EmitRejectActorRecommendationNode,
    create_accept_actor_recommendation_received_tree,
    create_recommend_actor_to_case_received_tree,
    create_reject_actor_recommendation_received_tree,
)
from vultron.core.behaviors.case.nodes.actor import (
    EmitInviteActorToCaseNode,
    EvaluateDefaultRolesNode,
)
from vultron.core.states.roles import CVDRole

_REC_ID = "https://example.org/recommendations/rec-1"
_RECOMMENDER = "https://example.org/actors/recommender"
_RECOMMENDED = "https://example.org/actors/recommended"
_CASE_ID = "https://example.org/cases/case-1"


class TestEvaluateDefaultRolesNode:
    """Unit tests for EvaluateDefaultRolesNode (AC-1, AC-2, AC-3, CM-15-003)."""

    def setup_method(self):
        py_trees.blackboard.Blackboard.enable_activity_stream()
        self.node = EvaluateDefaultRolesNode(
            suggested_actor_id=_RECOMMENDED,
            case_id=_CASE_ID,
        )
        self.node.setup()
        self.node.initialise()

    def teardown_method(self):
        py_trees.blackboard.Blackboard.disable_activity_stream()

    def test_node_exists(self):
        """AC-1: EvaluateDefaultRolesNode exists in the BT node library."""
        assert self.node is not None

    def test_node_name_defaults_to_class_name(self):
        assert self.node.name == "EvaluateDefaultRolesNode"

    def test_node_stores_suggested_actor_id(self):
        assert self.node.suggested_actor_id == _RECOMMENDED

    def test_node_stores_case_id(self):
        assert self.node.case_id == _CASE_ID

    def test_returns_success_unconditionally(self):
        """AC-3: returns SUCCESS unconditionally in the prototype."""
        result = self.node.update()
        assert result == Status.SUCCESS

    def test_writes_vendor_role_to_blackboard(self):
        """AC-2: writes suggested_roles = [CVDRole.VENDOR] to blackboard."""
        self.node.update()
        raw = py_trees.blackboard.Blackboard.storage.get("/suggested_roles")
        assert raw == [
            CVDRole.VENDOR
        ], f"Expected [CVDRole.VENDOR] in suggested_roles, got {raw!r}"

    def test_custom_name_accepted(self):
        node = EvaluateDefaultRolesNode(
            suggested_actor_id=_RECOMMENDED,
            case_id=_CASE_ID,
            name="MyCustomName",
        )
        assert node.name == "MyCustomName"


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
