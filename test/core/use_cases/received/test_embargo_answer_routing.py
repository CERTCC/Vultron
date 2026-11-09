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

from test.support.embargo_register import terminate
from test.support.ledger import consent_row_updates
from test.support.owner_decision import owner_decision_body
from test.support.received import received_event
from test.support.refusal_notice import assert_no_refusal_notice
from vultron.adapters.driven.trigger_activity_adapter import (
    TriggerActivityAdapter,
)
from vultron.adapters.outbox_sealed_body import read_sealed_body_dict
from vultron.core.behaviors.embargo.nodes import EMBARGO_TEARDOWN_SEMANTIC_TYPE
from vultron.core.behaviors.embargo.nodes.late_accept import (
    LateAcceptChangesNothingNode,
)
from vultron.core.behaviors.embargo.proposer import embargo_proposer_id
from vultron.core.behaviors.embargo.rsvp_stamp import invite_rsvp_deadline
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.embargo_consent import EmbargoConsent
from vultron.core.models.embargo_termination import (
    EmbargoTermination,
    ThreatSignal,
)
from vultron.core.models.use_case_result import (
    HandlerDisposition,
    HandlerResult,
)
from vultron.core.states.cs import CS_pxa
from vultron.core.states.em import EM
from vultron.core.states.embargo_register import EmbargoRegisterStatus
from vultron.core.states.participant_embargo_consent import (
    EmbargoConsentState,
)
from vultron.errors import VultronBTInternalError
from vultron.wire.as2.parser import parse_activity

from .test_embargo_relay_replay import (
    BYSTANDER,
    MANAGER,
    OWNER,
    _Network,
    _owner_answers,
    _owner_decides,
    _propose,
    _replay_to_bystander,
)


def _invited_only(
    participant: CaseParticipant,
    embargo_id: str,
    rsvp_deadline: datetime | None = None,
) -> list[EmbargoConsent]:
    """The rows of an invitee that has signed nothing but its *embargo_id* invite.

    Every register entry keeps a row (ADR-0122): the row for *embargo_id* is
    ``INVITED`` with *rsvp_deadline* (CM-28-013), and every other row is
    ``UNINVITED``.  A signatory to the embargo in force is never treated as
    lapsed (its Accept is an ordinary one), so the late-Accept routing is
    exercised with an invitee holding no AGREED row for the terms in force.
    """
    return [
        (
            EmbargoConsent(
                embargo_id=embargo_id,
                state=EmbargoConsentState.INVITED,
                rsvp_deadline=rsvp_deadline,
            )
            if row.embargo_id == embargo_id
            else EmbargoConsent(
                embargo_id=row.embargo_id, state=EmbargoConsentState.UNINVITED
            )
        )
        for row in participant.embargo_consents
    ]


def _reject(net: _Network, actor: str, index: int = 0) -> HandlerResult:
    """*actor* rejects its *index*-th relayed Invite; the manager receives it.

    The replica's own answer to the Invite stays in its outbox, so the
    test's Reject stands in for it and takes its number
    (``withdraw_unsent_numbers``, SYNC-21-002).
    """
    net.deliver(MANAGER, to=actor, type_="Invite")
    invite = net.queued(MANAGER, to=actor, type_="Invite")[index]
    net.withdraw_unsent_numbers(actor)
    _, sealed = TriggerActivityAdapter(net.stores[actor]).reject_embargo(
        proposal_id=invite.id_, case_id=net.case_id, actor=actor, to=[MANAGER]
    )
    return cast(HandlerResult, net.receive(MANAGER, json.loads(sealed)))


def _entries(
    net: _Network, actor: str, semantic_type: str
) -> list[CaseLedgerEntry]:
    return [
        obj
        for obj in net.stores[actor].list_objects("CaseLedgerEntry")
        if isinstance(obj, CaseLedgerEntry)
        and str(obj.semantic_type) == semantic_type
    ]


_INVITE = "invite_to_embargo_on_case"
_ACCEPT = "accept_invite_to_embargo_on_case"


def _invites_of(
    net: _Network, actor: str, invitee: str, embargo_id: str
) -> list[CaseLedgerEntry]:
    """Every ``invite_to_embargo_on_case`` entry to *invitee* of *embargo_id*."""
    return [
        entry
        for entry in _entries(net, actor, _INVITE)
        if entry.payload_snapshot.get("to") == [invitee]
        and isinstance(entry.payload_snapshot.get("object"), dict)
        and entry.payload_snapshot["object"].get("id") == embargo_id
    ]


