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
"""Embargo revision negotiation relays through the CASE_MANAGER (EP-09, ADR-0113).

A participant proposes a revision to the CASE_MANAGER only.  The CASE_MANAGER
moves the canonical case to ``EM.REVISE``, commits, then relays an
``Invite(EmbargoEvent)`` to every participant except the proposer.  A
participant that receives an Invite writes no case or consent state on receipt;
consent moves when the CASE_MANAGER commits its answer.  A revision Invite to a
``SIGNATORY`` changes nothing.

The manager-side relay (EP-09-001, EP-09-002, EP-09-004) landed with #3913;
the participant side and the replay of every relay entry (EP-09-003,
EP-09-007) with #3915 (``test_embargo_relay_replay.py``, beside this file,
pins the replay across per-actor stores); the sole-recipient invitee
(EP-09-010) with #3963.  The remaining strict ``xfail`` markers pin behaviour
#3961 (RSVP deadline) will deliver.  Each fails today for the reason its docstring names; when the
feature lands the ``xfail`` auto-promotes.
"""

from typing import cast

import pytest

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driven.sync_activity_adapter import SyncActivityAdapter
from vultron.adapters.driven.trigger_activity_adapter import (
    TriggerActivityAdapter,
)
from vultron.adapters.driven.wire_render.as2 import As2WireRenderAdapter
from vultron.core.models._helpers import days_from_now_utc
from vultron.core.models.activity import VultronActivity
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.use_case_result import HandlerDisposition
from vultron.core.states.cs import CS_pxa
from vultron.core.states.em import EM
from vultron.core.states.participant_embargo_consent import PEC, PEC_Trigger
from vultron.core.use_cases.received.embargo import (
    InviteToEmbargoOnCaseReceivedUseCase,
    resolve_proposer_id,
)
from vultron.errors import VultronBTInternalError
from vultron.wire.as2.factories import em_propose_embargo_activity
from vultron.wire.as2.vocab.objects.embargo_event import as_EmbargoEvent

from .conftest import make_embargo_case_with_actor

_TRACKING_3918 = "Concern #3918, ADR-0113."

MANAGER = "https://example.org/users/coord"
PROPOSER = "https://example.org/users/vendor"
OTHER_A = "https://example.org/users/vendor-a"
OTHER_B = "https://example.org/users/vendor-b"


def _active_case_with_revision(
    case_id: str, *, store_actor: str, participants: list[str]
) -> tuple[SqliteDataLayer, as_EmbargoEvent]:
    """Case at ``EM.ACTIVE`` under embargo A, plus a proposed revision B.

    The store belongs to *store_actor*; the CASE_MANAGER role holder is
    ``MANAGER`` in every store so the role gate reads the same everywhere.
    """
    dl, _, case, embargo_a = make_embargo_case_with_actor(
        case_id,
        MANAGER,
        extra_participants=participants,
        case_manager_actor_id=MANAGER,
    )
    if store_actor != MANAGER:
        # The same case, replicated into a participant's own store.
        replica = SqliteDataLayer("sqlite:///:memory:", actor_id=store_actor)
        for obj_id in [
            case.id_,
            embargo_a.id_,
            *(str(p) for p in case.case_participants),
            *(str(p) for p in case.actor_participant_index.values()),
        ]:
            obj = dl.read(obj_id)
            if obj is not None and replica.read(obj_id) is None:
                replica.create(obj)
        dl = replica
    case_read = cast(VulnerabilityCase, dl.read(case_id))
    case_read.current_status.em.state = EM.ACTIVE
    case_read.active_embargo = embargo_a.id_
    dl.save(case_read)

    revision = as_EmbargoEvent(
        id_=f"{case_id}/embargo_events/revision",
        content="Longer terms",
        context=case_id,
        end_time=days_from_now_utc(90),
    )
    dl.create(revision)
    return dl, revision


def _pec_of(dl: SqliteDataLayer, case_id: str, actor_id: str) -> PEC:
    case = cast(VulnerabilityCase, dl.read(case_id))
    participant = cast(
        CaseParticipant, dl.read(case.actor_participant_index[actor_id])
    )
    return PEC(participant.embargo_consent_state)


def _deliver(dl: SqliteDataLayer, activity, make_payload, receiving_actor_id):
    """Deliver *activity* into *dl* with the ports the inbox adapter injects.

    The CASE_MANAGER's commit renders the received activity through the wire
    render port and its relay constructs Invites through the trigger-activity
    port, so both are wired exactly as ``inbox_handler`` wires them.
    """
    dl.create(activity)
    event = make_payload(activity, receiving_actor_id=receiving_actor_id)
    return InviteToEmbargoOnCaseReceivedUseCase(
        dl,
        event,
        sync_port=SyncActivityAdapter(dl),
        trigger_activity=TriggerActivityAdapter(dl),
        wire_render_port=As2WireRenderAdapter(),
    ).execute()


