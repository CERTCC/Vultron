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

"""Tests for append/actions.py: load, resolve, and append action nodes."""

import py_trees
from py_trees.common import Status

from vultron.core.behaviors.status.nodes.append import (
    AppendStatusAndSaveParticipantNode,
    LoadParticipantNode,
    ResolveAndPersistStatusObjectNode,
)

from .conftest import ACTOR_ID, PARTICIPANT_ID, STATUS_ID

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

    def test_uses_fallback_when_missing_from_dl(self, bridge):
        """Fallback object is persisted and resolved when ID absent from DL."""
        from vultron.core.models.participant_status import ParticipantStatus
        from .conftest import CASE_ID

        fallback = ParticipantStatus(id_=STATUS_ID, context=CASE_ID)
        node = ResolveAndPersistStatusObjectNode(
            status_id=STATUS_ID, status_obj_fallback=fallback
        )
        result = bridge.execute_with_setup(tree=node, actor_id=ACTOR_ID)
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

    def test_missing_blackboard_data_fails(self, bridge):
        """No prior load/resolve on blackboard → FAILURE."""
        append = AppendStatusAndSaveParticipantNode(
            status_id=STATUS_ID, participant_id=PARTICIPANT_ID
        )
        result = bridge.execute_with_setup(tree=append, actor_id=ACTOR_ID)
        assert result.status == Status.FAILURE
