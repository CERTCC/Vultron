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
from collections import Counter
from datetime import UTC, datetime
from typing import Any, cast

import pytest
from py_trees.common import Status

from vultron.adapters.outbox_sealed_body import dump_outbound_body
from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.embargo.answer_trees import (
    accept_invite_to_embargo_tree,
)
from vultron.core.behaviors.embargo.nodes.answer_repeat import (
    EmbargoAnswerNotRecordedNode,
)
from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.embargo_consent_event_types import (
    UPDATE_EMBARGO_CONSENT_EVENT_TYPE,
)
from vultron.core.models.events.base import MessageSemantics
from vultron.core.models.rsvp_deadline import HONOUR_LATE_ACCEPT_EVENT_TYPE
from vultron.core.models.use_case_result import (
    HandlerDisposition,
    HandlerResult,
)
from vultron.core.states.cs import CS_pxa
from vultron.core.states.participant_embargo_consent import (
    EmbargoConsentState,
)
from vultron.core.use_cases.received._bt_verdict import find_node
from vultron.core.use_cases.received.embargo.accept import (
    AcceptInviteToEmbargoOnCaseReceivedUseCase,
)
from vultron.errors import VultronWiringError
from vultron.semantic_registry import extract_event
from vultron.wire.as2.factories import (
    em_accept_embargo_activity,
    em_reject_embargo_activity,
    withdraw_from_embargo_activity,
)
from vultron.wire.as2.parser import parse_activity

from ._ledger_network import BYSTANDER, MANAGER, OWNER, LedgerNetwork
from .test_embargo_relay_replay import _owner_answers, _propose

ACCEPT_EVENT = "accept_invite_to_embargo_on_case"
REJECT_EVENT = "reject_invite_to_embargo_on_case"
WITHDRAW_EVENT = "withdraw_from_embargo_on_case"


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


def _answer_body(
    net: LedgerNetwork,
    actor: str,
    invite_id: str,
    *,
    accept: bool,
    tag: str,
    receiver: str = MANAGER,
) -> dict[str, Any]:
    """*actor*'s answer to *invite_id* under a fresh id, addressed to *receiver*."""
    proposal = cast(Any, net.stores[actor].read(invite_id))
    build = (
        em_accept_embargo_activity if accept else em_reject_embargo_activity
    )
    activity = build(
        proposal,
        context=net.case_id,
        actor=actor,
        to=sorted({MANAGER, receiver}),
        id_=f"{actor}/answers/{tag}",
    )
    return cast(dict[str, Any], json.loads(dump_outbound_body(activity)))


def _answer(
    net: LedgerNetwork,
    actor: str,
    invite_id: str,
    *,
    accept: bool,
    tag: str,
    receiver: str = MANAGER,
) -> HandlerResult:
    """*actor* answers *invite_id* under a fresh activity id; *receiver* gets it."""
    body = _answer_body(
        net, actor, invite_id, accept=accept, tag=tag, receiver=receiver
    )
    return cast(HandlerResult, net.receive(receiver, body))


def _withdraw(
    net: LedgerNetwork, actor: str, embargo_id: str, *, tag: str
) -> HandlerResult:
    """*actor* leaves *embargo_id* with ``Leave(EmbargoEvent)`` (MSM-07-010)."""
    embargo = cast(Any, net.stores[actor].read(embargo_id))
    activity = withdraw_from_embargo_activity(
        embargo,
        context=net.case_id,
        actor=actor,
        to=[MANAGER],
        id_=f"{actor}/withdrawals/{tag}",
    )
    body = cast(dict[str, Any], json.loads(dump_outbound_body(activity)))
    return cast(HandlerResult, net.receive(MANAGER, body))


def _entries(net: LedgerNetwork) -> list[str]:
    return [
        str(obj.event_type)
        for obj in net.stores[MANAGER].list_objects("CaseLedgerEntry")
        if isinstance(obj, CaseLedgerEntry)
    ]


