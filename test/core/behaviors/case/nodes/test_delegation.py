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

"""Tests for the role-delegation nodes (ADR-0039, CM-33)."""

from unittest.mock import MagicMock

import pytest
from py_trees.common import Status

from test.support.ledger import (
    committed_event_types,
)
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driven.sync_activity_adapter import SyncActivityAdapter
from vultron.adapters.driven.trigger_activity_adapter import (
    TriggerActivityAdapter,
)
from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.case.nodes.delegation import (
    AutoAcceptCaseParticipantRoleNode,
    EmitRejectCaseParticipantRoleNode,
    ForwardRoleOfferToTargetNode,
    GrantCaseParticipantRoleNode,
    IsRoleOfferTargetNode,
)
from vultron.core.models.case_participant import CaseParticipant
from vultron.enums.roles import CVDRole
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)

VENDOR_ID = "https://example.org/actors/vendor"
ACTOR_ID = "https://example.org/actors/case-actor"
MANAGER_ID = "https://example.org/actors/coordinator"
OFFER_ID = "https://example.org/activities/offer-role-1"
CASE_ID = "https://example.org/cases/test-case-delegation"


@pytest.fixture
def dl():
    # These trees execute as ACTOR_ID, so the store under test is ACTOR_ID's
    # own (BT-05-005).  There is no unscoped DataLayer to open (ADR-0073).
    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=ACTOR_ID)
    # attributed_to triggers genesis_hash computation so that
    # commit_emitted_activity can bootstrap the chain (CLP-08-005).
    case = as_VulnerabilityCase(
        id_=CASE_ID, name="Delegation Test Case", attributed_to=ACTOR_ID
    )
    dl.create(case)
    return dl


@pytest.fixture
def factory(dl):
    return TriggerActivityAdapter(dl)


@pytest.fixture
def bridge(dl, factory):
    return BTBridge(datalayer=dl, trigger_activity=factory)


@pytest.fixture
def bridge_with_sync(dl, factory):
    """Bridge with a sync_port so ledger commits can fan out (ADR-0119)."""
    return BTBridge(
        datalayer=dl,
        trigger_activity=factory,
        sync_port=SyncActivityAdapter(dl),
    )


def _seed_participant(dl, actor_id: str, roles: list[CVDRole]) -> str:
    """Add *actor_id* to the case with *roles*; return the participant id."""
    case = dl.read(CASE_ID)
    participant = CaseParticipant(
        id_=f"{CASE_ID}/participants/{actor_id.rsplit('/', 1)[-1]}",
        attributed_to=actor_id,
        context=CASE_ID,
        case_roles=list(roles),
    )
    case.add_participant(participant)
    dl.create(participant)
    dl.save(case)
    return participant.id_


def _answer_node(node_cls, **overrides):
    kwargs = {
        "offer_id": OFFER_ID,
        "case_id": CASE_ID,
        "role": CVDRole.CASE_MANAGER,
        "target_actor_id": ACTOR_ID,
        "vendor_id": VENDOR_ID,
        **overrides,
    }
    return node_cls(**kwargs)


#: Both arms of the AcceptOrReject Selector, with the ledger event_type and
#: the factory method each one calls.
ANSWERS = pytest.mark.parametrize(
    ("node_cls", "event_type"),
    [
        (AutoAcceptCaseParticipantRoleNode, "accept_case_participant_role"),
        (EmitRejectCaseParticipantRoleNode, "reject_case_participant_role"),
    ],
    ids=["accept", "reject"],
)


@ANSWERS
class TestAnswerNodeInputs:
    """A missing input or a factory error returns FAILURE, writing nothing."""

    def test_failure_when_no_factory(self, dl, node_cls, event_type):
        bridge_no_factory = BTBridge(datalayer=dl)
        result = bridge_no_factory.execute_with_setup(
            tree=_answer_node(node_cls), actor_id=ACTOR_ID
        )

        assert result.status == Status.FAILURE
        assert dl.outbox_list() == []

    @pytest.mark.parametrize("field", ["case_id", "target_actor_id"])
    def test_failure_when_an_id_is_empty(
        self, bridge, dl, node_cls, event_type, field
    ):
        result = bridge.execute_with_setup(
            tree=_answer_node(node_cls, **{field: ""}), actor_id=ACTOR_ID
        )

        assert result.status == Status.FAILURE
        assert dl.outbox_list() == []

    def test_failure_when_factory_raises(self, dl, node_cls, event_type):
        mock_factory = MagicMock()
        getattr(mock_factory, event_type).side_effect = RuntimeError(
            "factory error"
        )
        bridge_bad_factory = BTBridge(
            datalayer=dl, trigger_activity=mock_factory
        )
        result = bridge_bad_factory.execute_with_setup(
            tree=_answer_node(node_cls), actor_id=ACTOR_ID
        )

        assert result.status == Status.FAILURE
        assert dl.outbox_list() == []

    def test_failure_when_the_case_is_not_held(
        self, bridge, dl, node_cls, event_type
    ):
        """An Accept that fails here lets the Selector answer with the Reject."""
        result = bridge.execute_with_setup(
            tree=_answer_node(
                node_cls, case_id="https://example.org/cases/not-held"
            ),
            actor_id=ACTOR_ID,
        )

        assert result.status == Status.FAILURE
        assert dl.outbox_list() == []


