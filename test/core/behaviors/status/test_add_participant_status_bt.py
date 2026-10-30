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

Covers the DEMOMA-07-003 steps (step 3 raw re-broadcast removed per DEMOMA-07-005)
and StatusAdoptionGate authorization (ADR-0046, RSH-01-001 to RSH-01-004):

  1. SenderIsParticipantNode             — unknown sender is rejected
  2. AppendParticipantStatusNode               — status appended, RM regression rejected
  StatusAdoptionGate: SenderIsCaseOwnerNode                — CASE_OWNER gospel bypass (RSH-01-002)
  StatusAdoptionGate: StatusAdoptionGate                   — Fallback: bypass or call-out (RSH-01-002)
  StatusAdoptionGate: EmitCaseStatusUpdateNode — direct ledger write
      (RSH-01-003, RSH-04-006)

AutoCloseSequence was removed per ADR-0050: canonical RM closure is routed
through the Leave(VulnerabilityCase) receive path in receive_close_case_tree.

Per specs/multi-actor-demo.yaml DEMOMA-07-003, DEMOMA-07-005.
Per specs/received-status-handling.yaml RSH-01-001 to RSH-01-004.
"""

from typing import cast

import py_trees
import pytest
from py_trees.common import Status

from test.support.case_owner import CASE_OWNER_ID
from test.support.note_wire import assert_case_manager_note_recorded
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driven.sync_activity_adapter import SyncActivityAdapter
from vultron.adapters.driven.trigger_activity_adapter import (
    TriggerActivityAdapter,
)
from vultron.adapters.driven.wire_render.as2 import As2WireRenderAdapter
from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.call_out import unwrap_call_out
from vultron.core.behaviors.call_out.bundles.status_authorization import (
    STATUS_AUTHORIZATION_DETERMINISTIC,
    StatusAuthorizationCallOutBundle,
)
from vultron.core.behaviors.call_out.nodes import AlwaysFail
from vultron.core.behaviors.case_status_snapshot import (
    EmitCaseStatusUpdateNode,
)
from vultron.core.behaviors.sender_entitlement import (
    SenderIsCaseOwnerNode,
    SenderIsParticipantNode,
)
from vultron.core.behaviors.status.add_participant_status_tree import (
    add_participant_status_tree,
)
from vultron.core.behaviors.status.append_participant_status_tree import (
    append_participant_status_tree,
)
from vultron.core.behaviors.status.nodes import (
    AllParticipantsRMClosedConditionNode,
    AppendStatusAndSaveParticipantNode,
    CheckStatusNotAlreadyAppendedNode,
    CloseNotYetEmittedConditionNode,
    EmitRMGapNoteNode,
    LoadParticipantNode,
    ResolveAndPersistStatusObjectNode,
    ValidateRMTransitionNode,
)
from vultron.core.behaviors.status.nodes.rm_rule import BB_RM_ANOMALY
from vultron.core.behaviors.status.nodes.threat_termination import (
    ThreatTerminationBranchNode,
)
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.case_status import CaseStatus
from vultron.core.models.dimensions import (
    DDimension,
    PxaDimension,
    RmDimension,
    VfDimension,
)
from vultron.core.states.cs import CS_d, CS_pxa, CS_vf
from vultron.core.states.em import EM
from vultron.core.states.rm import RM
from vultron.core.use_cases.received.status import (
    AddParticipantStatusToParticipantReceivedUseCase,
)
from vultron.enums.roles import CVDRole
from vultron.wire.as2.factories import add_status_to_participant_activity
from vultron.wire.as2.vocab.objects.case_participant import as_CaseParticipant
from vultron.wire.as2.vocab.objects.case_status import as_ParticipantStatus
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)

#: The declared rule the tree's sender guard is composed from (HP-01-008).
_STATUS_RULE = (
    AddParticipantStatusToParticipantReceivedUseCase.sender_entitlement
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


@pytest.fixture
def executing_actor_id(request):
    """The actor whose identity this test's tree runs under.

    Declared per test with ``@pytest.mark.executes_as(...)``; defaults to
    ``ACTOR_ID``. Every store fixture below derives from it, because a BT's store
    follows its executing actor (ADR-0073) — so declaring the actor once keeps the
    whole fixture chain (``dl`` → ``bridge`` → ``populated_dl`` →
    ``populated_bridge``) consistent without threading it through each signature.
    """
    marker = request.node.get_closest_marker("executes_as")
    return marker.args[0] if marker else ACTOR_ID


@pytest.fixture
def dl(executing_actor_id):
    return SqliteDataLayer("sqlite:///:memory:", actor_id=executing_actor_id)


@pytest.fixture
def bridge(dl):
    return BTBridge(
        datalayer=dl,
        wire_render_port=As2WireRenderAdapter(),
        sync_port=SyncActivityAdapter(dl),
    )


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
    """VulnerabilityCase with vendor and Case Manager participants."""
    obj = VulnerabilityCase(
        id_=CASE_ID, name="Test Case", attributed_to=CASE_MANAGER_ID
    )
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
    return BTBridge(
        datalayer=populated_dl,
        wire_render_port=As2WireRenderAdapter(),
        sync_port=SyncActivityAdapter(populated_dl),
    )


# ---------------------------------------------------------------------------
# Step 1: SenderIsParticipantNode
# ---------------------------------------------------------------------------


class TestSenderIsParticipantNode:
    @pytest.mark.executes_as(CASE_MANAGER_ID)
    def test_known_sender_succeeds(self, populated_bridge):
        node = SenderIsParticipantNode(
            sender_actor_id=ACTOR_ID,
            case_id=CASE_ID,
        )
        result = populated_bridge.execute_with_setup(
            tree=node, actor_id=CASE_MANAGER_ID
        )
        assert result.status == Status.SUCCESS

    @pytest.mark.executes_as(CASE_MANAGER_ID)
    def test_unknown_sender_fails(self, populated_bridge):
        node = SenderIsParticipantNode(
            sender_actor_id=OUTSIDER_ID,
            case_id=CASE_ID,
        )
        result = populated_bridge.execute_with_setup(
            tree=node, actor_id=CASE_MANAGER_ID
        )
        assert result.status == Status.FAILURE

    def test_missing_case_fails(self, bridge):
        """No case in DataLayer → FAILURE."""
        node = SenderIsParticipantNode(
            sender_actor_id=ACTOR_ID,
            case_id="https://example.org/cases/nonexistent",
        )
        result = bridge.execute_with_setup(tree=node, actor_id=ACTOR_ID)
        assert result.status == Status.FAILURE

    @pytest.mark.executes_as(CASE_MANAGER_ID)
    def test_no_case_id_fails(self, populated_bridge):
        """With no case to check the sender against, the guard fails."""
        node = SenderIsParticipantNode(
            sender_actor_id=ACTOR_ID,
            case_id=None,
        )
        result = populated_bridge.execute_with_setup(
            tree=node, actor_id=CASE_MANAGER_ID
        )
        assert result.status == Status.FAILURE


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

    def test_persists_fallback_when_not_found(self, dl, bridge):
        """Persists fallback object when status not in DataLayer."""
        from vultron.core.models.participant_status import ParticipantStatus

        fallback = ParticipantStatus(id_=STATUS_ID, context=CASE_ID)
        node = ResolveAndPersistStatusObjectNode(
            status_id=STATUS_ID,
            status_obj_fallback=fallback,
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

    @pytest.mark.spec("RSH-06-002")
    def test_rejects_backwards_transition(
        self, populated_dl, populated_bridge
    ):
        """Backwards RM transition (CLOSED → RECEIVED) is rejected."""
        p = populated_dl.read(PARTICIPANT_ID)
        closed_status = as_ParticipantStatus(
            id_=f"{STATUS_ID}/closed",
            context=CASE_ID,
            rm=RmDimension(state=RM.CLOSED),
        )
        p.participant_statuses.append(closed_status)
        populated_dl.save(p)
        populated_dl.create(closed_status)

        regressed_status = as_ParticipantStatus(
            id_=f"{STATUS_ID}/regressed",
            context=CASE_ID,
            rm=RmDimension(state=RM.RECEIVED),
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
            rm=RmDimension(state=RM.CLOSED),
        )
        p.participant_statuses.append(closed_status)
        populated_dl.save(p)
        populated_dl.create(closed_status)

        duplicate_closed_status = as_ParticipantStatus(
            id_=f"{STATUS_ID}/closed-dup",
            context=CASE_ID,
            rm=RmDimension(state=RM.CLOSED),
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

    @pytest.mark.spec("RSH-06-001")
    def test_accepts_forward_jump(self, populated_dl, populated_bridge):
        """Non-adjacent forward RM jump is accepted (sender authoritative)."""
        p = populated_dl.read(PARTICIPANT_ID)
        received_status = as_ParticipantStatus(
            id_=f"{STATUS_ID}/received",
            context=CASE_ID,
            rm=RmDimension(state=RM.RECEIVED),
        )
        p.participant_statuses.append(received_status)
        populated_dl.save(p)
        populated_dl.create(received_status)

        accepted_status = as_ParticipantStatus(
            id_=f"{STATUS_ID}/accepted",
            context=CASE_ID,
            rm=RmDimension(state=RM.ACCEPTED),
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
        bridge = BTBridge(
            datalayer=populated_dl,
            wire_render_port=As2WireRenderAdapter(),
            sync_port=SyncActivityAdapter(populated_dl),
        )

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
        bridge2 = BTBridge(
            datalayer=populated_dl,
            wire_render_port=As2WireRenderAdapter(),
            sync_port=SyncActivityAdapter(populated_dl),
        )
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

    @pytest.mark.spec("BTND-10-007")
    def test_backwards_rm_transition_fails(
        self, populated_dl, populated_bridge, participant
    ):
        """A backwards RM transition (CLOSED → RECEIVED) is rejected."""
        closed_status = as_ParticipantStatus(
            id_=f"{STATUS_ID}/prev",
            context=CASE_ID,
            rm=RmDimension(state=RM.CLOSED),
        )
        participant.participant_statuses.append(closed_status)
        populated_dl.save(participant)
        populated_dl.create(closed_status)

        regressed_status = as_ParticipantStatus(
            id_=f"{STATUS_ID}/regressed",
            context=CASE_ID,
            rm=RmDimension(state=RM.RECEIVED),
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
            rm=RmDimension(state=RM.CLOSED),
        )
        participant.participant_statuses.append(closed_status)
        populated_dl.save(participant)
        populated_dl.create(closed_status)

        duplicate_closed = as_ParticipantStatus(
            id_=f"{STATUS_ID}/closed-dup",
            context=CASE_ID,
            rm=RmDimension(state=RM.CLOSED),
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
            rm=RmDimension(state=RM.RECEIVED),
        )
        participant.participant_statuses.append(received_status)
        populated_dl.save(participant)
        populated_dl.create(received_status)

        accepted_status = as_ParticipantStatus(
            id_=f"{STATUS_ID}/accepted",
            context=CASE_ID,
            rm=RmDimension(state=RM.ACCEPTED),
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
# Step 5: AllParticipantsRMClosedConditionNode (DEMOMA-07-006)
# ---------------------------------------------------------------------------


class TestAllParticipantsRMClosedConditionNode:
    @pytest.mark.executes_as(CASE_MANAGER_ID)
    def test_fails_when_participants_not_closed(self, populated_bridge):
        """No closed status on participant → FAILURE (not all closed)."""
        node = AllParticipantsRMClosedConditionNode(case_id=CASE_ID)
        result = populated_bridge.execute_with_setup(
            tree=node, actor_id=CASE_MANAGER_ID
        )
        assert result.status == Status.FAILURE

    @pytest.mark.executes_as(CASE_MANAGER_ID)
    def test_succeeds_when_all_participants_closed(
        self,
        populated_dl,
        participant,
        case_manager_participant,
    ):
        """All CVD participants (including CaseActor) at RM.CLOSED → SUCCESS (ADR-0051)."""
        closed_vendor = as_ParticipantStatus(
            id_=f"{STATUS_ID}/closed",
            context=CASE_ID,
            rm=RmDimension(state=RM.CLOSED),
        )
        closed_cm = as_ParticipantStatus(
            id_=f"{CM_PARTICIPANT_ID}/statuses/closed",
            context=CASE_ID,
            rm=RmDimension(state=RM.CLOSED),
        )
        populated_dl.create(closed_vendor)
        populated_dl.create(closed_cm)
        participant.participant_statuses.append(closed_vendor)
        populated_dl.save(participant)
        case_manager_participant.participant_statuses.append(closed_cm)
        populated_dl.save(case_manager_participant)

        bridge = BTBridge(
            datalayer=populated_dl,
            wire_render_port=As2WireRenderAdapter(),
            sync_port=SyncActivityAdapter(populated_dl),
        )
        node = AllParticipantsRMClosedConditionNode(case_id=CASE_ID)
        result = bridge.execute_with_setup(tree=node, actor_id=CASE_MANAGER_ID)
        assert result.status == Status.SUCCESS

    @pytest.mark.executes_as(CASE_MANAGER_ID)
    def test_fails_when_case_manager_participant_not_closed(
        self,
        populated_dl,
        participant,
        case_manager_participant,
    ):
        """CaseActor not at RM.CLOSED → FAILURE; no CASE_MANAGER skip (ADR-0051)."""
        # Only the vendor is CLOSED; case_manager_participant has no RM.CLOSED status
        closed_vendor = as_ParticipantStatus(
            id_=f"{STATUS_ID}/closed",
            context=CASE_ID,
            rm=RmDimension(state=RM.CLOSED),
        )
        populated_dl.create(closed_vendor)
        participant.participant_statuses.append(closed_vendor)
        populated_dl.save(participant)

        bridge = BTBridge(
            datalayer=populated_dl,
            wire_render_port=As2WireRenderAdapter(),
            sync_port=SyncActivityAdapter(populated_dl),
        )
        node = AllParticipantsRMClosedConditionNode(case_id=CASE_ID)
        result = bridge.execute_with_setup(tree=node, actor_id=CASE_MANAGER_ID)
        # CaseActor is not RM.CLOSED → FAILURE (ADR-0051 removes the old skip)
        assert result.status == Status.FAILURE

    def test_fails_when_no_case_id(self, bridge):
        """No case_id → FAILURE."""
        node = AllParticipantsRMClosedConditionNode(case_id=None)
        result = bridge.execute_with_setup(tree=node, actor_id=ACTOR_ID)
        assert result.status == Status.FAILURE

    def test_fails_when_case_not_found(self, bridge):
        """Case not in DataLayer → FAILURE."""
        node = AllParticipantsRMClosedConditionNode(
            case_id="https://example.org/cases/nonexistent"
        )
        result = bridge.execute_with_setup(tree=node, actor_id=ACTOR_ID)
        assert result.status == Status.FAILURE


# ---------------------------------------------------------------------------
# Step 5: CloseNotYetEmittedConditionNode (DEMOMA-07-006 idempotency)
# ---------------------------------------------------------------------------


class TestCloseNotYetEmittedConditionNode:
    @pytest.mark.executes_as(CASE_MANAGER_ID)
    def test_succeeds_when_outbox_empty(self, populated_bridge):
        """Empty outbox → no prior Leave → SUCCESS."""
        node = CloseNotYetEmittedConditionNode(case_id=CASE_ID)
        result = populated_bridge.execute_with_setup(
            tree=node, actor_id=CASE_MANAGER_ID
        )
        assert result.status == Status.SUCCESS

    def test_fails_when_no_case_id(self, bridge):
        """No case_id → FAILURE."""
        node = CloseNotYetEmittedConditionNode(case_id=None)
        result = bridge.execute_with_setup(tree=node, actor_id=ACTOR_ID)
        assert result.status == Status.FAILURE

    @pytest.mark.executes_as(CASE_MANAGER_ID)
    def test_fails_when_leave_already_in_outbox(self, populated_dl):
        """Leave(VulnerabilityCase) already in outbox → FAILURE (idempotency)."""
        from vultron.core.models.activity import VultronActivity

        leave_activity = VultronActivity(
            id_=f"{CASE_ID}/activities/leave-01",
            type_="Leave",
            actor=CASE_MANAGER_ID,
            object_=CASE_ID,
        )
        populated_dl.create(leave_activity)
        populated_dl.outbox_append(leave_activity.id_)

        bridge = BTBridge(
            datalayer=populated_dl,
            wire_render_port=As2WireRenderAdapter(),
            sync_port=SyncActivityAdapter(populated_dl),
        )
        node = CloseNotYetEmittedConditionNode(case_id=CASE_ID)
        result = bridge.execute_with_setup(tree=node, actor_id=CASE_MANAGER_ID)
        assert result.status == Status.FAILURE

    @pytest.mark.executes_as(CASE_MANAGER_ID)
    def test_succeeds_when_leave_for_different_case(self, populated_dl):
        """Leave in outbox for a different case → SUCCESS (not our case)."""
        from vultron.core.models.activity import VultronActivity

        other_case_id = "https://example.org/cases/other-case"
        leave_activity = VultronActivity(
            id_=f"{other_case_id}/activities/leave-01",
            type_="Leave",
            actor=CASE_MANAGER_ID,
            object_=other_case_id,
        )
        populated_dl.create(leave_activity)
        populated_dl.outbox_append(leave_activity.id_)

        bridge = BTBridge(
            datalayer=populated_dl,
            wire_render_port=As2WireRenderAdapter(),
            sync_port=SyncActivityAdapter(populated_dl),
        )
        node = CloseNotYetEmittedConditionNode(case_id=CASE_ID)
        result = bridge.execute_with_setup(tree=node, actor_id=CASE_MANAGER_ID)
        assert result.status == Status.SUCCESS


# ---------------------------------------------------------------------------
# Full tree: add_participant_status_tree
# ---------------------------------------------------------------------------


class TestAddParticipantStatusTree:
    def _bridge_with_factory(self, dl: SqliteDataLayer) -> BTBridge:
        return BTBridge(
            datalayer=dl,
            trigger_activity=TriggerActivityAdapter(dl),
            wire_render_port=As2WireRenderAdapter(),
            sync_port=SyncActivityAdapter(dl),
        )

    @pytest.mark.spec("RSH-01-001")
    @pytest.mark.spec("RSH-01-003")
    @pytest.mark.spec("RSH-04-004")
    @pytest.mark.executes_as(CASE_MANAGER_ID)
    def test_full_tree_succeeds_for_case_owner_sender(
        self,
        populated_dl,
        make_payload,
    ):
        """End-to-end: a CASE_OWNER sender's status is adopted at the
        CASE_MANAGER → status appended, CaseStatus committed directly to ledger
        (RSH-01-001 to RSH-01-003, RSH-04-004).

        RSH-08-003 (#3814): the adoption pipeline (append → StatusAdoptionGate
        → EmitCaseStatusUpdateNode) now runs only at the CASE_MANAGER, so the
        tree executes in the CASE_MANAGER's store; the gospel bypass keys on
        the *sender's* CASE_OWNER role, which is ACTOR_ID.
        """
        from vultron.core.models.case import VulnerabilityCase as CoreCase

        activity = add_status_to_participant_activity(
            status=as_ParticipantStatus(id_=STATUS_ID, context=CASE_ID),
            target=as_CaseParticipant(
                id_=PARTICIPANT_ID, context=CASE_ID, attributed_to=ACTOR_ID
            ),
            actor=ACTOR_ID,
            to=[CASE_MANAGER_ID],
            context=as_VulnerabilityCase(
                attributed_to=CASE_OWNER_ID, id_=CASE_ID, name="Test"
            ),
        )
        event = make_payload(activity)
        bridge = self._bridge_with_factory(populated_dl)
        tree = add_participant_status_tree(
            request=event,
            case_id=CASE_ID,
            sender_rule=_STATUS_RULE,
        )
        case_before = populated_dl.read(CASE_ID)
        initial_status_count = (
            len(case_before.case_statuses)
            if isinstance(case_before, CoreCase)
            else 0
        )
        result = bridge.execute_with_setup(
            tree=tree, actor_id=CASE_MANAGER_ID, activity=event
        )
        assert result.status == Status.SUCCESS

        p = populated_dl.read(PARTICIPANT_ID)
        assert p is not None
        status_ids = [getattr(s, "id_", s) for s in p.participant_statuses]
        assert STATUS_ID in status_ids

        # RSH-01-003, RSH-04-006: EmitCaseStatusUpdateNode appends a new
        # CaseStatus directly to the case (no inbox routing).
        case_after = populated_dl.read(CASE_ID)
        assert isinstance(case_after, CoreCase)
        assert len(case_after.case_statuses) > initial_status_count, (
            "EmitCaseStatusUpdateNode must append a new CaseStatus to the case"
        )

    @pytest.mark.executes_as(OUTSIDER_ID)
    def test_full_tree_fails_for_unknown_sender(
        self,
        populated_dl,
        make_payload,
    ):
        """Unknown sender → SenderIsParticipantNode fails, tree halts."""
        activity = add_status_to_participant_activity(
            status=as_ParticipantStatus(id_=STATUS_ID, context=CASE_ID),
            target=as_CaseParticipant(
                id_=PARTICIPANT_ID, context=CASE_ID, attributed_to=OUTSIDER_ID
            ),
            actor=OUTSIDER_ID,
            context=as_VulnerabilityCase(
                attributed_to=CASE_OWNER_ID, id_=CASE_ID, name="Test"
            ),
        )
        event = make_payload(activity)
        bridge = self._bridge_with_factory(populated_dl)
        tree = add_participant_status_tree(
            request=event,
            case_id=CASE_ID,
            sender_rule=_STATUS_RULE,
        )
        result = bridge.execute_with_setup(tree=tree, actor_id=OUTSIDER_ID)
        assert result.status == Status.FAILURE

        p = populated_dl.read(PARTICIPANT_ID)
        assert p is not None
        # STATUS_ID was NOT appended; only the auto-initialised default status exists
        status_ids = [getattr(s, "id_", s) for s in p.participant_statuses]
        assert STATUS_ID not in status_ids

    @pytest.mark.spec("RSH-01-002")
    def test_guard_blocks_non_owner_when_call_out_fails(
        self,
        populated_dl,
        make_payload,
    ):
        """Non-CASE_OWNER sender with AlwaysFail call-out → blocked at gate
        (RSH-01-002): StatusAdoptionGate denied — Add(CaseStatus) NOT emitted to outbox.

        Uses CASE_MANAGER_ID as the sender (not CASE_OWNER) so SenderIsCaseOwnerNode
        returns FAILURE, routing to the AlwaysFail call-out which also fails.
        Executes as ACTOR_ID (vendor) to skip the guarded ledger-commit subtree.
        """
        bridge = self._bridge_with_factory(populated_dl)
        reject_bundle = StatusAuthorizationCallOutBundle(
            status_adoption_gate_factory=AlwaysFail  # type: ignore[arg-type]
        )
        cm_status_id = f"{STATUS_ID}/cm"
        cm_status = as_ParticipantStatus(id_=cm_status_id, context=CASE_ID)
        populated_dl.create(cm_status)
        # CASE_MANAGER_ID is NOT CASE_OWNER — SenderIsCaseOwnerNode will return FAILURE
        cm_activity = add_status_to_participant_activity(
            status=as_ParticipantStatus(id_=cm_status_id, context=CASE_ID),
            target=as_CaseParticipant(
                id_=CM_PARTICIPANT_ID,
                context=CASE_ID,
                attributed_to=CASE_MANAGER_ID,
            ),
            actor=CASE_MANAGER_ID,
            context=as_VulnerabilityCase(
                attributed_to=CASE_OWNER_ID, id_=CASE_ID, name="Test"
            ),
        )
        cm_event = make_payload(cm_activity)
        cm_tree = add_participant_status_tree(
            sender_rule=_STATUS_RULE,
            request=cm_event,
            case_id=CASE_ID,
            call_out=reject_bundle,
        )
        # Execute as the vendor (ACTOR_ID) — not CASE_MANAGER → ledger commit skipped
        result = bridge.execute_with_setup(tree=cm_tree, actor_id=ACTOR_ID)
        assert result.status == Status.FAILURE
        # Outbox must be empty: guard blocked before EmitCaseStatusUpdateNode
        outbox = populated_dl.outbox_list()
        assert len(outbox) == 0, (
            "StatusAdoptionGate denied — no Add(CaseStatus) must be in outbox"
        )

    @pytest.mark.spec("RSH-07-001")
    @pytest.mark.spec("RSH-01-002")
    def test_non_owner_blocked_by_require_case_owner_approval_default(
        self,
        populated_dl,
        make_payload,
    ):
        """Non-CASE_OWNER sender with default DETERMINISTIC bundle → blocked by RequireCaseOwnerApproval.

        RSH-07-001: the default status_adoption_gate_factory is RequireCaseOwnerApproval,
        not AlwaysSucceed.  A non-owner sender must not get their status adopted
        without explicit Case Owner authorization.
        """
        from vultron.core.behaviors.call_out.nodes import (
            RequireCaseOwnerApprovalNode,
        )

        bridge = self._bridge_with_factory(populated_dl)
        cm_status_id = f"{STATUS_ID}/cm-default"
        cm_status = as_ParticipantStatus(id_=cm_status_id, context=CASE_ID)
        populated_dl.create(cm_status)
        # CASE_MANAGER_ID is NOT CASE_OWNER — SenderIsCaseOwnerNode returns FAILURE → call-out fires
        cm_activity = add_status_to_participant_activity(
            status=cm_status,
            target=as_CaseParticipant(
                id_=CM_PARTICIPANT_ID,
                context=CASE_ID,
                attributed_to=CASE_MANAGER_ID,
            ),
            actor=CASE_MANAGER_ID,
            context=as_VulnerabilityCase(
                attributed_to=CASE_OWNER_ID, id_=CASE_ID, name="Test"
            ),
        )
        event = make_payload(cm_activity)
        # Default DETERMINISTIC bundle — RequireCaseOwnerApproval is wired
        cm_tree = add_participant_status_tree(
            request=event,
            case_id=CASE_ID,
            sender_rule=_STATUS_RULE,
        )

        # Verify RequireCaseOwnerApprovalNode is wired as the call-out
        def _collect_nodes(node):
            result_inner = [node]
            for child in getattr(node, "children", []):
                result_inner.extend(_collect_nodes(child))
            return result_inner

        all_nodes = _collect_nodes(cm_tree)
        assert any(
            isinstance(n, RequireCaseOwnerApprovalNode) for n in all_nodes
        ), (
            "RequireCaseOwnerApprovalNode must be present in the tree when using DETERMINISTIC bundle"
        )

        result = bridge.execute_with_setup(tree=cm_tree, actor_id=ACTOR_ID)
        assert result.status == Status.FAILURE, (
            "Non-CASE_OWNER sender must be blocked by RequireCaseOwnerApproval (RSH-07-001)"
        )
        outbox = populated_dl.outbox_list()
        assert len(outbox) == 0, (
            "RequireCaseOwnerApproval blocked — no Add(CaseStatus) must be in outbox"
        )

    @pytest.mark.spec("RSH-03-001")
    @pytest.mark.spec("RSH-03-003")
    def test_legacy_public_disclosure_branch_absent(
        self,
        populated_dl,
        make_payload,
    ):
        """The legacy ``PublicDisclosureBranchNode`` is not in the tree.

        Teardown runs in ``add_participant_status_tree`` only through the
        ``TeardownEffects`` sequence (gate → ``ThreatTerminationBranchNode``,
        RSH-01-004, RSH-03-001); the CS.P-only predecessor must be gone."""
        activity = add_status_to_participant_activity(
            status=as_ParticipantStatus(id_=STATUS_ID, context=CASE_ID),
            target=as_CaseParticipant(
                id_=PARTICIPANT_ID, context=CASE_ID, attributed_to=ACTOR_ID
            ),
            actor=ACTOR_ID,
            context=as_VulnerabilityCase(
                attributed_to=CASE_OWNER_ID, id_=CASE_ID, name="Test"
            ),
        )
        event = make_payload(activity)
        tree = add_participant_status_tree(
            request=event,
            case_id=CASE_ID,
            sender_rule=_STATUS_RULE,
        )

        # PublicDisclosureBranchNode must NOT appear anywhere in the tree
        def _collect_nodes(node: py_trees.behaviour.Behaviour) -> list:
            result_inner = [node]
            for child in getattr(node, "children", []):
                result_inner.extend(_collect_nodes(child))
            return result_inner

        all_nodes = _collect_nodes(tree)
        node_types = [type(n).__name__ for n in all_nodes]
        assert "PublicDisclosureBranchNode" not in node_types, (
            "PublicDisclosureBranchNode must NOT be in add_participant_status_tree "
            "(RSH-03-001: ThreatTerminationBranchNode under TeardownEffects "
            "replaced it)"
        )

    @pytest.mark.spec("RSH-03-004")
    @pytest.mark.spec("RSH-08-003")
    def test_teardown_branch_runs_only_at_the_case_manager(
        self,
        populated_dl,
        make_payload,
    ):
        """``ThreatTerminationBranchNode`` sits under the CASE_MANAGER gate.

        A replica therefore never runs the teardown, and never asks the
        CASE_MANAGER for one: it learns the teardown from the committed
        entries alone (RSH-03-004).
        """
        activity = add_status_to_participant_activity(
            status=as_ParticipantStatus(id_=STATUS_ID, context=CASE_ID),
            target=as_CaseParticipant(
                id_=PARTICIPANT_ID, context=CASE_ID, attributed_to=ACTOR_ID
            ),
            actor=ACTOR_ID,
            context=as_VulnerabilityCase(
                attributed_to=CASE_OWNER_ID, id_=CASE_ID, name="Test"
            ),
        )
        tree = add_participant_status_tree(
            request=make_payload(activity),
            case_id=CASE_ID,
            sender_rule=_STATUS_RULE,
        )

        gates = [
            n
            for n in tree.iterate()
            if n.name == "AdoptParticipantStatusIfCaseManager"
        ]
        assert len(gates) == 1
        under_gate = {id(n) for n in gates[0].iterate()}
        branches = [
            n
            for n in tree.iterate()
            if isinstance(n, ThreatTerminationBranchNode)
        ]
        assert branches, "the tree must tear down on an adopted P/X/A"
        assert all(id(n) in under_gate for n in branches)

    @pytest.mark.spec("RSH-01-001")
    @pytest.mark.spec("RSH-01-002")
    @pytest.mark.spec("RSH-04-004")
    @pytest.mark.spec("RSH-04-006")
    def test_emit_node_present_rsh_01_001(
        self,
        populated_dl,
        make_payload,
    ):
        """EmitCaseStatusUpdateNode and StatusAdoptionGate must be present
        in the tree (RSH-01-001, RSH-04-006)."""
        activity = add_status_to_participant_activity(
            status=as_ParticipantStatus(id_=STATUS_ID, context=CASE_ID),
            target=as_CaseParticipant(
                id_=PARTICIPANT_ID, context=CASE_ID, attributed_to=ACTOR_ID
            ),
            actor=ACTOR_ID,
            context=as_VulnerabilityCase(
                attributed_to=CASE_OWNER_ID, id_=CASE_ID, name="Test"
            ),
        )
        event = make_payload(activity)
        tree = add_participant_status_tree(
            request=event,
            case_id=CASE_ID,
            sender_rule=_STATUS_RULE,
        )

        def _collect_nodes(node: py_trees.behaviour.Behaviour) -> list:
            result_inner = [node]
            for child in getattr(node, "children", []):
                result_inner.extend(_collect_nodes(child))
            return result_inner

        all_nodes = _collect_nodes(tree)
        node_names = [n.name for n in all_nodes]
        node_types = [type(n).__name__ for n in all_nodes]

        assert "EmitCaseStatusUpdate" in node_names, (
            "EmitCaseStatusUpdateNode must be present (RSH-01-001, RSH-04-006)"
        )
        assert EmitCaseStatusUpdateNode.__name__ in node_types, (
            "EmitCaseStatusUpdateNode type must appear in tree (RSH-04-006)"
        )
        assert "EmitAddCaseStatusToSelf" not in node_names, (
            "EmitAddCaseStatusToSelfNode must NOT be in tree (replaced by RSH-04-006)"
        )
        assert "StatusAdoptionGate" in node_names, (
            "StatusAdoptionGate must be present (RSH-01-001)"
        )
        assert "SenderIsCaseOwner" in node_names, (
            "SenderIsCaseOwnerNode must be present inside StatusAdoptionGate (RSH-01-002)"
        )


# ---------------------------------------------------------------------------
# Regression: AutoCloseSequence must NOT be present (ADR-0050)
# ---------------------------------------------------------------------------


class TestNoAutoCloseSequenceInTree:
    """Regression guard: AutoCloseSequence is dead code per ADR-0050.

    Canonical RM closure is routed through Leave(VulnerabilityCase) receive
    path in receive_close_case_tree.  This tree must NOT contain any
    AutoCloseSequence, AutoCloseIfCaseManager, EmitCloseCaseNode, or
    ResolveCaseManagerNode subtrees.
    """

    def _all_nodes(self, node: py_trees.behaviour.Behaviour) -> list:
        result = [node]
        for child in getattr(node, "children", []):
            result.extend(self._all_nodes(child))
        return result

    def test_no_auto_close_sequence_node(self, make_payload):
        """AutoCloseSequence must not appear in add_participant_status_tree."""
        activity = add_status_to_participant_activity(
            status=as_ParticipantStatus(id_=STATUS_ID, context=CASE_ID),
            target=as_CaseParticipant(
                id_=PARTICIPANT_ID, context=CASE_ID, attributed_to=ACTOR_ID
            ),
            actor=ACTOR_ID,
            context=as_VulnerabilityCase(
                attributed_to=CASE_OWNER_ID, id_=CASE_ID, name="Test"
            ),
        )
        event = make_payload(activity)
        tree = add_participant_status_tree(
            request=event,
            case_id=CASE_ID,
            sender_rule=_STATUS_RULE,
        )
        all_nodes = self._all_nodes(tree)
        node_names = [n.name for n in all_nodes]
        assert "AutoCloseSequence" not in node_names, (
            "AutoCloseSequence must be removed per ADR-0050"
        )
        assert "AutoCloseIfCaseManager" not in node_names, (
            "AutoCloseIfCaseManager must be removed per ADR-0050"
        )

    def test_no_emit_close_case_node(self, make_payload):
        """EmitCloseCaseNode must not appear in add_participant_status_tree."""
        from vultron.core.behaviors.status.nodes.lifecycle import (
            EmitCloseCaseNode,
        )

        activity = add_status_to_participant_activity(
            status=as_ParticipantStatus(id_=STATUS_ID, context=CASE_ID),
            target=as_CaseParticipant(
                id_=PARTICIPANT_ID, context=CASE_ID, attributed_to=ACTOR_ID
            ),
            actor=ACTOR_ID,
            context=as_VulnerabilityCase(
                attributed_to=CASE_OWNER_ID, id_=CASE_ID, name="Test"
            ),
        )
        event = make_payload(activity)
        tree = add_participant_status_tree(
            request=event,
            case_id=CASE_ID,
            sender_rule=_STATUS_RULE,
        )
        all_nodes = self._all_nodes(tree)
        assert not any(isinstance(n, EmitCloseCaseNode) for n in all_nodes), (
            "EmitCloseCaseNode must not be in add_participant_status_tree (ADR-0050)"
        )


# ---------------------------------------------------------------------------
# StatusAdoptionGate: SenderIsCaseOwnerNode (RSH-01-002)
# ---------------------------------------------------------------------------


class TestSenderIsCaseOwnerNode:
    @pytest.mark.spec("RSH-01-002")
    @pytest.mark.executes_as(CASE_MANAGER_ID)
    def test_case_owner_returns_success(self, populated_bridge):
        """CASE_OWNER sender → SUCCESS (gospel bypass)."""
        node = SenderIsCaseOwnerNode(
            sender_actor_id=ACTOR_ID,  # has CASE_OWNER role in fixture
            case_id=CASE_ID,
        )
        result = populated_bridge.execute_with_setup(
            tree=node, actor_id=CASE_MANAGER_ID
        )
        assert result.status == Status.SUCCESS

    @pytest.mark.spec("RSH-01-002")
    @pytest.mark.executes_as(CASE_MANAGER_ID)
    def test_non_owner_returns_failure(self, populated_bridge):
        """CASE_MANAGER sender (not CASE_OWNER) → FAILURE (proceeds to call-out)."""
        node = SenderIsCaseOwnerNode(
            sender_actor_id=CASE_MANAGER_ID,  # has CASE_MANAGER role, not CASE_OWNER
            case_id=CASE_ID,
        )
        result = populated_bridge.execute_with_setup(
            tree=node, actor_id=CASE_MANAGER_ID
        )
        assert result.status == Status.FAILURE

    @pytest.mark.executes_as(CASE_MANAGER_ID)
    def test_unknown_actor_returns_failure(self, populated_bridge):
        """Actor not in actor_participant_index → FAILURE."""
        node = SenderIsCaseOwnerNode(
            sender_actor_id=OUTSIDER_ID,
            case_id=CASE_ID,
        )
        result = populated_bridge.execute_with_setup(
            tree=node, actor_id=CASE_MANAGER_ID
        )
        assert result.status == Status.FAILURE

    @pytest.mark.executes_as(CASE_MANAGER_ID)
    def test_no_case_returns_failure(self, bridge):
        """No case in DataLayer → FAILURE."""
        node = SenderIsCaseOwnerNode(
            sender_actor_id=ACTOR_ID,
            case_id="https://example.org/cases/nonexistent",
        )
        result = bridge.execute_with_setup(tree=node, actor_id=CASE_MANAGER_ID)
        assert result.status == Status.FAILURE

    @pytest.mark.executes_as(CASE_MANAGER_ID)
    def test_no_case_id_returns_failure(self, bridge):
        """No case_id at all → FAILURE."""
        node = SenderIsCaseOwnerNode(
            sender_actor_id=ACTOR_ID,
            case_id=None,
        )
        result = bridge.execute_with_setup(tree=node, actor_id=CASE_MANAGER_ID)
        assert result.status == Status.FAILURE


# ---------------------------------------------------------------------------
# StatusAdoptionGate: StatusAuthorizationCallOutBundle (RSH-01-002)
# ---------------------------------------------------------------------------


class TestStatusAuthorizationCallOutBundle:
    @pytest.mark.spec("RSH-07-001")
    @pytest.mark.executes_as(CASE_MANAGER_ID)
    def test_deterministic_singleton_blocks_by_default(self, populated_bridge):
        """STATUS_AUTHORIZATION_DETERMINISTIC has RequireCaseOwnerApprovalNode factory (ADR-0076)."""
        from vultron.core.behaviors.call_out.nodes import (
            RequireCaseOwnerApprovalNode,
        )

        node = STATUS_AUTHORIZATION_DETERMINISTIC.status_adoption_gate_factory(
            "CaseOwnerApprovesStatusUpdate"
        )
        assert isinstance(unwrap_call_out(node), RequireCaseOwnerApprovalNode)
        result = populated_bridge.execute_with_setup(
            tree=node, actor_id=CASE_MANAGER_ID
        )
        assert result.status == Status.FAILURE

    @pytest.mark.spec("RSH-07-003")
    @pytest.mark.executes_as(CASE_MANAGER_ID)
    def test_permissive_singleton_approves(self, populated_bridge):
        """STATUS_AUTHORIZATION_PERMISSIVE has AlwaysSucceed factory (explicit override)."""
        from vultron.core.behaviors.call_out.bundles.status_authorization import (
            STATUS_AUTHORIZATION_PERMISSIVE,
        )

        node = STATUS_AUTHORIZATION_PERMISSIVE.status_adoption_gate_factory(
            "CaseOwnerApprovesStatusUpdate"
        )
        result = populated_bridge.execute_with_setup(
            tree=node, actor_id=CASE_MANAGER_ID
        )
        assert result.status == Status.SUCCESS

    @pytest.mark.executes_as(CASE_MANAGER_ID)
    def test_custom_bundle_with_always_fail(self, populated_bridge):
        """Custom bundle with AlwaysFail factory → call-out denies approval."""
        bundle = StatusAuthorizationCallOutBundle(
            status_adoption_gate_factory=AlwaysFail  # type: ignore[arg-type]
        )
        node = bundle.status_adoption_gate_factory(
            "CaseOwnerApprovesStatusUpdate"
        )
        result = populated_bridge.execute_with_setup(
            tree=node, actor_id=CASE_MANAGER_ID
        )
        assert result.status == Status.FAILURE

    def test_bundle_is_frozen(self):
        """Bundle is immutable (frozen dataclass)."""
        import dataclasses

        assert dataclasses.is_dataclass(StatusAuthorizationCallOutBundle)
        bundle = StatusAuthorizationCallOutBundle()
        with pytest.raises((AttributeError, dataclasses.FrozenInstanceError)):
            bundle.status_adoption_gate_factory = lambda name: None  # type: ignore[method-assign]


# ---------------------------------------------------------------------------
# Regression: CLP-10-009 / ISSUE-2254 — validators in preconditions
# ---------------------------------------------------------------------------


class TestRejectionValidatorBeforeCommit:
    """CLP-10-009 / ISSUE-2254 regression.

    ValidateRMTransitionNode must NOT fire after GuardedCommit in the
    receive-side path.  Before the fix it did, causing canonical/replica
    divergence when it refused a status the ledger had already recorded.

    The fix is validate_rm=False in add_participant_status_tree, delegating
    rm judgment entirely to CheckParticipantStatusAcceptableNode
    (precondition guard), which refuses the whole status before the commit
    (RSH-09-001).
    """

    def _bridge_with_factory(self, dl: SqliteDataLayer) -> BTBridge:
        return BTBridge(
            datalayer=dl,
            trigger_activity=TriggerActivityAdapter(dl),
            wire_render_port=As2WireRenderAdapter(),
            sync_port=SyncActivityAdapter(dl),
        )

    @pytest.mark.spec("CLP-10-009", "RSH-09-002")
    def test_backward_rm_with_vf_advance_is_refused_before_the_commit(
        self, make_payload
    ):
        """Participant is RM.ACCEPTED; incoming status advances vf but asserts
        a backwards rm (VALID ≺ ACCEPTED).

        The whole status is refused in the precondition guard, so no receipt
        entry is committed and the vf advance is not recorded either: the
        ledger never records a status the sender did not send (RSH-09-001).
        """
        from vultron.core.models.case_ledger_entry import CaseLedgerEntry
        from vultron.core.states.cs import CS_vf
        from vultron.enums.roles import CVDRole

        # The tree runs as the case manager, so this is the case manager's
        # own store (BT-05-005, ADR-0073).
        dl = SqliteDataLayer("sqlite:///:memory:", actor_id=CASE_MANAGER_ID)
        cm_participant = CaseParticipant(
            id_=CM_PARTICIPANT_ID,
            context=CASE_ID,
            attributed_to=CASE_MANAGER_ID,
            case_roles=[CVDRole.CASE_MANAGER],
        )
        # attributed_to seeds the per-case genesis hash (CLP-08-003)
        case = VulnerabilityCase(
            id_=CASE_ID, name="Fix1 Regression", attributed_to=CASE_MANAGER_ID
        )
        case.add_participant(cm_participant)

        existing_status = as_ParticipantStatus(
            id_=f"{STATUS_ID}/existing",
            context=CASE_ID,
            rm=RmDimension(state=RM.ACCEPTED),
        )
        vendor_participant = as_CaseParticipant(
            id_=PARTICIPANT_ID,
            context=CASE_ID,
            attributed_to=ACTOR_ID,
            case_roles=[CVDRole.CASE_OWNER, CVDRole.VENDOR],
        )
        vendor_participant.participant_statuses.append(existing_status)
        case.add_participant(cast(CaseParticipant, vendor_participant))

        dl.create(case)
        dl.create(cm_participant)
        dl.create(vendor_participant)
        dl.create(existing_status)

        # Incoming status: rm=VALID (backwards from ACCEPTED), vfd advances to Vfd
        incoming_status = as_ParticipantStatus(
            id_=STATUS_ID,
            context=CASE_ID,
            rm=RmDimension(state=RM.VALID),
            vf=VfDimension(state=CS_vf.Vf),
        )
        dl.create(incoming_status)

        activity = add_status_to_participant_activity(
            status=incoming_status,
            target=vendor_participant,
            actor=ACTOR_ID,
            to=[CASE_MANAGER_ID],
            context=as_VulnerabilityCase(
                attributed_to=CASE_OWNER_ID,
                id_=CASE_ID,
                name="Fix1 Regression",
            ),
        )
        event = make_payload(activity, at=dl)

        bridge = self._bridge_with_factory(dl)
        tree = add_participant_status_tree(
            request=event,
            case_id=CASE_ID,
            sender_rule=_STATUS_RULE,
        )
        result = bridge.execute_with_setup(
            tree=tree, actor_id=CASE_MANAGER_ID, activity=event
        )
        assert result.status == Status.FAILURE, (
            "a backward rm refuses the whole status before GuardedCommit"
        )

        receipt_entries = [
            e
            for e in dl.list_objects("CaseLedgerEntry")
            if isinstance(e, CaseLedgerEntry)
            and getattr(e, "semantic_type", None)
            == "add_participant_status_to_participant"
        ]
        assert receipt_entries == [], (
            "a refused status commits no receipt entry (CLP-10-009)"
        )

    @pytest.mark.spec("CLP-10-009")
    def test_fully_rejected_update_produces_no_ledger_entry(
        self, make_payload
    ):
        """A status refused by CheckParticipantStatusAcceptableNode →
        FAILURE before GuardedCommit → zero CaseLedgerEntries (CLP-10-009).
        """
        from vultron.core.models.case_ledger_entry import CaseLedgerEntry
        from vultron.core.states.cs import CS_vf
        from vultron.enums.roles import CVDRole

        # The tree runs as the case manager, so this is the case manager's
        # own store (BT-05-005, ADR-0073).
        dl = SqliteDataLayer("sqlite:///:memory:", actor_id=CASE_MANAGER_ID)
        cm_participant = CaseParticipant(
            id_=CM_PARTICIPANT_ID,
            context=CASE_ID,
            attributed_to=CASE_MANAGER_ID,
            case_roles=[CVDRole.CASE_MANAGER],
        )
        # attributed_to seeds the per-case genesis hash (CLP-08-003)
        case = VulnerabilityCase(
            id_=CASE_ID, name="Fix1 Full Reject", attributed_to=CASE_MANAGER_ID
        )
        case.add_participant(cm_participant)

        existing_status = as_ParticipantStatus(
            id_=f"{STATUS_ID}/existing",
            context=CASE_ID,
            rm=RmDimension(state=RM.CLOSED),
            vf=VfDimension(state=CS_vf.Vf),
        )
        vendor_participant = as_CaseParticipant(
            id_=PARTICIPANT_ID,
            context=CASE_ID,
            attributed_to=ACTOR_ID,
            case_roles=[CVDRole.CASE_OWNER],
        )
        vendor_participant.participant_statuses.append(existing_status)
        case.add_participant(cast(CaseParticipant, vendor_participant))

        dl.create(case)
        dl.create(cm_participant)
        dl.create(vendor_participant)
        dl.create(existing_status)

        # Incoming status: rm backwards AND vfd backwards → all dimensions refused
        incoming_status = as_ParticipantStatus(
            id_=STATUS_ID,
            context=CASE_ID,
            rm=RmDimension(state=RM.VALID),
        )
        dl.create(incoming_status)

        activity = add_status_to_participant_activity(
            status=incoming_status,
            target=vendor_participant,
            actor=ACTOR_ID,
            context=as_VulnerabilityCase(
                attributed_to=CASE_OWNER_ID,
                id_=CASE_ID,
                name="Fix1 Full Reject",
            ),
        )
        event = make_payload(activity, at=dl)

        bridge = self._bridge_with_factory(dl)
        tree = add_participant_status_tree(
            request=event,
            case_id=CASE_ID,
            sender_rule=_STATUS_RULE,
        )
        result = bridge.execute_with_setup(
            tree=tree, actor_id=CASE_MANAGER_ID, activity=event
        )
        assert result.status == Status.FAILURE, (
            "A fully rejected update must fail before GuardedCommit"
        )

        entries = [
            e
            for e in dl.list_objects("CaseLedgerEntry")
            if isinstance(e, CaseLedgerEntry)
        ]
        assert len(entries) == 0, (
            "A fully rejected update must produce zero CaseLedgerEntries"
            " (CLP-10-009)"
        )


# ---------------------------------------------------------------------------
# EmitRMGapNoteNode (RSH-06)
# ---------------------------------------------------------------------------


@pytest.mark.executes_as(CASE_MANAGER_ID)
class TestEmitRMGapNoteNode:
    """EmitRMGapNoteNode records the RSH-06-004 note on RM anomaly (#4829).

    Every test here runs the node as the case manager, so ``dl`` — and the
    ``populated_dl`` built on it — must be the *case manager's* store: a BT's
    store follows its executing actor (BT-05-005, ADR-0073), and the node
    commits to whichever store it was handed.
    """

    def _bridge_with_factory(self, dl: SqliteDataLayer) -> BTBridge:
        return BTBridge(
            datalayer=dl,
            trigger_activity=TriggerActivityAdapter(dl),
            wire_render_port=As2WireRenderAdapter(),
            sync_port=SyncActivityAdapter(dl),
        )

    def _set_anomaly(self, anomaly_type: str, from_rm: RM, to_rm: RM) -> None:
        """Write BB_RM_ANOMALY directly to blackboard storage for the test."""
        import py_trees

        py_trees.blackboard.Blackboard.storage["/" + BB_RM_ANOMALY] = {
            "anomaly_type": anomaly_type,
            "from_rm": from_rm,
            "to_rm": to_rm,
        }

    def test_no_anomaly_is_noop_success(self, populated_dl):
        """BB_RM_ANOMALY=None → SUCCESS with no outbox entry (happy path)."""
        bridge = self._bridge_with_factory(populated_dl)
        node = EmitRMGapNoteNode(
            sender_actor_id=ACTOR_ID,
            case_id=CASE_ID,
        )
        result = bridge.execute_with_setup(tree=node, actor_id=CASE_MANAGER_ID)
        assert result.status == Status.SUCCESS
        outbox = populated_dl.outbox_list()
        assert len(outbox) == 0, "No anomaly → no outbox entry expected"

    @pytest.mark.spec("RSH-06-004")
    @pytest.mark.spec("VAM-01-010")
    @pytest.mark.spec("CLP-10-001")
    def test_gap_anomaly_records_note(self, populated_dl):
        """BB_RM_ANOMALY=gap → SUCCESS + one committed inline Add(Note)."""
        bridge = self._bridge_with_factory(populated_dl)
        node = EmitRMGapNoteNode(
            sender_actor_id=ACTOR_ID,
            case_id=CASE_ID,
        )
        # Pre-populate anomaly flag as if CheckParticipantStatusAcceptableNode ran
        self._set_anomaly("gap", RM.RECEIVED, RM.ACCEPTED)

        result = bridge.execute_with_setup(tree=node, actor_id=CASE_MANAGER_ID)
        assert result.status == Status.SUCCESS

        note = assert_case_manager_note_recorded(populated_dl, CASE_ID)
        assert "non-adjacent forward" in note["content"]

    @pytest.mark.spec("RSH-06-004")
    @pytest.mark.spec("VAM-01-010")
    @pytest.mark.spec("CLP-10-001")
    def test_regression_anomaly_records_note(self, populated_dl):
        """BB_RM_ANOMALY=regression → SUCCESS + one committed inline Add(Note)."""
        bridge = self._bridge_with_factory(populated_dl)
        node = EmitRMGapNoteNode(
            sender_actor_id=ACTOR_ID,
            case_id=CASE_ID,
        )
        self._set_anomaly("regression", RM.ACCEPTED, RM.RECEIVED)

        result = bridge.execute_with_setup(tree=node, actor_id=CASE_MANAGER_ID)
        assert result.status == Status.SUCCESS

        note = assert_case_manager_note_recorded(populated_dl, CASE_ID)
        assert "backward" in note["content"]

    @pytest.mark.spec("RSH-06-004")
    def test_refused_commit_is_logged_and_succeeds(
        self, populated_dl, monkeypatch
    ):
        """A refused note commit is a logged no-op: SHOULD-level (RSH-06-004).

        Nothing is attached, because the attach follows the commit.
        """
        from test.support.ledger import fail_commits
        from vultron.core.behaviors.sync import commit_tree

        refused = fail_commits(monkeypatch, commit_tree)
        bridge = self._bridge_with_factory(populated_dl)
        node = EmitRMGapNoteNode(sender_actor_id=ACTOR_ID, case_id=CASE_ID)
        self._set_anomaly("gap", RM.RECEIVED, RM.ACCEPTED)

        result = bridge.execute_with_setup(tree=node, actor_id=CASE_MANAGER_ID)

        assert result.status == Status.SUCCESS
        assert len(refused) == 1
        case = populated_dl.read_case(CASE_ID)
        assert case is not None
        assert case.notes == []

    def test_a_case_lost_after_the_commit_is_an_internal_error(
        self, populated_dl, monkeypatch
    ):
        """A failure after the entry committed is not logged as 'not recorded'.

        The best-effort skip covers a refused commit only; once the entry
        exists, the attach failing is an internal error.
        """
        bridge = self._bridge_with_factory(populated_dl)
        node = EmitRMGapNoteNode(sender_actor_id=ACTOR_ID, case_id=CASE_ID)
        self._set_anomaly("gap", RM.RECEIVED, RM.ACCEPTED)
        real_require_case = node._require_case
        calls: list[str] = []

        def _require_case_then_lose_it(case_id):
            calls.append(case_id)
            if len(calls) == 1:
                return real_require_case(case_id)
            return None, Status.FAILURE

        monkeypatch.setattr(node, "_require_case", _require_case_then_lose_it)

        result = bridge.execute_with_setup(tree=node, actor_id=CASE_MANAGER_ID)

        assert result.status == Status.FAILURE
        assert result.internal_error is True
        assert "vanished after its" in result.feedback_message

    def test_no_case_id_is_noop_success(self, populated_dl):
        """case_id=None → SUCCESS with no outbox entry (no case context)."""
        bridge = self._bridge_with_factory(populated_dl)
        node = EmitRMGapNoteNode(
            sender_actor_id=ACTOR_ID,
            case_id=None,
        )
        self._set_anomaly("gap", RM.RECEIVED, RM.ACCEPTED)

        result = bridge.execute_with_setup(tree=node, actor_id=CASE_MANAGER_ID)
        assert result.status == Status.SUCCESS
        outbox = populated_dl.outbox_list()
        assert len(outbox) == 0, "No case_id → no outbox entry expected"

    def test_no_factory_is_success_noop(self, populated_bridge):
        """No TriggerActivityPort → SUCCESS (degrades gracefully — SHOULD not MUST)."""
        node = EmitRMGapNoteNode(
            sender_actor_id=ACTOR_ID,
            case_id=CASE_ID,
        )
        self._set_anomaly("gap", RM.RECEIVED, RM.ACCEPTED)
        # populated_bridge has no trigger_activity_factory
        result = populated_bridge.execute_with_setup(
            tree=node, actor_id=CASE_MANAGER_ID
        )
        assert result.status == Status.SUCCESS


# ---------------------------------------------------------------------------
# Structural wiring: TeardownEffectsOrSkip subtree must be present after
# EmitCaseStatusUpdateNode (RSH-03-001 to RSH-03-003, RSH-04-004)
# ---------------------------------------------------------------------------


class TestAddParticipantStatusTeardownWiring:
    """Verify ThreatTerminationBranchNode + EmbargoTeardownAuthorizationGate
    are wired into the TeardownEffectsOrSkip subtree directly after
    EmitCaseStatusUpdateNode.

    Mirrors the structural assertions in test_trigger_tree.py.
    """

    def _collect_nodes(
        self, node: py_trees.behaviour.Behaviour
    ) -> list[py_trees.behaviour.Behaviour]:
        result: list[py_trees.behaviour.Behaviour] = [node]
        for child in getattr(node, "children", []):
            result.extend(self._collect_nodes(child))
        return result

    @pytest.mark.spec("RSH-03-001")
    @pytest.mark.spec("RSH-03-002")
    @pytest.mark.spec("RSH-03-003")
    def test_threat_termination_branch_present(self, make_payload):
        """ThreatTerminationBranchNode must appear in add_participant_status_tree."""
        activity = add_status_to_participant_activity(
            status=as_ParticipantStatus(id_=STATUS_ID, context=CASE_ID),
            target=as_CaseParticipant(
                id_=PARTICIPANT_ID, context=CASE_ID, attributed_to=ACTOR_ID
            ),
            actor=ACTOR_ID,
            context=as_VulnerabilityCase(
                attributed_to=CASE_OWNER_ID, id_=CASE_ID, name="Test"
            ),
        )
        event = make_payload(activity)
        tree = add_participant_status_tree(
            request=event,
            case_id=CASE_ID,
            sender_rule=_STATUS_RULE,
        )

        all_nodes = self._collect_nodes(tree)
        node_types = [type(n).__name__ for n in all_nodes]

        assert ThreatTerminationBranchNode.__name__ in node_types, (
            "ThreatTerminationBranchNode must be wired into"
            " add_participant_status_tree (RSH-03-001 to RSH-03-003)"
        )

    @pytest.mark.spec("RSH-02-001")
    def test_embargo_teardown_gate_present(self, make_payload):
        """EmbargoTeardownAuthorizationGate must appear in add_participant_status_tree."""
        activity = add_status_to_participant_activity(
            status=as_ParticipantStatus(id_=STATUS_ID, context=CASE_ID),
            target=as_CaseParticipant(
                id_=PARTICIPANT_ID, context=CASE_ID, attributed_to=ACTOR_ID
            ),
            actor=ACTOR_ID,
            context=as_VulnerabilityCase(
                attributed_to=CASE_OWNER_ID, id_=CASE_ID, name="Test"
            ),
        )
        event = make_payload(activity)
        tree = add_participant_status_tree(
            request=event,
            case_id=CASE_ID,
            sender_rule=_STATUS_RULE,
        )

        all_nodes = self._collect_nodes(tree)
        node_names = [n.name for n in all_nodes]

        assert "EmbargoTeardownAuthorizationGate" in node_names, (
            "EmbargoTeardownAuthorizationGate must be wired into the"
            " TeardownEffects subtree (RSH-02-001)"
        )

    @pytest.mark.spec("RSH-03-001")
    @pytest.mark.spec("RSH-04-004")
    @pytest.mark.spec("RSH-04-006")
    def test_teardown_after_emit_node(self, make_payload):
        """ThreatTerminationBranchNode must follow EmitCaseStatusUpdateNode in traversal order."""
        activity = add_status_to_participant_activity(
            status=as_ParticipantStatus(id_=STATUS_ID, context=CASE_ID),
            target=as_CaseParticipant(
                id_=PARTICIPANT_ID, context=CASE_ID, attributed_to=ACTOR_ID
            ),
            actor=ACTOR_ID,
            context=as_VulnerabilityCase(
                attributed_to=CASE_OWNER_ID, id_=CASE_ID, name="Test"
            ),
        )
        event = make_payload(activity)
        tree = add_participant_status_tree(
            request=event,
            case_id=CASE_ID,
            sender_rule=_STATUS_RULE,
        )

        all_nodes = self._collect_nodes(tree)
        node_names = [n.name for n in all_nodes]
        node_types = [type(n).__name__ for n in all_nodes]

        assert "EmitCaseStatusUpdate" in node_names
        assert ThreatTerminationBranchNode.__name__ in node_types

        emit_idx = node_names.index("EmitCaseStatusUpdate")
        threat_idx = node_types.index(ThreatTerminationBranchNode.__name__)
        assert threat_idx > emit_idx, (
            "ThreatTerminationBranchNode must appear after EmitCaseStatusUpdateNode"
            " in tree traversal order (RSH-03-001, RSH-04-004)"
        )

    @pytest.mark.spec("RSH-04-004")
    @pytest.mark.spec("RSH-04-006")
    def test_teardown_wrapped_in_failure_is_success(self, make_payload):
        """TeardownEffectsOrSkip must be a FailureIsSuccess decorator."""
        activity = add_status_to_participant_activity(
            status=as_ParticipantStatus(id_=STATUS_ID, context=CASE_ID),
            target=as_CaseParticipant(
                id_=PARTICIPANT_ID, context=CASE_ID, attributed_to=ACTOR_ID
            ),
            actor=ACTOR_ID,
            context=as_VulnerabilityCase(
                attributed_to=CASE_OWNER_ID, id_=CASE_ID, name="Test"
            ),
        )
        event = make_payload(activity)
        tree = add_participant_status_tree(
            request=event,
            case_id=CASE_ID,
            sender_rule=_STATUS_RULE,
        )

        all_nodes = self._collect_nodes(tree)
        node_names = [n.name for n in all_nodes]
        node_types_map = {n.name: type(n).__name__ for n in all_nodes}

        assert "TeardownEffectsOrSkip" in node_names, (
            "TeardownEffectsOrSkip wrapper must be present (RSH-04-004)"
        )
        assert node_types_map["TeardownEffectsOrSkip"] == "FailureIsSuccess", (
            "TeardownEffectsOrSkip must be a FailureIsSuccess decorator"
        )

    @pytest.mark.spec("RSH-01-004")
    @pytest.mark.spec("RSH-02-001")
    def test_teardown_effects_begin_with_authorization_gate(
        self, make_payload
    ):
        """``TeardownEffects`` is a Sequence whose first child is the gate.

        RSH-01-004: side-effects run only after the canonical write and pass
        through ``EmbargoTeardownAuthorizationGate`` before executing, so the
        gate must be the first child of the ``TeardownEffects`` Sequence.
        """
        activity = add_status_to_participant_activity(
            status=as_ParticipantStatus(id_=STATUS_ID, context=CASE_ID),
            target=as_CaseParticipant(
                id_=PARTICIPANT_ID, context=CASE_ID, attributed_to=ACTOR_ID
            ),
            actor=ACTOR_ID,
            context=as_VulnerabilityCase(
                attributed_to=CASE_OWNER_ID, id_=CASE_ID, name="Test"
            ),
        )
        event = make_payload(activity)
        tree = add_participant_status_tree(
            request=event,
            case_id=CASE_ID,
            sender_rule=_STATUS_RULE,
        )

        all_nodes = self._collect_nodes(tree)
        teardown = [n for n in all_nodes if n.name == "TeardownEffects"]
        assert len(teardown) == 1, "exactly one TeardownEffects Sequence"
        children = list(getattr(teardown[0], "children", []))
        assert children, "TeardownEffects must have children"
        assert children[0].name == "EmbargoTeardownAuthorizationGate", (
            "TeardownEffects must begin with EmbargoTeardownAuthorizationGate"
            " (RSH-01-004, RSH-02-001)"
        )


# ---------------------------------------------------------------------------
# Adoption of a reported P/X/A into the case status (RSH-01-003, #4956)
# ---------------------------------------------------------------------------

REPORTER_ID = "https://example.org/actors/reporter"
REPORTER_PARTICIPANT_ID = f"{CASE_ID}/participants/reporter"
PXA_STATUS_ID = f"{PARTICIPANT_ID}/statuses/pxa"


def _pxa_report(
    pxa: CS_pxa,
    *,
    sender: str = ACTOR_ID,
    participant_id: str = PARTICIPANT_ID,
    em: EM | None = None,
):
    """``Add(ParticipantStatus)`` reporting *pxa* in its embedded case status."""
    from vultron.core.models.dimensions import EmDimension
    from vultron.wire.as2.vocab.objects.case_status import as_CaseStatus

    embedded = as_CaseStatus(
        context=CASE_ID,
        pxa=PxaDimension(state=pxa),
        em=EmDimension(state=em) if em is not None else EmDimension(),
    )
    return add_status_to_participant_activity(
        status=as_ParticipantStatus(
            id_=f"{participant_id}/statuses/pxa",
            context=CASE_ID,
            case_status=embedded,
        ),
        target=as_CaseParticipant(
            id_=participant_id, context=CASE_ID, attributed_to=sender
        ),
        actor=sender,
        to=[CASE_MANAGER_ID],
        context=as_VulnerabilityCase(
            attributed_to=CASE_OWNER_ID, id_=CASE_ID, name="Test"
        ),
    )


def _cm_bridge(dl: SqliteDataLayer) -> BTBridge:
    return BTBridge(
        datalayer=dl,
        trigger_activity=TriggerActivityAdapter(dl),
        wire_render_port=As2WireRenderAdapter(),
        sync_port=SyncActivityAdapter(dl),
    )


def _run_at_case_manager(
    dl: SqliteDataLayer,
    event,
    call_out: StatusAuthorizationCallOutBundle | None = None,
):
    tree = add_participant_status_tree(
        request=event,
        case_id=CASE_ID,
        sender_rule=_STATUS_RULE,
        call_out=(
            call_out
            if call_out is not None
            else STATUS_AUTHORIZATION_DETERMINISTIC
        ),
    )
    return _cm_bridge(dl).execute_with_setup(
        tree=tree, actor_id=CASE_MANAGER_ID, activity=event
    )


def _case_status_entries(dl: SqliteDataLayer) -> list:
    from vultron.core.models.case_ledger_entry import CaseLedgerEntry

    return [
        e
        for e in dl.list_objects("CaseLedgerEntry")
        if isinstance(e, CaseLedgerEntry)
        and e.semantic_type == "add_case_status_to_case"
    ]


def _seed_case_pxa(dl: SqliteDataLayer, pxa: CS_pxa) -> None:
    """Record *pxa* as the case's status, stamped to the whole second as the
    status the tree commits is, so that one sorts after it (CM-29-001)."""
    from datetime import UTC, datetime

    case = dl.read(CASE_ID)
    assert isinstance(case, VulnerabilityCase)
    case.append_case_status(pxa=pxa)
    earlier = datetime.now(UTC).replace(microsecond=0)
    seeded = case.case_statuses[-1]
    assert isinstance(seeded, CaseStatus)
    seeded.published = earlier
    seeded.updated = earlier
    dl.save(case)


def _case_pxa(dl: SqliteDataLayer) -> CS_pxa:
    case = dl.read(CASE_ID)
    assert isinstance(case, VulnerabilityCase)
    return case.current_status.pxa.state


class TestAdoptedPxaReachesTheCaseStatus:
    """A participant's adopted P, X or A is what the CASE_MANAGER's committed
    CaseStatus records (RSH-01-003, #4956).

    Before #4956 ``EmitCaseStatusUpdateNode`` re-snapshotted the case's own
    ``pxa``, so the reported value never reached the case status.
    """

    @pytest.mark.spec("RSH-01-003")
    @pytest.mark.spec("RSH-04-003")
    @pytest.mark.spec("RSH-07-006")
    @pytest.mark.spec("CLP-10-009")
    @pytest.mark.executes_as(CASE_MANAGER_ID)
    def test_an_owners_public_awareness_is_adopted(
        self, populated_dl, make_payload
    ):

        result = _run_at_case_manager(
            populated_dl, make_payload(_pxa_report(CS_pxa.Pxa))
        )

        assert result.status == Status.SUCCESS, result.feedback_message
        assert _case_pxa(populated_dl) == CS_pxa.Pxa
        entries = _case_status_entries(populated_dl)
        assert len(entries) == 1, entries
        assert entries[0].payload_snapshot["object"]["pxaState"] == "Pxa"

    @pytest.mark.spec("RSH-01-003")
    @pytest.mark.executes_as(CASE_MANAGER_ID)
    def test_an_adopted_report_never_moves_em(
        self, populated_dl, make_payload
    ):
        """The P advance is adopted; the embedded EM is not (ADR-0122):
        EM is derived from the embargo register alone."""

        result = _run_at_case_manager(
            populated_dl,
            make_payload(_pxa_report(CS_pxa.Pxa, em=EM.PROPOSED)),
        )

        assert result.status == Status.SUCCESS, result.feedback_message
        case = populated_dl.read(CASE_ID)
        assert isinstance(case, VulnerabilityCase)
        assert case.current_status.pxa.state == CS_pxa.Pxa
        assert case.current_status.em.state == EM.NONE
        assert case.em_state == EM.NONE

    @pytest.mark.spec("RSH-01-003")
    @pytest.mark.spec("RSH-07-001")
    @pytest.mark.executes_as(CASE_MANAGER_ID)
    def test_a_refused_adoption_leaves_the_case_pxa(
        self, populated_dl, make_payload
    ):
        from test.core.use_cases.received.conftest import (
            seed_case_participant,
        )

        case = populated_dl.read(CASE_ID)
        assert isinstance(case, VulnerabilityCase)
        seed_case_participant(populated_dl, case, REPORTER_ID)
        populated_dl.save(case)

        result = _run_at_case_manager(
            populated_dl,
            make_payload(
                _pxa_report(
                    CS_pxa.Pxa,
                    sender=REPORTER_ID,
                    participant_id=REPORTER_PARTICIPANT_ID,
                )
            ),
            call_out=StatusAuthorizationCallOutBundle(
                status_adoption_gate_factory=AlwaysFail  # type: ignore[arg-type]
            ),
        )

        # A withheld adoption is not a failure of the act: it keeps its
        # entry and the append (RSH-09-008, CLP-07-015).
        assert result.status == Status.SUCCESS, result.feedback_message
        assert _case_pxa(populated_dl) == CS_pxa.pxa
        assert _case_status_entries(populated_dl) == []

    @pytest.mark.spec("CLP-07-015")
    @pytest.mark.spec("RSH-01-003")
    @pytest.mark.executes_as(CASE_MANAGER_ID)
    def test_a_failed_adoption_fails_the_act_and_keeps_nothing(
        self, populated_dl, make_payload, monkeypatch
    ):
        """Only a withheld adoption keeps the act; one that fails rolls back
        the append and the act's own entry with it (CLP-07-015)."""
        participant_before = populated_dl.read(PARTICIPANT_ID)
        assert isinstance(participant_before, CaseParticipant)
        ledger_before = {
            e.id_ for e in populated_dl.list_objects("CaseLedgerEntry")
        }
        monkeypatch.setattr(
            EmitCaseStatusUpdateNode, "update", lambda self: Status.FAILURE
        )

        result = _run_at_case_manager(
            populated_dl, make_payload(_pxa_report(CS_pxa.Pxa))
        )

        assert result.status == Status.FAILURE
        stored = populated_dl.read(PARTICIPANT_ID)
        assert isinstance(stored, CaseParticipant)
        assert stored.participant_statuses == (
            participant_before.participant_statuses
        ), "the append is rolled back"
        assert {
            e.id_ for e in populated_dl.list_objects("CaseLedgerEntry")
        } == ledger_before
        assert _case_pxa(populated_dl) == CS_pxa.pxa

    @pytest.mark.spec("RSH-01-003")
    @pytest.mark.executes_as(CASE_MANAGER_ID)
    def test_a_report_omitting_a_latch_keeps_it(
        self, populated_dl, make_payload, caplog
    ):
        """Case at PXa; a report of Pxa omits X, which the case keeps, and
        the kept latch is logged at INFO."""
        import logging

        _seed_case_pxa(populated_dl, CS_pxa.PXa)

        with caplog.at_level(logging.INFO):
            result = _run_at_case_manager(
                populated_dl, make_payload(_pxa_report(CS_pxa.Pxa))
            )

        kept = [
            r.getMessage()
            for r in caplog.records
            if r.levelno == logging.INFO
            and "already records; kept" in r.getMessage()
        ]
        assert len(kept) == 1, kept
        assert f"for case '{CASE_ID}' omits X" in kept[0], kept[0]
        assert f"actor_id={CASE_MANAGER_ID}" in kept[0], kept[0]

        assert result.status == Status.SUCCESS, result.feedback_message
        assert _case_pxa(populated_dl) == CS_pxa.PXa
        entries = _case_status_entries(populated_dl)
        assert [e.payload_snapshot["object"]["pxaState"] for e in entries] == [
            "PXa"
        ]

    @pytest.mark.spec("RSH-01-003")
    @pytest.mark.executes_as(CASE_MANAGER_ID)
    def test_a_report_without_case_status_keeps_case_pxa(
        self, populated_dl, make_payload
    ):
        """A status embedding no ``case_status`` reports no P/X/A."""
        _seed_case_pxa(populated_dl, CS_pxa.Pxa)
        activity = add_status_to_participant_activity(
            status=as_ParticipantStatus(
                id_=f"{PARTICIPANT_ID}/statuses/none", context=CASE_ID
            ),
            target=as_CaseParticipant(
                id_=PARTICIPANT_ID, context=CASE_ID, attributed_to=ACTOR_ID
            ),
            actor=ACTOR_ID,
            to=[CASE_MANAGER_ID],
            context=as_VulnerabilityCase(
                attributed_to=CASE_OWNER_ID, id_=CASE_ID, name="Test"
            ),
        )

        result = _run_at_case_manager(populated_dl, make_payload(activity))

        assert result.status == Status.SUCCESS, result.feedback_message
        assert _case_pxa(populated_dl) == CS_pxa.Pxa

    @pytest.mark.spec("RSH-01-003")
    @pytest.mark.executes_as(CASE_MANAGER_ID)
    def test_a_mixed_report_adds_its_new_latch(
        self, populated_dl, make_payload
    ):
        """Case at PxA; a report of PXa omits A but newly sets X: the case
        moves to PXA, so the teardown never acts on an X it does not record."""

        _seed_case_pxa(populated_dl, CS_pxa.PxA)

        result = _run_at_case_manager(
            populated_dl, make_payload(_pxa_report(CS_pxa.PXa))
        )

        assert result.status == Status.SUCCESS, result.feedback_message
        assert _case_pxa(populated_dl) == CS_pxa.PXA

    def _emit(self, dl: SqliteDataLayer, reported_status_id: str) -> Status:
        """Tick ``EmitCaseStatusUpdateNode`` alone, adopting the status
        stored at *reported_status_id*."""
        from vultron.core.behaviors.case_status_snapshot import (
            EmitCaseStatusUpdateNode,
        )

        node = EmitCaseStatusUpdateNode(
            case_id=CASE_ID, reported_status_id=reported_status_id
        )
        return (
            _cm_bridge(dl)
            .execute_with_setup(tree=node, actor_id=CASE_MANAGER_ID)
            .status
        )

    @pytest.mark.spec("RSH-01-003")
    @pytest.mark.executes_as(CASE_MANAGER_ID)
    def test_the_stored_status_is_what_is_adopted(self, populated_dl):
        """The node reads the report by id at tick, not from the inline
        activity, so the stored copy's P is adopted (#4956)."""
        status = _pxa_report(CS_pxa.Pxa).object_
        assert isinstance(status, as_ParticipantStatus)
        populated_dl.create(status)

        assert self._emit(populated_dl, status.id_) == Status.SUCCESS
        assert _case_pxa(populated_dl) == CS_pxa.Pxa

    @pytest.mark.spec("RSH-01-003")
    @pytest.mark.spec("ARCH-15-001")
    @pytest.mark.executes_as(CASE_MANAGER_ID)
    def test_a_missing_reported_status_fails_and_commits_nothing(
        self, populated_dl
    ):
        """Nothing stored at the id is a broken store, never a report to
        skip: the node fails and commits no CaseStatus."""
        missing = f"{PARTICIPANT_ID}/statuses/missing"

        assert self._emit(populated_dl, missing) == Status.FAILURE
        assert _case_status_entries(populated_dl) == []
        assert _case_pxa(populated_dl) == CS_pxa.pxa

    @pytest.mark.spec("RSH-01-003")
    @pytest.mark.spec("ARCH-15-001")
    @pytest.mark.executes_as(CASE_MANAGER_ID)
    def test_a_reported_id_naming_a_case_status_fails(self, populated_dl):
        """The id must name a ``ParticipantStatus``; a ``CaseStatus`` stored
        there fails the node and commits nothing."""
        from vultron.wire.as2.vocab.objects.case_status import as_CaseStatus

        wrong = as_CaseStatus(
            id_=f"{CASE_ID}/statuses/not-a-participant-status",
            context=CASE_ID,
            pxa=PxaDimension(state=CS_pxa.Pxa),
        )
        populated_dl.create(wrong)

        assert self._emit(populated_dl, wrong.id_) == Status.FAILURE
        assert _case_status_entries(populated_dl) == []
        assert _case_pxa(populated_dl) == CS_pxa.pxa


class TestAdoptedPxa:
    """``adopted_pxa`` adds the report's latches and clears none, promoted
    (SM-09-001)."""

    @pytest.mark.spec("RSH-01-003")
    @pytest.mark.spec("SM-09-001")
    @pytest.mark.parametrize(
        ("current", "reported", "expected"),
        [
            ("pxa", "Pxa", "Pxa"),  # forward
            ("pxa", "PXA", "PXA"),  # multi-component forward
            ("Pxa", "Pxa", "Pxa"),  # equal
            ("PXa", "Pxa", "PXa"),  # omits X: kept
            ("PxA", "PXa", "PXA"),  # omits A, sets X: union
            ("pxa", None, "pxa"),  # nothing reported
            ("pxa", "pXa", "PXa"),  # reported pX promoted to PX
            ("pXa", None, "PXa"),  # current pX promoted to PX
        ],
    )
    def test_adopted_pxa(self, current, reported, expected):
        from vultron.core.behaviors.case_status_snapshot import adopted_pxa
        from vultron.core.models.case_status import CaseStatus

        status = (
            None
            if reported is None
            else CaseStatus(
                context=CASE_ID, pxa=PxaDimension(state=CS_pxa[reported])
            )
        )
        assert adopted_pxa(CS_pxa[current], status) is CS_pxa[expected]


# ---------------------------------------------------------------------------
# Embargo teardown gate and CSB-18 diagnostic, behaviourally
# (moved from test_add_case_status_bt.py: the CASE_MANAGER adopts a P/X/A
# report only through Add(ParticipantStatus), RSH-04-005, #4851)
# ---------------------------------------------------------------------------


def _cm_store_with_active_embargo() -> SqliteDataLayer:
    """The CASE_MANAGER's store: the vendor (Case Owner) and the CASE_MANAGER
    seated on a case under an active embargo."""
    return _cm_store_with_embargo(EM.ACTIVE)


def _cm_store_with_embargo(em: EM) -> SqliteDataLayer:
    """The CASE_MANAGER's store: the vendor (Case Owner) and the CASE_MANAGER
    seated on a case whose embargo is proposed or active.

    The participants are attached before the embargo is registered, so each
    holds a consent row for it (ADR-0122).
    """
    from test.support.embargo_register import (
        activate,
        agree_to_active_embargo,
        propose,
        write_consent_rows,
    )
    from vultron.core.models._helpers import days_from_now_utc
    from vultron.wire.as2.vocab.objects.embargo_event import as_EmbargoEvent

    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=CASE_MANAGER_ID)
    vendor = as_CaseParticipant(
        id_=PARTICIPANT_ID,
        context=CASE_ID,
        attributed_to=ACTOR_ID,
        case_roles=[CVDRole.CASE_OWNER],
    )
    manager = as_CaseParticipant(
        id_=CM_PARTICIPANT_ID,
        context=CASE_ID,
        attributed_to=CASE_MANAGER_ID,
        case_roles=[CVDRole.CASE_MANAGER],
    )
    case = VulnerabilityCase(
        id_=CASE_ID, name="Teardown Case", attributed_to=CASE_MANAGER_ID
    )
    case.add_participant(vendor)
    case.add_participant(manager)
    embargo = as_EmbargoEvent(
        id_=f"{CASE_ID}/embargo_events/e1",
        context=CASE_ID,
        end_time=days_from_now_utc(45),
    )
    if em is EM.ACTIVE:
        activate(case, embargo.id_)
    else:
        propose(case, embargo.id_)
    dl.create(case)
    dl.create(vendor)
    dl.create(manager)
    dl.create(embargo)
    write_consent_rows(dl, case)
    if em is EM.ACTIVE:
        # Both are signatories, so the vendor's report is an active
        # participant's (CM-10-004) and every commit can address it.
        agree_to_active_embargo(dl, case, ACTOR_ID, CASE_MANAGER_ID)
    return dl


class TestAdoptedThreatTeardown:
    """EmbargoTeardownAuthorizationGate (RSH-02-001) and the post-cascade
    CSB-18 check (#4829) on an adopted P report under an active embargo."""

    @pytest.mark.executes_as(CASE_MANAGER_ID)
    @pytest.mark.parametrize(
        "call_out",
        [
            pytest.param(
                StatusAuthorizationCallOutBundle(
                    embargo_teardown_authorization_gate_factory=AlwaysFail  # type: ignore[arg-type]
                ),
                id="always-fail-teardown-gate",
                marks=pytest.mark.spec("RSH-02-001"),
            ),
            pytest.param(
                None,
                id="default-bundle",
                marks=pytest.mark.spec("RSH-07-002"),
            ),
        ],
    )
    def test_a_refusing_teardown_gate_holds_the_embargo(
        self, make_payload, call_out
    ):
        """A teardown gate that refuses leaves the embargo ACTIVE.

        The Case Owner's own P report passes adoption without approval
        (RSH-07-006), so the case's P is set. The teardown it calls for
        runs only past the teardown gate: an ``AlwaysFail`` gate
        (RSH-02-001), or the default bundle's gate, which refuses without
        the Case Owner's authorization, none being recorded (RSH-07-002).
        ``FailureIsSuccess`` wraps the teardown Sequence, so the tree still
        succeeds; the EM state is untouched.
        """

        populated_dl = _cm_store_with_active_embargo()

        result = _run_at_case_manager(
            populated_dl,
            make_payload(_pxa_report(CS_pxa.Pxa)),
            call_out=call_out,
        )

        assert result.status == Status.SUCCESS, result.feedback_message
        case = populated_dl.read(CASE_ID)
        assert isinstance(case, VulnerabilityCase)
        assert case.current_status.pxa.state == CS_pxa.Pxa
        assert case.current_status.em.state == EM.ACTIVE

    @pytest.mark.spec("CSB-18-002")
    @pytest.mark.spec("CSB-18-003")
    @pytest.mark.spec("CSB-18-004")
    def test_permissive_gate_teardown_fires_no_note_posted(self, make_payload):
        """PERMISSIVE gate — teardown fires, EM=EXITED → no violation, no note."""
        from vultron.core.behaviors.call_out.bundles.status_authorization import (
            STATUS_AUTHORIZATION_PERMISSIVE,
        )

        populated_dl = _cm_store_with_active_embargo()

        result = _run_at_case_manager(
            populated_dl,
            make_payload(_pxa_report(CS_pxa.Pxa)),
            call_out=STATUS_AUTHORIZATION_PERMISSIVE,
        )

        assert result.status == Status.SUCCESS, result.feedback_message
        case = populated_dl.read(CASE_ID)
        assert isinstance(case, VulnerabilityCase)
        assert case.current_status.em.state == EM.EXITED
        assert case.current_status.pxa.state == CS_pxa.Pxa
        # No CSB-18 violation remains, so the diagnostic attaches no note.
        assert case.notes == []

    @pytest.mark.spec("CSB-18-002")
    @pytest.mark.spec("CSB-18-003")
    @pytest.mark.spec("CSB-18-004")
    @pytest.mark.spec("VAM-01-010")
    def test_blocked_gate_invariant_violated_note_posted(self, make_payload):
        """AlwaysFail teardown gate — EM stays ACTIVE beside an adopted P →
        the CASE_MANAGER commits a CSB-18 note (#4829)."""

        populated_dl = _cm_store_with_active_embargo()

        result = _run_at_case_manager(
            populated_dl,
            make_payload(_pxa_report(CS_pxa.Pxa)),
            call_out=StatusAuthorizationCallOutBundle(
                embargo_teardown_authorization_gate_factory=AlwaysFail  # type: ignore[arg-type]
            ),
        )

        assert result.status == Status.SUCCESS, result.feedback_message
        case = populated_dl.read(CASE_ID)
        assert isinstance(case, VulnerabilityCase)
        assert case.current_status.em.state == EM.ACTIVE
        note = assert_case_manager_note_recorded(populated_dl, CASE_ID)
        assert "Cross-machine entailment violated" in note["content"]

    @pytest.mark.spec("CSB-12-004")
    @pytest.mark.spec("CSB-13-004")
    @pytest.mark.spec("CSB-14-005")
    @pytest.mark.spec("CSB-05-010")
    @pytest.mark.spec("CSB-06-010")
    @pytest.mark.parametrize(
        ("reported", "bit"),
        [(CS_pxa.Pxa, "P"), (CS_pxa.pXa, "X"), (CS_pxa.pxA, "A")],
    )
    def test_threat_status_is_committed_before_the_teardown(
        self, make_payload, reported, bit
    ):
        """The adopted P/X/A status precedes the embargo teardown in the
        ledger, so every replica replays the cause before its effect."""
        from vultron.core.behaviors.call_out.bundles.status_authorization import (
            STATUS_AUTHORIZATION_PERMISSIVE,
        )
        from vultron.core.behaviors.embargo.nodes import (
            EMBARGO_TEARDOWN_SEMANTIC_TYPE,
        )
        from vultron.core.models.case_ledger_entry import CaseLedgerEntry

        populated_dl = _cm_store_with_active_embargo()

        result = _run_at_case_manager(
            populated_dl,
            make_payload(_pxa_report(reported)),
            call_out=STATUS_AUTHORIZATION_PERMISSIVE,
        )

        assert result.status == Status.SUCCESS, result.feedback_message
        entries = sorted(
            (
                e
                for e in populated_dl.list_objects("CaseLedgerEntry")
                if isinstance(e, CaseLedgerEntry)
            ),
            key=lambda e: e.log_index,
        )
        threat = next(
            e
            for e in entries
            if e.semantic_type == "add_case_status_to_case"
            and bit in e.payload_snapshot["object"]["pxaState"]
        )
        teardown = next(
            e
            for e in entries
            if e.semantic_type == EMBARGO_TEARDOWN_SEMANTIC_TYPE
        )
        assert threat.log_index < teardown.log_index


class TestReceivedAttacksLeaveThePublicBit:
    """A received CA sets only the attacks bit: observed attacks are not
    public information about the vulnerability (CSB-06, CSB-17-002)."""

    @pytest.mark.spec("CSB-06-001")
    @pytest.mark.executes_as(CASE_MANAGER_ID)
    def test_attacks_with_no_embargo_leave_the_case_non_public(
        self, populated_dl, make_payload
    ):
        result = _run_at_case_manager(
            populated_dl, make_payload(_pxa_report(CS_pxa.pxA))
        )

        assert result.status == Status.SUCCESS, result.feedback_message
        assert _case_pxa(populated_dl) == CS_pxa.pxA

    @pytest.mark.spec("CSB-06-002")
    @pytest.mark.spec("CSB-06-003")
    @pytest.mark.executes_as(CASE_MANAGER_ID)
    @pytest.mark.parametrize("em", [EM.PROPOSED, EM.ACTIVE])
    def test_attacks_under_an_embargo_leave_the_case_non_public(
        self, make_payload, em
    ):
        from vultron.core.behaviors.call_out.bundles.status_authorization import (
            STATUS_AUTHORIZATION_PERMISSIVE,
        )

        dl = _cm_store_with_embargo(em)

        result = _run_at_case_manager(
            dl,
            make_payload(_pxa_report(CS_pxa.pxA)),
            call_out=STATUS_AUTHORIZATION_PERMISSIVE,
        )

        assert result.status == Status.SUCCESS, result.feedback_message
        assert _case_pxa(dl) == CS_pxa.pxA

    @pytest.mark.spec("CSB-06-005")
    @pytest.mark.executes_as(CASE_MANAGER_ID)
    def test_a_duplicate_ca_keeps_the_case_at_pxA(
        self, populated_dl, make_payload
    ):
        _seed_case_pxa(populated_dl, CS_pxa.pxA)

        result = _run_at_case_manager(
            populated_dl, make_payload(_pxa_report(CS_pxa.pxA))
        )

        assert result.status == Status.SUCCESS, result.feedback_message
        assert _case_pxa(populated_dl) == CS_pxa.pxA


# ---------------------------------------------------------------------------
# CSB-01-001 to CSB-03-001: receiving CV, CF and CD
# ---------------------------------------------------------------------------


def _vendor_store() -> SqliteDataLayer:
    """The CASE_MANAGER's store: a vendor and deployer (Case Owner) at RM
    Accepted, and the CASE_MANAGER, seated on one case."""
    from vultron.core.models.participant_status import ParticipantStatus

    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=CASE_MANAGER_ID)
    vendor = as_CaseParticipant(
        id_=PARTICIPANT_ID,
        context=CASE_ID,
        attributed_to=ACTOR_ID,
        case_roles=[CVDRole.CASE_OWNER, CVDRole.VENDOR, CVDRole.DEPLOYER],
    )
    manager = as_CaseParticipant(
        id_=CM_PARTICIPANT_ID,
        context=CASE_ID,
        attributed_to=CASE_MANAGER_ID,
        case_roles=[CVDRole.CASE_MANAGER],
        participant_statuses=[
            ParticipantStatus(
                context=CASE_ID,
                attributed_to=CASE_MANAGER_ID,
                rm=RmDimension(state=RM.ACCEPTED),
            )
        ],
    )
    case = VulnerabilityCase(
        id_=CASE_ID, name="Test Case", attributed_to=CASE_MANAGER_ID
    )
    case.add_participant(vendor)
    case.add_participant(manager)
    dl.create(case)
    dl.create(vendor)
    dl.create(manager)
    return dl


