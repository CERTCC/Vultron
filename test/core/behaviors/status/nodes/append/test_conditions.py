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

"""Tests for append/conditions.py: idempotency guards and RM validation."""

import py_trees
from py_trees.common import Status

from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.status.nodes.append import (
    CheckParticipantRMNotClosedNode,
    CheckStatusNotAlreadyAppendedNode,
    LoadParticipantNode,
    ResolveAndPersistStatusObjectNode,
    SkipIfIdempotentNode,
    ValidateRMTransitionNode,
)
from vultron.core.states.rm import RM
from vultron.wire.as2.vocab.objects.case_status import as_ParticipantStatus

from .conftest import ACTOR_ID, CASE_ID, PARTICIPANT_ID, STATUS_ID

# ---------------------------------------------------------------------------
# SkipIfIdempotentNode
# ---------------------------------------------------------------------------


class TestSkipIfIdempotentNode:
    def test_not_appended_fails(self, populated_bridge):
        """Status not yet on participant → FAILURE (proceed to append)."""
        load = LoadParticipantNode(participant_id=PARTICIPANT_ID)
        skip = SkipIfIdempotentNode(
            status_id=STATUS_ID, participant_id=PARTICIPANT_ID
        )
        seq = py_trees.composites.Sequence(
            name="TestSeq", memory=False, children=[load, skip]
        )
        result = populated_bridge.execute_with_setup(
            tree=seq, actor_id=ACTOR_ID
        )
        assert result.status == Status.FAILURE

    def test_already_appended_succeeds(self, populated_dl):
        """Status already on participant → SUCCESS (skip append)."""
        p = populated_dl.read(PARTICIPANT_ID)
        s = populated_dl.read(STATUS_ID)
        p.participant_statuses.append(s)
        populated_dl.save(p)

        bridge = BTBridge(datalayer=populated_dl)
        load = LoadParticipantNode(participant_id=PARTICIPANT_ID)
        skip = SkipIfIdempotentNode(
            status_id=STATUS_ID, participant_id=PARTICIPANT_ID
        )
        seq = py_trees.composites.Sequence(
            name="TestSeq", memory=False, children=[load, skip]
        )
        result = bridge.execute_with_setup(tree=seq, actor_id=ACTOR_ID)
        assert result.status == Status.SUCCESS


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

    def test_no_current_status_succeeds(self, populated_bridge):
        """Participant with no prior status passes transition validation."""
        resolve = ResolveAndPersistStatusObjectNode(
            status_id=STATUS_ID, status_obj_fallback=None
        )
        load = LoadParticipantNode(participant_id=PARTICIPANT_ID)
        validate = ValidateRMTransitionNode(participant_id=PARTICIPANT_ID)
        seq = py_trees.composites.Sequence(
            name="TestSeq",
            memory=False,
            children=[load, resolve, validate],
        )
        result = populated_bridge.execute_with_setup(
            tree=seq, actor_id=ACTOR_ID
        )
        assert result.status == Status.SUCCESS

    def test_backwards_transition_fails(self, populated_dl):
        """A status with CLOSED RM on a participant already CLOSED → FAILURE."""
        # Build a status with RM.CLOSED and append it to the participant.
        from vultron.wire.as2.vocab.objects.case_status import (
            as_ParticipantStatus,
        )

        closed_status_id = "https://example.org/cases/case-01/statuses/closed"
        closed_status = as_ParticipantStatus(
            id_=closed_status_id,
            context=CASE_ID,
            rm_state=RM.CLOSED,
        )
        populated_dl.create(closed_status)

        # Put participant in CLOSED — append CLOSED last so participant_status
        # (= participant_statuses[-1]) reflects RM.CLOSED.
        p = populated_dl.read(PARTICIPANT_ID)
        p.participant_statuses.append(closed_status)
        populated_dl.save(p)

        # Now try to validate a new status transition — should fail since
        # participant is already CLOSED.
        bridge = BTBridge(datalayer=populated_dl)
        load = LoadParticipantNode(participant_id=PARTICIPANT_ID)
        resolve = ResolveAndPersistStatusObjectNode(
            status_id=STATUS_ID, status_obj_fallback=None
        )
        validate = ValidateRMTransitionNode(participant_id=PARTICIPANT_ID)
        seq = py_trees.composites.Sequence(
            name="TestSeq",
            memory=False,
            children=[load, resolve, validate],
        )
        result = bridge.execute_with_setup(tree=seq, actor_id=ACTOR_ID)
        assert result.status == Status.FAILURE


# ---------------------------------------------------------------------------
# CheckParticipantRMNotClosedNode
# ---------------------------------------------------------------------------


class TestCheckParticipantRMNotClosedNode:
    def test_open_participant_succeeds(self, populated_dl):
        """Participant not in CLOSED state → SUCCESS."""
        bridge = BTBridge(datalayer=populated_dl)
        node = CheckParticipantRMNotClosedNode(participant_id=PARTICIPANT_ID)
        result = bridge.execute_with_setup(tree=node, actor_id=ACTOR_ID)
        assert result.status == Status.SUCCESS

    def test_missing_participant_succeeds(self, bridge):
        """Participant not found in DataLayer → SUCCESS (no terminal check)."""
        node = CheckParticipantRMNotClosedNode(
            participant_id="https://example.org/missing/participant"
        )
        result = bridge.execute_with_setup(tree=node, actor_id=ACTOR_ID)
        assert result.status == Status.SUCCESS

    def test_closed_participant_fails(self, populated_dl):
        """Participant already in RM.CLOSED without prior status match → FAILURE."""
        closed_status = as_ParticipantStatus(
            id_="https://example.org/cases/case-01/statuses/c1",
            context=CASE_ID,
            rm_state=RM.CLOSED,
        )
        populated_dl.create(closed_status)
        p = populated_dl.read(PARTICIPANT_ID)
        p.participant_statuses.append(closed_status)
        populated_dl.save(p)

        bridge = BTBridge(datalayer=populated_dl)
        node = CheckParticipantRMNotClosedNode(
            participant_id=PARTICIPANT_ID, status_id=STATUS_ID
        )
        result = bridge.execute_with_setup(tree=node, actor_id=ACTOR_ID)
        assert result.status == Status.FAILURE

    def test_closed_participant_with_matching_status_succeeds(
        self, populated_dl
    ):
        """Participant CLOSED but status already appended → SUCCESS (idempotent)."""
        status = populated_dl.read(STATUS_ID)
        closed_status = as_ParticipantStatus(
            id_="https://example.org/cases/case-01/statuses/c1",
            context=CASE_ID,
            rm_state=RM.CLOSED,
        )
        populated_dl.create(closed_status)
        p = populated_dl.read(PARTICIPANT_ID)
        # STATUS_ID appended first, then CLOSED last — so participant_status
        # (= participant_statuses[-1]) is CLOSED, but STATUS_ID is present.
        p.participant_statuses.append(status)
        p.participant_statuses.append(closed_status)
        populated_dl.save(p)

        bridge = BTBridge(datalayer=populated_dl)
        node = CheckParticipantRMNotClosedNode(
            participant_id=PARTICIPANT_ID, status_id=STATUS_ID
        )
        result = bridge.execute_with_setup(tree=node, actor_id=ACTOR_ID)
        assert result.status == Status.SUCCESS