@pytest.mark.spec("EP-09-001")
@pytest.mark.spec("EMB-03-001")
def test_case_manager_moves_canonical_case_to_revise(make_payload):
    """The Participant receiving EV is the CASE_MANAGER: ACTIVE → REVISE."""
    case_id = "https://example.org/cases/relay-revise"
    dl, revision = _active_case_with_revision(
        case_id, store_actor=MANAGER, participants=[PROPOSER]
    )
    proposal = em_propose_embargo_activity(
        revision,
        context=case_id,
        actor=PROPOSER,
        to=[MANAGER],
        id_=f"{case_id}/embargo_proposals/revision",
    )

    _deliver(dl, proposal, make_payload, receiving_actor_id=MANAGER)

    case = cast(VulnerabilityCase, dl.read(case_id))
    assert case.current_status.em.state == EM.REVISE


@pytest.mark.spec("EP-09-002")
def test_case_manager_invites_every_participant_except_the_proposer(
    make_payload,
):
    """One relayed Invite per non-proposer, actor=CASE_MANAGER, attributedTo=proposer."""
    case_id = "https://example.org/cases/relay-fanout"
    dl, revision = _active_case_with_revision(
        case_id,
        store_actor=MANAGER,
        participants=[PROPOSER, OTHER_A, OTHER_B],
    )
    proposal = em_propose_embargo_activity(
        revision,
        context=case_id,
        actor=PROPOSER,
        to=[MANAGER],
        id_=f"{case_id}/embargo_proposals/revision",
    )

    _deliver(dl, proposal, make_payload, receiving_actor_id=MANAGER)

    # The commit's Announce(CaseLedgerEntry) fan-out shares the outbox;
    # only the Invites are the relay.
    relayed = [
        a
        for a in (cast(VultronActivity, dl.read(i)) for i in dl.outbox_list())
        if a.type_ == "Invite"
    ]
    recipients = sorted(r for a in relayed for r in (a.to or []))
    assert relayed, "no Invite was relayed"
    assert recipients == sorted([OTHER_A, OTHER_B])
    assert all(a.actor == MANAGER for a in relayed)
    assert all(a.attributed_to == PROPOSER for a in relayed)


@pytest.mark.spec("EP-09-003")
@pytest.mark.spec("EMB-15-001")
def test_participant_writes_no_consent_on_receipt_of_relayed_invite(
    make_payload,
):
    """A relayed Invite is stored and answered; consent moves via the ledger."""
    case_id = "https://example.org/cases/relay-no-write"
    dl, revision = _active_case_with_revision(
        case_id, store_actor=OTHER_A, participants=[PROPOSER, OTHER_A]
    )
    assert _pec_of(dl, case_id, OTHER_A) is PEC.UNBOUND
    relayed = em_propose_embargo_activity(
        revision,
        context=case_id,
        actor=MANAGER,
        attributed_to=PROPOSER,
        to=[OTHER_A],
        id_=f"{case_id}/embargo_invites/other-a",
    )

    verdict = _deliver(dl, relayed, make_payload, receiving_actor_id=OTHER_A)

    assert verdict.disposition is HandlerDisposition.APPLIED
    case = cast(VulnerabilityCase, dl.read(case_id))
    assert case.current_status.em.state == EM.ACTIVE
    assert case.proposed_embargo_ids == []
    assert _pec_of(dl, case_id, OTHER_A) is PEC.UNBOUND
    other_a = cast(
        CaseParticipant, dl.read(case.actor_participant_index[OTHER_A])
    )
    assert revision.id_ not in other_a.accepted_embargo_ids
    assert dl.read(relayed.id_) is not None, "the Invite was not stored"
    answers = _outbox_of_type(dl, "Accept")
    assert len(answers) == 1, "the invitee did not answer its Invite"
    assert answers[0].actor == OTHER_A
    assert answers[0].to == [MANAGER]


@pytest.mark.spec("EP-09-004")
def test_revision_invite_to_a_signatory_succeeds_and_changes_nothing(
    make_payload,
):
    """A signatory is asked about the revision; its consent state is untouched."""
    case_id = "https://example.org/cases/relay-signatory"
    dl, revision = _active_case_with_revision(
        case_id, store_actor=OTHER_A, participants=[PROPOSER, OTHER_A]
    )
    case = cast(VulnerabilityCase, dl.read(case_id))
    signatory = cast(
        CaseParticipant, dl.read(case.actor_participant_index[OTHER_A])
    )
    object.__setattr__(signatory, "embargo_consent_state", PEC.SIGNATORY)
    dl.save(signatory)
    relayed = em_propose_embargo_activity(
        revision,
        context=case_id,
        actor=MANAGER,
        attributed_to=PROPOSER,
        to=[OTHER_A],
        id_=f"{case_id}/embargo_invites/other-a",
    )

    verdict = _deliver(dl, relayed, make_payload, receiving_actor_id=OTHER_A)

    assert verdict.disposition is HandlerDisposition.APPLIED
    assert _pec_of(dl, case_id, OTHER_A) is PEC.SIGNATORY


