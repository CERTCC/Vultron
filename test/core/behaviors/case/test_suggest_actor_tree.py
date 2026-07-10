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

Per specs/behavior-tree-integration.yaml BT-15-001, BTND-02-001 (memory=False),
ADR-0026/CM-16.
"""

import py_trees

from vultron.core.behaviors.case.suggest_actor_tree import (
    EmitAcceptActorRecommendationNode,
    EmitOfferCaseParticipantToOwnerNode,
    EmitRejectActorRecommendationNode,
    create_accept_actor_recommendation_received_tree,
    create_recommend_actor_to_case_received_tree,
    create_reject_actor_recommendation_received_tree,
)
from vultron.core.behaviors.case.nodes.actor import EmitInviteActorToCaseNode

_REC_ID = "https://example.org/recommendations/rec-1"
_RECOMMENDER = "https://example.org/actors/recommender"
_RECOMMENDED = "https://example.org/actors/recommended"
_CASE_ID = "https://example.org/cases/case-1"


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

    def test_has_emit_offer_case_participant_node(self):
        """Effect nodes must include EmitOfferCaseParticipantToOwnerNode."""
        flat_types = []
        for child in self.tree.children:
            if isinstance(child, py_trees.composites.Sequence):
                flat_types.extend(type(gc) for gc in child.children)
            else:
                flat_types.append(type(child))
        assert EmitOfferCaseParticipantToOwnerNode in flat_types or any(
            isinstance(c, EmitOfferCaseParticipantToOwnerNode)
            for c in self.tree.children
        ), "RecommendActorToCaseBT must contain EmitOfferCaseParticipantToOwnerNode"

    def test_emit_node_carries_recommendation_id(self):
        """The emit node must carry the original recommendation ID as origin."""
        emit_nodes = [
            c
            for c in self.tree.children
            if isinstance(c, EmitOfferCaseParticipantToOwnerNode)
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
