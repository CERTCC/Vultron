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
"""The revision relay converges every store through the ledger (EP-09-007).

Each actor has its own store (TB-06-007).  An activity crosses from one store
to another only as the sealed body the sender's outbox would deliver, parsed
and routed the way the inbox routes it.  A replica that never receives the
proposal or the owner's answer directly still reaches the CASE_MANAGER's
state, from the ``Announce(CaseLedgerEntry)`` broadcast alone (RSH-08-004,
ADR-0108, ADR-0113).
"""

import inspect
import json
from typing import Any, cast

import pytest

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driven.sync_activity_adapter import SyncActivityAdapter
from vultron.adapters.driven.trigger_activity_adapter import (
    TriggerActivityAdapter,
)
from vultron.adapters.driven.wire_render.as2 import As2WireRenderAdapter
from vultron.adapters.outbox_sealed_body import (
    dump_outbound_body,
    read_sealed_body_dict,
)
from vultron.core.behaviors.embargo.nodes import EMBARGO_TEARDOWN_EVENT_TYPE
from vultron.core.models._helpers import days_from_now_utc
from vultron.core.models.activity import VultronActivity
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.embargo_event import EmbargoEvent
from vultron.core.models.use_case_result import HandlerDisposition
from vultron.core.states.cs import CS_pxa
from vultron.core.states.em import EM
from vultron.core.states.participant_embargo_consent import PEC
from vultron.core.use_cases.triggers.embargo import (
    SvcAcceptEmbargoUseCase,
    SvcProposeEmbargoRevisionUseCase,
    SvcProposeEmbargoUseCase,
    SvcRejectEmbargoUseCase,
    SvcTerminateEmbargoUseCase,
)
from vultron.core.use_cases.triggers.requests import (
    AcceptEmbargoTriggerRequest,
    ProposeEmbargoRevisionTriggerRequest,
    ProposeEmbargoTriggerRequest,
    RejectEmbargoTriggerRequest,
    TerminateEmbargoTriggerRequest,
)
from vultron.semantic_registry import extract_event, use_case_map
from vultron.wire.as2.factories import em_propose_embargo_activity
from vultron.wire.as2.parser import parse_activity
from vultron.wire.as2.vocab.base.objects.actors import as_Service
from vultron.wire.as2.vocab.objects.embargo_event import as_EmbargoEvent

from .conftest import make_embargo_case_with_actor

MANAGER = "https://example.org/users/coord"
PROPOSER = "https://example.org/users/vendor"
#: The case owner: its answer decides a proposal (EP-09-005).
OWNER = "https://example.org/users/vendor-a"
#: A participant that is neither the proposer nor the owner.
BYSTANDER = "https://example.org/users/vendor-b"


class _Network:
    """One store per actor, and the outbox items each has delivered."""

    def __init__(
        self, case_id: str, *, owner: str = OWNER, em_state: EM = EM.ACTIVE
    ) -> None:
        self.case_id = case_id
        manager_dl, _, _case, embargo = make_embargo_case_with_actor(
            case_id,
            owner,
            extra_participants=[PROPOSER, BYSTANDER],
            case_manager_actor_id=MANAGER,
        )
        case_read = cast(VulnerabilityCase, manager_dl.read(case_id))
        case_read.current_status.em.state = em_state
        if em_state is EM.ACTIVE:
            case_read.active_embargo = embargo.id_
        manager_dl.save(case_read)
        # Every participant has signed the active embargo, so each is active
        # while it is in force and a case-content send reaches it (CM-10-004).
        # With no embargo in force every send reaches every participant.
        signatories = (
            case_read.actor_participant_index.values()
            if em_state is EM.ACTIVE
            else []
        )
        for participant_id in signatories:
            participant = cast(
                CaseParticipant, manager_dl.read(participant_id)
            )
            manager_dl.save(
                participant.model_copy(
                    update={"embargo_consent_state": PEC.SIGNATORY}
                )
            )
        self.initial_embargo_id = embargo.id_
        self.stores: dict[str, SqliteDataLayer] = {MANAGER: manager_dl}
        replicated = [
            case_id,
            embargo.id_,
            *(str(p) for p in case_read.actor_participant_index.values()),
        ]
        for actor_id in {owner, BYSTANDER} - {MANAGER}:
            replica = SqliteDataLayer("sqlite:///:memory:", actor_id=actor_id)
            for obj_id in replicated:
                obj = manager_dl.read(obj_id)
                if obj is not None:
                    replica.create(obj)
            self.stores[actor_id] = replica
        self._delivered: set[tuple[str, str]] = set()

    def receive(self, receiver: str, body: dict[str, Any]):
        """Route *body* into *receiver*'s store as the inbox routes it."""
        dl = self.stores[receiver]
        event = extract_event(parse_activity(body)).model_copy(
            update={"receiving_actor_id": receiver}
        )
        use_case = use_case_map()[event.semantic_type]
        offered: dict[str, Any] = {
            "sync_port": SyncActivityAdapter(dl),
            "trigger_activity": TriggerActivityAdapter(dl),
            "wire_render_port": As2WireRenderAdapter(),
        }
        accepted = inspect.signature(use_case).parameters
        ports = {k: v for k, v in offered.items() if k in accepted}
        return use_case(dl, event, **ports).execute()

    def queued(self, sender: str, *, to: str, type_: str | None = None):
        """*sender*'s outbox items addressed to *to*, oldest first."""
        dl = self.stores[sender]
        items = []
        for activity_id in dl.outbox_list():
            activity = cast(VultronActivity, dl.read(activity_id))
            recipients = [*(activity.to or []), *(activity.cc or [])]
            if to in recipients and (type_ is None or activity.type_ == type_):
                items.append(activity)
        return items

    def deliver(self, sender: str, *, to: str, type_: str | None = None):
        """Deliver every not-yet-delivered item *sender* queued for *to*."""
        verdicts = []
        for activity in self.queued(sender, to=to, type_=type_):
            key = (to, activity.id_)
            if key in self._delivered:
                continue
            self._delivered.add(key)
            body = read_sealed_body_dict(self.stores[sender], activity.id_)
            assert body is not None, f"'{activity.id_}' was never sealed"
            verdicts.append((activity.type_, self.receive(to, body)))
        return verdicts

    def case(self, actor_id: str) -> VulnerabilityCase:
        return cast(
            VulnerabilityCase, self.stores[actor_id].read(self.case_id)
        )