def _unbound_case(
    case_id: str, *, store_actor: str, participants: list[str]
) -> tuple[SqliteDataLayer, as_EmbargoEvent]:
    """Case at ``EM.NONE`` with no embargo, plus a first proposal."""
    dl, _ = _active_case_with_revision(
        case_id, store_actor=store_actor, participants=participants
    )
    case = cast(VulnerabilityCase, dl.read(case_id))
    case.current_status.em.state = EM.NONE
    case.active_embargo = None
    case.proposed_embargoes = []
    dl.save(case)
    first = as_EmbargoEvent(
        id_=f"{case_id}/embargo_events/first",
        content="First terms",
        context=case_id,
        end_time=days_from_now_utc(45),
    )
    dl.create(first)
    return dl, first


def _deadline_of(dl: SqliteDataLayer, case_id: str, actor_id: str):
    case = cast(VulnerabilityCase, dl.read(case_id))
    participant = cast(
        CaseParticipant, dl.read(case.actor_participant_index[actor_id])
    )
    return participant.invite_rsvp_deadline


def _outbox_of_type(dl: SqliteDataLayer, type_: str) -> list[VultronActivity]:
    return [
        a
        for a in (cast(VultronActivity, dl.read(i)) for i in dl.outbox_list())
        if a.type_ == type_
    ]


def _relayed_invites(dl: SqliteDataLayer) -> list[VultronActivity]:
    return _outbox_of_type(dl, "Invite")


@pytest.mark.spec("EP-09-001")
@pytest.mark.spec("EMB-01-001")
def test_case_manager_moves_first_proposal_to_proposed(make_payload):
    """The Participant receiving EP is the CASE_MANAGER: NONE → PROPOSED."""
    case_id = "https://example.org/cases/relay-first"
    dl, first = _unbound_case(
        case_id, store_actor=MANAGER, participants=[PROPOSER]
    )
    proposal = em_propose_embargo_activity(
        first,
        context=case_id,
        actor=PROPOSER,
        to=[MANAGER],
        id_=f"{case_id}/embargo_proposals/first",
    )

    _deliver(dl, proposal, make_payload, receiving_actor_id=MANAGER)

    case = cast(VulnerabilityCase, dl.read(case_id))
    assert case.current_status.em.state == EM.PROPOSED


@pytest.mark.xfail(
    strict=True,
    reason=(
        "CM-28-012: the CASE_MANAGER relays the Invites without stamping "
        "end_time, so none carries an RSVP deadline. Tracked by #3961. "
        + _TRACKING_3918
    ),
)
@pytest.mark.spec("CM-28-012")
def test_relayed_invites_carry_the_managers_rsvp_deadline(make_payload):
    """Each relayed Invite has end_time = its own published + the window."""
    case_id = "https://example.org/cases/relay-deadline-wire"
    dl, revision = _active_case_with_revision(
        case_id, store_actor=MANAGER, participants=[PROPOSER, OTHER_A]
    )
    proposal = em_propose_embargo_activity(
        revision,
        context=case_id,
        actor=PROPOSER,
        to=[MANAGER],
        id_=f"{case_id}/embargo_proposals/revision",
    )

    _deliver(dl, proposal, make_payload, receiving_actor_id=MANAGER)

    relayed = _relayed_invites(dl)
    assert relayed, "no Invite was relayed"
    for invite in relayed:
        assert invite.published is not None
        assert invite.end_time is not None
        assert invite.end_time > invite.published


@pytest.mark.xfail(
    strict=True,
    reason=(
        "CM-28-013: the RSVP deadline is written at receipt in every store, "
        "not at the CASE_MANAGER's commit of the relayed Invite. Tracked by "
        "#3961. " + _TRACKING_3918
    ),
)
@pytest.mark.spec("CM-28-013")
def test_manager_stores_invitee_deadline_at_its_commit(make_payload):
    """The invitee's deadline appears in the manager's store after the relay."""
    case_id = "https://example.org/cases/relay-deadline-store"
    dl, revision = _active_case_with_revision(
        case_id, store_actor=MANAGER, participants=[PROPOSER, OTHER_A]
    )
    proposal = em_propose_embargo_activity(
        revision,
        context=case_id,
        actor=PROPOSER,
        to=[MANAGER],
        id_=f"{case_id}/embargo_proposals/revision",
    )

    _deliver(dl, proposal, make_payload, receiving_actor_id=MANAGER)

    assert _deadline_of(dl, case_id, OTHER_A) is not None


@pytest.mark.xfail(
    strict=True,
    reason=(
        "CM-28-013: a participant derives and stores an RSVP deadline on "
        "receipt of a relayed Invite. Tracked by #3961. " + _TRACKING_3918
    ),
)
@pytest.mark.spec("CM-28-013")
@pytest.mark.spec("EP-09-003")
def test_participant_stores_no_deadline_on_receipt(make_payload):
    """A relayed Invite is stored; the deadline arrives by replay, not receipt."""
    case_id = "https://example.org/cases/relay-deadline-replica"
    dl, revision = _active_case_with_revision(
        case_id, store_actor=OTHER_A, participants=[PROPOSER, OTHER_A]
    )
    relayed = em_propose_embargo_activity(
        revision,
        context=case_id,
        actor=MANAGER,
        attributed_to=PROPOSER,
        to=[OTHER_A],
        id_=f"{case_id}/embargo_invites/other-a",
    )

    _deliver(dl, relayed, make_payload, receiving_actor_id=OTHER_A)

    assert _deadline_of(dl, case_id, OTHER_A) is None