def _semantic_types(net: _Network, actor: str) -> list[str]:
    return [
        str(obj.semantic_type)
        for obj in net.stores[actor].list_objects("CaseLedgerEntry")
        if isinstance(obj, CaseLedgerEntry)
    ]


def _deliver_all(net: _Network, to: str) -> None:
    for type_, verdict in net.deliver(MANAGER, to=to):
        assert verdict.disposition is HandlerDisposition.APPLIED, (
            type_,
            verdict.reason,
        )


# Integration tier, with the rest of the LedgerNetwork replay group
# (#4917): about 9s idle plus a 2s teardown rebuild, so under the
# full unit run's load it can pass the 30s ceiling.
@pytest.mark.integration
@pytest.mark.spec("EP-09-007")
@pytest.mark.spec("SYNC-12-001")
def test_a_late_reject_is_refused_uncommitted_and_the_replica_keeps_up():
    """A Reject of an already-decided revision leaves no entry to stall on."""
    net = _Network("https://example.org/cases/answer-late-reject")
    first = _propose(net, "decided", 90)
    net.deliver(MANAGER, to=BYSTANDER, type_="Invite")
    rejected = _owner_decides(net, first, accept=False)
    assert rejected.disposition is HandlerDisposition.APPLIED, rejected.reason

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


# Integration tier, with the rest of the LedgerNetwork replay group
# (#4917): about 9s idle plus a 2s teardown rebuild, so under the
# full unit run's load it can pass the 30s ceiling.
@pytest.mark.integration
@pytest.mark.spec("EP-08-001")
@pytest.mark.spec("EP-08-003")
def test_the_owner_rejecting_one_of_two_revisions_keeps_the_other_open():
    net = _Network("https://example.org/cases/answer-two-open")
    first = _propose(net, "r1", 90)
    second = _propose(net, "r2", 120)

    rejected = _owner_decides(net, first, accept=False)
    assert rejected.disposition is HandlerDisposition.APPLIED, rejected.reason
    _replay_to_bystander(net)

    for actor_id in (MANAGER, BYSTANDER):
        case = net.case(actor_id)
        assert case.current_status.em.state == EM.REVISE, actor_id
        assert case.active_embargo_id == net.initial_embargo_id, actor_id
        assert case.proposed_embargo_ids == [second], actor_id