def _participant_store() -> SqliteDataLayer:
    """ACTOR_ID's store: a case MANAGER_ID manages, ACTOR_ID a participant."""
    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=ACTOR_ID)
    dl.create(
        as_VulnerabilityCase(
            id_=CASE_ID, name="Delegation Test Case", attributed_to=MANAGER_ID
        )
    )
    _seed_participant(dl, MANAGER_ID, [CVDRole.CASE_MANAGER])
    _seed_participant(dl, ACTOR_ID, [CVDRole.REPORTER])
    return dl


@ANSWERS
class TestAnswerGoesToTheCaseManager:
    """The target answers the CASE_MANAGER only (CM-33-004, PCR-08-011)."""

    @pytest.mark.spec("CM-33-004")
    @pytest.mark.spec("PCR-08-001")
    def test_the_answer_is_addressed_to_the_case_manager_only(
        self, node_cls, event_type
    ):
        dl = _participant_store()
        bridge = BTBridge(
            datalayer=dl, trigger_activity=TriggerActivityAdapter(dl)
        )

        result = bridge.execute_with_setup(
            tree=_answer_node(node_cls), actor_id=ACTOR_ID
        )

        assert result.status == Status.SUCCESS, result
        (answer_id,) = dl.outbox_list()
        assert getattr(dl.read(answer_id), "to", None) == [MANAGER_ID]

    @pytest.mark.spec("PCR-08-011")
    def test_failure_when_the_case_names_no_case_manager(
        self, bridge, dl, node_cls, event_type
    ):
        """No CASE_MANAGER resolves: nothing is sent, so the Selector fails."""
        _seed_participant(dl, ACTOR_ID, [CVDRole.REPORTER])

        result = bridge.execute_with_setup(
            tree=_answer_node(node_cls), actor_id=ACTOR_ID
        )

        assert result.status == Status.FAILURE
        assert dl.outbox_list() == []

    @pytest.mark.spec("OX-06-002")
    def test_a_retry_sends_the_same_answer_once(self, node_cls, event_type):
        """The answer's id derives from the Offer, so a retry rebuilds it."""
        dl = _participant_store()
        bridge = BTBridge(
            datalayer=dl, trigger_activity=TriggerActivityAdapter(dl)
        )

        bridge.execute_with_setup(
            tree=_answer_node(node_cls), actor_id=ACTOR_ID
        )
        first = dl.outbox_list()
        bridge.execute_with_setup(
            tree=_answer_node(node_cls), actor_id=ACTOR_ID
        )

        assert len(first) == 1
        assert dl.outbox_list() == first


@ANSWERS
@pytest.mark.spec("CLP-09-001")
def test_an_ordinary_participant_answers_with_no_ledger_entry(
    node_cls, event_type
):
    """The offered actor is usually not the CASE_MANAGER (#4588 probe).

    The case is managed by MANAGER_ID; ACTOR_ID, an ordinary participant,
    answers in its own store.  Before the CASE_MANAGER gate the answer
    minted an entry in ACTOR_ID's replica ledger, forking the chain.
    """
    dl = _participant_store()
    bridge = BTBridge(
        datalayer=dl,
        trigger_activity=TriggerActivityAdapter(dl),
        sync_port=SyncActivityAdapter(dl),
    )

    result = bridge.execute_with_setup(
        tree=_answer_node(node_cls), actor_id=ACTOR_ID
    )

    assert result.status == Status.SUCCESS, result
    assert len(dl.outbox_list()) == 1
    assert committed_event_types(dl, CASE_ID) == []


