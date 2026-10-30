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

"""The nodes of the P/X/A refusal diversion (nodes/pxa_refusal.py).

``PxaBarsEmbargoNode`` is the diversion's condition (EMB-01-002, EMB-02-002);
``ReceiverIsInviteeNode`` and ``ErFactoryAvailableNode`` decide whether the
ER can be sent; ``SendEmbargoProposalRefusalNode`` sends it where an answer to
the Invite goes (EP-09-003, PCR-08-001).
"""

import py_trees
import pytest
from py_trees.common import Status

from test.core.behaviors.embargo.nodes.conftest import (
    CASE_MANAGER_ACTOR,
    OTHER_PARTICIPANT_ACTOR,
    make_case_with_manager,
)
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driven.trigger_activity_adapter import (
    TriggerActivityAdapter,
)
from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.embargo.nodes.pxa_refusal import (
    ErFactoryAvailableNode,
    PxaBarsEmbargoNode,
    ReceiverIsInviteeNode,
    SendEmbargoProposalRefusalNode,
)
from vultron.core.models.case import VulnerabilityCase
from vultron.core.states.cs import CS_pxa

_REASON = "EMB-01-002: P/X/A set"
_INVITE = "https://example.org/activities/pxa-invite"
_PROPOSER = "https://example.org/actors/proposer"


def _run(
    dl: SqliteDataLayer,
    node: py_trees.behaviour.Behaviour,
    actor_id: str,
    *,
    with_factory: bool = False,
) -> Status:
    tree = py_trees.composites.Sequence(
        name="Probe", memory=False, children=[node]
    )
    BTBridge(
        datalayer=dl,
        trigger_activity=TriggerActivityAdapter(dl) if with_factory else None,
    ).execute_with_setup(tree=tree, actor_id=actor_id)
    return node.status


def _case_with_pxa(suffix: str, pxa: str) -> tuple[str, SqliteDataLayer]:
    case, _, dl = make_case_with_manager(suffix)
    stored = dl.read(case.id_)
    assert isinstance(stored, VulnerabilityCase)
    stored.append_case_status(pxa=CS_pxa[pxa])
    dl.save(stored)
    return case.id_, dl


class TestPxaBarsEmbargoNode:
    @pytest.mark.spec("EMB-01-002")
    @pytest.mark.spec("EMB-02-002")
    @pytest.mark.parametrize(
        "pxa", ["Pxa", "pXa", "pxA", "PXa", "PxA", "pXA", "PXA"]
    )
    def test_any_pxa_bit_bars_the_embargo(self, pxa: str) -> None:
        case_id, dl = _case_with_pxa(f"pxa-bars-{pxa}", pxa)
        node = PxaBarsEmbargoNode(case_id=case_id, reason=_REASON)

        assert _run(dl, node, CASE_MANAGER_ACTOR) is Status.SUCCESS
        assert node.feedback_message == _REASON

    def test_a_clear_case_bars_nothing(self) -> None:
        case_id, dl = _case_with_pxa("pxa-clear", "pxa")
        node = PxaBarsEmbargoNode(case_id=case_id, reason=_REASON)

        assert _run(dl, node, CASE_MANAGER_ACTOR) is Status.FAILURE

    def test_a_case_this_store_does_not_hold_bars_nothing(self) -> None:
        _, dl = _case_with_pxa("pxa-missing", "PXA")
        node = PxaBarsEmbargoNode(
            case_id="https://example.org/cases/missing", reason=_REASON
        )

        assert _run(dl, node, CASE_MANAGER_ACTOR) is Status.FAILURE


class TestReceiverIsInviteeNode:
    @pytest.mark.spec("EP-09-010")
    def test_the_invitee_answers(self) -> None:
        _, _, dl = make_case_with_manager("invitee-yes")
        node = ReceiverIsInviteeNode(
            invitee_id=CASE_MANAGER_ACTOR, invite_id=_INVITE
        )

        assert _run(dl, node, CASE_MANAGER_ACTOR) is Status.SUCCESS

    @pytest.mark.spec("EP-09-010")
    def test_another_store_keeps_the_invite_unanswered(self, caplog) -> None:
        _, _, dl = make_case_with_manager("invitee-no")
        node = ReceiverIsInviteeNode(
            invitee_id=OTHER_PARTICIPANT_ACTOR, invite_id=_INVITE
        )

        with caplog.at_level("WARNING"):
            status = _run(dl, node, CASE_MANAGER_ACTOR)

        assert status is Status.FAILURE
        assert OTHER_PARTICIPANT_ACTOR in node.feedback_message
        assert "no ER sent" in caplog.text


class TestErFactoryAvailableNode:
    @pytest.mark.spec("EMB-01-002")
    def test_no_port_means_no_er(self, caplog) -> None:
        _, _, dl = make_case_with_manager("er-port-none")
        node = ErFactoryAvailableNode(case_id="c", invite_id=_INVITE)

        with caplog.at_level("WARNING"):
            status = _run(dl, node, CASE_MANAGER_ACTOR)

        assert status is Status.FAILURE
        assert "trigger_activity unavailable" in caplog.text

    def test_a_wired_port_passes(self) -> None:
        _, _, dl = make_case_with_manager("er-port-wired")
        node = ErFactoryAvailableNode(case_id="c", invite_id=_INVITE)

        assert (
            _run(dl, node, CASE_MANAGER_ACTOR, with_factory=True)
            is Status.SUCCESS
        )


class TestSendEmbargoProposalRefusalNodeRecipient:
    """The CASE_MANAGER answers the proposer; anyone else the CASE_MANAGER."""

    @staticmethod
    def _recipient(store_actor: str, executing_actor: str) -> str:
        case, _, dl = make_case_with_manager(
            f"er-to-{executing_actor.rsplit('/', 1)[-1]}",
            store_actor_id=store_actor,
        )
        node = SendEmbargoProposalRefusalNode(
            case_id=case.id_, invite_id=_INVITE, sender_id=_PROPOSER
        )
        node.datalayer = dl
        node.actor_id = executing_actor
        resolved = node._resolve_embargo_and_manager()
        assert not isinstance(resolved, Status), node.feedback_message
        return resolved[1]

    @pytest.mark.spec("EP-09-003")
    @pytest.mark.spec("EMB-01-002")
    @pytest.mark.spec("EMB-01-007")
    def test_the_case_manager_answers_the_proposer(self) -> None:
        recipient = self._recipient(CASE_MANAGER_ACTOR, CASE_MANAGER_ACTOR)
        assert recipient == _PROPOSER

    @pytest.mark.spec("PCR-08-001")
    def test_a_participant_answers_the_case_manager(self) -> None:
        recipient = self._recipient(
            OTHER_PARTICIPANT_ACTOR, OTHER_PARTICIPANT_ACTOR
        )
        assert recipient == CASE_MANAGER_ACTOR
