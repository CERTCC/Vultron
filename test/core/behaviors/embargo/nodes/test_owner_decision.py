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

"""The case owner's decision on an embargo proposal (nodes/owner_decision.py).

``Accept(EmbargoEvent, target=Case)`` activates and
``Reject(EmbargoEvent, target=Case)`` rejects (ADR-0122).  The guards refuse a
decision before the commit; the lifecycle nodes write ``STRICT``; the send
node queues the owner's decision to the CASE_MANAGER and fails by raising.
"""

from typing import cast
from unittest.mock import MagicMock

import py_trees
import pytest
from py_trees.common import Status

from test.core.behaviors.embargo.nodes.conftest import (
    make_case_and_embargo,
    setup_blackboard,
)
from test.support.embargo_register import propose
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driven.trigger_activity_adapter import (
    TriggerActivityAdapter,
)
from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.embargo.nodes import (
    ActivateEmbargoLifecycleNode,
    IsOpenEmbargoProposalNode,
    OwnerMayActivateEmbargoNode,
    RejectEmbargoProposalLifecycleNode,
    SendOwnerEmbargoDecisionNode,
)
from vultron.core.models._helpers import _as_id, days_from_now_utc
from vultron.core.models.activity import VultronActivity
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.embargo_consent import EmbargoConsent
from vultron.core.services.embargo_lifecycle import EmbargoLifecycleResult
from vultron.core.states.cs import CS_pxa
from vultron.core.states.em import EM
from vultron.core.states.participant_embargo_consent import (
    EmbargoConsentState,
)
from vultron.enums.roles import CVDRole
from vultron.errors import VultronError
from vultron.wire.as2.vocab.objects.case_participant import as_CaseParticipant
from vultron.wire.as2.vocab.objects.embargo_event import as_EmbargoEvent

OWNER = "https://example.org/actors/owner"
MANAGER = "https://example.org/actors/case-manager"


def _tick(node: py_trees.behaviour.Behaviour) -> Status:
    bt = py_trees.trees.BehaviourTree(root=node)
    bt.setup()
    bt.tick()
    return node.status


def _case_with_owner(
    dl: SqliteDataLayer,
    suffix: str,
    *,
    em_state: EM,
    owner_consent: EmbargoConsentState | None = None,
    with_revision: bool = True,
    store_active: bool = True,
) -> tuple[VulnerabilityCase, str, str, str]:
    """A case owned by OWNER with e1 at *em_state* and, optionally, open e2.

    ``owner_consent`` seeds the owner's row for the open proposal (e2 when
    *with_revision*, else e1).  Returns the case, e1's id, the open
    proposal's id and the owner's participant id.
    """
    case, first = make_case_and_embargo(
        suffix, em_state=em_state, attributed_to=OWNER
    )
    open_id = first.id_
    if with_revision:
        revision = as_EmbargoEvent(
            id_=f"{case.id_}/embargo_events/revision",
            context=case.id_,
            end_time=days_from_now_utc(90),
        )
        dl.create(revision)
        propose(case, revision)
        open_id = revision.id_
    consents = (
        []
        if owner_consent is None
        else [EmbargoConsent(embargo_id=open_id, state=owner_consent)]
    )
    owner_p = as_CaseParticipant(
        attributed_to=OWNER,
        context=case.id_,
        case_roles=[CVDRole.CASE_OWNER],
        embargo_consents=consents,
    )
    case.actor_participant_index[OWNER] = owner_p.id_
    case.case_participants = [owner_p.id_]
    if store_active:
        dl.create(first)
    dl.create(owner_p)
    dl.create(case)
    return case, first.id_, open_id, owner_p.id_


def _case(dl: SqliteDataLayer, case_id: str) -> VulnerabilityCase:
    return cast(VulnerabilityCase, dl.read(case_id))


# ---------------------------------------------------------------------------
# IsOpenEmbargoProposalNode
# ---------------------------------------------------------------------------


