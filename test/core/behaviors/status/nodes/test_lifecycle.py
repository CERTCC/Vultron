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

"""Unit tests for case lifecycle trigger nodes.

Tests PublicDisclosureBranchNode and EmitCloseCaseNode
from nodes.lifecycle.

Per DEMOMA-07-003 steps 4–5.
"""

import pytest
import py_trees
from py_trees.common import Status
from unittest.mock import MagicMock

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.status.nodes.lifecycle import (
    EmitCloseCaseNode,
    PublicDisclosureBranchNode,
    _PublicDisclosureSkipConditionNode,
)
from vultron.core.states.cs import CS_pxa
from vultron.core.states.em import EM
from vultron.enums.roles import CVDRole
from vultron.wire.as2.vocab.objects.case_participant import as_CaseParticipant
from vultron.wire.as2.vocab.objects.case_status import (
    as_CaseStatus,
    as_ParticipantStatus,
)
from vultron.wire.as2.vocab.objects.embargo_event import as_EmbargoEvent
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)

ACTOR_ID = "https://example.org/actors/vendor"
CASE_MANAGER_ID = "https://example.org/actors/case-actor"
CASE_ID = "https://example.org/cases/case-01"
PARTICIPANT_ID = "https://example.org/cases/case-01/participants/vendor"
CM_PARTICIPANT_ID = "https://example.org/cases/case-01/participants/case-actor"
STATUS_ID = "https://example.org/cases/case-01/statuses/s1"
EMBARGO_ID = "https://example.org/cases/case-01/embargo_events/e1"


@pytest.fixture(autouse=True)
def clear_blackboard():
    py_trees.blackboard.Blackboard.storage.clear()


@pytest.fixture
def dl():
    # ACTOR_ID's own store: the trees in this module execute as ACTOR_ID, and a
    # BT's store follows its executing actor (ADR-0066). CASE_MANAGER_ID appears
    # here as a *role holder named in the case*, not as the store's owner.
    return SqliteDataLayer("sqlite:///:memory:", actor_id=ACTOR_ID)


@pytest.fixture
def participant():
    return as_CaseParticipant(
        id_=PARTICIPANT_ID,
        context=CASE_ID,
        attributed_to=ACTOR_ID,
        case_roles=[CVDRole.CASE_OWNER],
    )


@pytest.fixture
def status_obj():
    return as_ParticipantStatus(id_=STATUS_ID, context=CASE_ID)


@pytest.fixture
def public_aware_status():
    """ParticipantStatus with CS.P set (CS_pxa.Pxa = public-aware)."""
    return as_ParticipantStatus(
        id_=STATUS_ID,
        context=CASE_ID,
        case_status=as_CaseStatus(pxa_state=CS_pxa.Pxa),
    )


@pytest.fixture
def embargo():
    return as_EmbargoEvent(id_=EMBARGO_ID, context=CASE_ID)


@pytest.fixture
def populated_dl(dl, participant, status_obj):
    case_manager_participant = as_CaseParticipant(
        id_=CM_PARTICIPANT_ID,
        context=CASE_ID,
        attributed_to=CASE_MANAGER_ID,
        case_roles=[CVDRole.CASE_MANAGER],
    )
    case = as_VulnerabilityCase(id_=CASE_ID, name="Test Case")
    case.add_participant(participant)
    case.add_participant(case_manager_participant)
    dl.create(case)
    dl.create(participant)
    dl.create(case_manager_participant)
    dl.create(status_obj)
    return dl


@pytest.fixture
def populated_bridge(populated_dl):
    return BTBridge(datalayer=populated_dl)


def _make_dl_with_em_state(
    em_state: EM,
    *,
    with_embargo: bool = False,
    with_proposed_embargo: bool = False,
    with_active_embargo: bool = False,
) -> SqliteDataLayer:
    """Return a populated SqliteDataLayer for skip-condition unit tests."""
    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=ACTOR_ID)
    case = as_VulnerabilityCase(id_=CASE_ID, name="Test Case")
    case.current_status.em_state = em_state

    if with_proposed_embargo or with_embargo:
        embargo = as_EmbargoEvent(id_=EMBARGO_ID, context=CASE_ID)
        case.proposed_embargoes = [embargo.id_]
        dl.create(embargo)

    if with_active_embargo or with_embargo:
        embargo = as_EmbargoEvent(id_=EMBARGO_ID, context=CASE_ID)
        case.active_embargo = embargo.id_
        try:
            dl.create(embargo)
        except Exception:
            pass

    participant = as_CaseParticipant(
        id_=PARTICIPANT_ID,
        context=CASE_ID,
        attributed_to=ACTOR_ID,
        case_roles=[CVDRole.CASE_OWNER],
    )
    case.add_participant(participant)
    dl.create(case)
    dl.create(participant)
    return dl