@pytest.mark.spec("EP-09-010")
def test_invite_with_several_recipients_is_refused(make_payload):
    """The invitee is the sole ``to`` recipient; several is a misrouting."""
    case_id = "https://example.org/cases/relay-two-recipients"
    dl, revision = _active_case_with_revision(
        case_id, store_actor=OTHER_A, participants=[PROPOSER, OTHER_A, OTHER_B]
    )
    invite = em_propose_embargo_activity(
        revision,
        context=case_id,
        actor=MANAGER,
        attributed_to=PROPOSER,
        to=[OTHER_A, OTHER_B],
        id_=f"{case_id}/embargo_invites/pair",
    )

    result = _deliver(dl, invite, make_payload, receiving_actor_id=OTHER_A)

    assert result.disposition is HandlerDisposition.REFUSED
    reason = (result.reason or "").lower()
    assert "recipient" in reason
    assert "2" in reason, "the refusal names the recipient count"


@pytest.mark.spec("EP-09-010")
def test_invite_with_no_recipient_is_refused(make_payload):
    """No ``to`` recipient means no invitee; refuse rather than guess."""
    case_id = "https://example.org/cases/relay-no-recipient"
    dl, revision = _active_case_with_revision(
        case_id, store_actor=OTHER_A, participants=[PROPOSER, OTHER_A]
    )
    invite = em_propose_embargo_activity(
        revision,
        context=case_id,
        actor=MANAGER,
        attributed_to=PROPOSER,
        to=[],
        id_=f"{case_id}/embargo_invites/nobody",
    )

    result = _deliver(dl, invite, make_payload, receiving_actor_id=OTHER_A)

    assert result.disposition is HandlerDisposition.REFUSED
    reason = (result.reason or "").lower()
    assert "recipient" in reason
    assert "0" in reason, "the refusal names the recipient count"


@pytest.mark.spec("EP-09-009")
def test_no_embargo_acknowledgement_message_exists():
    """The CASE_MANAGER's commit is the EK; no ack semantic or pattern exists."""
    from vultron.core.models.events.base import MessageSemantics
    from vultron.wire.as2.extractor import _instances

    ack_semantics = [
        m.name
        for m in MessageSemantics
        if "ACK" in m.name and "EMBARGO" in m.name
    ]
    assert ack_semantics == []
    ack_patterns = [
        name for name in dir(_instances) if "Ack" in name and "Embargo" in name
    ]
    assert ack_patterns == []


# ---------------------------------------------------------------------------
# The CASE_MANAGER's adjudication and relay, beyond the marker tests above
# (#3913: AC-1 through AC-3).
# ---------------------------------------------------------------------------


def _ledger_entries(
    dl: SqliteDataLayer, case_id: str
) -> list[CaseLedgerEntry]:
    entries = [
        cast(CaseLedgerEntry, e)
        for e in dl.list_objects("CaseLedgerEntry")
        if cast(CaseLedgerEntry, e).case_id == case_id
    ]
    return sorted(entries, key=lambda e: e.log_index)


def _participant_of(
    dl: SqliteDataLayer, case_id: str, actor_id: str
) -> CaseParticipant:
    case = cast(VulnerabilityCase, dl.read(case_id))
    return cast(
        CaseParticipant, dl.read(case.actor_participant_index[actor_id])
    )


def _proposal(revision, case_id: str, *, actor: str = PROPOSER, **kwargs):
    return em_propose_embargo_activity(
        revision,
        context=case_id,
        actor=actor,
        to=[MANAGER],
        id_=kwargs.pop("id_", f"{case_id}/embargo_proposals/revision"),
        **kwargs,
    )


@pytest.mark.spec("EP-09-001")
@pytest.mark.spec("EMB-01-003")
def test_counter_proposal_at_proposed_commits_without_a_transition(
    make_payload,
):
    """A second EP while PROPOSED is recorded; EM stays PROPOSED."""
    case_id = "https://example.org/cases/relay-counter-proposed"
    dl, first = _unbound_case(
        case_id, store_actor=MANAGER, participants=[PROPOSER, OTHER_A]
    )
    _deliver(dl, _proposal(first, case_id), make_payload, MANAGER)
    assert cast(
        VulnerabilityCase, dl.read(case_id)
    ).current_status.em.state == (EM.PROPOSED)
    counter = as_EmbargoEvent(
        id_=f"{case_id}/embargo_events/counter",
        content="Counter terms",
        context=case_id,
        end_time=days_from_now_utc(30),
    )
    dl.create(counter)
    entries_before = len(_ledger_entries(dl, case_id))

    verdict = _deliver(
        dl,
        _proposal(
            counter,
            case_id,
            actor=OTHER_A,
            id_=f"{case_id}/embargo_proposals/counter",
        ),
        make_payload,
        MANAGER,
    )

    assert verdict.disposition is HandlerDisposition.APPLIED
    case = cast(VulnerabilityCase, dl.read(case_id))
    assert case.current_status.em.state == EM.PROPOSED
    assert set(case.proposed_embargo_ids) >= {first.id_, counter.id_}
    assert len(_ledger_entries(dl, case_id)) > entries_before