class TestIsOpenEmbargoProposalNode:
    def test_an_open_proposal_passes(self, dl: SqliteDataLayer):
        case, _, revision_id, _ = _case_with_owner(
            dl, "open-ok", em_state=EM.ACTIVE
        )
        setup_blackboard(dl, actor_id=MANAGER)

        node = IsOpenEmbargoProposalNode(
            case_id=case.id_, embargo_id=revision_id
        )

        assert _tick(node) is Status.SUCCESS

    @pytest.mark.parametrize("named", ["active", "unknown"])
    def test_anything_but_an_open_proposal_fails(
        self, dl: SqliteDataLayer, named: str
    ):
        """The embargo in force, or one the case never saw: nothing to decide."""
        case, active_id, _, _ = _case_with_owner(
            dl, f"open-{named}", em_state=EM.ACTIVE
        )
        setup_blackboard(dl, actor_id=MANAGER)
        embargo_id = (
            active_id if named == "active" else f"{case.id_}/embargo_events/x"
        )

        node = IsOpenEmbargoProposalNode(
            case_id=case.id_, embargo_id=embargo_id
        )

        assert _tick(node) is Status.FAILURE
        assert "not an open proposal" in (node.feedback_message or "")

    def test_a_missing_case_fails(self, dl: SqliteDataLayer):
        setup_blackboard(dl, actor_id=MANAGER)
        node = IsOpenEmbargoProposalNode(
            case_id="https://example.org/cases/missing",
            embargo_id="https://example.org/cases/missing/embargo_events/e",
        )

        assert _tick(node) is Status.FAILURE


# ---------------------------------------------------------------------------
# OwnerMayActivateEmbargoNode
# ---------------------------------------------------------------------------


class TestOwnerMayActivateEmbargoNode:
    @pytest.mark.parametrize(
        "owner_consent",
        [None, EmbargoConsentState.INVITED, EmbargoConsentState.ACCEPTED],
        ids=["no-row", "invited", "accepted"],
    )
    def test_passes_with_pxa_clear_and_no_decline(
        self,
        dl: SqliteDataLayer,
        owner_consent: EmbargoConsentState | None,
    ):
        case, _, revision_id, _ = _case_with_owner(
            dl, "may-ok", em_state=EM.ACTIVE, owner_consent=owner_consent
        )
        setup_blackboard(dl, actor_id=MANAGER)

        node = OwnerMayActivateEmbargoNode(
            case_id=case.id_, embargo_id=revision_id
        )

        assert _tick(node) is Status.SUCCESS

    @pytest.mark.spec("EMB-02-002")
    def test_fails_when_pxa_is_set(self, dl: SqliteDataLayer):
        case, _, revision_id, _ = _case_with_owner(
            dl, "may-pxa", em_state=EM.ACTIVE
        )
        case.append_case_status(pxa_state=CS_pxa.Pxa)
        dl.save(case)
        setup_blackboard(dl, actor_id=MANAGER)

        node = OwnerMayActivateEmbargoNode(
            case_id=case.id_, embargo_id=revision_id
        )

        assert _tick(node) is Status.FAILURE
        assert "EMB-02-002" in (node.feedback_message or "")

    def test_fails_when_the_owner_declined_the_proposal(
        self, dl: SqliteDataLayer
    ):
        """ADR-0122: the owner is invited again before activating what it declined."""
        case, _, revision_id, _ = _case_with_owner(
            dl,
            "may-declined",
            em_state=EM.ACTIVE,
            owner_consent=EmbargoConsentState.DECLINED,
        )
        setup_blackboard(dl, actor_id=MANAGER)

        node = OwnerMayActivateEmbargoNode(
            case_id=case.id_, embargo_id=revision_id
        )

        assert _tick(node) is Status.FAILURE
        assert "declined" in (node.feedback_message or "")


# ---------------------------------------------------------------------------
# ActivateEmbargoLifecycleNode / RejectEmbargoProposalLifecycleNode
# ---------------------------------------------------------------------------