# ---------------------------------------------------------------------------
# _PublicDisclosureSkipConditionNode — unit tests (AC-4, EMB-16-001)
# ---------------------------------------------------------------------------


class TestPublicDisclosureSkipConditionNode:
    """Unit tests for _PublicDisclosureSkipConditionNode.

    Per EMB-16-001: teardown (FAILURE = proceed) must fire for EM PROPOSED,
    ACTIVE, and REVISE.  For EM NONE/EXITED or non-public-aware status the
    node must skip (SUCCESS).
    """

    def _make_bridge_and_node(
        self, dl: SqliteDataLayer, status_obj: as_ParticipantStatus
    ) -> tuple[BTBridge, _PublicDisclosureSkipConditionNode]:
        bridge = BTBridge(datalayer=dl)
        node = _PublicDisclosureSkipConditionNode(
            status_obj=status_obj,
            sender_actor_id=ACTOR_ID,
            case_id=CASE_ID,
        )
        return bridge, node

    # AC-4 case 1: PROPOSED + public-aware PXA → FAILURE (do not skip)
    def test_proposed_em_public_aware_returns_failure(
        self, public_aware_status
    ):
        """EM PROPOSED + CS.P set → skip-condition returns FAILURE (EMB-16-001).

        Spec: EMB-16-001 — when CASE_OWNER sends public-aware status while
        EM is PROPOSED the BT must route to reject_proposed_embargo_bt.
        """
        dl = _make_dl_with_em_state(EM.PROPOSED, with_proposed_embargo=True)
        bridge, node = self._make_bridge_and_node(dl, public_aware_status)
        result = bridge.execute_with_setup(tree=node, actor_id=ACTOR_ID)
        assert result.status == Status.FAILURE

    # AC-4 case 2: ACTIVE + public-aware PXA → FAILURE (do not skip)
    def test_active_em_public_aware_returns_failure(self, public_aware_status):
        """EM ACTIVE + CS.P set → skip-condition returns FAILURE (EMB-16-001)."""
        dl = _make_dl_with_em_state(EM.ACTIVE, with_active_embargo=True)
        bridge, node = self._make_bridge_and_node(dl, public_aware_status)
        result = bridge.execute_with_setup(tree=node, actor_id=ACTOR_ID)
        assert result.status == Status.FAILURE

    # AC-4 case 2b: REVISE + public-aware PXA → FAILURE (do not skip)
    def test_revise_em_public_aware_returns_failure(self, public_aware_status):
        """EM REVISE + CS.P set → skip-condition returns FAILURE (EMB-16-001)."""
        dl = _make_dl_with_em_state(EM.REVISE, with_active_embargo=True)
        bridge, node = self._make_bridge_and_node(dl, public_aware_status)
        result = bridge.execute_with_setup(tree=node, actor_id=ACTOR_ID)
        assert result.status == Status.FAILURE

    # AC-4 case 3: NONE + public-aware PXA → SUCCESS (skip; nothing to tear down)
    def test_none_em_public_aware_returns_success(self, public_aware_status):
        """EM NONE + CS.P set → skip-condition returns SUCCESS (nothing to tear down)."""
        dl = _make_dl_with_em_state(EM.NONE)
        bridge, node = self._make_bridge_and_node(dl, public_aware_status)
        result = bridge.execute_with_setup(tree=node, actor_id=ACTOR_ID)
        assert result.status == Status.SUCCESS

    # AC-4 case 3b: EXITED + public-aware PXA → SUCCESS (skip; embargo already gone)
    def test_exited_em_public_aware_returns_success(self, public_aware_status):
        """EM EXITED + CS.P set → skip-condition returns SUCCESS (nothing to tear down)."""
        dl = _make_dl_with_em_state(EM.EXITED)
        bridge, node = self._make_bridge_and_node(dl, public_aware_status)
        result = bridge.execute_with_setup(tree=node, actor_id=ACTOR_ID)
        assert result.status == Status.SUCCESS

    # AC-4 case 4: non-public-aware status → SUCCESS (skip regardless of EM)
    def test_non_public_aware_status_always_returns_success(
        self, status_obj, populated_bridge
    ):
        """Non-public-aware status → skip regardless of EM state."""
        node = _PublicDisclosureSkipConditionNode(
            status_obj=status_obj,
            sender_actor_id=ACTOR_ID,
            case_id=CASE_ID,
        )
        result = populated_bridge.execute_with_setup(
            tree=node, actor_id=ACTOR_ID
        )
        assert result.status == Status.SUCCESS