@pytest.mark.spec("EP-09-001")
@pytest.mark.spec("EMB-03-002")
def test_counter_revision_at_revise_commits_without_a_transition(make_payload):
    """A second EV while REVISE is recorded; EM stays REVISE."""
    case_id = "https://example.org/cases/relay-counter-revise"
    dl, revision = _active_case_with_revision(
        case_id, store_actor=MANAGER, participants=[PROPOSER, OTHER_A]
    )
    _deliver(dl, _proposal(revision, case_id), make_payload, MANAGER)
    assert cast(
        VulnerabilityCase, dl.read(case_id)
    ).current_status.em.state == (EM.REVISE)
    counter = as_EmbargoEvent(
        id_=f"{case_id}/embargo_events/counter",
        content="Counter revision",
        context=case_id,
        end_time=days_from_now_utc(75),
    )
    dl.create(counter)

    verdict = _deliver(
        dl,
        _proposal(
            counter,
            case_id,
            actor=OTHER_A,
            id_=f"{case_id}/embargo_proposals/counter",
        ),
        make_payload,
        MANAGER,
    )

    assert verdict.disposition is HandlerDisposition.APPLIED
    case = cast(VulnerabilityCase, dl.read(case_id))
    assert case.current_status.em.state == EM.REVISE
    assert counter.id_ in case.proposed_embargo_ids
    # The counter went out to the participant that did not propose it.
    assert [
        a.to for a in _relayed_invites(dl) if a.attributed_to == OTHER_A
    ] == [[PROPOSER]]


@pytest.mark.spec("EP-09-001")
def test_an_exited_case_refuses_a_proposal_before_committing(make_payload):
    """EXITED admits no proposal; the refusal leaves no canonical entry."""
    case_id = "https://example.org/cases/relay-exited"
    dl, revision = _active_case_with_revision(
        case_id, store_actor=MANAGER, participants=[PROPOSER, OTHER_A]
    )
    case = cast(VulnerabilityCase, dl.read(case_id))
    case.current_status.em.state = EM.EXITED
    dl.save(case)

    verdict = _deliver(dl, _proposal(revision, case_id), make_payload, MANAGER)

    assert verdict.disposition is HandlerDisposition.REFUSED
    assert "EXITED" in (verdict.reason or "")
    assert _ledger_entries(dl, case_id) == []
    assert _relayed_invites(dl) == []
    assert cast(
        VulnerabilityCase, dl.read(case_id)
    ).current_status.em.state == (EM.EXITED)


@pytest.mark.spec("EMB-03-003")
@pytest.mark.spec("EMB-01-002")
def test_a_revision_of_a_public_case_is_refused_with_er(make_payload):
    """P/X/A set: the manager rejects the revision and the case stays ACTIVE.

    The EMB-03-003 marker attests a *refusal*, not the ET its text names:
    ADR-0113 step 2 maps EMB-03-003 (with EMB-01-002) onto the CASE_MANAGER
    refusing a proposal on a public, exploited or attacked case — the embargo
    termination the requirement calls "emit ET" is the CS public-event
    cascade's job (``PublicDisclosureBranchNode``), which has already run or
    will run regardless of this proposal.  The received proposal itself is
    answered with the retained ER refusal (#3913 AC-1).  The tension between
    the requirement's literal text and the ADR's reading is recorded as an
    incoming learning for the spec.
    """
    case_id = "https://example.org/cases/relay-public"
    dl, revision = _active_case_with_revision(
        case_id, store_actor=MANAGER, participants=[PROPOSER, OTHER_A]
    )
    case = cast(VulnerabilityCase, dl.read(case_id))
    case.append_case_status(em_state=EM.ACTIVE, pxa_state=CS_pxa.Pxa)
    dl.save(case)

    verdict = _deliver(dl, _proposal(revision, case_id), make_payload, MANAGER)

    assert verdict.disposition is HandlerDisposition.REFUSED
    assert "EMB-01-002" in (verdict.reason or "")
    case = cast(VulnerabilityCase, dl.read(case_id))
    assert case.current_status.em.state == EM.ACTIVE
    rejects = [
        a
        for a in (cast(VultronActivity, dl.read(i)) for i in dl.outbox_list())
        if a.type_ == "Reject"
    ]
    assert [a.to for a in rejects] == [[PROPOSER]]
    assert _relayed_invites(dl) == []