def _propose(net: _Network, suffix: str, days: int) -> str:
    """PROPOSER sends a revision to the CASE_MANAGER only (EP-09-001)."""
    revision = as_EmbargoEvent(
        id_=f"{net.case_id}/embargo_events/{suffix}",
        content=f"Terms {suffix}",
        context=net.case_id,
        end_time=days_from_now_utc(days),
    )
    proposal = em_propose_embargo_activity(
        revision,
        context=net.case_id,
        actor=PROPOSER,
        to=[MANAGER],
        id_=f"{net.case_id}/embargo_proposals/{suffix}",
    )
    verdict = net.receive(MANAGER, json.loads(dump_outbound_body(proposal)))
    assert verdict.disposition is HandlerDisposition.APPLIED, verdict.reason
    return revision.id_


def _owner_answers(net: _Network) -> None:
    """The owner gets its relayed Invite, answers, and the answer arrives."""
    net.deliver(MANAGER, to=OWNER, type_="Invite")
    answers = net.queued(OWNER, to=MANAGER, type_="Accept")
    assert answers, "the owner did not answer its relayed Invite"
    delivered = net.deliver(OWNER, to=MANAGER, type_="Accept")
    assert delivered, "the owner's answer was already delivered"
    for type_, verdict in delivered:
        assert verdict.disposition is HandlerDisposition.APPLIED, (
            type_,
            verdict.reason,
        )


def _replay_to_bystander(net: _Network) -> None:
    """The bystander receives the CASE_MANAGER's ledger broadcast only."""
    delivered = net.deliver(MANAGER, to=BYSTANDER, type_="Announce")
    assert delivered, "the CASE_MANAGER broadcast no ledger entry"
    for type_, verdict in delivered:
        assert verdict.disposition is HandlerDisposition.APPLIED, (
            type_,
            verdict.reason,
        )


@pytest.mark.spec("EP-09-007")
@pytest.mark.spec("RSH-08-004")
@pytest.mark.spec("TB-06-007")
def test_a_replica_follows_a_revision_from_proposal_to_activation():
    """ACTIVE → REVISE → ACTIVE in the manager's store and the replica's."""
    net = _Network("https://example.org/cases/relay-replay")

    revision_id = _propose(net, "revision", 90)
    _replay_to_bystander(net)

    for actor_id in (MANAGER, BYSTANDER):
        case = net.case(actor_id)
        assert case.current_status.em.state == EM.REVISE, actor_id
        assert case.active_embargo_id == net.initial_embargo_id, actor_id
        assert case.proposed_embargo_ids == [revision_id], actor_id

    _owner_answers(net)
    _replay_to_bystander(net)

    for actor_id in (MANAGER, BYSTANDER):
        case = net.case(actor_id)
        assert case.current_status.em.state == EM.ACTIVE, actor_id
        assert case.active_embargo_id == revision_id, actor_id
        assert case.proposed_embargo_ids == [], actor_id


