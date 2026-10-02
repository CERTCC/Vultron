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
"""Answers to a relayed embargo Invite, decided by the CASE_MANAGER (EP-09).

Every store is its own (TB-06-007), using the harness of
``test_embargo_relay_replay.py``: what the CASE_MANAGER decides about an answer
must be what every replica replays from its ledger broadcast, and an answer
the CASE_MANAGER cannot apply must not be committed at all, or the replica's
replay slot fails and every later entry buffers behind it (SYNC-12-001,
SYNC-14-001).
"""

import json
from typing import cast

import pytest

from vultron.adapters.driven.trigger_activity_adapter import (
    TriggerActivityAdapter,
    embargo as adapter_embargo,
)
from vultron.adapters.outbox_sealed_body import read_sealed_body_dict
from vultron.core.behaviors.embargo.nodes.relay import invite_rsvp_deadline
from vultron.core.models._helpers import days_from_now_utc
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.use_case_result import (
    HandlerDisposition,
    HandlerResult,
)
from vultron.core.states.cs import CS_pxa
from vultron.core.states.em import EM

from .test_embargo_relay_replay import (
    BYSTANDER,
    MANAGER,
    OWNER,
    _Network,
    _propose,
    _replay_to_bystander,
)


def _reject(net: _Network, actor: str, index: int = 0) -> HandlerResult:
    """*actor* rejects its *index*-th relayed Invite; the manager receives it."""
    net.deliver(MANAGER, to=actor, type_="Invite")
    invite = net.queued(MANAGER, to=actor, type_="Invite")[index]
    _, sealed = TriggerActivityAdapter(net.stores[actor]).reject_embargo(
        proposal_id=invite.id_, case_id=net.case_id, actor=actor, to=[MANAGER]
    )
    return cast(HandlerResult, net.receive(MANAGER, json.loads(sealed)))


def _deliver_all(net: _Network, to: str) -> None:
    for type_, verdict in net.deliver(MANAGER, to=to):
        assert verdict.disposition is HandlerDisposition.APPLIED, (
            type_,
            verdict.reason,
        )


@pytest.mark.spec("EP-09-007")
@pytest.mark.spec("SYNC-12-001")
def test_a_late_reject_is_refused_uncommitted_and_the_replica_keeps_up():
    """A Reject of an already-decided revision leaves no entry to stall on."""
    net = _Network("https://example.org/cases/answer-late-reject")
    first = _propose(net, "decided", 90)
    net.deliver(MANAGER, to=BYSTANDER, type_="Invite")
    assert _reject(net, OWNER).disposition is HandlerDisposition.APPLIED

    late = _reject(net, BYSTANDER)

    assert late.disposition is HandlerDisposition.REFUSED
    assert "nothing to reject" in (late.reason or "")
    second = _propose(net, "next", 120)
    _replay_to_bystander(net)
    for actor_id in (MANAGER, BYSTANDER):
        case = net.case(actor_id)
        assert case.current_status.em.state == EM.REVISE, actor_id
        assert case.proposed_embargo_ids == [second], actor_id
        assert first not in case.proposed_embargo_ids, actor_id


@pytest.mark.spec("EP-08-001")
@pytest.mark.spec("EP-08-003")
def test_the_owner_rejecting_one_of_two_revisions_keeps_the_other_open():
    net = _Network("https://example.org/cases/answer-two-open")
    _propose(net, "r1", 90)
    second = _propose(net, "r2", 120)

    assert _reject(net, OWNER).disposition is HandlerDisposition.APPLIED
    _replay_to_bystander(net)

    for actor_id in (MANAGER, BYSTANDER):
        case = net.case(actor_id)
        assert case.current_status.em.state == EM.REVISE, actor_id
        assert case.active_embargo_id == net.initial_embargo_id, actor_id
        assert case.proposed_embargo_ids == [second], actor_id