@pytest.mark.spec("EMB-04-002")
@pytest.mark.spec("MSM-07-009")
@pytest.mark.spec("EMB-13-005")
@pytest.mark.spec("TB-06-007")
@pytest.mark.spec("MSM-07-032")
def test_the_owner_rejecting_a_revision_after_disclosure_ends_the_embargo():
    """EJ with P/X/A set ends EXITED in every store, not ACTIVE again.

    The owner's ``Reject(EmbargoEvent)[target=VulnerabilityCase]`` of the last open
    revision (ADR-0122, EMB-04-002): the revision ends ``REJECTED`` and the
    embargo ``TERMINATED`` with the threat signal as its cause, as two
    entries every replica copies (MSM-07-032, EMB-13-005).
    """
    net = _Network("https://example.org/cases/answer-after-disclosure")
    revision = _propose(net, "late", 90)
    _deliver_all(net, BYSTANDER)
    net.deliver(MANAGER, to=OWNER, type_="Invite")
    # P/X/A is set in every store directly, with no entry recording it.
    net.bypass_ledger()
    for actor_id in (MANAGER, OWNER, BYSTANDER):
        dl = net.stores[actor_id]
        case = cast(VulnerabilityCase, dl.read(net.case_id))
        case.current_status.pxa = case.current_status.pxa.model_copy(
            update={"state": CS_pxa.Pxa}
        )
        dl.save(case)
    _, body = owner_decision_body(
        net.stores[OWNER],
        net.case_id,
        revision,
        owner=OWNER,
        manager=MANAGER,
        accept=False,
    )

    verdict = net.receive(MANAGER, body)

    assert verdict.disposition is HandlerDisposition.APPLIED, verdict.reason
    _deliver_all(net, BYSTANDER)
    _deliver_all(net, OWNER)
    for actor_id in (MANAGER, OWNER, BYSTANDER):
        case = net.case(actor_id)
        assert case.current_status.em.state == EM.EXITED, actor_id
        assert case.active_embargo_id is None, actor_id
        assert case.proposed_embargo_ids == [], actor_id
        # Rejected as decided, then the embargo terminated (MSM-07-032).
        assert case.embargo_register_status(revision) is (
            EmbargoRegisterStatus.REJECTED
        ), actor_id
        assert case.embargo_register_status(net.initial_embargo_id) is (
            EmbargoRegisterStatus.TERMINATED
        ), actor_id
        assert case.embargo_termination == EmbargoTermination.threat(
            [ThreatSignal.P]
        ), actor_id
    entries = sorted(
        (
            obj
            for obj in net.stores[BYSTANDER].list_objects("CaseLedgerEntry")
            if isinstance(obj, CaseLedgerEntry)
        ),
        key=lambda entry: entry.log_index,
    )
    types = [str(entry.semantic_type) for entry in entries]
    assert types.index("reject_embargo_proposal_on_case") < types.index(
        EMBARGO_TEARDOWN_SEMANTIC_TYPE
    )


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
    invite = net.queued(MANAGER, to=OWNER, type_="Invite")[0]
    adapter = TriggerActivityAdapter(net.stores[OWNER])
    build = (
        adapter.accept_embargo
        if answer == "Accept"
        else (adapter.reject_embargo)
    )
    _, sealed = build(
        proposal_id=invite.id_,
        case_id=net.case_id,
        actor=OWNER,
        to=[MANAGER],
    )
    body = json.loads(sealed)

    verdict = net.receive(BYSTANDER, body)

    assert verdict.disposition is HandlerDisposition.REFUSED
    assert "neither the sender nor a recipient" in (verdict.reason or "")
    assert BYSTANDER in (verdict.reason or "")
    case = net.case(BYSTANDER)
    assert case.current_status.em.state == EM.REVISE
    assert case.proposed_embargo_ids == [revision]


@pytest.mark.spec("CM-28-013")
@pytest.mark.spec("CM-28-023")
@pytest.mark.spec("EP-09-007")
@pytest.mark.spec("CM-28-012")
def test_the_relay_and_its_replay_record_the_same_rsvp_deadline():
    """The invitee's deadline is the relayed Invite's ``endTime`` everywhere.

    The CASE_MANAGER stamps it as the Invite's ``published`` plus its default
    window (CM-28-012), records it at commit, and the replica records the same
    value from the committed entry (CM-28-023).
    """
    net = _Network("https://example.org/cases/answer-rsvp-deadline")
    revision_id = _propose(net, "deadline", 90)
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
        assert participant.rsvp_deadline_for(revision_id) == deadline, actor_id


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
    revision_id = _propose(net, "lapse", 90)
    bystander_pid = net.case(MANAGER).actor_participant_index[BYSTANDER]
    # A signatory's consent survives a revision Invite (EP-09-004), so seed an
    # invitee that has not yet signed, everywhere; only the manager's record
    # holds a passed deadline.
    # The rows are seeded outside the ledger, so no rebuild reaches them.
    net.bypass_ledger()
    for actor_id in (MANAGER, OWNER):
        dl = net.stores[actor_id]
        participant = cast(CaseParticipant, dl.read(bystander_pid))
        deadline = (
            datetime.now(tz=UTC) - timedelta(hours=1)
            if actor_id == MANAGER
            else None
        )
        dl.save(
            participant.model_copy(
                update={
                    "embargo_consents": _invited_only(
                        participant, revision_id, deadline
                    )
                }
            )
        )
    _replay_to_bystander(net)
    net.deliver(MANAGER, to=BYSTANDER, type_="Invite")
    (accept,) = net.queued(BYSTANDER, to=MANAGER, type_="Accept")
    body = read_sealed_body_dict(net.stores[BYSTANDER], accept.id_)
    assert body is not None

    net.receive(MANAGER, body)
    _deliver_all(net, OWNER)

    # The expiry the replica replayed, the CASE_MANAGER's TIMED_OUT row, is
    # the entry in its ledger.  The accepted revision is still open, so the
    # late Accept is then honoured (EMB-17-002) and the row ends AGREED.
    expiries = consent_row_updates(
        net.stores[OWNER], net.case_id, EmbargoConsentState.TIMED_OUT
    )
    assert len(expiries) == 1
    replayed = cast(CaseParticipant, net.stores[OWNER].read(bystander_pid))
    assert replayed.consent_for(revision_id) == EmbargoConsentState.AGREED


