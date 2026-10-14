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
"""An embargo answer is idempotent per participant and invitation (#4597).

A repeated ``Accept`` or ``Reject`` of the same embargo Invite by the same
actor, under a new activity id, changes no state at the CASE_MANAGER, adds no
ledger entry and sends no message (CM-13-005, HP-01-003).  A *changed* answer
by the same actor is a consent change, not a repeat, and still flows; an
answer by a different participant is its own consent.

Every store is its own (TB-06-007), using the harness of
``test_embargo_relay_replay.py``.
"""

import json
from typing import Any, cast

import pytest

from vultron.adapters.outbox_sealed_body import dump_outbound_body
from vultron.core.behaviors.embargo.nodes.answer_repeat import (
    EmbargoAnswerNotRecordedNode,
)
from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.use_case_result import (
    HandlerDisposition,
    HandlerResult,
)
from vultron.core.states.cs import CS_pxa
from vultron.core.states.participant_embargo_consent import (
    EmbargoConsentState,
)
from vultron.errors import VultronWiringError
from vultron.wire.as2.factories import (
    em_accept_embargo_activity,
    em_reject_embargo_activity,
)

from ._ledger_network import BYSTANDER, MANAGER, OWNER, LedgerNetwork
from .test_embargo_relay_replay import _owner_answers, _propose

ACCEPT_EVENT = "accept_invite_to_embargo_on_case"
REJECT_EVENT = "reject_invite_to_embargo_on_case"


def _invited(net: LedgerNetwork, actor: str, suffix: str) -> tuple[str, str]:
    """A revision is proposed and *actor* holds its relayed Invite.

    Returns ``(embargo_id, invite_id)``.  The Invite is delivered, so the
    actor's replica auto-answers it; that answer is left in the actor's
    outbox, undelivered, and the test sends its own.
    """
    embargo_id = _propose(net, suffix, 90)
    net.deliver(MANAGER, to=actor, type_="Invite")
    invites = net.queued(MANAGER, to=actor, type_="Invite")
    return embargo_id, invites[-1].id_


def _answer(
    net: LedgerNetwork, actor: str, invite_id: str, *, accept: bool, tag: str
) -> HandlerResult:
    """*actor* answers *invite_id* under a fresh activity id; the manager receives it."""
    proposal = cast(Any, net.stores[actor].read(invite_id))
    build = (
        em_accept_embargo_activity if accept else em_reject_embargo_activity
    )
    activity = build(
        proposal,
        context=net.case_id,
        actor=actor,
        to=[MANAGER],
        id_=f"{actor}/answers/{tag}",
    )
    return cast(
        HandlerResult,
        net.receive(MANAGER, json.loads(dump_outbound_body(activity))),
    )


def _entries(net: LedgerNetwork) -> list[str]:
    return [
        str(obj.event_type)
        for obj in net.stores[MANAGER].list_objects("CaseLedgerEntry")
        if isinstance(obj, CaseLedgerEntry)
    ]


def _consent(net: LedgerNetwork, actor: str, embargo_id: str) -> str:
    case = net.case(MANAGER)
    participant = net.stores[MANAGER].read(case.actor_participant_index[actor])
    assert isinstance(participant, CaseParticipant)
    return participant.consent_for(embargo_id)


def _snapshot(net: LedgerNetwork) -> dict[str, Any]:
    """Everything a repeat must leave as it was at the CASE_MANAGER."""
    dl = net.stores[MANAGER]
    case = net.case(MANAGER)
    rows = {}
    for member, participant_id in case.actor_participant_index.items():
        participant = dl.read(participant_id)
        assert isinstance(participant, CaseParticipant)
        rows[member] = [r.model_dump() for r in participant.embargo_consents]
    return {
        "entries": _entries(net),
        "outbox": list(dl.outbox_list()),
        "rows": rows,
        "case": case.model_dump(exclude={"updated"}),
    }


@pytest.mark.spec("CM-13-005")
@pytest.mark.spec("HP-01-003")
@pytest.mark.parametrize("accept", [True, False], ids=["accept", "reject"])
def test_a_repeat_answer_under_a_new_id_changes_nothing(accept: bool):
    """A second identical answer adds no entry, no Announce, no state."""
    net = LedgerNetwork(
        f"https://example.org/cases/answer-repeat-{'a' if accept else 'r'}"
    )
    embargo_id, invite_id = _invited(net, BYSTANDER, "repeat")
    expected = (
        EmbargoConsentState.AGREED if accept else EmbargoConsentState.DECLINED
    )

    first = _answer(net, BYSTANDER, invite_id, accept=accept, tag="1")
    assert first.disposition is HandlerDisposition.APPLIED, first.reason
    assert _consent(net, BYSTANDER, embargo_id) == expected
    before = _snapshot(net)

    again = _answer(net, BYSTANDER, invite_id, accept=accept, tag="2")

    assert again.disposition is HandlerDisposition.SKIPPED, again.reason
    after = _snapshot(net)
    assert after["entries"] == before["entries"]
    assert after["outbox"] == before["outbox"]
    assert after["rows"] == before["rows"]
    assert after["case"] == before["case"]