class TestActivateEmbargoLifecycleNode:
    @pytest.mark.spec("EMB-18-001")
    def test_activates_the_proposal_and_records_the_owners_agreement(
        self, dl: SqliteDataLayer
    ):
        case, active_id, revision_id, owner_pid = _case_with_owner(
            dl, "act-ok", em_state=EM.ACTIVE
        )
        setup_blackboard(dl, actor_id=MANAGER)
        result_out: dict[str, object] = {}

        node = ActivateEmbargoLifecycleNode(
            case_id=case.id_, embargo_id=revision_id, result_out=result_out
        )

        assert _tick(node) is Status.SUCCESS
        decided = _case(dl, case.id_)
        assert decided.current_status.em.state == EM.ACTIVE
        assert decided.active_embargo_id == revision_id
        assert decided.proposed_embargo_ids == []
        assert result_out["em_before"] == EM.REVISE
        assert result_out["em_after"] == EM.ACTIVE
        assert isinstance(
            result_out["lifecycle_result"], EmbargoLifecycleResult
        )
        owner_p = cast(CaseParticipant, dl.read(owner_pid))
        assert owner_p.is_signatory(revision_id)
        assert active_id != revision_id

    def test_an_embargo_already_in_force_fails_strict(
        self, dl: SqliteDataLayer
    ):
        case, active_id, _, _ = _case_with_owner(
            dl, "act-active", em_state=EM.ACTIVE
        )
        setup_blackboard(dl, actor_id=MANAGER)
        result_out: dict[str, object] = {}

        node = ActivateEmbargoLifecycleNode(
            case_id=case.id_, embargo_id=active_id, result_out=result_out
        )

        assert _tick(node) is Status.FAILURE
        assert isinstance(result_out["error"], VultronError)
        assert _case(dl, case.id_).current_status.em.state == EM.REVISE

    @pytest.mark.spec("EMB-18-003")
    @pytest.mark.spec("EP-05-001")
    def test_an_unreadable_replaced_embargo_fails_closed(
        self, dl: SqliteDataLayer
    ):
        """A is not held here: FAILURE before the register or any row moves."""
        case, active_id, revision_id, owner_pid = _case_with_owner(
            dl, "act-unread", em_state=EM.ACTIVE, store_active=False
        )
        setup_blackboard(dl, actor_id=MANAGER)

        node = ActivateEmbargoLifecycleNode(
            case_id=case.id_, embargo_id=revision_id, result_out={}
        )

        assert _tick(node) is Status.FAILURE
        untouched = _case(dl, case.id_)
        assert untouched.current_status.em.state == EM.REVISE
        assert untouched.active_embargo_id == active_id
        assert untouched.proposed_embargo_ids == [revision_id]
        owner_p = cast(CaseParticipant, dl.read(owner_pid))
        assert owner_p.consent_for(revision_id) is None


class TestRejectEmbargoProposalLifecycleNode:
    @pytest.mark.spec("EP-08-003")
    def test_rejects_the_revision_and_writes_no_consent(
        self, dl: SqliteDataLayer
    ):
        case, active_id, revision_id, owner_pid = _case_with_owner(
            dl,
            "rej-ok",
            em_state=EM.ACTIVE,
            owner_consent=EmbargoConsentState.INVITED,
        )
        setup_blackboard(dl, actor_id=MANAGER)
        result_out: dict[str, object] = {}

        node = RejectEmbargoProposalLifecycleNode(
            case_id=case.id_, embargo_id=revision_id, result_out=result_out
        )

        assert _tick(node) is Status.SUCCESS
        decided = _case(dl, case.id_)
        assert decided.current_status.em.state == EM.ACTIVE
        assert decided.active_embargo_id == active_id
        assert decided.proposed_embargo_ids == []
        assert result_out["em_after"] == EM.ACTIVE
        owner_p = cast(CaseParticipant, dl.read(owner_pid))
        assert owner_p.consent_for(revision_id) is EmbargoConsentState.INVITED

    @pytest.mark.spec("EMB-04-002")
    def test_strict_ej_with_pxa_set_fails_and_writes_nothing(
        self, dl: SqliteDataLayer
    ):
        case, _, revision_id, _ = _case_with_owner(
            dl, "rej-pxa", em_state=EM.ACTIVE
        )
        case.append_case_status(pxa_state=CS_pxa.Pxa)
        dl.save(case)
        setup_blackboard(dl, actor_id=MANAGER)
        result_out: dict[str, object] = {}

        node = RejectEmbargoProposalLifecycleNode(
            case_id=case.id_, embargo_id=revision_id, result_out=result_out
        )

        assert _tick(node) is Status.FAILURE
        assert isinstance(result_out["error"], VultronError)
        kept = _case(dl, case.id_)
        assert kept.current_status.em.state == EM.REVISE
        assert kept.proposed_embargo_ids == [revision_id]


# ---------------------------------------------------------------------------
# SendOwnerEmbargoDecisionNode
# ---------------------------------------------------------------------------