@pytest.mark.spec("EP-09-002")
@pytest.mark.spec("CLP-10-006")
def test_each_relayed_invite_is_committed_after_the_proposal(make_payload):
    """One entry for the received proposal, then one per relayed Invite."""
    case_id = "https://example.org/cases/relay-commits"
    dl, revision = _active_case_with_revision(
        case_id,
        store_actor=MANAGER,
        participants=[PROPOSER, OTHER_A, OTHER_B],
    )

    _deliver(dl, _proposal(revision, case_id), make_payload, MANAGER)

    entries = _ledger_entries(dl, case_id)
    assert [e.event_type for e in entries] == ["invite_to_embargo_on_case"] * 3
    snapshots = [e.payload_snapshot for e in entries]
    assert snapshots[0]["actor"] == PROPOSER
    assert [s["actor"] for s in snapshots[1:]] == [MANAGER, MANAGER]
    assert {s["attributedTo"] for s in snapshots[1:]} == {PROPOSER}
    assert sorted(s["to"][0] for s in snapshots[1:]) == sorted(
        [OTHER_A, OTHER_B]
    )
    # The committed snapshot is the delivered body (VM-08-003).
    queued = {a.id_ for a in _relayed_invites(dl)}
    assert {s["id"] for s in snapshots[1:]} == queued


@pytest.mark.spec("EP-09-002")
@pytest.mark.spec("MSM-07-002")
@pytest.mark.spec("CM-18-003")
def test_invitees_move_to_invited_at_the_managers_commit(make_payload):
    """AC-3: the invitee's INVITE is written where the manager commits the Invite."""
    case_id = "https://example.org/cases/relay-invited"
    dl, revision = _active_case_with_revision(
        case_id,
        store_actor=MANAGER,
        participants=[PROPOSER, OTHER_A, OTHER_B],
    )
    for actor in (MANAGER, PROPOSER, OTHER_A, OTHER_B):
        assert _pec_of(dl, case_id, actor) is PEC.UNBOUND

    verdict = _deliver(dl, _proposal(revision, case_id), make_payload, MANAGER)

    assert verdict.disposition is HandlerDisposition.APPLIED
    assert _pec_of(dl, case_id, OTHER_A) is PEC.INVITED
    assert _pec_of(dl, case_id, OTHER_B) is PEC.INVITED
    # Neither the proposer nor the manager is asked (EP-09-002, ADR-0109) ...
    assert _pec_of(dl, case_id, PROPOSER) is PEC.UNBOUND
    assert _pec_of(dl, case_id, MANAGER) is PEC.UNBOUND
    assert MANAGER not in {r for a in _relayed_invites(dl) for r in a.to or []}
    # ... and proposing terms is consenting to them (ADR-0093), list only.
    assert (
        revision.id_
        in _participant_of(dl, case_id, PROPOSER).accepted_embargo_ids
    )
    assert (
        revision.id_
        not in _participant_of(dl, case_id, MANAGER).accepted_embargo_ids
    )


@pytest.mark.spec("EP-09-004")
@pytest.mark.spec("EP-05-002")
def test_a_signatory_is_asked_but_keeps_its_state_at_the_manager(make_payload):
    """The manager relays to a SIGNATORY and writes no consent for it."""
    case_id = "https://example.org/cases/relay-signatory-manager"
    dl, revision = _active_case_with_revision(
        case_id, store_actor=MANAGER, participants=[PROPOSER, OTHER_A]
    )
    signatory = _participant_of(dl, case_id, OTHER_A)
    signatory.apply_pec_transition(PEC_Trigger.ACCEPT)
    dl.save(signatory)

    verdict = _deliver(dl, _proposal(revision, case_id), make_payload, MANAGER)

    assert verdict.disposition is HandlerDisposition.APPLIED
    assert [a.to for a in _relayed_invites(dl)] == [[OTHER_A]]
    assert _pec_of(dl, case_id, OTHER_A) is PEC.SIGNATORY


@pytest.mark.spec("CM-24-002")
def test_a_relayed_proposal_is_attributed_to_its_original_proposer(
    make_payload,
):
    """A relayed Invite — sent by the CASE_MANAGER — names its proposer in ``attributedTo``."""
    case_id = "https://example.org/cases/relay-attributed"
    dl, revision = _active_case_with_revision(
        case_id,
        store_actor=MANAGER,
        participants=[PROPOSER, OTHER_A, OTHER_B],
    )

    _deliver(
        dl,
        _proposal(revision, case_id, actor=MANAGER, attributed_to=PROPOSER),
        make_payload,
        MANAGER,
    )

    relayed = _relayed_invites(dl)
    assert sorted(r for a in relayed for r in (a.to or [])) == sorted(
        [OTHER_A, OTHER_B]
    )
    assert {a.attributed_to for a in relayed} == {PROPOSER}
    assert (
        revision.id_
        in _participant_of(dl, case_id, PROPOSER).accepted_embargo_ids
    )