@pytest.mark.spec("EP-09-007")
@pytest.mark.spec("SYNC-12-001")
def test_a_ledger_only_replica_resolves_two_successive_revisions():
    """Proposal A, accept A, proposal B, accept B: both resolve in the replica.

    Each revision is shorter than the terms it replaces, so every signatory
    carries over (ADR-0093) and the bystander's ledger stream is never paused.
    A longer revision lapses the bystander, which never answered its Invite,
    and the content gate then pauses its stream (CM-10-005; see
    ``test_a_lapsed_bystander_gets_its_invite_but_no_ledger_entry``).
    """
    net = _Network("https://example.org/cases/relay-replay-twice")

    first = _propose(net, "first", 30)
    _owner_answers(net)
    second = _propose(net, "second", 20)
    _owner_answers(net)
    _replay_to_bystander(net)

    manager, replica = net.case(MANAGER), net.case(BYSTANDER)
    assert manager.active_embargo_id == second
    assert replica.active_embargo_id == second
    assert replica.current_status.em.state == EM.ACTIVE
    assert replica.proposed_embargo_ids == []
    # Both terms resolve in a store seeded only from the ledger (EMB-18-003).
    for embargo_id in (first, second):
        assert isinstance(net.stores[BYSTANDER].read(embargo_id), EmbargoEvent)


@pytest.mark.spec("EP-09-007")
@pytest.mark.spec("RSH-08-004")
def test_a_participants_rejection_is_fanned_out_and_replayed():
    """The CASE_MANAGER's commit of a Reject reaches every other replica."""
    net = _Network("https://example.org/cases/relay-replay-reject")
    revision_id = _propose(net, "rejected", 90)
    net.deliver(MANAGER, to=BYSTANDER, type_="Invite")
    (invite,) = net.queued(MANAGER, to=BYSTANDER, type_="Invite")

    # The bystander answers Reject instead of its default Accept (EMB-15).
    _, sealed = TriggerActivityAdapter(net.stores[BYSTANDER]).reject_embargo(
        proposal_id=invite.id_,
        case_id=net.case_id,
        actor=BYSTANDER,
        to=[MANAGER],
    )
    verdict = net.receive(MANAGER, json.loads(sealed))
    assert verdict.disposition is HandlerDisposition.APPLIED, verdict.reason

    rejections = [
        activity
        for activity in net.queued(MANAGER, to=OWNER, type_="Announce")
        if (read_sealed_body_dict(net.stores[MANAGER], activity.id_) or {})
        .get("object", {})
        .get("eventType")
        == "reject_invite_to_embargo_on_case"
    ]
    assert len(rejections) == 1, "the Reject commit was not fanned out"
    # In chain order, so the Reject entry finds its predecessors (SYNC-14-001).
    delivered = net.deliver(MANAGER, to=OWNER, type_="Announce")
    assert len(delivered) >= 2
    for type_, replayed in delivered:
        assert replayed.disposition is HandlerDisposition.APPLIED, (
            type_,
            replayed.reason,
        )

    # The owner's replica records the bystander's refusal, and only that: a
    # participant's Reject is consent and decides nothing (EP-08-003).
    replica = net.stores[OWNER]
    case = net.case(OWNER)
    bystander = replica.read(case.actor_participant_index[BYSTANDER])
    assert isinstance(bystander, CaseParticipant)
    assert revision_id not in bystander.accepted_embargo_ids
    assert case.current_status.em.state == EM.REVISE
    assert case.proposed_embargo_ids == [revision_id]


@pytest.mark.spec("EP-09-007")
@pytest.mark.spec("EP-08-003")
@pytest.mark.spec("TB-06-007")
def test_the_owners_rejection_returns_every_store_to_the_prior_terms():
    """ACTIVE → REVISE → ACTIVE on the prior embargo when the owner rejects."""
    net = _Network("https://example.org/cases/relay-replay-owner-reject")
    _propose(net, "refused", 90)
    net.deliver(MANAGER, to=OWNER, type_="Invite")
    (invite,) = net.queued(MANAGER, to=OWNER, type_="Invite")

    _, sealed = TriggerActivityAdapter(net.stores[OWNER]).reject_embargo(
        proposal_id=invite.id_,
        case_id=net.case_id,
        actor=OWNER,
        to=[MANAGER],
    )
    verdict = net.receive(MANAGER, json.loads(sealed))
    assert verdict.disposition is HandlerDisposition.APPLIED, verdict.reason
    _replay_to_bystander(net)

    for actor_id in (MANAGER, BYSTANDER):
        case = net.case(actor_id)
        assert case.current_status.em.state == EM.ACTIVE, actor_id
        assert case.active_embargo_id == net.initial_embargo_id, actor_id
        assert case.proposed_embargo_ids == [], actor_id


def _set_pxa(net: _Network, actor_id: str) -> None:
    """Make the case public in *actor_id*'s store (P/X/A set)."""
    case = net.case(actor_id)
    case.current_status.pxa.state = CS_pxa.Pxa
    net.stores[actor_id].save(case)


