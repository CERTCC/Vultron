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

"""The P/X/A refusal diversions' shape (BT-17-008, CLP-10-026).

The ER is the receiver's own answer, so each refusal is a ``RECEIVER``
diversion whose one emit is admitted by the ``EMBARGO_INVITE_REFUSAL``
exemption; the factory refuses it otherwise.  The ER comes last, after the
checks that decide whether it can be sent at all.
"""

import pytest

from vultron.core.behaviors.case.nodes.diversion_stage import (
    DiversionGate,
    DiversionStage,
)
from vultron.core.behaviors.case.receive_activity_tree import (
    create_receive_activity_tree,
)
from vultron.core.behaviors.embargo.nodes.cascade import (
    PersistEmbargoEventNode,
)
from vultron.core.behaviors.embargo.nodes.invite_answer import (
    SendEmbargoInviteAnswerNode,
)
from vultron.core.behaviors.embargo.nodes.proposal import (
    CreateAndStoreInviteNode,
)
from vultron.core.behaviors.embargo.nodes.pxa_refusal import (
    EmbargoInviteNotYetRefusedNode,
    ErFactoryAvailableNode,
    PxaBarsEmbargoNode,
    ReceiverIsInviteeNode,
    SendEmbargoProposalRefusalNode,
)
from vultron.core.behaviors.embargo.refusal_tree import (
    PXA_ACCEPT_REFUSAL,
    PXA_INVITE_REFUSAL,
    pxa_accept_refusal,
    pxa_invite_refusal,
)
from vultron.core.behaviors.replica_emit_exemptions import (
    EMBARGO_INVITE_REFUSAL,
)
from vultron.core.models._helpers import days_from_now_utc
from vultron.core.models.embargo_event import EmbargoEvent

_CASE = "https://example.org/cases/refusal"
_INVITE = "https://example.org/activities/invite-refusal"
_INVITEE = "https://example.org/actors/invitee"
_SENDER = "https://example.org/actors/sender"


def _invite_refusal(embargo: EmbargoEvent | None = None):
    return pxa_invite_refusal(
        case_id=_CASE,
        invite_id=_INVITE,
        invitee_id=_INVITEE,
        sender_id=_SENDER,
        embargo=embargo,
    )


@pytest.mark.spec("BT-17-008")
@pytest.mark.spec("CLP-10-026")
def test_the_invite_refusal_stores_checks_then_sends_the_er_last() -> None:
    embargo = EmbargoEvent(
        id_=f"{_CASE}/embargo_events/e1",
        context=_CASE,
        end_time=days_from_now_utc(45),
    )
    refusal = _invite_refusal(embargo)

    assert refusal.name == PXA_INVITE_REFUSAL
    assert refusal.gate is DiversionGate.RECEIVER
    assert refusal.emit_exemption == EMBARGO_INVITE_REFUSAL
    assert isinstance(refusal.condition, PxaBarsEmbargoNode)
    assert [type(n) for n in refusal.effects] == [
        CreateAndStoreInviteNode,
        PersistEmbargoEventNode,
        ReceiverIsInviteeNode,
        ErFactoryAvailableNode,
        EmbargoInviteNotYetRefusedNode,
        SendEmbargoProposalRefusalNode,
    ]
    assert refusal.effects[-1].name == "SendEmbargoRefusalER"


@pytest.mark.spec("EMB-01-002")
def test_an_invite_naming_its_terms_by_uri_stores_no_terms() -> None:
    types = [type(n) for n in _invite_refusal().effects]

    assert PersistEmbargoEventNode not in types
    assert types[0] is CreateAndStoreInviteNode


@pytest.mark.spec("EMB-02-002")
def test_the_accept_refusal_answers_the_accepter() -> None:
    refusal = pxa_accept_refusal(
        case_id=_CASE, invite_id=_INVITE, accepting_actor_id=_SENDER
    )

    assert refusal.name == PXA_ACCEPT_REFUSAL
    assert [type(n) for n in refusal.effects] == [
        ErFactoryAvailableNode,
        EmbargoInviteNotYetRefusedNode,
        SendEmbargoInviteAnswerNode,
    ]
    send = refusal.effects[-1]
    assert isinstance(send, SendEmbargoInviteAnswerNode)
    assert send._recipient_id == _SENDER


@pytest.mark.spec("CLP-10-026")
@pytest.mark.spec("BT-17-008")
def test_the_factory_builds_each_refusal_in_place() -> None:
    tree = create_receive_activity_tree(
        name="Probe",
        case_id=_CASE,
        precondition_guards=[
            _invite_refusal(),
            pxa_accept_refusal(
                case_id=_CASE, invite_id=_INVITE, accepting_actor_id=_SENDER
            ),
        ],
    )

    stages = [n for n in tree.iterate() if isinstance(n, DiversionStage)]
    assert [s.name for s in stages] == [PXA_INVITE_REFUSAL, PXA_ACCEPT_REFUSAL]