def _consent(
    net: LedgerNetwork, actor: str, embargo_id: str, *, store: str = MANAGER
) -> str:
    case = net.case(store)
    participant = net.stores[store].read(case.actor_participant_index[actor])
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
def test_a_reject_after_an_accept_is_a_consent_change():
    """Accept → Reject of a *proposed* embargo is a consent change, not a repeat.

    The row becomes ``DECLINED`` and the answer is ledgered.
    """
    net = LedgerNetwork("https://example.org/cases/answer-accept-then-reject")
    embargo_id, invite_id = _invited(net, BYSTANDER, "change-ar")
    accepted = _answer(net, BYSTANDER, invite_id, accept=True, tag="1")
    assert accepted.disposition is HandlerDisposition.APPLIED
    committed = _entries(net).count(REJECT_EVENT)

    rejected = _answer(net, BYSTANDER, invite_id, accept=False, tag="2")

    assert rejected.disposition is HandlerDisposition.APPLIED, rejected.reason
    assert _entries(net).count(REJECT_EVENT) == committed + 1
    assert _consent(net, BYSTANDER, embargo_id) == EmbargoConsentState.DECLINED


@pytest.mark.spec("MSM-07-004")
@pytest.mark.spec("MSM-07-010")
def test_a_reject_of_the_agreed_embargo_in_force_is_refused_leave_withdraws():
    """Accept → activation → Reject is refused: a Reject never withdraws.

    The refusal is decided before the commit, so nothing is ledgered and the
    row stays ``AGREED``; the signatory withdraws with ``Leave(EmbargoEvent)``.
    """
    net = LedgerNetwork("https://example.org/cases/answer-accept-then-leave")
    embargo_id, invite_id = _invited(net, BYSTANDER, "change-al")
    accepted = _answer(net, BYSTANDER, invite_id, accept=True, tag="1")
    assert accepted.disposition is HandlerDisposition.APPLIED
    _owner_answers(net, embargo_id)
    assert net.case(MANAGER).active_embargo_id == embargo_id
    entries = len(_entries(net))

    rejected = _answer(net, BYSTANDER, invite_id, accept=False, tag="2")

    assert rejected.disposition is HandlerDisposition.REFUSED
    assert "Leave(EmbargoEvent)" in (rejected.reason or "")
    assert len(_entries(net)) == entries
    assert _consent(net, BYSTANDER, embargo_id) == EmbargoConsentState.AGREED

    withdrawn = _withdraw(net, BYSTANDER, embargo_id, tag="3")

    assert withdrawn.disposition is HandlerDisposition.APPLIED, (
        withdrawn.reason
    )
    # The Leave, then its declined row as the CASE_MANAGER's own entry
    # (ADR-0124, CLP-07-013).
    assert _entries(net)[entries:] == [
        WITHDRAW_EVENT,
        UPDATE_EMBARGO_CONSENT_EVENT_TYPE,
    ]
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
@pytest.mark.spec("EMB-17-002")
@pytest.mark.parametrize(
    "activated", [False, True], ids=["proposed", "active"]
)
def test_an_accept_after_a_reject_records_the_new_answer(activated: bool):
    """Reject → Accept by one actor changes the recorded answer to ``AGREED``.

    The participant has just said it accepts, so its row moves straight from
    ``DECLINED`` to ``AGREED`` (CM-18-003): there is no re-invite step, real
    or bookkeeping, and no Invite is sent.  On the embargo in force the
    Accept follows a withdrawal
    (``Leave(EmbargoEvent)``, MSM-07-010), so the Accept is a late answer the CASE_MANAGER honours (EMB-17-002).
    """
    net = LedgerNetwork(
        "https://example.org/cases/answer-reject-then-accept"
        f"-{'active' if activated else 'proposed'}"
    )
    embargo_id, invite_id = _invited(net, BYSTANDER, "change-ra")
    if activated:
        agreed = _answer(net, BYSTANDER, invite_id, accept=True, tag="0")
        assert agreed.disposition is HandlerDisposition.APPLIED
        _owner_answers(net, embargo_id)
        assert net.case(MANAGER).active_embargo_id == embargo_id
        declined = _withdraw(net, BYSTANDER, embargo_id, tag="1")
    else:
        declined = _answer(net, BYSTANDER, invite_id, accept=False, tag="1")
    assert declined.disposition is HandlerDisposition.APPLIED, declined.reason
    assert _consent(net, BYSTANDER, embargo_id) == EmbargoConsentState.DECLINED
    entries = _entries(net)
    invites = net.queued(MANAGER, to=BYSTANDER, type_="Invite")

    accepted = _answer(net, BYSTANDER, invite_id, accept=True, tag="2")

    assert accepted.disposition is HandlerDisposition.APPLIED, accepted.reason
    assert _consent(net, BYSTANDER, embargo_id) == EmbargoConsentState.AGREED
    # Proposed: the Accept's own entry records the change.  Active: the
    # CASE_MANAGER's honour decision, then the AGREED row it commits as its
    # own Update(EmbargoConsent) entry (CLP-07-013, ADR-0124).
    added = Counter(_entries(net)) - Counter(entries)
    assert added == Counter(
        [HONOUR_LATE_ACCEPT_EVENT_TYPE, UPDATE_EMBARGO_CONSENT_EVENT_TYPE]
        if activated
        else [MessageSemantics.ACCEPT_INVITE_TO_EMBARGO_ON_CASE.value]
    )
    assert net.queued(MANAGER, to=BYSTANDER, type_="Invite") == invites