def _consent_states(net: _Network, actor_id: str) -> dict[str, PEC]:
    """Every participant's consent state as *actor_id*'s store holds it."""
    case = net.case(actor_id)
    states: dict[str, PEC] = {}
    for member, participant_id in case.actor_participant_index.items():
        participant = net.stores[actor_id].read(participant_id)
        assert isinstance(participant, CaseParticipant)
        states[member] = participant.embargo_consent_state
    return states


@pytest.mark.spec("EMB-01-002")
@pytest.mark.spec("EP-09-003")
@pytest.mark.spec("TB-06-007")
def test_a_participant_with_pxa_set_rejects_a_relayed_invite_to_the_case_manager():
    """A public case refuses the relayed Invite and answers ER (#4104)."""
    net = _Network("https://example.org/cases/relay-replay-pxa")
    _propose(net, "public", 90)
    _set_pxa(net, OWNER)
    em_before = net.case(OWNER).current_status.em.state
    consent_before = _consent_states(net, OWNER)
    (invite,) = net.queued(MANAGER, to=OWNER, type_="Invite")

    ((_, verdict),) = net.deliver(MANAGER, to=OWNER, type_="Invite")

    assert verdict.disposition is HandlerDisposition.REFUSED
    assert verdict.reason is not None and "EMB-01-002" in verdict.reason
    (reject,) = net.queued(OWNER, to=MANAGER, type_="Reject")
    assert reject.to == [MANAGER]
    sealed = read_sealed_body_dict(net.stores[OWNER], reject.id_)
    assert sealed is not None
    assert sealed["object"]["id"] == invite.id_
    # The refusal moves no case EM or consent state (EP-09-003).
    assert net.case(OWNER).current_status.em.state == em_before
    assert _consent_states(net, OWNER) == consent_before
    # The ER reaches the CASE_MANAGER as a routable activity.
    ((type_, answered),) = net.deliver(OWNER, to=MANAGER, type_="Reject")
    assert answered.disposition is HandlerDisposition.APPLIED, (
        type_,
        answered.reason,
    )


@pytest.mark.spec("EMB-03-003")
@pytest.mark.spec("EMB-01-002")
@pytest.mark.spec("TB-06-007")
def test_a_participant_with_pxa_set_answers_a_revision_with_er_never_et():
    """A non-owner, non-manager answers a P/X/A revision with ER only.

    Termination is the case owner's or the delegated CASE_MANAGER's to
    initiate (EMB-03-003, EP-09-003, ADR-0113): the participant's store
    queues exactly one activity — the ER, to the CASE_MANAGER — and its
    EM state and active embargo stay as they were.
    """
    net = _Network("https://example.org/cases/relay-replay-pxa-revision")
    _propose(net, "public-revision", 90)
    _set_pxa(net, BYSTANDER)
    before = net.case(BYSTANDER)
    em_before = before.current_status.em.state
    active_before = before.active_embargo_id
    assert active_before is not None, "the Invite must be a revision"
    outbox_before = set(net.stores[BYSTANDER].outbox_list())

    ((_, verdict),) = net.deliver(MANAGER, to=BYSTANDER, type_="Invite")

    assert verdict.disposition is HandlerDisposition.REFUSED
    queued = [
        cast(VultronActivity, net.stores[BYSTANDER].read(activity_id))
        for activity_id in net.stores[BYSTANDER].outbox_list()
        if activity_id not in outbox_before
    ]
    assert [(a.type_, a.to) for a in queued] == [("Reject", [MANAGER])]
    after = net.case(BYSTANDER)
    assert after.current_status.em.state == em_before
    assert after.active_embargo_id == active_before


@pytest.mark.spec("EMB-01-002")
def test_a_bare_uri_invite_with_pxa_set_is_refused_without_raising(caplog):
    """No copy of the terms means no ER can be built: refuse, never raise."""
    net = _Network("https://example.org/cases/relay-replay-pxa-uri")
    _propose(net, "public-uri", 90)
    _set_pxa(net, OWNER)
    (invite,) = net.queued(MANAGER, to=OWNER, type_="Invite")
    body = read_sealed_body_dict(net.stores[MANAGER], invite.id_)
    assert body is not None
    body["object"] = body["object"]["id"]

    with caplog.at_level("WARNING"):
        verdict = net.receive(OWNER, body)

    assert verdict.disposition is HandlerDisposition.REFUSED
    assert verdict.reason is not None and "EMB-01-002" in verdict.reason
    assert verdict.reason is not None and "no ER sent" in verdict.reason
    assert net.queued(OWNER, to=MANAGER) == []
    assert net.stores[OWNER].read(invite.id_) is not None
    assert any(
        "by id only" in record.getMessage() and record.levelname == "WARNING"
        for record in caplog.records
    )