@pytest.mark.spec("CLP-10-017")
def test_the_manager_persists_the_proposed_embargo_from_the_message(
    make_payload,
):
    """The inline EmbargoEvent becomes a record in the manager's store."""
    case_id = "https://example.org/cases/relay-persist"
    dl, _ = _unbound_case(
        case_id, store_actor=MANAGER, participants=[PROPOSER, OTHER_A]
    )
    fresh = as_EmbargoEvent(
        id_=f"{case_id}/embargo_events/fresh",
        content="Never seen here",
        context=case_id,
        end_time=days_from_now_utc(45),
    )
    assert dl.read(fresh.id_) is None

    verdict = _deliver(dl, _proposal(fresh, case_id), make_payload, MANAGER)

    assert verdict.disposition is HandlerDisposition.APPLIED
    assert dl.read(fresh.id_) is not None
    assert [a.to for a in _relayed_invites(dl)] == [[OTHER_A]]


@pytest.mark.spec("BT-19-001")
def test_a_missing_trigger_port_is_a_wiring_fault_that_moves_no_state(
    make_payload,
):
    """No factory, no relay — and the routing guard runs before the EM write."""
    case_id = "https://example.org/cases/relay-no-port"
    dl, revision = _active_case_with_revision(
        case_id, store_actor=MANAGER, participants=[PROPOSER, OTHER_A]
    )
    proposal = _proposal(revision, case_id)
    dl.create(proposal)
    event = make_payload(proposal, receiving_actor_id=MANAGER)

    with pytest.raises(
        VultronBTInternalError, match="trigger_activity_factory"
    ):
        InviteToEmbargoOnCaseReceivedUseCase(
            dl,
            event,
            sync_port=SyncActivityAdapter(dl),
            wire_render_port=As2WireRenderAdapter(),
        ).execute()

    assert cast(
        VulnerabilityCase, dl.read(case_id)
    ).current_status.em.state == (EM.ACTIVE)
    assert _relayed_invites(dl) == []
    # The received proposal was committed before the routing guard failed
    # (CLP-10-006); the retry re-adjudicates under the idempotency guard.
    assert [e.event_type for e in _ledger_entries(dl, case_id)] == [
        "invite_to_embargo_on_case"
    ]


def test_an_invite_naming_no_embargo_is_refused(make_payload):
    """Nothing to adjudicate or relay without the proposed terms."""
    case_id = "https://example.org/cases/relay-no-embargo"
    dl, revision = _active_case_with_revision(
        case_id, store_actor=MANAGER, participants=[PROPOSER, OTHER_A]
    )
    proposal = _proposal(revision, case_id)
    dl.create(proposal)
    event = make_payload(proposal, receiving_actor_id=MANAGER).model_copy(
        update={"object_": None}
    )

    verdict = InviteToEmbargoOnCaseReceivedUseCase(
        dl,
        event,
        sync_port=SyncActivityAdapter(dl),
        trigger_activity=TriggerActivityAdapter(dl),
        wire_render_port=As2WireRenderAdapter(),
    ).execute()

    assert verdict.disposition is HandlerDisposition.REFUSED
    assert "names no embargo" in (verdict.reason or "")
    assert _ledger_entries(dl, case_id) == []
    assert cast(
        VulnerabilityCase, dl.read(case_id)
    ).current_status.em.state == (EM.ACTIVE)


@pytest.mark.spec("PCR-08-010")
def test_a_participant_cannot_attribute_its_proposal_to_a_third_party(
    make_payload,
):
    """Only the CASE_MANAGER relays; anyone else's attributedTo is ignored."""
    case_id = "https://example.org/cases/relay-spoof"
    dl, revision = _active_case_with_revision(
        case_id,
        store_actor=MANAGER,
        participants=[PROPOSER, OTHER_A, OTHER_B],
    )

    _deliver(
        dl,
        _proposal(revision, case_id, actor=PROPOSER, attributed_to=OTHER_B),
        make_payload,
        MANAGER,
    )

    relayed = _relayed_invites(dl)
    # OTHER_B is invited like anyone else, and the sender is the proposer.
    assert sorted(r for a in relayed for r in (a.to or [])) == sorted(
        [OTHER_A, OTHER_B]
    )
    assert {a.attributed_to for a in relayed} == {PROPOSER}
    assert (
        revision.id_
        in _participant_of(dl, case_id, PROPOSER).accepted_embargo_ids
    )
    assert (
        revision.id_
        not in _participant_of(dl, case_id, OTHER_B).accepted_embargo_ids
    )


@pytest.mark.spec("CLP-13-001")
@pytest.mark.spec("HP-01-003")
def test_a_redelivered_proposal_is_skipped_and_relays_nothing_twice(
    make_payload,
):
    """The same Invite again commits no entry and sends no second round."""
    case_id = "https://example.org/cases/relay-redelivered"
    dl, revision = _active_case_with_revision(
        case_id, store_actor=MANAGER, participants=[PROPOSER, OTHER_A]
    )
    proposal = _proposal(revision, case_id)
    first = _deliver(dl, proposal, make_payload, MANAGER)
    assert first.disposition is HandlerDisposition.APPLIED
    entries_after_first = len(_ledger_entries(dl, case_id))
    invites_after_first = len(_relayed_invites(dl))

    event = make_payload(proposal, receiving_actor_id=MANAGER)
    second = InviteToEmbargoOnCaseReceivedUseCase(
        dl,
        event,
        sync_port=SyncActivityAdapter(dl),
        trigger_activity=TriggerActivityAdapter(dl),
        wire_render_port=As2WireRenderAdapter(),
    ).execute()

    assert second.disposition is HandlerDisposition.SKIPPED
    assert "already applied" in (second.reason or "")
    assert len(_ledger_entries(dl, case_id)) == entries_after_first
    assert len(_relayed_invites(dl)) == invites_after_first == 1