# ---------------------------------------------------------------------------
# PublicDisclosureBranchNode — integration tests (AC-5, EMB-16-001)
# ---------------------------------------------------------------------------


class TestPublicDisclosureBranchNodeProposedEmPath:
    """Integration tests: CS.P/X/A fires while EM is PROPOSED.

    Per EMB-16-001 the BranchNode must route to reject_proposed_embargo_bt
    (not terminate_embargo_bt), transitioning EM from PROPOSED to NONE and
    queuing an ER reject activity to the Case Manager.
    """

    def _setup(
        self,
        public_aware_status: as_ParticipantStatus,
        *,
        reject_activity_id: str = "https://example.org/activities/reject-01",
    ) -> tuple[SqliteDataLayer, BTBridge, PublicDisclosureBranchNode]:
        dl = SqliteDataLayer("sqlite:///:memory:", actor_id=ACTOR_ID)

        embargo = as_EmbargoEvent(id_=EMBARGO_ID, context=CASE_ID)
        case = as_VulnerabilityCase(id_=CASE_ID, name="Test Case")
        case.attributed_to = (
            ACTOR_ID  # required by EmbargoLifecycle.is_owner check
        )
        case.current_status.em_state = EM.PROPOSED
        case.proposed_embargoes = [embargo.id_]

        participant = as_CaseParticipant(
            id_=PARTICIPANT_ID,
            context=CASE_ID,
            attributed_to=ACTOR_ID,
            case_roles=[CVDRole.CASE_OWNER],
        )
        cm_participant = as_CaseParticipant(
            id_=CM_PARTICIPANT_ID,
            context=CASE_ID,
            attributed_to=CASE_MANAGER_ID,
            case_roles=[CVDRole.CASE_MANAGER],
        )
        case.add_participant(participant)
        case.add_participant(cm_participant)
        dl.create(embargo)
        dl.create(case)
        dl.create(participant)
        dl.create(cm_participant)

        factory = MagicMock()
        factory.reject_embargo.return_value = (reject_activity_id, {})

        bridge = BTBridge(datalayer=dl, trigger_activity=factory)
        node = PublicDisclosureBranchNode(
            status_obj=public_aware_status,
            sender_actor_id=ACTOR_ID,
            case_id=CASE_ID,
        )
        return dl, bridge, node

    # AC-5: full integration — EM PROPOSED + P fires → EM→NONE + ER queued
    def test_proposed_em_pxa_routes_to_reject_path_and_succeeds(
        self, public_aware_status
    ):
        """EM PROPOSED + CS.P → BranchNode succeeds; EM transitions to NONE.

        Per EMB-16-001: reject_proposed_embargo_bt arm must execute, driving
        EM PROPOSED → NO_EMBARGO via reject_embargo_invite().
        """
        reject_id = "https://example.org/activities/reject-01"
        dl, bridge, node = self._setup(
            public_aware_status, reject_activity_id=reject_id
        )
        result = bridge.execute_with_setup(tree=node, actor_id=ACTOR_ID)
        assert result.status == Status.SUCCESS

        # AC-5: EM must have transitioned to NONE after the BT ran
        from vultron.core.models.case import VulnerabilityCase

        updated_case = dl.read(CASE_ID)
        assert isinstance(updated_case, VulnerabilityCase)
        assert updated_case.current_status.em.state == EM.NONE

    def test_proposed_em_pxa_queues_reject_activity_to_outbox(
        self, public_aware_status
    ):
        """EM PROPOSED + CS.P → reject activity queued in actor outbox.

        Per EMB-16-001: SendRejectEmbargoActivityNode must call
        factory.reject_embargo() and record the result in the outbox.
        """
        reject_id = "https://example.org/activities/reject-01"
        dl, bridge, node = self._setup(
            public_aware_status, reject_activity_id=reject_id
        )
        bridge.execute_with_setup(tree=node, actor_id=ACTOR_ID)

        outbox = dl.outbox_list()
        assert reject_id in outbox


