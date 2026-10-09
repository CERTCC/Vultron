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

Tests EmitCloseCaseNode from nodes.lifecycle, and the EM PROPOSED path of
ThreatTerminationBranchNode (EMB-16-001, EMB-16-002).

Per DEMOMA-07-003 steps 4–5.
"""

from unittest.mock import MagicMock

import py_trees
import pytest
from py_trees.common import Status

from test.support.embargo_register import propose
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driven.sync_activity_adapter import SyncActivityAdapter
from vultron.adapters.driven.trigger_activity_adapter import (
    TriggerActivityAdapter,
)
from vultron.adapters.driven.wire_render.as2 import As2WireRenderAdapter
from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.status.nodes.lifecycle import EmitCloseCaseNode
from vultron.core.behaviors.status.nodes.threat_termination import (
    ThreatTerminationBranchNode,
)
from vultron.core.models._helpers import days_from_now_utc
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.dimensions import (
    PxaDimension,
)
from vultron.core.states.cs import CS_pxa
from vultron.core.states.em import EM
from vultron.enums.roles import CVDRole
from vultron.wire.as2.factories import em_propose_embargo_activity
from vultron.wire.as2.vocab.objects.case_status import (
    as_CaseStatus,
    as_ParticipantStatus,
)
from vultron.wire.as2.vocab.objects.embargo_event import as_EmbargoEvent
from vultron.wire.as2.vocab.objects.vulnerability_case import (  # noqa: F401
    as_VulnerabilityCase,
)

ACTOR_ID = "https://example.org/actors/vendor"
CASE_MANAGER_ID = "https://example.org/actors/case-actor"
CASE_ID = "https://example.org/cases/case-01"
PARTICIPANT_ID = "https://example.org/cases/case-01/participants/vendor"
CM_PARTICIPANT_ID = "https://example.org/cases/case-01/participants/case-actor"
STATUS_ID = "https://example.org/cases/case-01/statuses/s1"
EMBARGO_ID = "https://example.org/cases/case-01/embargo_events/e1"


@pytest.fixture
def dl():
    # ACTOR_ID's own store: the trees in this module execute as ACTOR_ID, and a
    # BT's store follows its executing actor (ADR-0073). CASE_MANAGER_ID appears
    # here as a *role holder named in the case*, not as the store's owner.
    return SqliteDataLayer("sqlite:///:memory:", actor_id=ACTOR_ID)


@pytest.fixture
def participant():
    return CaseParticipant(
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
        case_status=as_CaseStatus(
            context=CASE_ID, pxa=PxaDimension(state=CS_pxa.Pxa)
        ),
    )


@pytest.fixture
def populated_dl(dl, participant, status_obj):
    case_manager_participant = CaseParticipant(
        id_=CM_PARTICIPANT_ID,
        context=CASE_ID,
        attributed_to=CASE_MANAGER_ID,
        case_roles=[CVDRole.CASE_MANAGER],
    )
    case = VulnerabilityCase(
        id_=CASE_ID, name="Test Case", attributed_to=ACTOR_ID
    )
    case.add_participant(participant)
    case.add_participant(case_manager_participant)
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
# ThreatTerminationBranchNode — PROPOSED path (EMB-16-001)
# ---------------------------------------------------------------------------


class TestThreatTerminationBranchNodeProposedEmPath:
    """Integration tests: CS.P/X/A fires while EM is PROPOSED.

    Per EMB-16-001 the branch routes to reject_proposed_embargo_bt (not
    terminate_embargo_bt).  Abandoning the proposal writes shared EM state,
    so only the CASE_MANAGER makes it (EP-09-008, #4131): the manager's run
    drives EM ``PROPOSED → NONE``, and the owner's run writes and sends
    nothing (EMB-16-002, #4148).  Each run executes in its own actor's store.
    """

    def _setup(
        self,
        public_aware_status: as_ParticipantStatus,
        *,
        store_actor: str = ACTOR_ID,
    ) -> tuple[SqliteDataLayer, BTBridge, ThreatTerminationBranchNode]:
        dl = SqliteDataLayer("sqlite:///:memory:", actor_id=store_actor)

        embargo = as_EmbargoEvent(
            id_=EMBARGO_ID, context=CASE_ID, end_time=days_from_now_utc(45)
        )
        invite = em_propose_embargo_activity(
            embargo, context=CASE_ID, actor=ACTOR_ID, to=[CASE_MANAGER_ID]
        )
        case = VulnerabilityCase(
            id_=CASE_ID, name="Test Case", attributed_to=ACTOR_ID
        )
        propose(case, embargo.id_)
        case.pending_embargo_proposal_index = {embargo.id_: invite.id_}

        participant = CaseParticipant(
            id_=PARTICIPANT_ID,
            context=CASE_ID,
            attributed_to=ACTOR_ID,
            case_roles=[CVDRole.CASE_OWNER],
        )
        cm_participant = CaseParticipant(
            id_=CM_PARTICIPANT_ID,
            context=CASE_ID,
            attributed_to=CASE_MANAGER_ID,
            case_roles=[CVDRole.CASE_MANAGER],
        )
        case.add_participant(participant)
        case.add_participant(cm_participant)
        dl.create(embargo)
        dl.create(invite)
        dl.create(case)
        dl.create(participant)
        dl.create(cm_participant)

        bridge = BTBridge(
            datalayer=dl,
            trigger_activity=TriggerActivityAdapter(dl),
            wire_render_port=As2WireRenderAdapter(),
            sync_port=SyncActivityAdapter(dl),
        )
        node = ThreatTerminationBranchNode(
            status_obj=public_aware_status,
            sender_actor_id=ACTOR_ID,
            case_id=CASE_ID,
        )
        return dl, bridge, node

    @pytest.mark.spec("EMB-16-001")
    @pytest.mark.spec("EP-09-008")
    def test_as_the_case_manager_em_returns_to_none(self, public_aware_status):
        dl, bridge, node = self._setup(
            public_aware_status, store_actor=CASE_MANAGER_ID
        )
        result = bridge.execute_with_setup(tree=node, actor_id=CASE_MANAGER_ID)
        assert result.status == Status.SUCCESS

        updated_case = dl.read(CASE_ID)
        assert isinstance(updated_case, VulnerabilityCase)
        assert updated_case.current_status.em.state == EM.NONE
        assert updated_case.proposed_embargo_ids == []

    @pytest.mark.spec("EMB-16-002")
    @pytest.mark.spec("EP-09-008")
    def test_the_owner_writes_and_sends_nothing(self, public_aware_status):
        dl, bridge, node = self._setup(public_aware_status)
        result = bridge.execute_with_setup(tree=node, actor_id=ACTOR_ID)
        assert result.status == Status.SUCCESS

        updated_case = dl.read(CASE_ID)
        assert isinstance(updated_case, VulnerabilityCase)
        assert updated_case.current_status.em.state == EM.PROPOSED
        assert updated_case.proposed_embargo_ids == [EMBARGO_ID]
        assert dl.outbox_list() == []


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

    @pytest.mark.xfail(
        strict=True,
        reason=(
            "CM-24-006: EmitCloseCaseNode returns SUCCESS with a warning when "
            "no CASE_MANAGER was resolved. Tracked by #3964 (Concern #3918, "
            "ADR-0113)."
        ),
    )
    @pytest.mark.spec("CM-24-006")
    def test_fails_when_case_manager_id_missing(self, populated_bridge):
        """No CASE_MANAGER resolved is a fault: FAILURE, not a skip."""
        node = EmitCloseCaseNode(case_id=CASE_ID)
        result = populated_bridge.execute_with_setup(
            tree=node, actor_id=ACTOR_ID
        )
        assert result.status == Status.FAILURE

    @pytest.mark.spec("CM-23-001")
    def test_happy_path_emits_leave_and_records_outbox(self, populated_dl):
        """With factory + case_manager_id on blackboard → queues Leave, SUCCESS."""
        activity_id = "https://example.org/activities/leave-01"
        factory = MagicMock()
        factory.close_case.return_value = (activity_id, {})

        py_trees.blackboard.Blackboard.storage["/case_manager_id"] = (
            CASE_MANAGER_ID
        )
        bridge = BTBridge(
            datalayer=populated_dl,
            trigger_activity=factory,
            wire_render_port=As2WireRenderAdapter(),
            sync_port=SyncActivityAdapter(populated_dl),
        )
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
        bridge = BTBridge(
            datalayer=populated_dl,
            trigger_activity=factory,
            wire_render_port=As2WireRenderAdapter(),
            sync_port=SyncActivityAdapter(populated_dl),
        )
        node = EmitCloseCaseNode(case_id=CASE_ID)
        result = bridge.execute_with_setup(tree=node, actor_id=ACTOR_ID)

        assert result.status == Status.FAILURE