def _seed_bystander_row(
    net: _Network,
    bystander_pid: str,
    embargo_id: str,
    state: EmbargoConsentState,
) -> None:
    """Seed BYSTANDER's *state* row for *embargo_id*, outside the ledger.

    ``INVITED`` carries a passed deadline in the CASE_MANAGER's store only,
    so the manager's expiry finds it late; every other row is ``UNINVITED``
    (:func:`_invited_only`).  Any other *state* is the row in every store.
    """
    net.bypass_ledger()
    for actor_id in (MANAGER, OWNER):
        dl = net.stores[actor_id]
        participant = cast(CaseParticipant, dl.read(bystander_pid))
        deadline = (
            datetime.now(tz=UTC) - timedelta(hours=1)
            if actor_id == MANAGER
            else None
        )
        rows = _invited_only(participant, embargo_id, deadline)
        if state is not EmbargoConsentState.INVITED:
            rows = [
                EmbargoConsent(embargo_id=embargo_id, state=state)
                if row.embargo_id == embargo_id
                else row
                for row in rows
            ]
        dl.save(participant.model_copy(update={"embargo_consents": rows}))


@pytest.mark.spec("EMB-17-002")
@pytest.mark.spec("EMB-17-009")
@pytest.mark.spec("EMB-17-012")
@pytest.mark.spec("EMB-17-018")
@pytest.mark.spec("MSM-07-003")
@pytest.mark.spec("TB-06-007")
@pytest.mark.parametrize(
    "seeded", [EmbargoConsentState.INVITED, EmbargoConsentState.DECLINED]
)
def test_a_late_accept_of_an_open_revision_is_honoured(seeded):
    """A late Accept of a still-open proposal is recorded, not dropped.

    The revision is open (EM ``REVISE``) and not yet activated, so the case
    can still answer it (MSM-07-003): the CASE_MANAGER commits the received
    Accept verbatim, its entry carrying the ``AGREED`` row for the revision,
    reached directly from ``TIMED_OUT`` (the expired Invite) or from
    ``DECLINED`` (a changed answer), with no further entry for that row and
    no re-invite (EMB-17-002, EMB-17-009, EMB-17-018).  The accepter binds
    itself to nothing in force: its row for the Active Embargo is unchanged.
    """
    net = _Network(
        f"https://example.org/cases/answer-honour-open-{seeded.value.lower()}"
    )
    revision_id = _propose(net, "open", 90)
    bystander_pid = net.case(MANAGER).actor_participant_index[BYSTANDER]
    _replay_to_bystander(net)
    net.deliver(MANAGER, to=BYSTANDER, type_="Invite")
    (accept,) = net.queued(BYSTANDER, to=MANAGER, type_="Accept")
    body = read_sealed_body_dict(net.stores[BYSTANDER], accept.id_)
    assert body is not None
    _deliver_all(net, OWNER)
    _seed_bystander_row(net, bystander_pid, revision_id, seeded)
    active_id = net.case(MANAGER).active_embargo_id
    assert active_id is not None and active_id != revision_id

    verdict = net.receive(MANAGER, body)
    assert verdict.disposition is HandlerDisposition.APPLIED, verdict.reason
    _deliver_all(net, OWNER)

    (accept_entry,) = [
        e
        for e in _entries(net, MANAGER, _ACCEPT)
        if e.log_object_id == str(body["id"])
    ]
    assert accept_entry.payload_snapshot == body
    assert (
        consent_row_updates(
            net.stores[MANAGER],
            net.case_id,
            EmbargoConsentState.AGREED,
            BYSTANDER,
        )
        == []
    )
    assert _invites_of(net, MANAGER, BYSTANDER, active_id) == []
    for actor_id in (MANAGER, OWNER):
        record = cast(
            CaseParticipant, net.stores[actor_id].read(bystander_pid)
        )
        assert record.consent_for(revision_id) == EmbargoConsentState.AGREED
        assert record.consent_for(active_id) == EmbargoConsentState.UNINVITED
        assert not record.is_signatory(active_id), actor_id
    assert net.case(MANAGER).proposed_embargo_ids == [revision_id]