@pytest.mark.spec("EMB-02-002")
@pytest.mark.spec("TB-06-007")
def test_a_case_manager_with_pxa_set_rejects_an_owners_acceptance():
    """A public case at the CASE_MANAGER answers an Accept with ER."""
    net = _Network("https://example.org/cases/relay-replay-pxa-accept")
    _propose(net, "public-accept", 90)
    net.deliver(MANAGER, to=OWNER, type_="Invite")
    (invite,) = net.queued(MANAGER, to=OWNER, type_="Invite")
    _set_pxa(net, MANAGER)

    ((_, verdict),) = net.deliver(OWNER, to=MANAGER, type_="Accept")

    assert verdict.disposition is HandlerDisposition.REFUSED
    assert verdict.reason is not None and "EMB-02-002" in verdict.reason
    (reject,) = net.queued(MANAGER, to=OWNER, type_="Reject")
    assert reject.to == [OWNER]
    sealed = read_sealed_body_dict(net.stores[MANAGER], reject.id_)
    assert sealed is not None
    assert sealed["object"]["id"] == invite.id_


def _pxa_invite_body(
    net: _Network,
    sender: str,
    to: str,
    suffix: str,
    cc: list[str] | None = None,
):
    """An inline ``Invite(EmbargoEvent)`` from *sender* to *to* alone.

    *cc* names copy recipients that are not the invitee.
    """
    terms = as_EmbargoEvent(
        id_=f"{net.case_id}/embargo_events/{suffix}",
        content=f"Terms {suffix}",
        context=net.case_id,
        end_time=days_from_now_utc(90),
    )
    proposal = em_propose_embargo_activity(
        terms,
        context=net.case_id,
        actor=sender,
        to=[to],
        cc=cc,
        id_=f"{net.case_id}/embargo_proposals/{suffix}",
    )
    return proposal.id_, json.loads(dump_outbound_body(proposal))


@pytest.mark.spec("EMB-01-002")
@pytest.mark.spec("HP-01-003")
@pytest.mark.spec("TB-06-007")
@pytest.mark.xfail(
    strict=True,
    reason="#4140: the P/X/A refusal records no decision, so a re-delivered"
    " Invite is refused again and a second ER is queued",
)
def test_a_redelivered_invite_with_pxa_set_is_refused_once():
    """A re-delivery was answered on first arrival: no second ER."""
    net = _Network("https://example.org/cases/relay-replay-pxa-again")
    _propose(net, "public-again", 90)
    _set_pxa(net, OWNER)
    (invite,) = net.queued(MANAGER, to=OWNER, type_="Invite")
    body = read_sealed_body_dict(net.stores[MANAGER], invite.id_)
    assert body is not None

    first = net.receive(OWNER, body)
    again = net.receive(OWNER, body)

    assert first.disposition is HandlerDisposition.REFUSED
    assert again.disposition is HandlerDisposition.SKIPPED
    assert len(net.queued(OWNER, to=MANAGER, type_="Reject")) == 1


@pytest.mark.spec("EMB-01-002")
@pytest.mark.spec("HP-01-003")
def test_an_invite_answered_before_pxa_is_not_contradicted_on_redelivery():
    """An Invite accepted before the case went public gets no later ER."""
    net = _Network("https://example.org/cases/relay-replay-pxa-late")
    _propose(net, "late", 90)
    (invite,) = net.queued(MANAGER, to=OWNER, type_="Invite")
    body = read_sealed_body_dict(net.stores[MANAGER], invite.id_)
    assert body is not None
    net.deliver(MANAGER, to=OWNER, type_="Invite")
    assert net.queued(OWNER, to=MANAGER, type_="Accept")
    _set_pxa(net, OWNER)

    verdict = net.receive(OWNER, body)

    assert verdict.disposition is HandlerDisposition.SKIPPED
    assert net.queued(OWNER, to=MANAGER, type_="Reject") == []


@pytest.mark.spec("EMB-01-002")
@pytest.mark.spec("EP-09-003")
@pytest.mark.spec("PCR-08-001")
def test_a_participant_answers_a_peers_invite_with_pxa_set_to_the_case_manager():
    """The ER goes to the CASE_MANAGER, never to the peer that sent it."""
    net = _Network("https://example.org/cases/relay-replay-pxa-peer")
    _set_pxa(net, OWNER)
    invite_id, body = _pxa_invite_body(net, BYSTANDER, OWNER, "peer")

    verdict = net.receive(OWNER, body)

    assert verdict.disposition is HandlerDisposition.REFUSED
    assert net.queued(OWNER, to=BYSTANDER) == []
    (reject,) = net.queued(OWNER, to=MANAGER, type_="Reject")
    assert reject.to == [MANAGER]
    sealed = read_sealed_body_dict(net.stores[OWNER], reject.id_)
    assert sealed is not None
    assert sealed["object"]["id"] == invite_id