CASE_ID = "https://example.org/cases/case-owner-decision"
EMBARGO_ID = f"{CASE_ID}/embargo_events/e1"


def _owner_store(*, with_manager: bool = True) -> SqliteDataLayer:
    """The owner's replica: the case, its CASE_MANAGER and the proposal."""
    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=OWNER)
    dl.create(
        as_EmbargoEvent(
            id_=EMBARGO_ID, context=CASE_ID, end_time=days_from_now_utc(45)
        )
    )
    case = VulnerabilityCase(id_=CASE_ID, attributed_to=OWNER)
    if with_manager:
        manager = as_CaseParticipant(
            id_=f"{CASE_ID}/participants/cm",
            attributed_to=MANAGER,
            context=CASE_ID,
            case_roles=[CVDRole.CASE_MANAGER],
        )
        dl.create(manager)
        case.actor_participant_index[MANAGER] = manager.id_
    propose(case, EMBARGO_ID)
    dl.create(case)
    return dl


def _run(dl: SqliteDataLayer, tree, *, factory=None):
    return BTBridge(datalayer=dl).execute_with_setup(
        tree=tree,
        actor_id=OWNER,
        trigger_activity_factory=(
            factory if factory is not None else TriggerActivityAdapter(dl)
        ),
    )


def _send(accept: bool) -> SendOwnerEmbargoDecisionNode:
    return SendOwnerEmbargoDecisionNode(
        case_id=CASE_ID, embargo_id=EMBARGO_ID, accept=accept
    )


class TestSendOwnerEmbargoDecisionNode:
    @pytest.mark.spec("PCR-08-001")
    @pytest.mark.parametrize(
        ("accept", "type_"), [(True, "Accept"), (False, "Reject")]
    )
    def test_queues_the_decision_on_the_embargo_to_the_case_manager(
        self, accept: bool, type_: str
    ):
        """The object is the EmbargoEvent itself and the target the case."""
        dl = _owner_store()

        result = _run(dl, _send(accept))

        assert result.status == Status.SUCCESS
        (queued,) = [
            cast(VultronActivity, dl.read(i)) for i in dl.outbox_list()
        ]
        assert queued.type_ == type_
        assert queued.actor == OWNER
        assert queued.to == [MANAGER]
        assert _as_id(queued.object_) == EMBARGO_ID
        assert _as_id(queued.target) == CASE_ID

    @pytest.mark.parametrize(
        ("accept", "called", "not_called"),
        [
            (True, "activate_embargo", "reject_embargo_proposal"),
            (False, "reject_embargo_proposal", "activate_embargo"),
        ],
    )
    def test_calls_the_owner_decision_factory_method(
        self, accept: bool, called: str, not_called: str
    ):
        dl = _owner_store()
        factory = MagicMock()
        getattr(factory, called).return_value = ("urn:decision:1", "{}")

        result = _run(dl, _send(accept), factory=factory)

        assert result.status == Status.SUCCESS
        getattr(factory, called).assert_called_once_with(
            embargo_id=EMBARGO_ID,
            case_id=CASE_ID,
            actor=OWNER,
            to=[MANAGER],
        )
        getattr(factory, not_called).assert_not_called()
        factory.accept_embargo.assert_not_called()
        factory.reject_embargo.assert_not_called()

    @pytest.mark.spec("EMB-15-001")
    def test_a_failed_activation_never_falls_through_to_rejection(self):
        """The accept arm raises, so the Selector never tries the reject arm."""
        dl = _owner_store()
        factory = MagicMock()
        factory.activate_embargo.side_effect = ValueError("factory broke")
        tree = py_trees.composites.Selector(
            "Decide", memory=False, children=[_send(True), _send(False)]
        )

        result = _run(dl, tree, factory=factory)

        assert result.status == Status.FAILURE
        assert result.internal_error
        factory.reject_embargo_proposal.assert_not_called()
        assert dl.outbox_list() == []

    @pytest.mark.spec("CM-24-006")
    def test_a_case_with_no_manager_is_a_fault(self):
        dl = _owner_store(with_manager=False)

        result = _run(dl, _send(True))

        assert result.status == Status.FAILURE
        assert result.internal_error
        assert "CM-24-006" in (result.feedback_message or "")
        assert dl.outbox_list() == []
