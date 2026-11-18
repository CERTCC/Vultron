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
"""How a P/X/A refusal of an embargo Invite or Accept is read (ADR-0195).

The refusal's ``DiversionStage`` declares it, for the P/X/A condition's
reason, whether or not its ``Reject`` could be sent (EMB-01-002,
EMB-02-004, HP-01-003).  The shared ``pxa_refusal_reader`` reads only a
``Reject`` already sent (``SKIPPED``), and the Invite handler's reader adds
why no ``Reject`` went out when the receiver is not the invitee
(EP-09-010).  The statuses are set by hand: the nodes' own behavior is
tested beside them, and a run through the handler in
``test_embargo_relay_replay.py``.
"""

import py_trees
import pytest
from py_trees.common import Status

from vultron.core.behaviors.bridge import BTExecutionResult
from vultron.core.behaviors.case.nodes.diversion_stage import DiversionStage
from vultron.core.behaviors.case.received_run import (
    ReceivedOutcome,
    pxa_refusal_reader,
    read_outcome,
)
from vultron.core.behaviors.embargo.invite_received_tree import (
    EmbargoInviteSubjects,
)
from vultron.core.behaviors.embargo.nodes.pxa_refusal import (
    EmbargoInviteNotYetRefusedNode,
    ReceiverIsInviteeNode,
)
from vultron.core.behaviors.embargo.refusal_tree import (
    PXA_INVITE_REFUSAL,
    pxa_invite_refusal,
)
from vultron.core.models.use_case_result import HandlerDisposition
from vultron.core.use_cases.received.embargo.invite import _refusal_reader

_CASE = "https://example.org/cases/pxa-reading"
_INVITE = "https://example.org/activities/pxa-reading-invite"
_INVITEE = "https://example.org/actors/invitee"
_RECEIVER = "https://example.org/actors/receiver"
_REASON = f"EMB-01-002: P/X/A set on case '{_CASE}'; embargo proposal rejected"
_WHERE = f"Invite(EmbargoEvent) '{_INVITE}' on case '{_CASE}'"
_SUBJECTS = EmbargoInviteSubjects(
    embargo_id="https://example.org/embargoes/e",
    invitee_id=_INVITEE,
    attributed_to=None,
)


def _diverted(failed: type[py_trees.behaviour.Behaviour] | None):
    """A run the P/X/A Invite refusal diverted.

    *failed* names the answer's node that failed, so the answer stopped
    there; ``None`` means the answer completed.
    """
    diversion = pxa_invite_refusal(
        case_id=_CASE,
        invite_id=_INVITE,
        invitee_id=_INVITEE,
        sender_id="https://example.org/actors/manager",
        embargo=None,
    )
    effects = py_trees.composites.Sequence(
        name="Answer", memory=False, children=list(diversion.effects)
    )
    stage = DiversionStage(
        diversion.name,
        diversion.condition,
        effects,
        refuses=diversion.refuses,
        refuses_unanswered=diversion.refuses_unanswered,
    )
    root = py_trees.composites.Sequence(
        name="InviteToEmbargoOnCaseBT", memory=False, children=[stage]
    )
    diversion.condition.status = Status.SUCCESS
    diversion.condition.feedback_message = _REASON
    for node in effects.children:
        node.status = Status.SUCCESS
        if failed is not None and isinstance(node, failed):
            node.status = Status.FAILURE
            break
    effects.status = Status.FAILURE if failed else Status.SUCCESS
    stage.taken = True
    stage.status = Status.FAILURE
    root.status = Status.FAILURE
    return ReceivedOutcome.of(
        root,
        BTExecutionResult(status=Status.FAILURE),
        "InviteToEmbargoOnCaseBT",
        receiving_actor_id=_RECEIVER,
    )


@pytest.mark.spec("EMB-01-002", "HP-01-003")
@pytest.mark.parametrize(
    "failed",
    [None, ReceiverIsInviteeNode],
    ids=["answered", "not-the-invitee"],
)
def test_the_stage_declares_the_refusal_answered_or_not(failed) -> None:
    outcome = _diverted(failed)

    assert pxa_refusal_reader(PXA_INVITE_REFUSAL, _WHERE)(outcome) is None
    verdict = read_outcome(outcome)
    assert verdict.disposition is HandlerDisposition.REFUSED
    assert verdict.reason == _REASON


@pytest.mark.spec("EMB-01-002", "HP-01-003")
def test_the_invite_reading_leaves_an_answered_refusal_to_the_stage() -> None:
    outcome = _diverted(None)

    assert _refusal_reader(_INVITE, _CASE, _SUBJECTS)(outcome) is None
    verdict = read_outcome(
        outcome, reader=_refusal_reader(_INVITE, _CASE, _SUBJECTS)
    )
    assert verdict.disposition is HandlerDisposition.REFUSED
    assert verdict.reason == _REASON


@pytest.mark.spec("EMB-01-002", "EP-09-010")
def test_the_invite_reading_says_no_reject_went_to_another_invitee() -> None:
    verdict = read_outcome(
        _diverted(ReceiverIsInviteeNode),
        reader=_refusal_reader(_INVITE, _CASE, _SUBJECTS),
    )

    assert verdict.disposition is HandlerDisposition.REFUSED
    assert verdict.reason == (
        f"{_REASON}; no Reject sent, the Invite is addressed to"
        f" '{_INVITEE}' (EP-09-010)"
    )


@pytest.mark.spec("HP-01-014", "ID-04-005")
def test_a_reject_already_sent_is_skipped() -> None:
    outcome = _diverted(EmbargoInviteNotYetRefusedNode)

    verdict = read_outcome(
        outcome, reader=_refusal_reader(_INVITE, _CASE, _SUBJECTS)
    )

    assert verdict.disposition is HandlerDisposition.SKIPPED
    assert verdict.reason == (
        f"{_WHERE} not refused again: the Reject was already sent (HP-01-003)"
    )
