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

The Reject is the receiver's own answer, and what bounds its emit is the
``ReceiverIsInviteeNode`` ahead of it, which admits the invitee alone and is
BT-17-008's second arm; neither refusal records an exemption.  The Reject
comes last, after the checks that decide whether it can be sent at all.
"""

import pytest

from vultron.core.behaviors.case.nodes.diversion_stage import (
    DiversionStage,
)
from vultron.core.behaviors.case.nodes.received_path import ReceivedPath
from vultron.core.behaviors.case.receive_activity_tree import (
    create_receive_activity_tree,
)
from vultron.core.behaviors.embargo.nodes.cascade import (
    PersistEmbargoEventNode,
)
from vultron.core.behaviors.embargo.nodes.invite_answer import (
    SendEmbargoInviteAnswerNode,
)
from vultron.core.behaviors.embargo.nodes.pxa_refusal import (
    EmbargoInviteNotYetRefusedNode,
    PxaBarsEmbargoNode,
    ReceiverIsInviteeNode,
    RefusalFactoryAvailableNode,
    SendEmbargoProposalRefusalNode,
)
from vultron.core.behaviors.embargo.refusal_tree import (
    PXA_ACCEPT_REFUSAL,
    PXA_INVITE_REFUSAL,
    pxa_accept_refusal,
    pxa_invite_refusal,
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
def test_the_invite_refusal_stores_checks_then_sends_the_reject_last() -> None:
    embargo = EmbargoEvent(
        id_=f"{_CASE}/embargo_events/e1",
        context=_CASE,
        end_time=days_from_now_utc(45),
    )
    refusal = _invite_refusal(embargo)

    assert refusal.name == PXA_INVITE_REFUSAL
    # Its host tree declares the manager and the participant-replica path, so
    # the declaration does not bound the Reject's emit; ReceiverIsInviteeNode
    # ahead of it does, so no exemption is recorded (BT-17-008, HP-01-038).
    assert refusal.emit_exemption is None
    assert isinstance(refusal.condition, PxaBarsEmbargoNode)
    assert [type(n) for n in refusal.effects] == [
        PersistEmbargoEventNode,
        ReceiverIsInviteeNode,
        RefusalFactoryAvailableNode,
        EmbargoInviteNotYetRefusedNode,
        SendEmbargoProposalRefusalNode,
    ]
    assert refusal.effects[-1].name == "SendEmbargoRefusal"


@pytest.mark.spec("EMB-01-002")
def test_an_invite_naming_its_terms_by_uri_stores_no_terms() -> None:
    types = [type(n) for n in _invite_refusal().effects]

    assert PersistEmbargoEventNode not in types
    assert types[0] is ReceiverIsInviteeNode


@pytest.mark.spec("EMB-02-004")
def test_the_accept_refusal_answers_the_accepter() -> None:
    refusal = pxa_accept_refusal(
        case_id=_CASE, invite_id=_INVITE, accepting_actor_id=_SENDER
    )

    assert refusal.name == PXA_ACCEPT_REFUSAL
    assert [type(n) for n in refusal.effects] == [
        RefusalFactoryAvailableNode,
        EmbargoInviteNotYetRefusedNode,
        SendEmbargoInviteAnswerNode,
    ]
    send = refusal.effects[-1]
    assert isinstance(send, SendEmbargoInviteAnswerNode)
    assert send._recipient_id == _SENDER


@pytest.mark.spec("CLP-10-026")
@pytest.mark.spec("BT-17-008")
@pytest.mark.spec("EMB-15-010")
@pytest.mark.spec("HP-01-038")
@pytest.mark.parametrize(
    ("refusal", "paths", "expected"),
    [
        pytest.param(
            _invite_refusal(),
            {ReceivedPath.CASE_MANAGER, ReceivedPath.PARTICIPANT_REPLICA},
            PXA_INVITE_REFUSAL,
            id="invite-refusal-on-both-paths",
        ),
        pytest.param(
            pxa_accept_refusal(
                case_id=_CASE, invite_id=_INVITE, accepting_actor_id=_SENDER
            ),
            {ReceivedPath.CASE_MANAGER},
            PXA_ACCEPT_REFUSAL,
            id="accept-refusal-on-the-manager-path",
        ),
    ],
)
def test_the_factory_builds_each_refusal_in_place(
    refusal, paths, expected: str
) -> None:
    """Each refusal builds in a tree declaring the paths its host declares.

    They do not share one: the Invite tree admits a non-manager receiver and
    so carries the emit exemption, while the Accept tree declares the
    CASE_MANAGER path alone and must not (BT-17-008, HP-01-038).
    """
    tree = create_receive_activity_tree(
        name="Probe",
        case_id=_CASE,
        paths=paths,
        precondition_guards=[refusal],
    )

    stages = [n for n in tree.iterate() if isinstance(n, DiversionStage)]
    assert [s.name for s in stages] == [expected]