@pytest.mark.spec("EMB-17-003")
@pytest.mark.spec("CM-28-012")
@pytest.mark.spec("CM-28-013")
@pytest.mark.spec("EP-09-007")
@pytest.mark.spec("RSH-08-004")
@pytest.mark.spec("CLP-10-006")
@pytest.mark.spec("TB-06-007")
@pytest.mark.spec("EP-09-002")
@pytest.mark.spec("EMB-17-013")
@pytest.mark.spec("EMB-17-014")
def test_the_managers_reinvite_is_committed_and_replayed_by_a_replica():
    """A late Accept of a rejected embargo is re-invited; a replica learns it.

    The owner rejected the accepted revision, so the case can no longer
    answer it and the accepter is asked about the Active Embargo instead
    (EMB-17-003).  The re-invite is a relay (ADR-0152): the manager commits the fresh
    Invite as ``invite_to_embargo_on_case``, ``attributedTo`` the embargo's
    proposer, which for this case's creation-time embargo is the manager
    itself.  The replica, replaying it through the relay slot, moves the
    invitee's row for the embargo in force to ``INVITED`` with the Invite's
    new deadline and leaves EM alone (CM-28-013, EP-09-007).
    """
    net = _Network("https://example.org/cases/answer-reinvite")
    revision_id = _propose(net, "reinvite", 90)
    bystander_pid = net.case(MANAGER).actor_participant_index[BYSTANDER]
    _replay_to_bystander(net)
    net.deliver(MANAGER, to=BYSTANDER, type_="Invite")
    (accept,) = net.queued(BYSTANDER, to=MANAGER, type_="Accept")
    body = read_sealed_body_dict(net.stores[BYSTANDER], accept.id_)
    assert body is not None
    rejected = _owner_decides(net, revision_id, accept=False)
    assert rejected.disposition is HandlerDisposition.APPLIED, rejected.reason
    # The rows are seeded outside the ledger, so no rebuild reaches them.
    net.bypass_ledger()
    for actor_id in (MANAGER, OWNER):
        dl = net.stores[actor_id]
        participant = cast(CaseParticipant, dl.read(bystander_pid))
        deadline = (
            datetime.now(tz=UTC) - timedelta(hours=1)
            if actor_id == MANAGER
            else None
        )
        dl.save(
            participant.model_copy(
                update={
                    "embargo_consents": _invited_only(
                        participant, revision_id, deadline
                    )
                }
            )
        )

    # The replica has replayed the proposal before the re-invite exists, so
    # what it holds then is what the re-invite entry must leave alone.
    _deliver_all(net, OWNER)
    before = net.case(OWNER)
    em_before = before.current_status.em.state
    proposals_before = list(before.proposed_embargo_ids)
    active_before = before.active_embargo_id
    assert em_before == EM.ACTIVE
    assert proposals_before == []
    assert active_before is not None
    assert _invites_of(net, MANAGER, BYSTANDER, active_before) == []

    net.receive(MANAGER, body)
    # A late-Accept arm answers the delivery itself (CLP-10-026).
    assert_no_refusal_notice(
        net.stores[MANAGER], manager=MANAGER, refused_id=str(body["id"])
    )
    _deliver_all(net, OWNER)

    manager_record = cast(
        CaseParticipant, net.stores[MANAGER].read(bystander_pid)
    )
    assert active_before is not None
    # The rejected revision's row is final: the stale Accept moves nothing
    # (EMB-17-005, ADR-0122).
    assert (
        manager_record.consent_for(revision_id) == EmbargoConsentState.INVITED
    )
    assert (
        manager_record.consent_for(active_before)
        == EmbargoConsentState.INVITED
    )
    manager_deadline = manager_record.rsvp_deadline_for(active_before)
    assert manager_deadline is not None
    assert manager_deadline > datetime.now(tz=UTC)
    (entry,) = _invites_of(net, MANAGER, BYSTANDER, active_before)
    snapshot = entry.payload_snapshot
    assert snapshot["actor"] == MANAGER
    # The case's embargo in force is the manager's own terms, so the manager
    # names itself as their proposer (ADR-0152).
    entries = sorted(
        _entries(net, MANAGER, _INVITE), key=lambda e: e.log_index
    )
    assert embargo_proposer_id(entries, active_before) in (None, MANAGER)
    assert snapshot["attributedTo"] == MANAGER
    assert snapshot["to"] == [BYSTANDER]
    # The entry is the body the outbox delivers, with the deadline as endTime.
    assert invite_rsvp_deadline(snapshot) == manager_deadline

    # The replica's own store (TB-06-007): same consent and deadline, no EM move.
    assert len(_invites_of(net, OWNER, BYSTANDER, active_before)) == 1
    replayed = cast(CaseParticipant, net.stores[OWNER].read(bystander_pid))
    assert replayed.consent_for(revision_id) == EmbargoConsentState.INVITED
    assert replayed.consent_for(active_before) == EmbargoConsentState.INVITED
    assert replayed.rsvp_deadline_for(active_before) == manager_deadline
    # The entry replays as a re-invite, never as a second proposal of the
    # embargo it names: EM, the open proposals and the active embargo stay put.
    after = net.case(OWNER)
    assert after.current_status.em.state == em_before
    assert list(after.proposed_embargo_ids) == proposals_before
    assert after.active_embargo_id == active_before


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
    invites_before = _semantic_types(net, OWNER).count(_INVITE)

    net.receive(OWNER, body)

    assert _semantic_types(net, OWNER).count(_INVITE) == invites_before
    assert (
        len(net.queued(OWNER, to=BYSTANDER, type_="Invite")) == queued_before
    )