@pytest.mark.spec("EMB-01-002")
@pytest.mark.spec("HP-01-005")
def test_an_invite_with_pxa_set_addressed_to_another_actor_gets_no_er(caplog):
    """An unaddressed copy is refused at the door, and not answered.

    EMB-01-002's ER duty binds only the addressee (ADR-0117, #4132): a
    store named in neither ``to`` nor ``cc`` runs no tree, so P/X/A is
    never consulted and no ER is built.
    """
    net = _Network("https://example.org/cases/relay-replay-pxa-misrouted")
    _set_pxa(net, BYSTANDER)
    _, body = _pxa_invite_body(net, MANAGER, OWNER, "misrouted")

    with caplog.at_level("WARNING"):
        verdict = net.receive(BYSTANDER, body)

    assert verdict.disposition is HandlerDisposition.REFUSED
    assert verdict.reason is not None
    assert "neither the sender nor a recipient" in verdict.reason
    assert BYSTANDER in verdict.reason and OWNER in verdict.reason
    assert net.queued(BYSTANDER, to=MANAGER) == []
    assert net.queued(BYSTANDER, to=OWNER) == []
    assert not any(
        "EMB-01-002" in record.getMessage() for record in caplog.records
    )


@pytest.mark.spec("EMB-01-002")
@pytest.mark.spec("EP-09-010")
def test_a_cc_copy_of_an_invite_with_pxa_set_gets_no_er(caplog):
    """A ``cc`` recipient is addressed but is not the invitee: no ER.

    The copy passes the door check (HP-01-005) and is refused by the
    invitee check instead (EP-09-010); only the invitee answers.
    """
    net = _Network("https://example.org/cases/relay-replay-pxa-cc")
    _set_pxa(net, BYSTANDER)
    _, body = _pxa_invite_body(net, MANAGER, OWNER, "cc-copy", cc=[BYSTANDER])

    with caplog.at_level("WARNING"):
        verdict = net.receive(BYSTANDER, body)

    assert verdict.disposition is HandlerDisposition.REFUSED
    assert verdict.reason is not None and "EP-09-010" in verdict.reason
    assert net.queued(BYSTANDER, to=MANAGER) == []
    assert net.queued(BYSTANDER, to=OWNER) == []
    assert any(
        "EP-09-010" in record.getMessage() and record.levelname == "WARNING"
        for record in caplog.records
    )


@pytest.mark.spec("EMB-01-002")
@pytest.mark.spec("TB-06-007")
def test_a_case_manager_with_pxa_set_rejects_a_proposal_to_its_proposer():
    """The CASE_MANAGER answers the proposer that sent the Invite."""
    net = _Network("https://example.org/cases/relay-replay-pxa-manager")
    _set_pxa(net, MANAGER)
    invite_id, body = _pxa_invite_body(net, PROPOSER, MANAGER, "to-manager")

    verdict = net.receive(MANAGER, body)

    assert verdict.disposition is HandlerDisposition.REFUSED
    (reject,) = net.queued(MANAGER, to=PROPOSER, type_="Reject")
    assert reject.to == [PROPOSER]
    assert net.queued(MANAGER, to=OWNER, type_="Invite") == []
    sealed = read_sealed_body_dict(net.stores[MANAGER], reject.id_)
    assert sealed is not None
    assert sealed["object"]["id"] == invite_id


def _manager_ports(net: _Network) -> dict[str, Any]:
    """The ports ``TriggerDispatcher`` hands a trigger run by the manager."""
    dl = net.stores[MANAGER]
    return {
        "trigger_activity": TriggerActivityAdapter(dl),
        "sync_port": SyncActivityAdapter(dl),
        "wire_render_port": As2WireRenderAdapter(),
    }


def _managing_owner_network(case_id: str, **kwargs: Any) -> _Network:
    """A network whose case owner is the CASE_MANAGER and has an actor."""
    net = _Network(case_id, owner=MANAGER, **kwargs)
    net.stores[MANAGER].create(as_Service(id_=MANAGER, name="Coordinator"))
    return net


def _manager_revises(net: _Network, *, days: int = 90) -> str:
    """The managing owner proposes a revision by trigger; return its id."""
    SvcProposeEmbargoRevisionUseCase(
        net.stores[MANAGER],
        ProposeEmbargoRevisionTriggerRequest(
            actor_id=MANAGER,
            case_id=net.case_id,
            end_time=days_from_now_utc(days),
        ),
        **_manager_ports(net),
    ).execute()
    (revision_id,) = net.case(MANAGER).proposed_embargo_ids
    return revision_id