class _AdapterFailingOnSecondInvite(TriggerActivityAdapter):
    """A trigger-activity port whose second ``propose_embargo`` call raises."""

    def __init__(self, dl: SqliteDataLayer) -> None:
        super().__init__(dl)
        self.calls = 0

    def propose_embargo(
        self, *args: object, **kwargs: object
    ) -> tuple[str, str]:
        self.calls += 1
        if self.calls == 2:
            raise RuntimeError("factory down mid-relay")
        return super().propose_embargo(*args, **kwargs)  # type: ignore[arg-type]


@pytest.mark.spec("ID-04-005")
@pytest.mark.spec("BT-14-001")
def test_a_redelivery_after_a_mid_relay_fault_relays_to_everyone_again(
    make_payload,
):
    """A fault mid-fan-out leaves the latch unwritten; the retry re-relays.

    Pins what ``RelayEmbargoInviteToEachNode``'s docstring says happens: the
    first delivery raises after one Invite went out, writes no
    ``pending_embargo_proposal_index`` latch (ID-04-005), and the redelivery
    therefore passes the idempotency guard and relays to *every* recipient
    again — the received proposal's own entry is reused, the recipient already
    invited receives a second Invite and stays INVITED, and the one the fault
    skipped is invited now.
    """
    case_id = "https://example.org/cases/relay-partial"
    dl, revision = _active_case_with_revision(
        case_id,
        store_actor=MANAGER,
        participants=[PROPOSER, OTHER_A, OTHER_B],
    )
    proposal = _proposal(revision, case_id)
    dl.create(proposal)
    event = make_payload(proposal, receiving_actor_id=MANAGER)

    with pytest.raises(VultronBTInternalError, match="mid-relay"):
        InviteToEmbargoOnCaseReceivedUseCase(
            dl,
            event,
            sync_port=SyncActivityAdapter(dl),
            trigger_activity=_AdapterFailingOnSecondInvite(dl),
            wire_render_port=As2WireRenderAdapter(),
        ).execute()

    first_round = _relayed_invites(dl)
    assert len(first_round) == 1
    (invited_first,) = first_round[0].to or []
    (not_yet,) = {OTHER_A, OTHER_B} - {invited_first}
    assert _pec_of(dl, case_id, invited_first) is PEC.INVITED
    assert _pec_of(dl, case_id, not_yet) is PEC.UNBOUND
    case = cast(VulnerabilityCase, dl.read(case_id))
    assert case.current_status.em.state == EM.REVISE
    assert revision.id_ not in case.pending_embargo_proposal_index
    assert [e.event_type for e in _ledger_entries(dl, case_id)] == [
        "invite_to_embargo_on_case"
    ] * 2

    second = InviteToEmbargoOnCaseReceivedUseCase(
        dl,
        event,
        sync_port=SyncActivityAdapter(dl),
        trigger_activity=TriggerActivityAdapter(dl),
        wire_render_port=As2WireRenderAdapter(),
    ).execute()

    assert second.disposition is HandlerDisposition.APPLIED
    recipients = sorted(r for a in _relayed_invites(dl) for r in (a.to or []))
    assert recipients == sorted([invited_first, invited_first, not_yet])
    assert _pec_of(dl, case_id, invited_first) is PEC.INVITED
    assert _pec_of(dl, case_id, not_yet) is PEC.INVITED
    # One entry for the proposal (reused, not duplicated) and one per Invite.
    assert [e.event_type for e in _ledger_entries(dl, case_id)] == [
        "invite_to_embargo_on_case"
    ] * 4
    case = cast(VulnerabilityCase, dl.read(case_id))
    assert case.pending_embargo_proposal_index[revision.id_] == proposal.id_


@pytest.mark.spec("CM-24-002")
def test_attribution_without_a_local_case_falls_back_to_the_sender(
    make_payload, caplog
):
    """No case to resolve the CASE_MANAGER from: the sender is the proposer.

    A store that does not hold the case cannot tell a relay from a spoof, and
    cannot run the manager arm either, so the value is only ever logged.
    """
    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=OTHER_A)
    case_id = "https://example.org/cases/relay-unknown-case"
    revision = as_EmbargoEvent(
        id_=f"{case_id}/embargo_events/revision",
        context=case_id,
        end_time=days_from_now_utc(90),
    )
    invite = _proposal(
        revision, case_id, actor=MANAGER, attributed_to=PROPOSER
    )
    event = make_payload(invite, receiving_actor_id=OTHER_A)

    caplog.set_level("WARNING")
    assert resolve_proposer_id(event, dl) == MANAGER
    assert any("holds no case" in r.message for r in caplog.records)
