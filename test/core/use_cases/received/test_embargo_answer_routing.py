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
from datetime import UTC, datetime, timedelta
from typing import cast

import pytest
from py_trees.common import Status

from vultron.adapters.driven.trigger_activity_adapter import (
    TriggerActivityAdapter,
)
from vultron.adapters.outbox_sealed_body import read_sealed_body_dict
from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.embargo.expiry_tree import (
    create_reinvite_stale_accepter_tree,
)
from vultron.core.behaviors.embargo.nodes.relay import invite_rsvp_deadline
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.rsvp_deadline import (
    EMBARGO_REINVITE_EVENT_TYPE,
    INVITE_EXPIRED_EVENT_TYPE,
    INVITE_EXPIRED_NOOP_EVENT_TYPE,
)
from vultron.core.models.use_case_result import (
    HandlerDisposition,
    HandlerResult,
)
from vultron.core.states.cs import CS_pxa
from vultron.core.states.em import EM
from vultron.core.states.participant_embargo_consent import PEC

from .test_embargo_relay_replay import (
    BYSTANDER,
    MANAGER,
    OWNER,
    _Network,
    _owner_answers,
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


def _entries(
    net: _Network, actor: str, event_type: str
) -> list[CaseLedgerEntry]:
    return [
        obj
        for obj in net.stores[actor].list_objects("CaseLedgerEntry")
        if isinstance(obj, CaseLedgerEntry)
        and str(obj.event_type) == event_type
    ]


def _event_types(net: _Network, actor: str) -> list[str]:
    return [
        str(obj.event_type)
        for obj in net.stores[actor].list_objects("CaseLedgerEntry")
        if isinstance(obj, CaseLedgerEntry)
    ]


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
    refused at the door before any tree runs (HP-01-005, ADR-0118).
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
@pytest.mark.spec("CM-28-012")
def test_the_relay_and_its_replay_record_the_same_rsvp_deadline():
    """The invitee's deadline is the relayed Invite's ``endTime`` everywhere.

    The CASE_MANAGER stamps it as the Invite's ``published`` plus its default
    window (CM-28-012), records it at commit, and the replica records the same
    value from the committed entry (CM-28-013).
    """
    net = _Network("https://example.org/cases/answer-rsvp-deadline")
    _propose(net, "deadline", 90)
    (invite,) = net.queued(MANAGER, to=BYSTANDER, type_="Invite")
    body = read_sealed_body_dict(net.stores[MANAGER], invite.id_)
    assert body is not None
    deadline = invite_rsvp_deadline(body)
    assert deadline is not None
    assert deadline - datetime.fromisoformat(body["published"]) == timedelta(
        days=7
    )
    _replay_to_bystander(net)

    for actor_id in (MANAGER, BYSTANDER):
        dl = net.stores[actor_id]
        index = net.case(actor_id).actor_participant_index
        participant = dl.read(index[BYSTANDER])
        assert isinstance(participant, CaseParticipant)
        assert participant.invite_rsvp_deadline == deadline, actor_id


@pytest.mark.spec("CM-28-014")
@pytest.mark.spec("CM-28-009")
@pytest.mark.spec("TB-06-007")
def test_the_managers_expiry_is_committed_and_replayed_by_a_replica():
    """A late Accept expires in the manager's store; a replica replays it.

    The replica never evaluates the deadline — its own record still holds the
    relayed 7-day one — it applies the CASE_MANAGER's committed expiry entry
    (CM-28-014, ADR-0118), an entry distinct from the Accept (CM-28-009).
    """
    net = _Network("https://example.org/cases/answer-lapse-replay")
    _propose(net, "lapse", 90)
    bystander_pid = net.case(MANAGER).actor_participant_index[BYSTANDER]
    # A signatory's consent survives a revision Invite (EP-09-004), so seed an
    # invitee that has not yet signed, everywhere; only the manager's record
    # holds a passed deadline.
    for actor_id in (MANAGER, OWNER):
        dl = net.stores[actor_id]
        participant = cast(CaseParticipant, dl.read(bystander_pid))
        update: dict[str, object] = {"embargo_consent_state": PEC.INVITED}
        if actor_id == MANAGER:
            update["invite_rsvp_deadline"] = datetime.now(tz=UTC) - timedelta(
                hours=1
            )
        dl.save(participant.model_copy(update=update))
    _replay_to_bystander(net)
    net.deliver(MANAGER, to=BYSTANDER, type_="Invite")
    (accept,) = net.queued(BYSTANDER, to=MANAGER, type_="Accept")
    body = read_sealed_body_dict(net.stores[BYSTANDER], accept.id_)
    assert body is not None

    net.receive(MANAGER, body)
    _deliver_all(net, OWNER)

    # The accepted embargo is a pending revision, not the current one, so the
    # manager also re-invites (EMB-17-003) and the replica ends re-invited; the
    # expiry it replayed on the way is the entry in its ledger.
    assert _event_types(net, OWNER).count(INVITE_EXPIRED_EVENT_TYPE) == 1
    replayed = cast(CaseParticipant, net.stores[OWNER].read(bystander_pid))
    assert replayed.embargo_consent_state == PEC.INVITED
    assert replayed.invite_rsvp_deadline is not None
    assert replayed.invite_rsvp_deadline > datetime.now(tz=UTC)


@pytest.mark.spec("EMB-17-003")
@pytest.mark.spec("CM-28-012")
@pytest.mark.spec("CM-28-013")
@pytest.mark.spec("EP-09-007")
@pytest.mark.spec("RSH-08-004")
@pytest.mark.spec("CLP-10-006")
@pytest.mark.spec("TB-06-007")
def test_the_managers_reinvite_is_committed_and_replayed_by_a_replica():
    """A late Accept of a stale embargo is re-invited; a replica learns it.

    The manager commits the fresh Invite as its own ledger entry before it
    queues it, so the ledger holds the entry before the outbox does
    (CLP-10-006).  The replica, replaying it, moves the invitee to ``INVITED``
    with the Invite's new deadline and leaves EM alone (CM-28-013, EP-09-007).
    """
    net = _Network("https://example.org/cases/answer-reinvite")
    _propose(net, "reinvite", 90)
    bystander_pid = net.case(MANAGER).actor_participant_index[BYSTANDER]
    _replay_to_bystander(net)
    net.deliver(MANAGER, to=BYSTANDER, type_="Invite")
    (accept,) = net.queued(BYSTANDER, to=MANAGER, type_="Accept")
    body = read_sealed_body_dict(net.stores[BYSTANDER], accept.id_)
    assert body is not None
    for actor_id in (MANAGER, OWNER):
        dl = net.stores[actor_id]
        participant = cast(CaseParticipant, dl.read(bystander_pid))
        update: dict[str, object] = {"embargo_consent_state": PEC.INVITED}
        if actor_id == MANAGER:
            update["invite_rsvp_deadline"] = datetime.now(tz=UTC) - timedelta(
                hours=1
            )
        dl.save(participant.model_copy(update=update))

    # The replica has replayed the proposal before the re-invite exists, so
    # what it holds then is what the re-invite entry must leave alone.
    _deliver_all(net, OWNER)
    before = net.case(OWNER)
    em_before = before.current_status.em.state
    proposals_before = list(before.proposed_embargo_ids)
    active_before = before.active_embargo_id
    assert em_before == EM.REVISE

    net.receive(MANAGER, body)
    _deliver_all(net, OWNER)

    manager_record = cast(
        CaseParticipant, net.stores[MANAGER].read(bystander_pid)
    )
    assert manager_record.embargo_consent_state == PEC.INVITED
    assert manager_record.invite_rsvp_deadline is not None
    assert manager_record.invite_rsvp_deadline > datetime.now(tz=UTC)
    assert _event_types(net, MANAGER).count(EMBARGO_REINVITE_EVENT_TYPE) == 1
    (entry,) = _entries(net, MANAGER, EMBARGO_REINVITE_EVENT_TYPE)
    snapshot = entry.payload_snapshot
    assert snapshot["actor"] == MANAGER
    assert snapshot.get("attributedTo") is None
    assert snapshot["to"] == [BYSTANDER]
    # The entry is the body the outbox delivers, with the deadline as endTime.
    assert (
        invite_rsvp_deadline(snapshot) == manager_record.invite_rsvp_deadline
    )

    # The replica's own store (TB-06-007): same consent and deadline, no EM move.
    assert _event_types(net, OWNER).count(EMBARGO_REINVITE_EVENT_TYPE) == 1
    replayed = cast(CaseParticipant, net.stores[OWNER].read(bystander_pid))
    assert replayed.embargo_consent_state == PEC.INVITED
    assert replayed.invite_rsvp_deadline == manager_record.invite_rsvp_deadline
    # The entry replays as a re-invite, never as a second proposal of the
    # embargo it names: EM, the open proposals and the active embargo stay put.
    after = net.case(OWNER)
    assert after.current_status.em.state == em_before
    assert list(after.proposed_embargo_ids) == proposals_before
    assert after.active_embargo_id == active_before


@pytest.mark.spec("EMB-17-003")
@pytest.mark.spec("CLP-10-020")
def test_a_reinvite_is_not_committed_by_a_store_that_is_not_the_manager():
    """The gate is the tree's: a non-manager tree writes and sends nothing."""
    net = _Network("https://example.org/cases/answer-reinvite-gated")
    _propose(net, "gated", 90)
    revision = net.case(MANAGER).active_embargo_id
    assert revision is not None
    dl = net.stores[OWNER]
    tree = create_reinvite_stale_accepter_tree(
        case_id=net.case_id, embargo_id=revision, invitee_id=BYSTANDER
    )

    result = BTBridge(
        datalayer=dl,
        trigger_activity=TriggerActivityAdapter(dl),
    ).execute_with_setup(tree=tree, actor_id=OWNER)

    assert result.status == Status.SUCCESS
    assert _event_types(net, OWNER).count(EMBARGO_REINVITE_EVENT_TYPE) == 0


@pytest.mark.spec("EMB-17-003")
@pytest.mark.spec("BT-17-001")
def test_a_late_accept_of_a_stale_embargo_reinvites_nobody_from_a_replica():
    """The use case, run on a store that is not the manager, commits nothing."""
    net = _Network("https://example.org/cases/answer-reinvite-replica")
    _propose(net, "replica", 90)
    _replay_to_bystander(net)
    net.deliver(MANAGER, to=BYSTANDER, type_="Invite")
    (accept,) = net.queued(BYSTANDER, to=MANAGER, type_="Accept")
    body = read_sealed_body_dict(net.stores[BYSTANDER], accept.id_)
    assert body is not None
    _deliver_all(net, OWNER)
    queued_before = len(net.queued(OWNER, to=BYSTANDER, type_="Invite"))

    net.receive(OWNER, body)

    assert _event_types(net, OWNER).count(EMBARGO_REINVITE_EVENT_TYPE) == 0
    assert (
        len(net.queued(OWNER, to=BYSTANDER, type_="Invite")) == queued_before
    )


@pytest.mark.spec("EMB-17-001")
@pytest.mark.spec("EMB-17-009")
@pytest.mark.spec("RSH-08-004")
@pytest.mark.spec("TB-06-007")
def test_the_managers_honour_decision_is_committed_and_replayed_by_a_replica():
    """Late Accept honours into SIGNATORY when the embargo is still active.

    When the invitee's RSVP deadline has passed and the embargo is still
    active and matching, the CASE_MANAGER commits an expiry entry
    (``INVITED → EXPIRED``, CM-28-009) and then a honour entry
    (``EXPIRED → SIGNATORY``, EMB-17-001, EMB-17-009).
    The replica replays both entries from the ledger broadcast without
    re-evaluating the deadline (RSH-08-004, ADR-0118).

    OWNER answers first so that ``active_embargo_id == embargo_id`` when
    BYSTANDER's late Accept arrives — that is the condition that routes to the
    honour branch rather than re-invite (EMB-17-002).
    """
    net = _Network("https://example.org/cases/answer-honour-late-accept")
    _propose(net, "honour", 90)
    bystander_pid = net.case(MANAGER).actor_participant_index[BYSTANDER]

    # Deliver proposal entries and the Invite to BYSTANDER so BYSTANDER can
    # generate its Accept for the revision embargo.
    # Capture the body before OWNER answers so we can submit it late.
    _replay_to_bystander(net)
    net.deliver(MANAGER, to=BYSTANDER, type_="Invite")
    (accept,) = net.queued(BYSTANDER, to=MANAGER, type_="Accept")
    body = read_sealed_body_dict(net.stores[BYSTANDER], accept.id_)
    assert body is not None

    # OWNER answers: EM REVISE → ACTIVE, active_embargo = revision.
    # Now active_embargo_id == embargo_id (both are the revision), so the
    # CASE_MANAGER takes the honour branch when the late Accept arrives
    # (EMB-17-001), not the re-invite branch (EMB-17-002).
    _owner_answers(net)

    # Seed BYSTANDER as INVITED with a passed deadline on MANAGER's store so
    # the expiry tree fires (NEEDS_APPLY=True → expiry entry committed).
    # OWNER's store holds INVITED with no deadline: the relay-entry Announces
    # replayed by _deliver_all sequence BYSTANDER correctly
    # (INVITED → EXPIRED via expiry, EXPIRED → SIGNATORY via honour).
    # Pre-seeding EXPIRED would cause the relay-invite replay to revert it to
    # INVITED (INVITE is legal from EXPIRED), creating an ordering hazard.
    for actor_id in (MANAGER, OWNER):
        dl = net.stores[actor_id]
        participant = cast(CaseParticipant, dl.read(bystander_pid))
        update: dict[str, object] = {"embargo_consent_state": PEC.INVITED}
        if actor_id == MANAGER:
            update["invite_rsvp_deadline"] = datetime.now(tz=UTC) - timedelta(
                hours=1
            )
        dl.save(participant.model_copy(update=update))

    net.receive(MANAGER, body)
    _deliver_all(net, OWNER)

    replayed = cast(CaseParticipant, net.stores[OWNER].read(bystander_pid))
    assert replayed.embargo_consent_state == PEC.SIGNATORY


@pytest.mark.spec("EMB-17-004")
@pytest.mark.spec("EMB-17-010")
@pytest.mark.spec("RSH-08-004")
@pytest.mark.spec("TB-06-007")
def test_the_managers_noop_decision_is_committed_and_replayed_by_a_replica():
    """Late Accept on exited embargo: no-op entry replayed, PEC ends EXPIRED.

    When a late Accept arrives with EM EXITED on the CASE_MANAGER's store,
    the CASE_MANAGER commits an expiry entry (``INVITED → EXPIRED``,
    CM-28-009) and then ``INVITE_EXPIRED_NOOP_EVENT_TYPE`` without any
    further PEC transition (EMB-17-004, EMB-17-010).
    After delivery the replica store's ledger has replayed past the no-op
    entry (asserting on the entry's presence so a silently skipped slot
    fails), and the participant PEC is ``EXPIRED`` (RSH-08-004, ADR-0118).
    """
    net = _Network("https://example.org/cases/answer-noop-late-accept")
    _propose(net, "noop", 90)
    bystander_pid = net.case(MANAGER).actor_participant_index[BYSTANDER]

    # Deliver proposal entries and the Invite to BYSTANDER so an Accept is
    # queued in BYSTANDER's outbox before we force EM to EXITED.
    _replay_to_bystander(net)
    net.deliver(MANAGER, to=BYSTANDER, type_="Invite")
    (accept,) = net.queued(BYSTANDER, to=MANAGER, type_="Accept")
    body = read_sealed_body_dict(net.stores[BYSTANDER], accept.id_)
    assert body is not None

    # Force EM EXITED on MANAGER's store so the noop branch fires (EMB-17-004).
    # Only MANAGER's store needs EXITED: the fan-out uses MANAGER's embargo
    # state (embargo_in_force=False → all participants are recipients), and
    # the expiry/noop replay nodes on OWNER's store have no EM dependency.
    # BYSTANDER's store keeps the original state — it is the sender, not the judge.
    dl_mgr = net.stores[MANAGER]
    case_mgr = net.case(MANAGER)
    case_mgr.current_status.em.state = EM.EXITED
    dl_mgr.save(case_mgr)

    # Seed BYSTANDER as INVITED with a passed deadline on MANAGER's store so
    # the expiry tree fires (NEEDS_APPLY=True → expiry entry committed).
    # OWNER's store holds INVITED with no deadline: the relay-entry Announces
    # replayed by _deliver_all sequence BYSTANDER correctly
    # (INVITED → EXPIRED via expiry; noop entry makes no further change).
    # Pre-seeding EXPIRED would cause the relay-invite replay to revert it to
    # INVITED (INVITE is legal from EXPIRED), creating an ordering hazard.
    for actor_id in (MANAGER, OWNER):
        dl = net.stores[actor_id]
        participant = cast(CaseParticipant, dl.read(bystander_pid))
        update: dict[str, object] = {"embargo_consent_state": PEC.INVITED}
        if actor_id == MANAGER:
            update["invite_rsvp_deadline"] = datetime.now(tz=UTC) - timedelta(
                hours=1
            )
        dl.save(participant.model_copy(update=update))

    net.receive(MANAGER, body)
    _deliver_all(net, OWNER)

    # The replica's participant PEC is EXPIRED: the expiry entry fired
    # (INVITED → EXPIRED) and the no-op entry made no further change.
    replayed = cast(CaseParticipant, net.stores[OWNER].read(bystander_pid))
    assert replayed.embargo_consent_state == PEC.EXPIRED
    # The replica's ledger contains the no-op entry, proving the replay slot
    # fired rather than silently skipping it (SYNC-12-001, RSH-08-004).
    noop_entries = [
        obj
        for obj in net.stores[OWNER].list_objects("CaseLedgerEntry")
        if isinstance(obj, CaseLedgerEntry)
        and str(obj.event_type) == INVITE_EXPIRED_NOOP_EVENT_TYPE
    ]
    assert len(noop_entries) == 1