@pytest.mark.spec("EP-09-007")
@pytest.mark.spec("EP-09-008")
@pytest.mark.spec("RSH-08-004")
@pytest.mark.spec("TB-06-007")
def test_a_replica_follows_the_managing_owners_revision_by_trigger():
    """The owner is the CASE_MANAGER and decides by trigger (#4085).

    Its revision and its own acceptance are committed as ledger entries, so a
    replica that receives nothing but the ``Announce(CaseLedgerEntry)``
    fan-out converges ``ACTIVE → REVISE → ACTIVE`` with it.  The revision is
    shorter than the initial terms, so the bystander stays a signatory
    (ADR-0093) and its stream is not paused (CM-10-005).
    """
    net = _managing_owner_network("https://example.org/cases/manager-owner")
    dl = net.stores[MANAGER]

    revision_id = _manager_revises(net, days=30)
    # The manager mails itself nothing (CLP-10-001); each participant gets
    # its relayed Invite (EP-09-002).
    assert net.queued(MANAGER, to=MANAGER) == []
    assert len(net.queued(MANAGER, to=BYSTANDER, type_="Invite")) == 1
    _replay_to_bystander(net)

    for actor_id in (MANAGER, BYSTANDER):
        case = net.case(actor_id)
        assert case.current_status.em.state == EM.REVISE, actor_id
        assert case.active_embargo_id == net.initial_embargo_id, actor_id
        assert case.proposed_embargo_ids == [revision_id], actor_id

    SvcAcceptEmbargoUseCase(
        dl,
        AcceptEmbargoTriggerRequest(actor_id=MANAGER, case_id=net.case_id),
        **_manager_ports(net),
    ).execute()
    assert net.queued(MANAGER, to=MANAGER) == []
    _replay_to_bystander(net)

    for actor_id in (MANAGER, BYSTANDER):
        case = net.case(actor_id)
        assert case.current_status.em.state == EM.ACTIVE, actor_id
        assert case.active_embargo_id == revision_id, actor_id
        assert case.proposed_embargo_ids == [], actor_id


@pytest.mark.spec("CM-10-005")
@pytest.mark.spec("CM-10-006")
@pytest.mark.spec("EP-09-002")
@pytest.mark.spec("TB-06-007")
def test_a_lapsed_bystander_gets_its_invite_but_no_ledger_entry():
    """Longer terms lapse a silent signatory and pause its ledger stream.

    The managing owner activates a revision longer than the terms the
    bystander signed, before the bystander answers its Invite, so the
    bystander lapses (ADR-0093).  The content gate then withholds every
    ``Announce(CaseLedgerEntry)`` from it (CM-10-005), while its relayed
    Invite, which is embargo meta-protocol traffic, still reaches it
    directly.  Once it accepts, the paused stream is backfilled in log order
    and its replica converges on the new terms (CM-10-006).
    """
    net = _managing_owner_network("https://example.org/cases/lapsed-bystander")
    dl = net.stores[MANAGER]

    revision_id = _manager_revises(net, days=90)
    _replay_to_bystander(net)
    SvcAcceptEmbargoUseCase(
        dl,
        AcceptEmbargoTriggerRequest(actor_id=MANAGER, case_id=net.case_id),
        **_manager_ports(net),
    ).execute()

    assert _consent_states(net, MANAGER)[BYSTANDER] is PEC.LAPSED
    assert net.deliver(MANAGER, to=BYSTANDER, type_="Announce") == []
    assert net.case(BYSTANDER).current_status.em.state == EM.REVISE
    (invite,) = net.queued(MANAGER, to=BYSTANDER, type_="Invite")
    assert invite.to == [BYSTANDER]

    net.deliver(MANAGER, to=BYSTANDER, type_="Invite")
    delivered = net.deliver(BYSTANDER, to=MANAGER, type_="Accept")
    assert delivered, "the bystander did not answer its relayed Invite"
    for type_, verdict in delivered:
        assert verdict.disposition is HandlerDisposition.APPLIED, (
            type_,
            verdict.reason,
        )
    assert _consent_states(net, MANAGER)[BYSTANDER] is PEC.SIGNATORY
    _replay_to_bystander(net)

    replica = net.case(BYSTANDER)
    assert replica.current_status.em.state == EM.ACTIVE
    assert replica.active_embargo_id == revision_id
    assert replica.proposed_embargo_ids == []


@pytest.mark.spec("EP-09-007")
@pytest.mark.spec("EP-09-008")
@pytest.mark.spec("TB-06-007")
def test_a_replica_follows_the_managing_owners_first_proposal_by_trigger():
    """NONE → PROPOSED in the manager's store and the replica's (#4085)."""
    net = _managing_owner_network(
        "https://example.org/cases/manager-owner-propose", em_state=EM.NONE
    )

    SvcProposeEmbargoUseCase(
        net.stores[MANAGER],
        ProposeEmbargoTriggerRequest(
            actor_id=MANAGER,
            case_id=net.case_id,
            end_time=days_from_now_utc(90),
        ),
        **_manager_ports(net),
    ).execute()
    (proposal_id,) = net.case(MANAGER).proposed_embargo_ids
    assert net.queued(MANAGER, to=MANAGER) == []
    _replay_to_bystander(net)

    for actor_id in (MANAGER, BYSTANDER):
        case = net.case(actor_id)
        assert case.current_status.em.state == EM.PROPOSED, actor_id
        assert case.active_embargo_id is None, actor_id
        assert case.proposed_embargo_ids == [proposal_id], actor_id


