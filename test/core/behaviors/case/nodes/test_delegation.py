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

"""Tests for AutoAcceptCaseParticipantRoleNode and EmitRejectCaseParticipantRoleNode (ADR-0039)."""

from unittest.mock import MagicMock

import pytest
from py_trees.common import Status

import vultron.core.behaviors.sync.commit_tree as _commit_mod
from test.support.ledger import (
    committed_event_types,
    fail_commits,
    ledger_entries,
    record_sends_and_commits,
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
    GrantCaseParticipantRoleNode,
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


@ANSWERS
class TestAnswerAtTheCaseManager:
    """The CASE_MANAGER's answer is sent, then ledgered (ADR-0119)."""

    @pytest.fixture(autouse=True)
    def _actor_is_case_manager(self, dl):
        _seed_participant(dl, ACTOR_ID, [CVDRole.CASE_MANAGER])

    @pytest.mark.spec("SYNC-09-002")
    @pytest.mark.spec("CLP-02-012")
    def test_the_answer_is_queued_then_committed(
        self, bridge_with_sync, dl, monkeypatch, node_cls, event_type
    ):
        events = record_sends_and_commits(monkeypatch, ACTOR_ID)
        result = bridge_with_sync.execute_with_setup(
            tree=_answer_node(node_cls), actor_id=ACTOR_ID
        )

        assert result.status == Status.SUCCESS
        (answer_id,) = dl.outbox_list()
        assert events == [("queued", answer_id), (event_type, answer_id)]
        assert committed_event_types(dl, CASE_ID).count(event_type) == 1

    @pytest.mark.spec("OX-06-002")
    def test_a_retry_after_a_failed_commit_sends_and_records_once(
        self, bridge_with_sync, dl, monkeypatch, node_cls, event_type
    ):
        """The answer's id derives from the Offer, so a retry rebuilds it.

        A failed commit raises rather than returning FAILURE: the answer is
        already queued, and a FAILURE would let the Selector send the other
        answer after it.
        """
        with monkeypatch.context() as patched:
            fail_commits(patched, _commit_mod, allowed=0)
            first = bridge_with_sync.execute_with_setup(
                tree=_answer_node(node_cls), actor_id=ACTOR_ID
            )
        assert first.internal_error, first
        (answer_id,) = dl.outbox_list()
        assert event_type not in committed_event_types(dl, CASE_ID)

        retry = bridge_with_sync.execute_with_setup(
            tree=_answer_node(node_cls), actor_id=ACTOR_ID
        )

        assert retry.status == Status.SUCCESS
        assert dl.outbox_list() == [answer_id]
        (entry,) = [
            e
            for e in ledger_entries(dl, CASE_ID)
            if e.event_type == event_type
        ]
        assert entry.log_object_id == answer_id


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
    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=ACTOR_ID)
    dl.create(
        as_VulnerabilityCase(
            id_=CASE_ID, name="Delegation Test Case", attributed_to=MANAGER_ID
        )
    )
    _seed_participant(dl, MANAGER_ID, [CVDRole.CASE_MANAGER])
    _seed_participant(dl, ACTOR_ID, [CVDRole.VENDOR])
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