@pytest.mark.spec("EMB-17-001")
@pytest.mark.spec("EMB-17-002")
@pytest.mark.spec("EMB-17-009")
@pytest.mark.spec("RSH-08-004")
@pytest.mark.spec("TB-06-007")
@pytest.mark.spec("EMB-17-018")
def test_an_honoured_late_accept_is_committed_and_replayed_by_a_replica():
    """Late Accept honours into an AGREED row when the embargo is still active.

    When the invitee's RSVP deadline has passed and the embargo is still
    active and matching, the CASE_MANAGER commits the ``TIMED_OUT`` row
    (CM-28-009) and then the received Accept itself, carrying the ``AGREED``
    row it states, as an on-time Accept is (EMB-17-002, EMB-17-009).  No
    ``Update(EmbargoConsent)`` of the ``AGREED`` row follows: one state
    change, one entry (CLP-07-002, ADR-0152).  The replica copies the row
    from the Accept's entry without re-evaluating the deadline (RSH-08-004,
    ADR-0124).

    OWNER activates the revision first so that ``active_embargo_id == embargo_id`` when
    BYSTANDER's late Accept arrives — that is the condition that routes to the
    honour branch rather than re-invite (EMB-17-002).
    """
    net = _Network("https://example.org/cases/answer-honour-late-accept")
    revision_id = _propose(net, "honour", 90)
    bystander_pid = net.case(MANAGER).actor_participant_index[BYSTANDER]

    # Deliver proposal entries and the Invite to BYSTANDER so BYSTANDER can
    # generate its Accept for the revision embargo.
    # Capture the body before OWNER answers so we can submit it late.
    _replay_to_bystander(net)
    net.deliver(MANAGER, to=BYSTANDER, type_="Invite")
    (accept,) = net.queued(BYSTANDER, to=MANAGER, type_="Accept")
    body = read_sealed_body_dict(net.stores[BYSTANDER], accept.id_)
    assert body is not None

    # OWNER activates: EM REVISE → ACTIVE, active_embargo = revision.
    # Now active_embargo_id == embargo_id (both are the revision), so the
    # CASE_MANAGER takes the honour branch when the late Accept arrives
    # (EMB-17-001), not the re-invite branch (EMB-17-002).
    _owner_answers(net, revision_id)

    # Seed BYSTANDER as INVITED with a passed deadline on MANAGER's store so
    # the expiry tree fires (NEEDS_APPLY=True → expiry entry committed).
    # OWNER's store holds INVITED with no deadline: the relay-entry Announces
    # replayed by _deliver_all sequence BYSTANDER correctly
    # (INVITED → TIMED_OUT via expiry, TIMED_OUT → AGREED via honour).
    # Pre-seeding TIMED_OUT would cause the relay-invite replay to revert it to
    # INVITED (INVITE is legal from TIMED_OUT), creating an ordering hazard.
    # The rows are seeded outside the ledger, so no rebuild reaches them.
    net.bypass_ledger()
    for actor_id in (MANAGER, OWNER):
        dl = net.stores[actor_id]
        participant = cast(CaseParticipant, dl.read(bystander_pid))
        deadline = (
            datetime.now(tz=UTC) - timedelta(hours=1)
            if actor_id == MANAGER
            else None
        )
        dl.save(
            participant.model_copy(
                update={
                    "embargo_consents": _invited_only(
                        participant, revision_id, deadline
                    )
                }
            )
        )

    net.receive(MANAGER, body)
    # A late-Accept arm answers the delivery itself (CLP-10-026).
    assert_no_refusal_notice(
        net.stores[MANAGER], manager=MANAGER, refused_id=str(body["id"])
    )
    _deliver_all(net, OWNER)

    replayed = cast(CaseParticipant, net.stores[OWNER].read(bystander_pid))
    assert replayed.consent_for(revision_id) == EmbargoConsentState.AGREED
    assert replayed.is_signatory(revision_id)

    # The Accept itself is the entry, verbatim, and nothing records the row
    # a second time.
    (accept_entry,) = [
        e
        for e in _entries(net, MANAGER, _ACCEPT)
        if e.log_object_id == str(body["id"])
    ]
    assert accept_entry.payload_snapshot == body
    assert (
        consent_row_updates(
            net.stores[MANAGER],
            net.case_id,
            EmbargoConsentState.AGREED,
            BYSTANDER,
        )
        == []
    )
    # The same row an on-time Accept leaves (AC-4).
    manager_record = cast(
        CaseParticipant, net.stores[MANAGER].read(bystander_pid)
    )
    assert replayed.embargo_consents == manager_record.embargo_consents


