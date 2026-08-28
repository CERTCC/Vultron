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

  1. VerifySenderIsParticipantNode             — unknown sender is rejected
  2. AppendParticipantStatusNode               — status appended, RM regression rejected
  StatusAdoptionGate: CheckIsCaseOwnerNode                — CASE_OWNER gospel bypass (RSH-01-002)
  StatusAdoptionGate: StatusAdoptionGate                   — Fallback: bypass or call-out (RSH-01-002)
  StatusAdoptionGate: EmitAddCaseStatusToSelfNode         — self-addressed Add(CaseStatus) (RSH-01-003)

AutoCloseSequence was removed per ADR-0050: canonical RM closure is routed
through the Leave(VulnerabilityCase) receive path in receive_close_case_tree.

Per specs/multi-actor-demo.yaml DEMOMA-07-003, DEMOMA-07-005.
Per specs/received-status-handling.yaml RSH-01-001 to RSH-01-004.
"""

import py_trees
import pytest
from py_trees.common import Status

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driven.trigger_activity_adapter import (
    TriggerActivityAdapter,
)
from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.call_out.bundles.status_authorization import (
    STATUS_AUTHORIZATION_DETERMINISTIC,
    StatusAuthorizationCallOutBundle,
)
from vultron.core.behaviors.call_out.nodes import AlwaysFail
from vultron.core.behaviors.case.nodes.vfd_role_guards import (
    CheckIsCaseOwnerNode,
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
    EmitAddCaseStatusToSelfNode,
    EmitRMGapNoteNode,
    LoadParticipantNode,
    PublicDisclosureBranchNode,
    ResolveAndPersistStatusObjectNode,
    ValidateRMTransitionNode,
    VerifySenderIsParticipantNode,
)
from vultron.core.behaviors.status.nodes.dimension_filter import BB_RM_ANOMALY
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
    @pytest.mark.executes_as(CASE_MANAGER_ID)
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

    @pytest.mark.executes_as(CASE_MANAGER_ID)
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

    @pytest.mark.executes_as(CASE_MANAGER_ID)
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

    @pytest.mark.spec("RSH-06-001")
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
    @pytest.mark.executes_as(CASE_MANAGER_ID)
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

    @pytest.mark.executes_as(CASE_MANAGER_ID)
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

    @pytest.mark.executes_as(CASE_MANAGER_ID)
    def test_skips_when_sender_is_not_case_owner(
        self, populated_dl, populated_bridge, status_obj
    ):
        """CASE_MANAGER sender (not CASE_OWNER) → skips teardown, SUCCESS."""
        from vultron.core.states.cs import CS_pxa
        from vultron.wire.as2.vocab.objects.case_status import as_CaseStatus

        # ``context`` is required by core CaseStatus; omitting it made the
        # nested status unprojectable to the core shape (#2232).
        cs = as_CaseStatus(context=CASE_ID)
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

    @pytest.mark.executes_as(CASE_MANAGER_ID)
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

        # ``context`` is required by core CaseStatus; omitting it made the
        # nested status unprojectable to the core shape (#2232).
        cs = as_CaseStatus(context=CASE_ID)
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
            rm_state=RM.CLOSED,
        )
        closed_cm = as_ParticipantStatus(
            id_=f"{CM_PARTICIPANT_ID}/statuses/closed",
            context=CASE_ID,
            rm_state=RM.CLOSED,
        )
        populated_dl.create(closed_vendor)
        populated_dl.create(closed_cm)
        participant.participant_statuses.append(closed_vendor)
        populated_dl.save(participant)
        case_manager_participant.participant_statuses.append(closed_cm)
        populated_dl.save(case_manager_participant)

        bridge = BTBridge(datalayer=populated_dl)
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
            rm_state=RM.CLOSED,
        )
        populated_dl.create(closed_vendor)
        participant.participant_statuses.append(closed_vendor)
        populated_dl.save(participant)

        bridge = BTBridge(datalayer=populated_dl)
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

        bridge = BTBridge(datalayer=populated_dl)
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

        bridge = BTBridge(datalayer=populated_dl)
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
        )

    @pytest.mark.spec("RSH-01-001")
    @pytest.mark.spec("RSH-01-003")
    def test_full_tree_succeeds_for_case_owner_sender(
        self,
        populated_dl,
        make_payload,
    ):
        """End-to-end: CASE_OWNER sender bypasses StatusAdoptionGate → status
        appended, self-addressed Add(CaseStatus) queued (RSH-01-001 to RSH-01-003).

        Uses a ParticipantStatus with an embedded CaseStatus so
        EmitAddCaseStatusToSelfNode can construct the outbound activity.
        Runs with actor_id=ACTOR_ID (not CASE_MANAGER) to skip the
        guarded ledger-commit subtree.
        """
        from vultron.wire.as2.vocab.objects.case_status import as_CaseStatus

        cs = as_CaseStatus(id_=f"{STATUS_ID}/cs", context=CASE_ID)
        status_with_cs = as_ParticipantStatus(
            id_=STATUS_ID,
            context=CASE_ID,
            case_status=cs,
        )
        populated_dl.save(status_with_cs)

        activity = add_status_to_participant_activity(
            status=status_with_cs,
            target=as_CaseParticipant(
                id_=PARTICIPANT_ID, context=CASE_ID, attributed_to=ACTOR_ID
            ),
            actor=ACTOR_ID,
            context=as_VulnerabilityCase(id_=CASE_ID, name="Test"),
        )
        event = make_payload(activity)
        bridge = self._bridge_with_factory(populated_dl)
        tree = add_participant_status_tree(request=event, case_id=CASE_ID)
        # actor_id=ACTOR_ID → not CASE_MANAGER → ledger commit is skipped
        result = bridge.execute_with_setup(tree=tree, actor_id=ACTOR_ID)
        assert result.status == Status.SUCCESS

        p = populated_dl.read(PARTICIPANT_ID)
        assert p is not None
        status_ids = [getattr(s, "id_", s) for s in p.participant_statuses]
        assert STATUS_ID in status_ids

        # RSH-01-003: self-addressed Add(CaseStatus) must be queued in outbox
        outbox = populated_dl.outbox_list()
        assert (
            len(outbox) > 0
        ), "EmitAddCaseStatusToSelfNode must queue Add(CaseStatus)"

    @pytest.mark.executes_as(OUTSIDER_ID)
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
        bridge = self._bridge_with_factory(populated_dl)
        tree = add_participant_status_tree(request=event, case_id=CASE_ID)
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

        Uses CASE_MANAGER_ID as the sender (not CASE_OWNER) so CheckIsCaseOwnerNode
        returns FAILURE, routing to the AlwaysFail call-out which also fails.
        Executes as ACTOR_ID (vendor) to skip the guarded ledger-commit subtree.
        """
        bridge = self._bridge_with_factory(populated_dl)
        reject_bundle = StatusAuthorizationCallOutBundle(
            status_adoption_gate_factory=lambda name: AlwaysFail(name)  # type: ignore[arg-type]
        )
        cm_status_id = f"{STATUS_ID}/cm"
        cm_status = as_ParticipantStatus(id_=cm_status_id, context=CASE_ID)
        populated_dl.create(cm_status)
        # CASE_MANAGER_ID is NOT CASE_OWNER — CheckIsCaseOwnerNode will return FAILURE
        cm_activity = add_status_to_participant_activity(
            status=as_ParticipantStatus(id_=cm_status_id, context=CASE_ID),
            target=as_CaseParticipant(
                id_=CM_PARTICIPANT_ID,
                context=CASE_ID,
                attributed_to=CASE_MANAGER_ID,
            ),
            actor=CASE_MANAGER_ID,
            context=as_VulnerabilityCase(id_=CASE_ID, name="Test"),
        )
        cm_event = make_payload(cm_activity)
        cm_tree = add_participant_status_tree(
            request=cm_event,
            case_id=CASE_ID,
            call_out=reject_bundle,
        )
        # Execute as the vendor (ACTOR_ID) — not CASE_MANAGER → ledger commit skipped
        result = bridge.execute_with_setup(tree=cm_tree, actor_id=ACTOR_ID)
        assert result.status == Status.FAILURE
        # Outbox must be empty: guard blocked before EmitAddCaseStatusToSelfNode
        outbox = populated_dl.outbox_list()
        assert (
            len(outbox) == 0
        ), "StatusAdoptionGate denied — no Add(CaseStatus) must be in outbox"

    @pytest.mark.spec("RSH-01-004")
    @pytest.mark.spec("RSH-03-003")
    def test_no_side_effects_execute_directly_rsh_01_004(
        self,
        populated_dl,
        make_payload,
    ):
        """add_participant_status_tree must NOT execute embargo teardown
        directly (RSH-01-004).  After SUCCESS the tree has no PublicDisclosureBranchNode
        in its children."""
        activity = add_status_to_participant_activity(
            status=as_ParticipantStatus(id_=STATUS_ID, context=CASE_ID),
            target=as_CaseParticipant(
                id_=PARTICIPANT_ID, context=CASE_ID, attributed_to=ACTOR_ID
            ),
            actor=ACTOR_ID,
            context=as_VulnerabilityCase(id_=CASE_ID, name="Test"),
        )
        event = make_payload(activity)
        tree = add_participant_status_tree(request=event, case_id=CASE_ID)

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
            "(RSH-01-004: side-effects belong in add_case_status_tree)"
        )

    @pytest.mark.spec("RSH-01-001")
    @pytest.mark.spec("RSH-01-002")
    def test_emit_node_present_rsh_01_001(
        self,
        populated_dl,
        make_payload,
    ):
        """EmitAddCaseStatusToSelfNode and StatusAdoptionGate must be present
        in the tree (RSH-01-001)."""
        activity = add_status_to_participant_activity(
            status=as_ParticipantStatus(id_=STATUS_ID, context=CASE_ID),
            target=as_CaseParticipant(
                id_=PARTICIPANT_ID, context=CASE_ID, attributed_to=ACTOR_ID
            ),
            actor=ACTOR_ID,
            context=as_VulnerabilityCase(id_=CASE_ID, name="Test"),
        )
        event = make_payload(activity)
        tree = add_participant_status_tree(request=event, case_id=CASE_ID)

        def _collect_nodes(node: py_trees.behaviour.Behaviour) -> list:
            result_inner = [node]
            for child in getattr(node, "children", []):
                result_inner.extend(_collect_nodes(child))
            return result_inner

        all_nodes = _collect_nodes(tree)
        node_names = [n.name for n in all_nodes]

        assert (
            "EmitAddCaseStatusToSelf" in node_names
        ), "EmitAddCaseStatusToSelfNode must be present (RSH-01-001)"
        assert (
            "StatusAdoptionGate" in node_names
        ), "StatusAdoptionGate must be present (RSH-01-001)"
        assert (
            "CheckIsCaseOwner" in node_names
        ), "CheckIsCaseOwnerNode must be present inside StatusAdoptionGate (RSH-01-002)"


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
            context=as_VulnerabilityCase(id_=CASE_ID, name="Test"),
        )
        event = make_payload(activity)
        tree = add_participant_status_tree(request=event, case_id=CASE_ID)
        all_nodes = self._all_nodes(tree)
        node_names = [n.name for n in all_nodes]
        assert (
            "AutoCloseSequence" not in node_names
        ), "AutoCloseSequence must be removed per ADR-0050"
        assert (
            "AutoCloseIfCaseManager" not in node_names
        ), "AutoCloseIfCaseManager must be removed per ADR-0050"

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
            context=as_VulnerabilityCase(id_=CASE_ID, name="Test"),
        )
        event = make_payload(activity)
        tree = add_participant_status_tree(request=event, case_id=CASE_ID)
        all_nodes = self._all_nodes(tree)
        assert not any(
            isinstance(n, EmitCloseCaseNode) for n in all_nodes
        ), "EmitCloseCaseNode must not be in add_participant_status_tree (ADR-0050)"