# ---------------------------------------------------------------------------
# PublicDisclosureBranchNode
# ---------------------------------------------------------------------------


class TestPublicDisclosureBranchNode:
    def test_always_succeeds_when_not_public_aware(
        self, populated_bridge, status_obj
    ):
        """Non-public-aware status → skip condition returns SUCCESS → branch
        returns SUCCESS without attempting embargo teardown."""
        node = PublicDisclosureBranchNode(
            status_obj=status_obj,
            sender_actor_id=ACTOR_ID,
            case_id=CASE_ID,
        )
        result = populated_bridge.execute_with_setup(
            tree=node, actor_id=ACTOR_ID
        )
        assert result.status == Status.SUCCESS

    def test_none_case_id_succeeds(self, populated_bridge, status_obj):
        """None case_id → skip condition exits early → returns SUCCESS."""
        node = PublicDisclosureBranchNode(
            status_obj=status_obj,
            sender_actor_id=ACTOR_ID,
            case_id=None,
        )
        result = populated_bridge.execute_with_setup(
            tree=node, actor_id=ACTOR_ID
        )
        assert result.status == Status.SUCCESS


# ---------------------------------------------------------------------------
# EmitCloseCaseNode
# ---------------------------------------------------------------------------


class TestEmitCloseCaseNode:
    def test_succeeds_when_no_factory(self, populated_bridge):
        """No trigger_activity_factory → best-effort SUCCESS (receive-side)."""
        # Seed blackboard with a case_manager_id
        py_trees.blackboard.Blackboard.storage["/case_manager_id"] = (
            CASE_MANAGER_ID
        )
        node = EmitCloseCaseNode(case_id=CASE_ID)
        result = populated_bridge.execute_with_setup(
            tree=node, actor_id=ACTOR_ID
        )
        assert result.status == Status.SUCCESS

    def test_succeeds_with_none_case_id(self, populated_bridge):
        """None case_id → early SUCCESS (nothing to emit)."""
        node = EmitCloseCaseNode(case_id=None)
        result = populated_bridge.execute_with_setup(
            tree=node, actor_id=ACTOR_ID
        )
        assert result.status == Status.SUCCESS

    def test_succeeds_when_case_manager_id_missing(self, populated_bridge):
        """Missing case_manager_id on blackboard → WARNING + SUCCESS."""
        node = EmitCloseCaseNode(case_id=CASE_ID)
        result = populated_bridge.execute_with_setup(
            tree=node, actor_id=ACTOR_ID
        )
        assert result.status == Status.SUCCESS

    def test_happy_path_emits_leave_and_records_outbox(self, populated_dl):
        """With factory + case_manager_id on blackboard → queues Leave, SUCCESS."""
        activity_id = "https://example.org/activities/leave-01"
        factory = MagicMock()
        factory.close_case.return_value = (activity_id, {})

        py_trees.blackboard.Blackboard.storage["/case_manager_id"] = (
            CASE_MANAGER_ID
        )
        bridge = BTBridge(datalayer=populated_dl, trigger_activity=factory)
        node = EmitCloseCaseNode(case_id=CASE_ID)
        result = bridge.execute_with_setup(tree=node, actor_id=ACTOR_ID)

        assert result.status == Status.SUCCESS
        factory.close_case.assert_called_once_with(
            case_id=CASE_ID,
            actor=ACTOR_ID,
            to=[CASE_MANAGER_ID],
        )
        outbox = populated_dl.outbox_list()
        assert activity_id in outbox

    def test_fails_on_factory_exception(self, populated_dl):
        """factory.close_case raises → FAILURE (unexpected error path)."""
        factory = MagicMock()
        factory.close_case.side_effect = RuntimeError("boom")

        py_trees.blackboard.Blackboard.storage["/case_manager_id"] = (
            CASE_MANAGER_ID
        )
        bridge = BTBridge(datalayer=populated_dl, trigger_activity=factory)
        node = EmitCloseCaseNode(case_id=CASE_ID)
        result = bridge.execute_with_setup(tree=node, actor_id=ACTOR_ID)

        assert result.status == Status.FAILURE
