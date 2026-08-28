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

"""Tests for append/conditions.py: idempotency guards and RM validation.

Tests SkipIfIdempotentNode, LoadParticipantNode,
CheckStatusNotAlreadyAppendedNode, ResolveAndPersistStatusObjectNode and
AppendStatusAndSaveParticipantNode from ``nodes.append``, plus
ValidateRMTransitionNode from ``nodes.rm_validation``.

Per DEMOMA-07-003 step 2.
"""

import logging

import pytest
import py_trees
from py_trees.common import Status

from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.status.nodes.append import (
    CheckStatusNotAlreadyAppendedNode,
    LoadParticipantNode,
    ResolveAndPersistStatusObjectNode,
    SkipIfIdempotentNode,
)
from vultron.core.behaviors.status.nodes.dimension_filter import BB_RM_ANOMALY
from vultron.core.behaviors.status.nodes.rm_validation import (
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

    @pytest.mark.spec("RSH-06-001")
    @pytest.mark.spec("RSH-06-003")
    def test_forward_gap_succeeds_with_warning_and_anomaly(
        self, populated_dl, caplog
    ):
        """Non-adjacent forward RM jump: SUCCESS + WARNING log + anomaly flag (RSH-06-001, RSH-06-003)."""
        received_status = as_ParticipantStatus(
            id_="https://example.org/cases/case-01/statuses/received",
            context=CASE_ID,
            rm_state=RM.RECEIVED,
        )
        populated_dl.create(received_status)
        p = populated_dl.read(PARTICIPANT_ID)
        p.participant_statuses.append(received_status)
        populated_dl.save(p)

        # RECEIVED → ACCEPTED is a non-adjacent forward jump (skips VALID)
        accepted_status = as_ParticipantStatus(
            id_="https://example.org/cases/case-01/statuses/accepted",
            context=CASE_ID,
            rm_state=RM.ACCEPTED,
        )
        populated_dl.create(accepted_status)

        bridge = BTBridge(datalayer=populated_dl)
        load = LoadParticipantNode(participant_id=PARTICIPANT_ID)
        resolve = ResolveAndPersistStatusObjectNode(
            status_id=accepted_status.id_, status_obj_fallback=None
        )
        validate = ValidateRMTransitionNode(
            participant_id=PARTICIPANT_ID, status_id=accepted_status.id_
        )
        seq = py_trees.composites.Sequence(
            name="TestSeq",
            memory=False,
            children=[load, resolve, validate],
        )

        with caplog.at_level(logging.WARNING):
            result = bridge.execute_with_setup(tree=seq, actor_id=ACTOR_ID)

        assert result.status == Status.SUCCESS
        # RSH-06-003: must log at WARNING level
        assert any(
            r.levelno == logging.WARNING for r in caplog.records
        ), "Expected WARNING log for non-adjacent forward RM jump"
        # RSH-06: anomaly flag must be set on blackboard
        anomaly = py_trees.blackboard.Blackboard.storage.get(
            "/" + BB_RM_ANOMALY
        )
        assert anomaly is not None, "BB_RM_ANOMALY not set for forward gap"
        assert anomaly["anomaly_type"] == "gap"
        assert anomaly["from_rm"] == RM.RECEIVED
        assert anomaly["to_rm"] == RM.ACCEPTED

    @pytest.mark.spec("RSH-06-002")
    @pytest.mark.spec("RSH-06-003")
    def test_backward_regression_sets_anomaly(self, populated_dl):
        """Backward RM regression: FAILURE + anomaly flag set (RSH-06-002, RSH-06-003)."""
        accepted_status = as_ParticipantStatus(
            id_="https://example.org/cases/case-01/statuses/accepted",
            context=CASE_ID,
            rm_state=RM.ACCEPTED,
        )
        populated_dl.create(accepted_status)
        p = populated_dl.read(PARTICIPANT_ID)
        p.participant_statuses.append(accepted_status)
        populated_dl.save(p)

        # ACCEPTED → RECEIVED is a backward regression
        regression_status = as_ParticipantStatus(
            id_="https://example.org/cases/case-01/statuses/regression",
            context=CASE_ID,
            rm_state=RM.RECEIVED,
        )
        populated_dl.create(regression_status)

        bridge = BTBridge(datalayer=populated_dl)
        load = LoadParticipantNode(participant_id=PARTICIPANT_ID)
        resolve = ResolveAndPersistStatusObjectNode(
            status_id=regression_status.id_, status_obj_fallback=None
        )
        validate = ValidateRMTransitionNode(
            participant_id=PARTICIPANT_ID, status_id=regression_status.id_
        )
        seq = py_trees.composites.Sequence(
            name="TestSeq",
            memory=False,
            children=[load, resolve, validate],
        )
        result = bridge.execute_with_setup(tree=seq, actor_id=ACTOR_ID)

        assert result.status == Status.FAILURE
        anomaly = py_trees.blackboard.Blackboard.storage.get(
            "/" + BB_RM_ANOMALY
        )
        assert anomaly is not None, "BB_RM_ANOMALY not set for regression"
        assert anomaly["anomaly_type"] == "regression"
        assert anomaly["from_rm"] == RM.ACCEPTED
        assert anomaly["to_rm"] == RM.RECEIVED

    def test_adjacent_transition_clears_anomaly_flag(self, populated_dl):
        """Valid adjacent RM transition: no anomaly flag set (happy path)."""
        received_status = as_ParticipantStatus(
            id_="https://example.org/cases/case-01/statuses/received",
            context=CASE_ID,
            rm_state=RM.RECEIVED,
        )
        populated_dl.create(received_status)
        p = populated_dl.read(PARTICIPANT_ID)
        p.participant_statuses.append(received_status)
        populated_dl.save(p)

        # RECEIVED → VALID is a valid adjacent transition
        valid_status = as_ParticipantStatus(
            id_="https://example.org/cases/case-01/statuses/valid",
            context=CASE_ID,
            rm_state=RM.VALID,
        )
        populated_dl.create(valid_status)

        bridge = BTBridge(datalayer=populated_dl)
        load = LoadParticipantNode(participant_id=PARTICIPANT_ID)
        resolve = ResolveAndPersistStatusObjectNode(
            status_id=valid_status.id_, status_obj_fallback=None
        )
        validate = ValidateRMTransitionNode(
            participant_id=PARTICIPANT_ID, status_id=valid_status.id_
        )
        seq = py_trees.composites.Sequence(
            name="TestSeq",
            memory=False,
            children=[load, resolve, validate],
        )
        result = bridge.execute_with_setup(tree=seq, actor_id=ACTOR_ID)

        assert result.status == Status.SUCCESS
        anomaly = py_trees.blackboard.Blackboard.storage.get(
            "/" + BB_RM_ANOMALY
        )
        assert (
            anomaly is None
        ), f"Expected no anomaly for adjacent transition, got {anomaly}"