class TestIsRoleOfferTargetNode:
    """Only the target answers a role Offer (CM-33-004, BT-17-008)."""

    @pytest.mark.spec("CM-33-004")
    def test_succeeds_for_the_target(self, bridge):
        result = bridge.execute_with_setup(
            tree=IsRoleOfferTargetNode(target_actor_id=ACTOR_ID),
            actor_id=ACTOR_ID,
        )

        assert result.status == Status.SUCCESS

    @pytest.mark.spec("CM-33-004")
    def test_fails_for_any_other_actor(self, bridge):
        node = IsRoleOfferTargetNode(target_actor_id=VENDOR_ID)

        result = bridge.execute_with_setup(tree=node, actor_id=ACTOR_ID)

        assert result.status == Status.FAILURE
        assert "is not the target" in node.feedback_message


def _forward_node() -> ForwardRoleOfferToTargetNode:
    return ForwardRoleOfferToTargetNode(
        case_id=CASE_ID,
        role=CVDRole.VENDOR,
        target_actor_id=MANAGER_ID,
        offer_id=OFFER_ID,
        owner_id=VENDOR_ID,
    )


class TestForwardRoleOfferToTargetNode:
    """The CASE_MANAGER forwards the recorded Offer to its target (CM-33-001)."""

    @pytest.mark.spec("CM-33-001")
    @pytest.mark.spec("CM-24-005")
    def test_forward_names_the_recorded_offer_and_its_owner(self, bridge, dl):
        result = bridge.execute_with_setup(
            tree=_forward_node(), actor_id=ACTOR_ID
        )

        assert result.status == Status.SUCCESS, result
        (forward_id,) = dl.outbox_list()
        forward = dl.read(forward_id)
        assert forward.to == [MANAGER_ID]
        assert forward.actor == ACTOR_ID
        assert forward.attributed_to == VENDOR_ID
        assert forward.in_reply_to == OFFER_ID
        assert forward.object_.role is CVDRole.VENDOR

    @pytest.mark.spec("OX-06-002")
    def test_a_retry_queues_the_same_forward_once(self, bridge, dl):
        bridge.execute_with_setup(tree=_forward_node(), actor_id=ACTOR_ID)
        first = dl.outbox_list()
        bridge.execute_with_setup(tree=_forward_node(), actor_id=ACTOR_ID)

        assert len(first) == 1
        assert dl.outbox_list() == first

    def test_failure_when_no_factory(self, dl):
        result = BTBridge(datalayer=dl).execute_with_setup(
            tree=_forward_node(), actor_id=ACTOR_ID
        )

        assert result.status == Status.FAILURE
        assert dl.outbox_list() == []

    @pytest.mark.spec("ARCH-15-001")
    def test_a_factory_fault_is_an_internal_error(self, dl):
        """It runs after the commit: a fault is ours, never a refusal."""
        mock_factory = MagicMock()
        mock_factory.offer_case_participant_role.side_effect = RuntimeError(
            "factory error"
        )

        result = BTBridge(
            datalayer=dl, trigger_activity=mock_factory
        ).execute_with_setup(tree=_forward_node(), actor_id=ACTOR_ID)

        assert result.status == Status.FAILURE
        assert result.internal_error
        assert dl.outbox_list() == []


class TestGrantCaseParticipantRoleNode:
    """The CASE_MANAGER grants the role on its own copy at commit (CM-02-016)."""

    @pytest.mark.spec("CM-02-016")
    def test_grants_role_on_own_copy(self, bridge, dl):
        participant_id = _seed_participant(dl, ACTOR_ID, [CVDRole.VENDOR])
        node = GrantCaseParticipantRoleNode(
            case_id=CASE_ID,
            role=CVDRole.CASE_MANAGER,
            target_actor_id=ACTOR_ID,
        )
        result = bridge.execute_with_setup(tree=node, actor_id=ACTOR_ID)

        assert result.status == Status.SUCCESS
        granted = dl.read(participant_id)
        assert granted.has_role(CVDRole.CASE_MANAGER)  # newly granted
        assert granted.has_role(CVDRole.VENDOR)  # pre-existing role kept

    @pytest.mark.spec("CM-02-016")
    def test_missing_participant_is_non_fatal(self, bridge, dl):
        """No participant for the target: SUCCESS, nothing written."""
        node = GrantCaseParticipantRoleNode(
            case_id=CASE_ID,
            role=CVDRole.CASE_MANAGER,
            target_actor_id=ACTOR_ID,
        )
        result = bridge.execute_with_setup(tree=node, actor_id=ACTOR_ID)

        assert result.status == Status.SUCCESS
        assert ACTOR_ID not in dl.read(CASE_ID).actor_participant_index
