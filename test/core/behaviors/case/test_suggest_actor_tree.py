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
Tests for the SuggestActorToCase behavior tree factory.

Covers stateless-ticking invariant (memory=False) for the root Sequence.
Per specs/behavior-tree-integration.yaml and issue #716.
"""

import py_trees

from vultron.core.behaviors.case.suggest_actor_tree import (
    create_suggest_actor_tree,
)


class TestCreateSuggestActorTree:
    """Structural tests for the SuggestActorToCaseBT factory."""

    def test_root_is_sequence_with_memory_false(self) -> None:
        """Regression guard: root Sequence must use memory=False (#716).

        memory=True would skip re-evaluating preconditions (CheckIsCaseOwnerNode,
        CheckNoExistingInviteNode) on re-entry after a child returns RUNNING,
        defeating the stateless-ticking contract of all case BTs.
        """
        tree = create_suggest_actor_tree(
            recommendation_id="https://example.org/recommendations/rec-1",
            recommender_id="https://example.org/actors/recommender",
            invitee_id="https://example.org/actors/invitee",
            case_id="https://example.org/cases/case-1",
        )
        assert isinstance(tree, py_trees.composites.Sequence)
        assert tree.memory is False, (
            "SuggestActorToCaseBT root Sequence must use memory=False "
            "to ensure preconditions are re-evaluated on every tick"
        )