@pytest.mark.spec("EMB-04-002")
@pytest.mark.spec("TB-06-007")
def test_the_owner_rejecting_a_revision_after_disclosure_ends_the_embargo():
    """EJ with P/X/A set terminates (ET) in every store, not ACTIVE again."""
    net = _Network("https://example.org/cases/answer-after-disclosure")
    _propose(net, "late", 90)
    _deliver_all(net, BYSTANDER)
    net.deliver(MANAGER, to=OWNER, type_="Invite")
    for actor_id in (MANAGER, OWNER, BYSTANDER):
        dl = net.stores[actor_id]
        case = cast(VulnerabilityCase, dl.read(net.case_id))
        case.current_status.pxa = case.current_status.pxa.model_copy(
            update={"state": CS_pxa.Pxa}
        )
        dl.save(case)
    invite = net.queued(MANAGER, to=OWNER, type_="Invite")[0]
    _, sealed = TriggerActivityAdapter(net.stores[OWNER]).reject_embargo(
        proposal_id=invite.id_, case_id=net.case_id, actor=OWNER, to=[MANAGER]
    )

    verdict = net.receive(MANAGER, json.loads(sealed))

    assert verdict.disposition is HandlerDisposition.APPLIED, verdict.reason
    _deliver_all(net, BYSTANDER)
    _deliver_all(net, OWNER)
    for actor_id in (MANAGER, OWNER, BYSTANDER):
        case = net.case(actor_id)
        assert case.current_status.em.state == EM.EXITED, actor_id
        assert case.active_embargo_id is None, actor_id
        assert case.proposed_embargo_ids == [], actor_id


@pytest.mark.spec("BT-17-001")
@pytest.mark.spec("HP-01-005")
@pytest.mark.parametrize("answer", ["Accept", "Reject"])
def test_a_participant_handed_an_answer_refuses_it_and_writes_nothing(answer):
    """Only the CASE_MANAGER records an answer; a replica replays it.

    The answer is addressed to the CASE_MANAGER, so the bystander's copy is
    refused at the door before any tree runs (HP-01-005, ADR-0117).
    """
    net = _Network(f"https://example.org/cases/answer-misrouted-{answer}")
    revision = _propose(net, "misrouted", 90)
    _replay_to_bystander(net)
    net.deliver(MANAGER, to=OWNER, type_="Invite")
    if answer == "Accept":
        (activity,) = net.queued(OWNER, to=MANAGER, type_="Accept")
        body = read_sealed_body_dict(net.stores[OWNER], activity.id_)
    else:
        invite = net.queued(MANAGER, to=OWNER, type_="Invite")[0]
        _, sealed = TriggerActivityAdapter(net.stores[OWNER]).reject_embargo(
            proposal_id=invite.id_,
            case_id=net.case_id,
            actor=OWNER,
            to=[MANAGER],
        )
        body = json.loads(sealed)
    assert body is not None

    verdict = net.receive(BYSTANDER, body)

    assert verdict.disposition is HandlerDisposition.REFUSED
    assert "neither the sender nor a recipient" in (verdict.reason or "")
    assert BYSTANDER in (verdict.reason or "")
    case = net.case(BYSTANDER)
    assert case.current_status.em.state == EM.REVISE
    assert case.proposed_embargo_ids == [revision]


@pytest.mark.spec("CM-28-013")
@pytest.mark.spec("EP-09-007")
def test_the_relay_and_its_replay_record_the_same_rsvp_deadline(monkeypatch):
    """The invitee's deadline is the relayed Invite's ``endTime`` everywhere.

    The relay does not stamp a deadline yet (#3961), so the factory the relay
    calls is wrapped to stamp one, the way CM-28-012 will.
    """
    stamped = days_from_now_utc(30)
    factory = adapter_embargo.em_propose_embargo_activity

    def stamping_factory(*args, **kwargs):
        return factory(*args, rsvp_deadline=stamped, **kwargs)

    monkeypatch.setattr(
        adapter_embargo, "em_propose_embargo_activity", stamping_factory
    )
    net = _Network("https://example.org/cases/answer-rsvp-deadline")
    _propose(net, "deadline", 90)
    (invite,) = net.queued(MANAGER, to=BYSTANDER, type_="Invite")
    body = read_sealed_body_dict(net.stores[MANAGER], invite.id_)
    assert body is not None
    deadline = invite_rsvp_deadline(body)
    assert deadline is not None
    _replay_to_bystander(net)

    for actor_id in (MANAGER, BYSTANDER):
        dl = net.stores[actor_id]
        index = net.case(actor_id).actor_participant_index
        participant = dl.read(index[BYSTANDER])
        assert isinstance(participant, CaseParticipant)
        assert participant.invite_rsvp_deadline == deadline, actor_id