def _statuses(dl: SqliteDataLayer, participant_id: str) -> list:
    participant = dl.read(participant_id)
    assert isinstance(participant, CaseParticipant)
    return participant.participant_statuses


class TestReceiveVendorPathNotices:
    """CV, CF and CD arrive as ``Add(ParticipantStatus)`` (MSM-03-001).

    The receiver records the sender's new state, its own state is unchanged,
    and no CK message is queued: the only outbound activities are the
    ``Announce`` fan-out of the committed entries.
    """

    @pytest.mark.spec("CSB-01-001")
    @pytest.mark.spec("CSB-02-001")
    @pytest.mark.spec("CSB-03-001")
    @pytest.mark.parametrize(
        ("dimensions", "expected"),
        [
            pytest.param(
                {"vf": VfDimension(state=CS_vf.Vf)},
                ("vf", CS_vf.Vf),
                id="CV",
            ),
            pytest.param(
                {"vf": VfDimension(state=CS_vf.VF)},
                ("vf", CS_vf.VF),
                id="CF",
            ),
            pytest.param(
                {"d": DDimension(state=CS_d.D)},
                ("d", CS_d.D),
                id="CD",
            ),
        ],
    )
    def test_updates_sender_model_without_ck(
        self, make_payload, dimensions, expected
    ):
        dl = _vendor_store()
        manager_before = _statuses(dl, CM_PARTICIPANT_ID)
        activity = add_status_to_participant_activity(
            status=as_ParticipantStatus(
                id_=f"{PARTICIPANT_ID}/statuses/vfd",
                context=CASE_ID,
                rm=RmDimension(state=RM.ACCEPTED),
                **dimensions,
            ),
            target=as_CaseParticipant(
                id_=PARTICIPANT_ID, context=CASE_ID, attributed_to=ACTOR_ID
            ),
            actor=ACTOR_ID,
            to=[CASE_MANAGER_ID],
            context=as_VulnerabilityCase(
                attributed_to=CASE_OWNER_ID, id_=CASE_ID, name="Test"
            ),
        )

        result = _run_at_case_manager(dl, make_payload(activity))

        assert result.status == Status.SUCCESS, result.feedback_message
        field, state = expected
        latest = _statuses(dl, PARTICIPANT_ID)[-1]
        assert getattr(latest, field).state == state
        assert _statuses(dl, CM_PARTICIPANT_ID) == manager_before
        outbound = [
            getattr(dl.read(a), "type_", None) for a in dl.outbox_list()
        ]
        assert outbound
        assert all(t == "Announce" for t in outbound), outbound