def _late_accept_on_an_exited_embargo(
    net: _Network,
) -> tuple[dict[str, object], str, str, str]:
    """Queue BYSTANDER's Accept, then end the embargo at the CASE_MANAGER.

    Returns the Accept's sealed body, its id, BYSTANDER's participant id and
    the answered revision's id.  The Accept reaches the CASE_MANAGER after
    its Invite expired and once no embargo can bind it, so it takes the
    no-op arm (EMB-17-004).
    """
    revision_id = _propose(net, "noop", 90)
    bystander_pid = net.case(MANAGER).actor_participant_index[BYSTANDER]

    # Deliver proposal entries and the Invite to BYSTANDER so an Accept is
    # queued in BYSTANDER's outbox before the embargo is terminated.
    _replay_to_bystander(net)
    net.deliver(MANAGER, to=BYSTANDER, type_="Invite")
    (accept,) = net.queued(BYSTANDER, to=MANAGER, type_="Accept")
    body = read_sealed_body_dict(net.stores[BYSTANDER], accept.id_)
    assert body is not None

    # Terminate the embargo on MANAGER's store (EM EXITED) so the no-op arm
    # is taken (EMB-17-004).  Only MANAGER's store needs EXITED: it is the
    # judge.  BYSTANDER's store keeps the original state — it is the sender.
    # The termination is written outside the ledger, so no rebuild reaches it.
    net.bypass_ledger()
    dl_mgr = net.stores[MANAGER]
    case_mgr = net.case(MANAGER)
    terminate(case_mgr)
    assert case_mgr.em_state == EM.EXITED
    dl_mgr.save(case_mgr)

    # Seed BYSTANDER as INVITED with a passed deadline on MANAGER's store so
    # the Invite reads as expired.  Its register entry is final, so no expiry
    # is committed for it (ADR-0122), and the late Accept takes the no-op arm.
    for actor_id in (MANAGER, OWNER):
        dl = net.stores[actor_id]
        participant = cast(CaseParticipant, dl.read(bystander_pid))
        deadline = (
            datetime.now(tz=UTC) - timedelta(hours=1)
            if actor_id == MANAGER
            else None
        )
        dl.save(
            participant.model_copy(
                update={
                    "embargo_consents": _invited_only(
                        participant, revision_id, deadline
                    )
                }
            )
        )

    return body, accept.id_, bystander_pid, revision_id


def _no_trace(net: _Network) -> tuple[list[str], list[str]]:
    """The CASE_MANAGER's ledger and outbox, to show a delivery added neither."""
    dl = net.stores[MANAGER]
    return _semantic_types(net, MANAGER), list(dl.outbox_list())