# ---------------------------------------------------------------------------
# StatusAdoptionGate: CheckIsCaseOwnerNode (RSH-01-002)
# ---------------------------------------------------------------------------


class TestCheckIsCaseOwnerNode:
    @pytest.mark.spec("RSH-01-002")
    @pytest.mark.executes_as(CASE_MANAGER_ID)
    def test_case_owner_returns_success(self, populated_bridge):
        """CASE_OWNER sender → SUCCESS (gospel bypass)."""
        node = CheckIsCaseOwnerNode(
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
        node = CheckIsCaseOwnerNode(
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
        node = CheckIsCaseOwnerNode(
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
        node = CheckIsCaseOwnerNode(
            sender_actor_id=ACTOR_ID,
            case_id="https://example.org/cases/nonexistent",
        )
        result = bridge.execute_with_setup(tree=node, actor_id=CASE_MANAGER_ID)
        assert result.status == Status.FAILURE

    @pytest.mark.executes_as(CASE_MANAGER_ID)
    def test_no_case_id_returns_failure(self, bridge):
        """No case_id at all → FAILURE."""
        node = CheckIsCaseOwnerNode(
            sender_actor_id=ACTOR_ID,
            case_id=None,
        )
        result = bridge.execute_with_setup(tree=node, actor_id=CASE_MANAGER_ID)
        assert result.status == Status.FAILURE


# ---------------------------------------------------------------------------
# StatusAdoptionGate: EmitAddCaseStatusToSelfNode (RSH-01-003)
# ---------------------------------------------------------------------------


class TestEmitAddCaseStatusToSelfNode:
    def _bridge_with_factory(self, dl: SqliteDataLayer) -> BTBridge:
        return BTBridge(
            datalayer=dl,
            trigger_activity=TriggerActivityAdapter(dl),
        )

    @pytest.mark.spec("RSH-01-003")
    @pytest.mark.executes_as(CASE_MANAGER_ID)
    def test_emits_activity_and_queues_in_outbox(self, dl):
        """With a factory and embedded case_status: activity queued in outbox."""
        from vultron.wire.as2.vocab.objects.case_status import as_CaseStatus

        cs = as_CaseStatus(id_=f"{STATUS_ID}/cs", context=CASE_ID)
        status_with_cs = as_ParticipantStatus(
            id_=f"{STATUS_ID}/with-cs",
            context=CASE_ID,
            case_status=cs,
        )
        case = as_VulnerabilityCase(id_=CASE_ID, name="Test")
        dl.create(case)
        dl.create(status_with_cs)

        bridge = self._bridge_with_factory(dl)
        node = EmitAddCaseStatusToSelfNode(
            participant_status_id=status_with_cs.id_,
            case_id=CASE_ID,
        )
        result = bridge.execute_with_setup(tree=node, actor_id=CASE_MANAGER_ID)
        assert result.status == Status.SUCCESS

        outbox = dl.outbox_list()
        assert len(outbox) > 0, "Activity should be queued in outbox"

    @pytest.mark.executes_as(CASE_MANAGER_ID)
    def test_fails_without_factory(self, populated_bridge):
        """No TriggerActivityPort → FAILURE (BT-14-001)."""
        node = EmitAddCaseStatusToSelfNode(
            participant_status_id=STATUS_ID,
            case_id=CASE_ID,
        )
        result = populated_bridge.execute_with_setup(
            tree=node, actor_id=CASE_MANAGER_ID
        )
        assert result.status == Status.FAILURE

    @pytest.mark.executes_as(CASE_MANAGER_ID)
    def test_fails_when_participant_status_id_empty(self, populated_dl):
        """Empty participant_status_id → FAILURE."""
        bridge = self._bridge_with_factory(populated_dl)
        node = EmitAddCaseStatusToSelfNode(
            participant_status_id="", case_id=CASE_ID
        )
        result = bridge.execute_with_setup(tree=node, actor_id=CASE_MANAGER_ID)
        assert result.status == Status.FAILURE

    @pytest.mark.executes_as(CASE_MANAGER_ID)
    def test_fails_when_case_id_none(self, populated_dl):
        """None case_id → FAILURE."""
        bridge = self._bridge_with_factory(populated_dl)
        node = EmitAddCaseStatusToSelfNode(
            participant_status_id=STATUS_ID, case_id=None
        )
        result = bridge.execute_with_setup(tree=node, actor_id=CASE_MANAGER_ID)
        assert result.status == Status.FAILURE

    @pytest.mark.executes_as(CASE_MANAGER_ID)
    def test_returns_success_when_status_has_no_case_status(
        self, populated_dl
    ):
        """ParticipantStatus with no embedded case_status → SUCCESS (soft skip).

        No canonical update to emit; the Sequence must continue to
        AutoCloseIfCaseManager (DEMOMA-07-003 step 5), so the node returns
        SUCCESS rather than blocking the sequence with FAILURE.
        """
        bridge = self._bridge_with_factory(populated_dl)
        # STATUS_ID in the fixture has no embedded case_status
        node = EmitAddCaseStatusToSelfNode(
            participant_status_id=STATUS_ID, case_id=CASE_ID
        )
        result = bridge.execute_with_setup(tree=node, actor_id=CASE_MANAGER_ID)
        assert result.status == Status.SUCCESS


# ---------------------------------------------------------------------------
# StatusAdoptionGate: StatusAuthorizationCallOutBundle (RSH-01-002)
# ---------------------------------------------------------------------------


class TestStatusAuthorizationCallOutBundle:
    @pytest.mark.executes_as(CASE_MANAGER_ID)
    def test_deterministic_singleton_approves_by_default(
        self, populated_bridge
    ):
        """STATUS_AUTHORIZATION_DETERMINISTIC has AlwaysSucceed factory."""
        node = STATUS_AUTHORIZATION_DETERMINISTIC.status_adoption_gate_factory(
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
            status_adoption_gate_factory=lambda name: AlwaysFail(name)  # type: ignore[arg-type]
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
    divergence for a participant at RM.CLOSED whose update was partially
    accepted (vfd or other dimension advanced).

    The fix is validate_rm=False in add_participant_status_tree, delegating
    rm adjudication entirely to FilterParticipantStatusDimensionsNode
    (precondition guard).  The _rm_was_carried_forward() workaround was
    removed; this test proves it is not needed.
    """

    def _bridge_with_factory(self, dl: SqliteDataLayer) -> BTBridge:
        return BTBridge(
            datalayer=dl,
            trigger_activity=TriggerActivityAdapter(dl),
        )

    @pytest.mark.spec("CLP-10-009")
    def test_partial_accept_with_closed_rm_succeeds_and_produces_ledger_entry(
        self, make_payload
    ):
        """Participant is RM.CLOSED; incoming status advances vfd but asserts
        a backwards rm (VALID ≺ CLOSED).

        FilterParticipantStatusDimensionsNode refuses rm and carries CLOSED
        forward; vfd advance is accepted (partial accept → SUCCESS).
        GuardedCommit fires and produces one CaseLedgerEntry.
        ValidateRMTransitionNode is SKIPPED (validate_rm=False), so the
        carried-forward CLOSED rm no longer causes a post-commit FAILURE.

        This test FAILS on pre-fix code where ValidateRMTransitionNode ran
        after GuardedCommit and the _rm_was_carried_forward() workaround had
        been removed (demonstrating the latent divergence risk).
        """
        from vultron.core.models.case_ledger_entry import CaseLedgerEntry
        from vultron.core.states.cs import CS_vfd
        from vultron.enums.roles import CVDRole

        # The tree runs as the case manager, so this is the case manager's
        # own store (BT-05-005, ADR-0073).
        dl = SqliteDataLayer("sqlite:///:memory:", actor_id=CASE_MANAGER_ID)
        cm_participant = as_CaseParticipant(
            id_=CM_PARTICIPANT_ID,
            context=CASE_ID,
            attributed_to=CASE_MANAGER_ID,
            case_roles=[CVDRole.CASE_MANAGER],
        )
        # attributed_to seeds the per-case genesis hash (CLP-08-003)
        case = as_VulnerabilityCase(
            id_=CASE_ID, name="Fix1 Regression", attributed_to=CASE_MANAGER_ID
        )
        case.add_participant(cm_participant)

        existing_status = as_ParticipantStatus(
            id_=f"{STATUS_ID}/existing",
            context=CASE_ID,
            rm_state=RM.CLOSED,
            vfd_state=CS_vfd.vfd,
        )
        vendor_participant = as_CaseParticipant(
            id_=PARTICIPANT_ID,
            context=CASE_ID,
            attributed_to=ACTOR_ID,
            case_roles=[CVDRole.CASE_OWNER],
        )
        vendor_participant.participant_statuses.append(existing_status)
        case.add_participant(vendor_participant)

        dl.create(case)
        dl.create(cm_participant)
        dl.create(vendor_participant)
        dl.create(existing_status)

        # Incoming status: rm=VALID (backwards from CLOSED), vfd advances to Vfd
        incoming_status = as_ParticipantStatus(
            id_=STATUS_ID,
            context=CASE_ID,
            rm_state=RM.VALID,
            vfd_state=CS_vfd.Vfd,
        )
        dl.create(incoming_status)

        activity = add_status_to_participant_activity(
            status=incoming_status,
            target=vendor_participant,
            actor=ACTOR_ID,
            context=as_VulnerabilityCase(id_=CASE_ID, name="Fix1 Regression"),
        )
        event = make_payload(activity).model_copy(
            update={"activity": activity}
        )

        bridge = self._bridge_with_factory(dl)
        tree = add_participant_status_tree(request=event, case_id=CASE_ID)
        result = bridge.execute_with_setup(
            tree=tree, actor_id=CASE_MANAGER_ID, activity=event
        )
        assert result.status == Status.SUCCESS, (
            "Partial accept (rm refused, vfd accepted) must succeed — "
            "ValidateRMTransitionNode must NOT abort after GuardedCommit (CLP-10-009)"
        )

        entries = [
            e
            for e in dl.list_objects("CaseLedgerEntry")
            if isinstance(e, CaseLedgerEntry)
        ]
        assert len(entries) == 1, (
            "One CaseLedgerEntry must be committed for the partial accept "
            "(rm refused → carried forward, vfd accepted)"
        )

    @pytest.mark.spec("CLP-10-009")
    def test_fully_rejected_update_produces_no_ledger_entry(
        self, make_payload
    ):
        """All dimensions refused by FilterParticipantStatusDimensionsNode →
        FAILURE before GuardedCommit → zero CaseLedgerEntries (CLP-10-009).
        """
        from vultron.core.models.case_ledger_entry import CaseLedgerEntry
        from vultron.core.states.cs import CS_vfd
        from vultron.enums.roles import CVDRole

        # The tree runs as the case manager, so this is the case manager's
        # own store (BT-05-005, ADR-0073).
        dl = SqliteDataLayer("sqlite:///:memory:", actor_id=CASE_MANAGER_ID)
        cm_participant = as_CaseParticipant(
            id_=CM_PARTICIPANT_ID,
            context=CASE_ID,
            attributed_to=CASE_MANAGER_ID,
            case_roles=[CVDRole.CASE_MANAGER],
        )
        # attributed_to seeds the per-case genesis hash (CLP-08-003)
        case = as_VulnerabilityCase(
            id_=CASE_ID, name="Fix1 Full Reject", attributed_to=CASE_MANAGER_ID
        )
        case.add_participant(cm_participant)

        existing_status = as_ParticipantStatus(
            id_=f"{STATUS_ID}/existing",
            context=CASE_ID,
            rm_state=RM.CLOSED,
            vfd_state=CS_vfd.Vfd,
        )
        vendor_participant = as_CaseParticipant(
            id_=PARTICIPANT_ID,
            context=CASE_ID,
            attributed_to=ACTOR_ID,
            case_roles=[CVDRole.CASE_OWNER],
        )
        vendor_participant.participant_statuses.append(existing_status)
        case.add_participant(vendor_participant)

        dl.create(case)
        dl.create(cm_participant)
        dl.create(vendor_participant)
        dl.create(existing_status)

        # Incoming status: rm backwards AND vfd backwards → all dimensions refused
        incoming_status = as_ParticipantStatus(
            id_=STATUS_ID,
            context=CASE_ID,
            rm_state=RM.VALID,
            vfd_state=CS_vfd.vfd,
        )
        dl.create(incoming_status)

        activity = add_status_to_participant_activity(
            status=incoming_status,
            target=vendor_participant,
            actor=ACTOR_ID,
            context=as_VulnerabilityCase(id_=CASE_ID, name="Fix1 Full Reject"),
        )
        event = make_payload(activity)

        bridge = self._bridge_with_factory(dl)
        tree = add_participant_status_tree(request=event, case_id=CASE_ID)
        result = bridge.execute_with_setup(
            tree=tree, actor_id=CASE_MANAGER_ID, activity=event
        )
        assert (
            result.status == Status.FAILURE
        ), "A fully rejected update must fail before GuardedCommit"

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
    """EmitRMGapNoteNode emits Add(Note,Case) on RM anomaly (RSH-06-004).

    Every test here runs the node as the case manager, so ``dl`` — and the
    ``populated_dl`` built on it — must be the *case manager's* store: a BT's
    store follows its executing actor (BT-05-005, ADR-0073), and the node
    enqueues to whichever store it was handed.
    """

    def _bridge_with_factory(self, dl: SqliteDataLayer) -> BTBridge:
        return BTBridge(
            datalayer=dl,
            trigger_activity=TriggerActivityAdapter(dl),
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
    def test_gap_anomaly_emits_note(self, populated_dl):
        """BB_RM_ANOMALY=gap → SUCCESS + Add(Note,Case) queued (RSH-06-004)."""
        bridge = self._bridge_with_factory(populated_dl)
        node = EmitRMGapNoteNode(
            sender_actor_id=ACTOR_ID,
            case_id=CASE_ID,
        )
        # Pre-populate anomaly flag as if FilterParticipantStatusDimensionsNode ran
        self._set_anomaly("gap", RM.RECEIVED, RM.ACCEPTED)

        result = bridge.execute_with_setup(tree=node, actor_id=CASE_MANAGER_ID)
        assert result.status == Status.SUCCESS

        outbox = populated_dl.outbox_list()
        assert (
            len(outbox) == 1
        ), "Gap anomaly should emit exactly one Add(Note,Case)"

    @pytest.mark.spec("RSH-06-004")
    def test_regression_anomaly_emits_note(self, populated_dl):
        """BB_RM_ANOMALY=regression → SUCCESS + Add(Note,Case) queued (RSH-06-004)."""
        bridge = self._bridge_with_factory(populated_dl)
        node = EmitRMGapNoteNode(
            sender_actor_id=ACTOR_ID,
            case_id=CASE_ID,
        )
        self._set_anomaly("regression", RM.ACCEPTED, RM.RECEIVED)

        result = bridge.execute_with_setup(tree=node, actor_id=CASE_MANAGER_ID)
        assert result.status == Status.SUCCESS

        outbox = populated_dl.outbox_list()
        assert (
            len(outbox) == 1
        ), "Regression anomaly should emit exactly one Add(Note,Case)"

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