@pytest.mark.spec("EP-09-007")
@pytest.mark.spec("EP-09-008")
@pytest.mark.spec("TB-06-007")
def test_a_replica_follows_the_managing_owners_rejection_by_trigger():
    """ACTIVE → REVISE → ACTIVE on the prior terms when the manager rejects."""
    net = _managing_owner_network(
        "https://example.org/cases/manager-owner-reject"
    )
    _manager_revises(net)

    SvcRejectEmbargoUseCase(
        net.stores[MANAGER],
        RejectEmbargoTriggerRequest(actor_id=MANAGER, case_id=net.case_id),
        **_manager_ports(net),
    ).execute()
    assert net.queued(MANAGER, to=MANAGER) == []
    _replay_to_bystander(net)

    for actor_id in (MANAGER, BYSTANDER):
        case = net.case(actor_id)
        assert case.current_status.em.state == EM.ACTIVE, actor_id
        assert case.active_embargo_id == net.initial_embargo_id, actor_id
        assert case.proposed_embargo_ids == [], actor_id


@pytest.mark.spec("EP-09-007")
@pytest.mark.spec("EP-09-008")
@pytest.mark.spec("EMB-19-001")
@pytest.mark.spec("VM-08-003")
@pytest.mark.spec("TB-06-007")
def test_a_replica_follows_the_managing_owners_termination_by_trigger():
    """ACTIVE → EXITED from the fan-out; the Remove is sealed as committed.

    The manager commits its own ``Remove(EmbargoEvent)``, so the sealed body
    names the case in ``context`` (VM-08-003), the committed snapshot is that
    body unchanged (OX-07-001), and it is addressed to every other
    participant, never to the manager itself (EMB-19-001, #4112).
    """
    net = _managing_owner_network(
        "https://example.org/cases/manager-owner-terminate"
    )

    SvcTerminateEmbargoUseCase(
        net.stores[MANAGER],
        TerminateEmbargoTriggerRequest(actor_id=MANAGER, case_id=net.case_id),
        **_manager_ports(net),
    ).execute()
    assert net.queued(MANAGER, to=MANAGER) == []
    (remove,) = net.queued(MANAGER, to=BYSTANDER, type_="Remove")
    sealed = read_sealed_body_dict(net.stores[MANAGER], remove.id_)
    assert sealed is not None
    assert sealed["context"] == net.case_id
    (entry,) = [
        obj
        for obj in net.stores[MANAGER].list_objects("CaseLedgerEntry")
        if isinstance(obj, CaseLedgerEntry)
        and str(obj.event_type) == EMBARGO_TEARDOWN_EVENT_TYPE
    ]
    assert entry.payload_snapshot == sealed

    _replay_to_bystander(net)

    for actor_id in (MANAGER, BYSTANDER):
        case = net.case(actor_id)
        assert case.current_status.em.state == EM.EXITED, actor_id
        assert case.active_embargo_id is None, actor_id


@pytest.mark.spec("CM-18-003")
@pytest.mark.spec("MSM-07-006")
@pytest.mark.spec("EMB-17-004")
@pytest.mark.spec("TB-06-007")
def test_termination_exits_every_participant_in_every_store():
    """Every record reads UNBOUND_EXITED on the manager and on a replica.

    Termination ends the embargo for everyone, the owner included, so no
    record is left able to sign it (ADR-0117).  UNBOUND_EXITED is terminal:
    every record, in both stores, refuses a later ``INVITE`` trigger.
    """
    from vultron.core.states.participant_embargo_consent import PEC_Trigger
    from vultron.errors import VultronInvalidStateTransitionError

    net = _managing_owner_network(
        "https://example.org/cases/manager-owner-terminate-pec"
    )
    SvcTerminateEmbargoUseCase(
        net.stores[MANAGER],
        TerminateEmbargoTriggerRequest(actor_id=MANAGER, case_id=net.case_id),
        **_manager_ports(net),
    ).execute()
    _replay_to_bystander(net)

    for actor_id in (MANAGER, BYSTANDER):
        states = _consent_states(net, actor_id)
        assert set(states) == {MANAGER, PROPOSER, BYSTANDER}, actor_id
        assert set(states.values()) == {PEC.UNBOUND_EXITED}, (
            actor_id,
            states,
        )
        for participant_id in net.case(
            actor_id
        ).actor_participant_index.values():
            participant = net.stores[actor_id].read(participant_id)
            assert isinstance(participant, CaseParticipant)
            assert participant.accepts_pec_trigger(PEC_Trigger.INVITE) is False
            with pytest.raises(VultronInvalidStateTransitionError):
                participant.apply_pec_transition(PEC_Trigger.INVITE)