@pytest.mark.spec("EMB-17-004")
@pytest.mark.spec("CLP-02-013")
@pytest.mark.spec("EMB-17-015")
@pytest.mark.spec("EMB-17-016")
@pytest.mark.spec("EMB-17-017")
def test_a_late_accept_with_no_embargo_to_bind_records_and_sends_nothing():
    """Late Accept on an exited embargo: no entry, no message, no row moved.

    When a late Accept arrives with EM EXITED on the CASE_MANAGER's store,
    every register entry is final, so the invitation's row accepts no trigger
    (ADR-0122).  The Accept changes nothing anywhere, so the CASE_MANAGER
    commits no entry, queues nothing and leaves the row ``INVITED``
    (EMB-17-004, ADR-0152); the handler reports the no-op ``SKIPPED``.
    """
    net = _Network("https://example.org/cases/answer-noop-late-accept")
    body, _accept_id, bystander_pid, revision_id = (
        _late_accept_on_an_exited_embargo(net)
    )
    dl_mgr = net.stores[MANAGER]
    before = _no_trace(net)

    verdict = net.receive(MANAGER, body)

    assert verdict.disposition is HandlerDisposition.SKIPPED, verdict.reason
    assert "EMB-17-004" in (verdict.reason or "")
    assert _no_trace(net) == before
    # A late-Accept arm answers the delivery itself (CLP-10-026): no
    # refusal notice either.
    assert_no_refusal_notice(
        dl_mgr, manager=MANAGER, refused_id=str(body["id"])
    )
    participant = cast(CaseParticipant, dl_mgr.read(bystander_pid))
    assert participant.consent_for(revision_id) == EmbargoConsentState.INVITED
    assert (
        consent_row_updates(dl_mgr, net.case_id, EmbargoConsentState.TIMED_OUT)
        == []
    )


@pytest.mark.spec("EMB-17-004")
@pytest.mark.spec("IE-10-001")
@pytest.mark.spec("VM-08-002")
@pytest.mark.parametrize("evidence", ["archived body", "no received body"])
def test_a_redelivered_late_accept_gets_the_same_result(evidence: str):
    """A redelivery of the late Accept also records and sends nothing.

    The inbox routes a resend either as the body intake archived or with no
    received body at all (IE-10-001, VM-08-009, VM-08-010).  Nothing is built from the
    Accept, so either way the arm answers it the same: ``SKIPPED``, with no
    entry and no message.
    """
    net = _Network(
        "https://example.org/cases/answer-noop-late-accept-"
        + evidence.replace(" ", "-")
    )
    body, _accept_id, _bystander_pid, _revision_id = (
        _late_accept_on_an_exited_embargo(net)
    )
    first = net.receive(MANAGER, body)
    before = _no_trace(net)

    if evidence == "archived body":
        again = net.receive(MANAGER, body)
    else:
        resend = received_event(
            parse_activity(body),
            receiving_actor_id=MANAGER,
            received_evidence=None,
        )
        again = net.receive_event(MANAGER, resend)

    assert first.disposition is HandlerDisposition.SKIPPED, first.reason
    assert again.disposition is HandlerDisposition.SKIPPED, again.reason
    assert _no_trace(net) == before


@pytest.mark.spec("CLP-10-026")
@pytest.mark.spec("EMB-17-004")
def test_a_late_accept_answer_that_does_not_complete_raises(monkeypatch):
    """A taken late-Accept arm that fails is an internal error, not a verdict.

    The tree chose to answer the delivery instead of committing it, so an
    answer that does not complete leaves the Accept neither recorded nor
    answered: the handler raises (CLP-10-026), and no consent row moves.
    """
    net = _Network("https://example.org/cases/answer-late-accept-fails")
    body, _accept_id, bystander_pid, revision_id = (
        _late_accept_on_an_exited_embargo(net)
    )
    monkeypatch.setattr(
        LateAcceptChangesNothingNode,
        "update",
        lambda self: Status.FAILURE,
    )

    before = _no_trace(net)

    with pytest.raises(VultronBTInternalError, match="LateAcceptBindsNothing"):
        net.receive(MANAGER, body)

    assert _no_trace(net) == before
    participant = cast(
        CaseParticipant, net.stores[MANAGER].read(bystander_pid)
    )
    # The register entry is final, so the row stays as it was (ADR-0122).
    assert participant.consent_for(revision_id) is (
        EmbargoConsentState.INVITED
    )
