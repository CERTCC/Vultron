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
from vultron.core.models._helpers import days_from_now_utc
from vultron.core.models.activity import VultronActivity
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.embargo_event import EmbargoEvent
from vultron.core.models.use_case_result import HandlerDisposition
from vultron.core.states.em import EM
from vultron.core.states.participant_embargo_consent import PEC
from vultron.core.use_cases.triggers.embargo import (
    SvcAcceptEmbargoUseCase,
    SvcProposeEmbargoRevisionUseCase,
)
from vultron.core.use_cases.triggers.requests import (
    AcceptEmbargoTriggerRequest,
    ProposeEmbargoRevisionTriggerRequest,
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

    def __init__(self, case_id: str, *, owner: str = OWNER) -> None:
        self.case_id = case_id
        manager_dl, _, _case, embargo = make_embargo_case_with_actor(
            case_id,
            owner,
            extra_participants=[PROPOSER, BYSTANDER],
            case_manager_actor_id=MANAGER,
        )
        case_read = cast(VulnerabilityCase, manager_dl.read(case_id))
        case_read.current_status.em.state = EM.ACTIVE
        case_read.active_embargo = embargo.id_
        manager_dl.save(case_read)
        # Every participant has signed the active embargo, so each is active
        # while it is in force and a case-content send reaches it (CM-10-004).
        for participant_id in case_read.actor_participant_index.values():
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
    """Proposal A, accept A, proposal B, accept B: both resolve in the replica."""
    net = _Network("https://example.org/cases/relay-replay-twice")

    first = _propose(net, "first", 90)
    _owner_answers(net)
    second = _propose(net, "second", 120)
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


def _manager_ports(net: _Network) -> dict[str, Any]:
    """The ports ``TriggerDispatcher`` hands a trigger run by the manager."""
    dl = net.stores[MANAGER]
    return {
        "trigger_activity": TriggerActivityAdapter(dl),
        "sync_port": SyncActivityAdapter(dl),
        "wire_render_port": As2WireRenderAdapter(),
    }


@pytest.mark.spec("EP-09-007")
@pytest.mark.spec("EP-09-008")
@pytest.mark.spec("RSH-08-004")
@pytest.mark.spec("TB-06-007")
def test_a_replica_follows_the_managing_owners_revision_by_trigger():
    """The owner is the CASE_MANAGER and decides by trigger (#4085).

    Its revision and its own acceptance are committed as ledger entries, so a
    replica that receives nothing but the ``Announce(CaseLedgerEntry)``
    fan-out converges ``ACTIVE → REVISE → ACTIVE`` with it.
    """
    net = _Network("https://example.org/cases/manager-owner", owner=MANAGER)
    dl = net.stores[MANAGER]
    dl.create(as_Service(id_=MANAGER, name="Coordinator"))

    SvcProposeEmbargoRevisionUseCase(
        dl,
        ProposeEmbargoRevisionTriggerRequest(
            actor_id=MANAGER,
            case_id=net.case_id,
            end_time=days_from_now_utc(90),
        ),
        **_manager_ports(net),
    ).execute()
    (revision_id,) = net.case(MANAGER).proposed_embargo_ids
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
