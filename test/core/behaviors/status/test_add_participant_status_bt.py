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

Covers all four DEMOMA-07-003 steps (step 3 raw re-broadcast removed
per DEMOMA-07-005):
  1. VerifySenderIsParticipantNode — unknown sender is rejected
  2. AppendParticipantStatusNode  — status appended, RM regression rejected
  4. PublicDisclosureBranchNode   — always SUCCESS, only triggers teardown on CS.P + CASE_OWNER
  5. AutoCloseBranchNode          — always SUCCESS, logs when all RM.CLOSED

Per specs/multi-actor-demo.yaml DEMOMA-07-003 and DEMOMA-07-005.
"""

import py_trees
import pytest
from py_trees.common import Status

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.status.add_participant_status_tree import (
    add_participant_status_tree,
)
from vultron.core.behaviors.status.append_participant_status_tree import (
    append_participant_status_tree,
)
from vultron.core.behaviors.status.nodes import (
    AppendStatusAndSaveParticipantNode,
    AutoCloseBranchNode,
    CheckStatusNotAlreadyAppendedNode,
    LoadParticipantNode,
    PublicDisclosureBranchNode,
    ResolveAndPersistStatusObjectNode,
    ValidateRMTransitionNode,
    VerifySenderIsParticipantNode,
)
from vultron.core.states.rm import RM
from vultron.enums.roles import CVDRole
from vultron.wire.as2.factories import add_status_to_participant_activity
from vultron.wire.as2.vocab.objects.case_participant import as_CaseParticipant
from vultron.wire.as2.vocab.objects.case_status import as_ParticipantStatus
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)

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
    return as_ParticipantStatus(
        id_=STATUS_ID,
        context=CASE_ID,
    )


@pytest.fixture
def participant():
    return as_CaseParticipant(
        id_=PARTICIPANT_ID,
        context=CASE_ID,
        attributed_to=ACTOR_ID,
        case_roles=[CVDRole.CASE_OWNER],
    )


@pytest.fixture
def case_manager_participant():
    return as_CaseParticipant(
        id_=CM_PARTICIPANT_ID,
        context=CASE_ID,
        attributed_to=CASE_MANAGER_ID,
        case_roles=[CVDRole.CASE_MANAGER],
    )


@pytest.fixture
def case(participant, case_manager_participant):
    """as_VulnerabilityCase with vendor and Case Manager participants."""
    obj = as_VulnerabilityCase(id_=CASE_ID, name="Test Case")
    obj.add_participant(participant)
    obj.add_participant(case_manager_participant)
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


# ---------------------------------------------------------------------------
# Step 2: AppendParticipantStatusBT (composed subtree)
# ---------------------------------------------------------------------------


class TestLoadParticipantNode:
    """Tests for LoadParticipantNode."""

    def test_loads_participant_successfully(
        self, populated_dl, populated_bridge
    ):
        node = LoadParticipantNode(participant_id=PARTICIPANT_ID)
        result = populated_bridge.execute_with_setup(
            tree=node, actor_id=ACTOR_ID
        )
        assert result.status == Status.SUCCESS
        participant = py_trees.blackboard.Blackboard().get(
            "append_status_participant"
        )
        assert participant is not None
        assert participant.id_ == PARTICIPANT_ID

    def test_fails_when_participant_missing(self, bridge):
        node = LoadParticipantNode(
            participant_id="https://example.org/cases/case-01/participants/missing"
        )
        result = bridge.execute_with_setup(tree=node, actor_id=ACTOR_ID)
        assert result.status == Status.FAILURE


class TestCheckStatusNotAlreadyAppendedNode:
    """Tests for CheckStatusNotAlreadyAppendedNode."""

    def test_succeeds_when_status_not_appended(
        self, populated_dl, populated_bridge
    ):
        """Status check passes when status is not yet appended."""
        tree = py_trees.composites.Sequence(
            name="test-check",
            memory=False,
            children=[
                LoadParticipantNode(participant_id=PARTICIPANT_ID),
                CheckStatusNotAlreadyAppendedNode(
                    status_id=STATUS_ID,
                    participant_id=PARTICIPANT_ID,
                ),
            ],
        )
        result = populated_bridge.execute_with_setup(
            tree=tree, actor_id=ACTOR_ID
        )
        assert result.status == Status.SUCCESS

    def test_fails_when_status_already_appended(
        self, populated_dl, populated_bridge
    ):
        """Status check fails when status is already appended (idempotency)."""
        p = populated_dl.read(PARTICIPANT_ID)
        status_obj = populated_dl.read(STATUS_ID)
        p.participant_statuses.append(status_obj)
        populated_dl.save(p)

        tree = py_trees.composites.Sequence(
            name="test-check",
            memory=False,
            children=[
                LoadParticipantNode(participant_id=PARTICIPANT_ID),
                CheckStatusNotAlreadyAppendedNode(
                    status_id=STATUS_ID,
                    participant_id=PARTICIPANT_ID,
                ),
            ],
        )
        result = populated_bridge.execute_with_setup(
            tree=tree, actor_id=ACTOR_ID
        )
        assert result.status == Status.FAILURE


class TestResolveAndPersistStatusObjectNode:
    """Tests for ResolveAndPersistStatusObjectNode."""

    def test_resolves_status_from_datalayer(
        self, populated_dl, populated_bridge
    ):
        node = ResolveAndPersistStatusObjectNode(
            status_id=STATUS_ID,
            status_obj_fallback=None,
        )
        result = populated_bridge.execute_with_setup(
            tree=node, actor_id=ACTOR_ID
        )
        assert result.status == Status.SUCCESS
        status_obj = py_trees.blackboard.Blackboard().get(
            "append_status_status_obj"
        )
        assert status_obj is not None
        assert status_obj.id_ == STATUS_ID

    def test_persists_fallback_when_not_found(self, dl, bridge, status_obj):
        """Persists fallback object when status not in DataLayer."""
        node = ResolveAndPersistStatusObjectNode(
            status_id=STATUS_ID,
            status_obj_fallback=status_obj,
        )
        result = bridge.execute_with_setup(tree=node, actor_id=ACTOR_ID)
        assert result.status == Status.SUCCESS
        persisted = dl.read(STATUS_ID)
        assert persisted is not None
        assert persisted.id_ == STATUS_ID

    def test_fails_when_status_missing(self, bridge):
        node = ResolveAndPersistStatusObjectNode(
            status_id="https://example.org/missing",
            status_obj_fallback=None,
        )
        result = bridge.execute_with_setup(tree=node, actor_id=ACTOR_ID)
        assert result.status == Status.FAILURE


class TestValidateRMTransitionNode:
    """Tests for ValidateRMTransitionNode."""

    def test_accepts_valid_transition(self, populated_dl, populated_bridge):
        """Valid adjacent RM transition is accepted."""
        tree = py_trees.composites.Sequence(
            name="test-validate",
            memory=False,
            children=[
                LoadParticipantNode(participant_id=PARTICIPANT_ID),
                ResolveAndPersistStatusObjectNode(
                    status_id=STATUS_ID,
                    status_obj_fallback=None,
                ),
                ValidateRMTransitionNode(participant_id=PARTICIPANT_ID),
            ],
        )
        result = populated_bridge.execute_with_setup(
            tree=tree, actor_id=ACTOR_ID
        )
        assert result.status == Status.SUCCESS

    def test_rejects_backwards_transition(
        self, populated_dl, populated_bridge
    ):
        """Backwards RM transition (CLOSED → RECEIVED) is rejected."""
        p = populated_dl.read(PARTICIPANT_ID)
        closed_status = as_ParticipantStatus(
            id_=f"{STATUS_ID}/closed",
            context=CASE_ID,
            rm_state=RM.CLOSED,
        )
        p.participant_statuses.append(closed_status)
        populated_dl.save(p)
        populated_dl.create(closed_status)

        regressed_status = as_ParticipantStatus(
            id_=f"{STATUS_ID}/regressed",
            context=CASE_ID,
            rm_state=RM.RECEIVED,
        )
        populated_dl.create(regressed_status)

        tree = py_trees.composites.Sequence(
            name="test-validate-backwards",
            memory=False,
            children=[
                LoadParticipantNode(participant_id=PARTICIPANT_ID),
                ResolveAndPersistStatusObjectNode(
                    status_id=regressed_status.id_,
                    status_obj_fallback=regressed_status,
                ),
                ValidateRMTransitionNode(participant_id=PARTICIPANT_ID),
            ],
        )
        result = populated_bridge.execute_with_setup(
            tree=tree, actor_id=ACTOR_ID
        )
        assert result.status == Status.FAILURE

    def test_rejects_terminal_closed_rewrite(
        self, populated_dl, populated_bridge
    ):
        """RM.CLOSED is terminal; CLOSED -> CLOSED rewrites are rejected."""
        p = populated_dl.read(PARTICIPANT_ID)
        closed_status = as_ParticipantStatus(
            id_=f"{STATUS_ID}/closed",
            context=CASE_ID,
            rm_state=RM.CLOSED,
        )
        p.participant_statuses.append(closed_status)
        populated_dl.save(p)
        populated_dl.create(closed_status)

        duplicate_closed_status = as_ParticipantStatus(
            id_=f"{STATUS_ID}/closed-dup",
            context=CASE_ID,
            rm_state=RM.CLOSED,
        )
        populated_dl.create(duplicate_closed_status)

        tree = py_trees.composites.Sequence(
            name="test-validate-terminal-closed",
            memory=False,
            children=[
                LoadParticipantNode(participant_id=PARTICIPANT_ID),
                ResolveAndPersistStatusObjectNode(
                    status_id=duplicate_closed_status.id_,
                    status_obj_fallback=duplicate_closed_status,
                ),
                ValidateRMTransitionNode(participant_id=PARTICIPANT_ID),
            ],
        )
        result = populated_bridge.execute_with_setup(
            tree=tree, actor_id=ACTOR_ID
        )
        assert result.status == Status.FAILURE

    def test_accepts_forward_jump(self, populated_dl, populated_bridge):
        """Non-adjacent forward RM jump is accepted (sender authoritative)."""
        p = populated_dl.read(PARTICIPANT_ID)
        received_status = as_ParticipantStatus(
            id_=f"{STATUS_ID}/received",
            context=CASE_ID,
            rm_state=RM.RECEIVED,
        )
        p.participant_statuses.append(received_status)
        populated_dl.save(p)
        populated_dl.create(received_status)

        accepted_status = as_ParticipantStatus(
            id_=f"{STATUS_ID}/accepted",
            context=CASE_ID,
            rm_state=RM.ACCEPTED,
        )
        populated_dl.create(accepted_status)

        tree = py_trees.composites.Sequence(
            name="test-validate-forward-jump",
            memory=False,
            children=[
                LoadParticipantNode(participant_id=PARTICIPANT_ID),
                ResolveAndPersistStatusObjectNode(
                    status_id=accepted_status.id_,
                    status_obj_fallback=accepted_status,
                ),
                ValidateRMTransitionNode(participant_id=PARTICIPANT_ID),
            ],
        )
        result = populated_bridge.execute_with_setup(
            tree=tree, actor_id=ACTOR_ID
        )
        assert result.status == Status.SUCCESS


class TestAppendStatusAndSaveParticipantNode:
    """Tests for AppendStatusAndSaveParticipantNode."""

    def test_appends_and_saves(self, populated_dl, populated_bridge):
        tree = py_trees.composites.Sequence(
            name="test-append-save",
            memory=False,
            children=[
                LoadParticipantNode(participant_id=PARTICIPANT_ID),
                ResolveAndPersistStatusObjectNode(
                    status_id=STATUS_ID,
                    status_obj_fallback=None,
                ),
                AppendStatusAndSaveParticipantNode(
                    status_id=STATUS_ID,
                    participant_id=PARTICIPANT_ID,
                ),
            ],
        )
        result = populated_bridge.execute_with_setup(
            tree=tree, actor_id=ACTOR_ID
        )
        assert result.status == Status.SUCCESS
        p = populated_dl.read(PARTICIPANT_ID)
        assert p is not None
        status_ids = [getattr(s, "id_", s) for s in p.participant_statuses]
        assert STATUS_ID in status_ids


class TestAppendParticipantStatusSubtree:
    """Integration tests for the AppendParticipantStatusBT subtree."""

    def test_appends_status(self, populated_dl, populated_bridge, status_obj):
        tree = append_participant_status_tree(
            status_id=STATUS_ID,
            participant_id=PARTICIPANT_ID,
            status_obj_fallback=status_obj,
        )
        result = populated_bridge.execute_with_setup(
            tree=tree, actor_id=ACTOR_ID
        )
        assert result.status == Status.SUCCESS
        p = populated_dl.read(PARTICIPANT_ID)
        assert p is not None
        status_ids = [getattr(s, "id_", s) for s in p.participant_statuses]
        assert STATUS_ID in status_ids

    def test_idempotent_when_already_present(self, populated_dl, status_obj):
        """Running the subtree twice does not duplicate the status."""
        bridge = BTBridge(datalayer=populated_dl)

        def _make_tree():
            return append_participant_status_tree(
                status_id=STATUS_ID,
                participant_id=PARTICIPANT_ID,
                status_obj_fallback=status_obj,
            )

        # First call appends the status
        result1 = bridge.execute_with_setup(
            tree=_make_tree(), actor_id=ACTOR_ID
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
            tree=_make_tree(), actor_id=ACTOR_ID
        )
        assert result2.status == Status.SUCCESS
        p2 = populated_dl.read(PARTICIPANT_ID)
        assert len(p2.participant_statuses) == count_after_first

    def test_missing_participant_fails(self, bridge, status_obj):
        tree = append_participant_status_tree(
            status_id=STATUS_ID,
            participant_id="https://example.org/cases/case-01/participants/missing",
            status_obj_fallback=status_obj,
        )
        result = bridge.execute_with_setup(tree=tree, actor_id=ACTOR_ID)
        assert result.status == Status.FAILURE

    def test_backwards_rm_transition_fails(
        self, populated_dl, populated_bridge, participant
    ):
        """A backwards RM transition (CLOSED → RECEIVED) is rejected."""
        closed_status = as_ParticipantStatus(
            id_=f"{STATUS_ID}/prev",
            context=CASE_ID,
            rm_state=RM.CLOSED,
        )
        participant.participant_statuses.append(closed_status)
        populated_dl.save(participant)
        populated_dl.create(closed_status)

        regressed_status = as_ParticipantStatus(
            id_=f"{STATUS_ID}/regressed",
            context=CASE_ID,
            rm_state=RM.RECEIVED,
        )
        populated_dl.create(regressed_status)

        tree = append_participant_status_tree(
            status_id=regressed_status.id_,
            participant_id=PARTICIPANT_ID,
            status_obj_fallback=regressed_status,
        )
        result = populated_bridge.execute_with_setup(
            tree=tree, actor_id=ACTOR_ID
        )
        assert result.status == Status.FAILURE

    def test_terminal_closed_duplicate_is_rejected_and_not_appended(
        self, populated_dl, populated_bridge, participant
    ):
        """Repeated CLOSED updates are rejected and do not append new status."""
        closed_status = as_ParticipantStatus(
            id_=f"{STATUS_ID}/prev",
            context=CASE_ID,
            rm_state=RM.CLOSED,
        )
        participant.participant_statuses.append(closed_status)
        populated_dl.save(participant)
        populated_dl.create(closed_status)

        duplicate_closed = as_ParticipantStatus(
            id_=f"{STATUS_ID}/closed-dup",
            context=CASE_ID,
            rm_state=RM.CLOSED,
        )
        populated_dl.create(duplicate_closed)

        before_count = len(participant.participant_statuses)
        tree = append_participant_status_tree(
            status_id=duplicate_closed.id_,
            participant_id=PARTICIPANT_ID,
            status_obj_fallback=duplicate_closed,
        )
        result = populated_bridge.execute_with_setup(
            tree=tree, actor_id=ACTOR_ID
        )
        assert result.status == Status.FAILURE

        updated_participant = populated_dl.read(PARTICIPANT_ID)
        assert updated_participant is not None
        assert len(updated_participant.participant_statuses) == before_count

    def test_forward_rm_jump_accepted(
        self, populated_dl, populated_bridge, participant
    ):
        """A non-adjacent but forward RM jump is accepted (sender authoritative)."""
        received_status = as_ParticipantStatus(
            id_=f"{STATUS_ID}/received",
            context=CASE_ID,
            rm_state=RM.RECEIVED,
        )
        participant.participant_statuses.append(received_status)
        populated_dl.save(participant)
        populated_dl.create(received_status)

        accepted_status = as_ParticipantStatus(
            id_=f"{STATUS_ID}/accepted",
            context=CASE_ID,
            rm_state=RM.ACCEPTED,
        )
        populated_dl.create(accepted_status)

        tree = append_participant_status_tree(
            status_id=accepted_status.id_,
            participant_id=PARTICIPANT_ID,
            status_obj_fallback=accepted_status,
        )
        result = populated_bridge.execute_with_setup(
            tree=tree, actor_id=ACTOR_ID
        )
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

    def test_skips_when_sender_is_not_case_owner(
        self, populated_dl, populated_bridge, status_obj
    ):
        """CASE_MANAGER sender (not CASE_OWNER) → skips teardown, SUCCESS."""
        from vultron.core.states.cs import CS_pxa
        from vultron.wire.as2.vocab.objects.case_status import as_CaseStatus

        cs = as_CaseStatus()
        cs.pxa_state = CS_pxa.Pxa  # public-aware
        status_obj.case_status = cs
        populated_dl.save(status_obj)

        node = PublicDisclosureBranchNode(
            status_obj=status_obj,
            sender_actor_id=CASE_MANAGER_ID,  # not CASE_OWNER
            case_id=CASE_ID,
        )
        result = populated_bridge.execute_with_setup(
            tree=node, actor_id=CASE_MANAGER_ID
        )
        assert result.status == Status.SUCCESS

    def test_triggers_teardown_on_public_aware_case_owner(
        self, populated_dl, populated_bridge, case, status_obj
    ):
        """CS.P + CASE_OWNER sender → embargo terminated (EM=EXITED), but
        FAILURE when no broadcast factory (BT-14-001).

        State transitions are committed before broadcast; the FAILURE propagates
        from the missing factory so callers can handle delivery errors.
        """
        from vultron.core.states.cs import CS_pxa
        from vultron.core.states.em import EM
        from vultron.wire.as2.vocab.objects.case_status import as_CaseStatus
        from vultron.wire.as2.vocab.objects.embargo_event import (
            as_EmbargoEvent,
        )

        # Give the case an active embargo in ACTIVE state
        embargo = as_EmbargoEvent(
            id_=f"{CASE_ID}/embargo_events/e1", context=CASE_ID
        )
        case.active_embargo = embargo.id_
        case.current_status.em_state = EM.ACTIVE
        populated_dl.create(embargo)
        populated_dl.save(case)

        cs = as_CaseStatus()
        cs.pxa_state = CS_pxa.Pxa  # public-aware
        status_obj.case_status = cs
        populated_dl.save(status_obj)

        # ACTOR_ID holds CASE_OWNER role (see `participant` fixture)
        node = PublicDisclosureBranchNode(
            status_obj=status_obj,
            sender_actor_id=ACTOR_ID,
            case_id=CASE_ID,
        )
        # No factory → broadcast fails → FAILURE (BT-14-001)
        result = populated_bridge.execute_with_setup(
            tree=node, actor_id=CASE_MANAGER_ID
        )
        assert result.status == Status.FAILURE

        from typing import cast as c

        from vultron.core.models.case import VulnerabilityCase

        # State was still applied before the broadcast attempt
        updated = c(VulnerabilityCase, populated_dl.read(CASE_ID))
        assert updated.current_status.em.state == EM.EXITED
        assert updated.active_embargo is None


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
        closed_status = as_ParticipantStatus(
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
            status=as_ParticipantStatus(id_=STATUS_ID, context=CASE_ID),
            target=as_CaseParticipant(
                id_=PARTICIPANT_ID, context=CASE_ID, attributed_to=ACTOR_ID
            ),
            actor=ACTOR_ID,
            context=as_VulnerabilityCase(id_=CASE_ID, name="Test"),
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
            status=as_ParticipantStatus(id_=STATUS_ID, context=CASE_ID),
            target=as_CaseParticipant(
                id_=PARTICIPANT_ID, context=CASE_ID, attributed_to=OUTSIDER_ID
            ),
            actor=OUTSIDER_ID,
            context=as_VulnerabilityCase(id_=CASE_ID, name="Test"),
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