@pytest.mark.spec("CM-13-005")
@pytest.mark.parametrize("accept", [True, False], ids=["accept", "reject"])
def test_another_participants_answer_is_still_its_own_consent(accept: bool):
    """The guard is per actor: a second participant's answer is recorded."""
    net = LedgerNetwork(
        f"https://example.org/cases/answer-other-{'a' if accept else 'r'}"
    )
    event = ACCEPT_EVENT if accept else REJECT_EVENT
    expected = (
        EmbargoConsentState.AGREED if accept else EmbargoConsentState.DECLINED
    )
    embargo_id, bystander_invite = _invited(net, BYSTANDER, "two-actors")
    net.deliver(MANAGER, to=OWNER, type_="Invite")
    (owner_invite,) = net.queued(MANAGER, to=OWNER, type_="Invite")

    first = _answer(net, BYSTANDER, bystander_invite, accept=accept, tag="b")
    assert first.disposition is HandlerDisposition.APPLIED, first.reason
    committed = _entries(net).count(event)

    second = _answer(net, OWNER, owner_invite.id_, accept=accept, tag="o")

    assert second.disposition is HandlerDisposition.APPLIED, second.reason
    assert _entries(net).count(event) == committed + 1
    assert _consent(net, OWNER, embargo_id) == expected
    assert _consent(net, BYSTANDER, embargo_id) == expected


@pytest.mark.spec("CM-13-005")
@pytest.mark.spec("MSM-07-004")
@pytest.mark.parametrize(
    "activated", [False, True], ids=["proposed", "active"]
)
def test_a_reject_after_an_accept_is_a_consent_change(activated: bool):
    """Accept → Reject by one actor is a consent change, not a repeat.

    Rejecting a *proposed* embargo after agreeing to it declines that
    embargo's row; rejecting the embargo *in force* is withdrawal
    (MSM-07-004, ADR-0093), the path a Reject takes until withdrawal moves to
    ``Leave(EmbargoEvent)`` (#4388).  Either way the row becomes ``DECLINED``
    and the answer is ledgered.
    """
    net = LedgerNetwork(
        "https://example.org/cases/answer-accept-then-reject"
        f"-{'active' if activated else 'proposed'}"
    )
    embargo_id, invite_id = _invited(net, BYSTANDER, "change-ar")
    accepted = _answer(net, BYSTANDER, invite_id, accept=True, tag="1")
    assert accepted.disposition is HandlerDisposition.APPLIED
    if activated:
        _owner_answers(net, embargo_id)
        assert net.case(MANAGER).active_embargo_id == embargo_id
    committed = _entries(net).count(REJECT_EVENT)

    rejected = _answer(net, BYSTANDER, invite_id, accept=False, tag="2")

    assert rejected.disposition is HandlerDisposition.APPLIED, rejected.reason
    assert _entries(net).count(REJECT_EVENT) == committed + 1
    assert _consent(net, BYSTANDER, embargo_id) == EmbargoConsentState.DECLINED


@pytest.mark.spec("CM-13-005")
@pytest.mark.spec("EMB-02-002")
def test_a_repeat_accept_on_a_public_case_sends_no_refusal():
    """The repeat guard runs before the P/X/A refusal, which sends an ER.

    An Accept recorded before the case went public, repeated after, changes
    nothing and is answered with nothing.
    """
    net = LedgerNetwork("https://example.org/cases/answer-repeat-pxa")
    _embargo_id, invite_id = _invited(net, BYSTANDER, "repeat-pxa")
    first = _answer(net, BYSTANDER, invite_id, accept=True, tag="1")
    assert first.disposition is HandlerDisposition.APPLIED, first.reason
    case = net.case(MANAGER)
    case.current_status.pxa.state = CS_pxa.Pxa
    net.stores[MANAGER].save(case)
    before = _snapshot(net)

    again = _answer(net, BYSTANDER, invite_id, accept=True, tag="2")

    assert again.disposition is HandlerDisposition.SKIPPED, again.reason
    assert net.queued(MANAGER, to=BYSTANDER, type_="Reject") == []
    assert _snapshot(net)["outbox"] == before["outbox"]
    assert _snapshot(net)["entries"] == before["entries"]


def test_the_repeat_guard_takes_only_an_answer_state():
    """Only AGREED and DECLINED are answers (CM-18-003)."""
    with pytest.raises(VultronWiringError):
        EmbargoAnswerNotRecordedNode(
            case_id="https://example.org/cases/c",
            embargo_id="https://example.org/cases/c/embargo_events/e",
            answering_actor_id=BYSTANDER,
            answer=EmbargoConsentState.INVITED,
        )


@pytest.mark.spec("CM-13-005")
@pytest.mark.spec("CM-18-003")
def test_an_accept_after_a_reject_is_not_treated_as_a_repeat():
    """Reject → Accept by one actor is not swallowed by the repeat guard.

    It is processed as an answer, so the CASE_MANAGER ledgers it.  The row
    stays ``DECLINED``: ``AGREE`` is not a legal PEC transition from
    ``DECLINED`` (CM-18-003), so an actor that declined agrees through a
    fresh re-invite (EMB-17).  That consent rule is unchanged here (#4597).
    """
    net = LedgerNetwork("https://example.org/cases/answer-reject-then-accept")
    embargo_id, invite_id = _invited(net, BYSTANDER, "change-ra")
    rejected = _answer(net, BYSTANDER, invite_id, accept=False, tag="1")
    assert rejected.disposition is HandlerDisposition.APPLIED
    committed = _entries(net).count(ACCEPT_EVENT)

    accepted = _answer(net, BYSTANDER, invite_id, accept=True, tag="2")

    assert accepted.disposition is HandlerDisposition.APPLIED, accepted.reason
    assert _entries(net).count(ACCEPT_EVENT) == committed + 1
    assert _consent(net, BYSTANDER, embargo_id) == EmbargoConsentState.DECLINED