@pytest.mark.spec("CM-13-005")
@pytest.mark.spec("EMB-17-003")
def test_an_accept_after_a_reject_of_replaced_terms_is_invited_to_the_current():
    """A changed answer to terms no longer current is not recorded on them.

    The bystander withdraws from embargo B, and B is then replaced by C.  Its
    Accept of B's Invite is an Accept of stale terms: B's row stays
    ``DECLINED``, and the CASE_MANAGER invites it to C instead (EMB-17-003).
    """
    net = LedgerNetwork("https://example.org/cases/answer-ra-replaced")
    stale_id, invite_id = _invited(net, BYSTANDER, "change-stale")
    agreed = _answer(net, BYSTANDER, invite_id, accept=True, tag="0")
    assert agreed.disposition is HandlerDisposition.APPLIED
    _owner_answers(net, stale_id)
    withdrawn = _withdraw(net, BYSTANDER, stale_id, tag="1")
    assert withdrawn.disposition is HandlerDisposition.APPLIED, (
        withdrawn.reason
    )
    current_id = _propose(net, "change-current", 120)
    _owner_answers(net, current_id)
    assert net.case(MANAGER).active_embargo_id == current_id
    invites = len(net.queued(MANAGER, to=BYSTANDER, type_="Invite"))

    accepted = _answer(net, BYSTANDER, invite_id, accept=True, tag="2")

    assert accepted.disposition is HandlerDisposition.APPLIED, accepted.reason
    assert _consent(net, BYSTANDER, stale_id) == EmbargoConsentState.DECLINED
    assert _consent(net, BYSTANDER, current_id) == EmbargoConsentState.INVITED
    fresh = net.queued(MANAGER, to=BYSTANDER, type_="Invite")[invites:]
    assert [cast(Any, i).object_.id_ for i in fresh] == [current_id]


