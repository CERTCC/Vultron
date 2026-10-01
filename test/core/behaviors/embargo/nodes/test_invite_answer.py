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

"""Tests for the participant's answer to an embargo Invite (EP-09-003).

``CanAnswerEmbargoInviteNode`` decides whether this store answers;
``SendEmbargoInviteAnswerNode`` queues the ``Accept``/``Reject`` to the
CASE_MANAGER and fails by raising, so that the accept arm of the EMB-15
Selector can never fall through to the reject arm.
"""

from typing import cast
from unittest.mock import MagicMock

import py_trees
import pytest
from py_trees.common import Status

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driven.trigger_activity_adapter import (
    TriggerActivityAdapter,
)
from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.embargo.nodes import (
    CanAnswerEmbargoInviteNode,
    SendEmbargoInviteAnswerNode,
)
from vultron.core.models._helpers import days_from_now_utc
from vultron.core.models.activity import VultronActivity
from vultron.core.models.case import VulnerabilityCase
from vultron.enums.roles import CVDRole
from vultron.wire.as2.factories import em_propose_embargo_activity
from vultron.wire.as2.vocab.objects.case_participant import as_CaseParticipant
from vultron.wire.as2.vocab.objects.embargo_event import as_EmbargoEvent

MANAGER = "https://example.org/actors/case-manager"
INVITEE = "https://example.org/actors/vendor"
CASE_ID = "https://example.org/cases/case-invite-answer"
EMBARGO_ID = f"{CASE_ID}/embargo_events/e1"
INVITE_ID = f"{CASE_ID}/invites/i1"


@pytest.fixture(autouse=True)
def clear_blackboard():
    py_trees.blackboard.Blackboard.storage.clear()
    yield
    py_trees.blackboard.Blackboard.storage.clear()


def _store(
    *,
    with_case: bool = True,
    with_manager: bool = True,
    with_embargo: bool = True,
):
    """The invitee's store, holding the Invite the CASE_MANAGER relayed."""
    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=INVITEE)
    embargo = as_EmbargoEvent(
        id_=EMBARGO_ID, context=CASE_ID, end_time=days_from_now_utc(45)
    )
    if with_embargo:
        dl.create(embargo)
    case = VulnerabilityCase(id_=CASE_ID, attributed_to=MANAGER)
    if with_manager:
        manager = as_CaseParticipant(
            id_=f"{CASE_ID}/participants/cm",
            attributed_to=MANAGER,
            context=CASE_ID,
            case_roles=[CVDRole.CASE_MANAGER],
        )
        dl.create(manager)
        case.actor_participant_index[MANAGER] = manager.id_
    invitee = as_CaseParticipant(
        id_=f"{CASE_ID}/participants/vendor",
        attributed_to=INVITEE,
        context=CASE_ID,
    )
    dl.create(invitee)
    case.actor_participant_index[INVITEE] = invitee.id_
    if with_case:
        dl.create(case)
    invite = em_propose_embargo_activity(
        embargo, context=CASE_ID, actor=MANAGER, to=[INVITEE], id_=INVITE_ID
    )
    dl.create(invite)
    return dl


def _run(dl, tree, *, actor_id: str = INVITEE, factory=None):
    return BTBridge(datalayer=dl).execute_with_setup(
        tree=tree,
        actor_id=actor_id,
        trigger_activity_factory=(
            factory if factory is not None else TriggerActivityAdapter(dl)
        ),
    )


def _queued(dl) -> list[VultronActivity]:
    return [cast(VultronActivity, dl.read(i)) for i in dl.outbox_list()]


def _send(accept: bool) -> SendEmbargoInviteAnswerNode:
    return SendEmbargoInviteAnswerNode(
        case_id=CASE_ID, invite_id=INVITE_ID, accept=accept
    )


class TestCanAnswerEmbargoInviteNode:
    def _node(self) -> CanAnswerEmbargoInviteNode:
        return CanAnswerEmbargoInviteNode(
            case_id=CASE_ID, invitee_id=INVITEE, embargo_id=EMBARGO_ID
        )

    @pytest.mark.spec("EP-09-003")
    def test_the_invitee_holding_the_case_answers(self):
        result = _run(_store(), self._node())
        assert result.status == Status.SUCCESS

    @pytest.mark.spec("EP-09-010")
    def test_a_store_that_is_not_the_invitee_does_not_answer(self, caplog):
        result = _run(
            _store(), self._node(), actor_id="https://example.org/actors/x"
        )
        assert result.status == Status.FAILURE
        assert not result.internal_error
        assert "is not the invitee" in caplog.text

    @pytest.mark.spec("EP-09-003")
    def test_an_invitee_without_the_case_does_not_answer(self, caplog):
        result = _run(_store(with_case=False), self._node())
        assert result.status == Status.FAILURE
        assert not result.internal_error
        assert "holds no copy of case" in caplog.text

    @pytest.mark.spec("EP-09-003")
    def test_an_invitee_without_the_embargo_does_not_answer(self, caplog):
        """The answer carries the Invite whole, which needs its embargo."""
        result = _run(_store(with_embargo=False), self._node())
        assert result.status == Status.FAILURE
        assert not result.internal_error
        assert "does not hold embargo" in caplog.text


class TestSendEmbargoInviteAnswerNode:
    @pytest.mark.spec("EP-09-003")
    @pytest.mark.spec("PCR-08-001")
    @pytest.mark.parametrize(
        ("accept", "type_"), [(True, "Accept"), (False, "Reject")]
    )
    def test_queues_the_answer_to_the_case_manager(self, accept, type_):
        dl = _store()

        result = _run(dl, _send(accept))

        assert result.status == Status.SUCCESS
        (answer,) = _queued(dl)
        assert answer.type_ == type_
        assert answer.actor == INVITEE
        assert answer.to == [MANAGER]

    @pytest.mark.spec("BT-14-001")
    def test_a_missing_factory_is_a_wiring_fault(self):
        dl = _store()
        result = BTBridge(datalayer=dl).execute_with_setup(
            tree=_send(True), actor_id=INVITEE
        )
        assert result.status == Status.FAILURE
        assert result.internal_error
        assert dl.outbox_list() == []

    @pytest.mark.spec("CM-24-006")
    def test_a_case_with_no_manager_is_a_fault(self):
        dl = _store(with_manager=False)
        result = _run(dl, _send(True))
        assert result.status == Status.FAILURE
        assert result.internal_error
        assert "CM-24-006" in (result.feedback_message or "")

    @pytest.mark.spec("EP-09-003")
    def test_a_missing_case_is_a_fault(self):
        result = _run(_store(with_case=False), _send(True))
        assert result.status == Status.FAILURE
        assert result.internal_error

    @pytest.mark.spec("EMB-15-001")
    def test_a_failed_accept_never_falls_through_to_reject(self):
        """The accept arm raises, so the Selector never tries the reject arm."""
        dl = _store()
        factory = MagicMock()
        factory.accept_embargo.side_effect = ValueError("factory broke")
        tree = py_trees.composites.Selector(
            "Answer", memory=False, children=[_send(True), _send(False)]
        )

        result = _run(dl, tree, factory=factory)

        assert result.status == Status.FAILURE
        assert result.internal_error
        factory.reject_embargo.assert_not_called()
        assert dl.outbox_list() == []