@pytest.mark.spec("CM-13-005")
@pytest.mark.spec("HP-01-005")
def test_a_repeat_at_a_replica_is_refused_not_skipped():
    """Only the CASE_MANAGER treats a repeat as a no-op.

    A replica that holds the recorded answer still refuses the copy, because
    it holds no role to act on it (HP-01-005), so the repeat guard does not
    turn the refusal into a ``SKIPPED``.
    """
    net = LedgerNetwork("https://example.org/cases/answer-repeat-replica")
    embargo_id, invite_id = _invited(net, BYSTANDER, "repeat-replica")
    first = _answer(net, BYSTANDER, invite_id, accept=True, tag="1")
    assert first.disposition is HandlerDisposition.APPLIED, first.reason
    net.deliver(MANAGER, to=OWNER, type_="Announce")
    assert (
        _consent(net, BYSTANDER, embargo_id, store=OWNER)
        == EmbargoConsentState.AGREED
    )

    again = _answer(
        net, BYSTANDER, invite_id, accept=True, tag="2", receiver=OWNER
    )

    assert again.disposition is HandlerDisposition.REFUSED, again.reason


def _guard(
    net: LedgerNetwork,
    actor: str,
    embargo_id: str,
    answer: EmbargoConsentState,
) -> tuple[EmbargoAnswerNotRecordedNode, Status]:
    node = EmbargoAnswerNotRecordedNode(
        case_id=net.case_id,
        embargo_id=embargo_id,
        answering_actor_id=actor,
        answer=answer,
    )
    result = BTBridge(datalayer=net.stores[MANAGER]).execute_with_setup(
        tree=node, actor_id=MANAGER
    )
    return node, result.status


@pytest.mark.spec("CM-13-005")
@pytest.mark.parametrize(
    "answer",
    [EmbargoConsentState.AGREED, EmbargoConsentState.DECLINED],
    ids=["accept", "reject"],
)
def test_the_repeat_guard_admits_an_answer_with_no_recorded_one(
    answer: EmbargoConsentState,
):
    """No participant record, or no row for the embargo, is not a repeat."""
    net = LedgerNetwork(f"https://example.org/cases/answer-guard-{answer}")
    embargo_id, _invite_id = _invited(net, BYSTANDER, "guard")

    stranger, stranger_status = _guard(
        net, "https://example.org/actors/stranger", embargo_id, answer
    )
    unknown, unknown_status = _guard(
        net, BYSTANDER, f"{net.case_id}/embargo_events/unknown", answer
    )

    assert stranger_status is Status.SUCCESS and not stranger.is_repeat
    assert unknown_status is Status.SUCCESS and not unknown.is_repeat


@pytest.mark.spec("CM-13-005")
def test_the_accept_trees_own_repeat_guard_stops_a_repeat():
    """The in-tree guard is the one repeat check: no handler check precedes it."""
    net = LedgerNetwork("https://example.org/cases/answer-guard-tree")
    embargo_id, invite_id = _invited(net, BYSTANDER, "guard-tree")
    first = _answer(net, BYSTANDER, invite_id, accept=True, tag="1")
    assert first.disposition is HandlerDisposition.APPLIED, first.reason
    entries = _entries(net)
    tree = accept_invite_to_embargo_tree(
        case_id=net.case_id,
        embargo_id=embargo_id,
        accepting_actor_id=BYSTANDER,
        invite_id=invite_id,
        sender_rule=AcceptInviteToEmbargoOnCaseReceivedUseCase.sender_entitlement,
        now=datetime.now(tz=UTC),
        published=datetime.now(tz=UTC).isoformat(),
        expiry_out={},
    )

    event = extract_event(
        parse_activity(
            _answer_body(net, BYSTANDER, invite_id, accept=True, tag="2")
        )
    ).model_copy(update={"receiving_actor_id": MANAGER})

    result = BTBridge(datalayer=net.stores[MANAGER]).execute_with_setup(
        tree=tree, actor_id=MANAGER, activity=event
    )

    assert result.status is Status.FAILURE
    guard = find_node(tree, EmbargoAnswerNotRecordedNode)
    assert guard is not None and guard.is_repeat
    assert _entries(net) == entries
