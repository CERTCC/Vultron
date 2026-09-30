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

Every test here but the acknowledgement check is a strict ``xfail`` pinning
behaviour #3913 (manager-side relay), #3915 (participant side and replay) and
#3961 (RSVP deadline) and #3963 (invitee resolution) will deliver.  Each fails today for the reason its docstring names;
when the feature lands the ``xfail`` auto-promotes.
"""

from typing import cast

import pytest

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driven.sync_activity_adapter import SyncActivityAdapter
from vultron.core.models._helpers import days_from_now_utc
from vultron.core.models.activity import VultronActivity
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.use_case_result import HandlerDisposition
from vultron.core.states.em import EM
from vultron.core.states.participant_embargo_consent import PEC
from vultron.core.use_cases.received.embargo import (
    InviteToEmbargoOnCaseReceivedUseCase,
)
from vultron.wire.as2.factories import em_propose_embargo_activity
from vultron.wire.as2.vocab.objects.embargo_event import as_EmbargoEvent

from .conftest import make_embargo_case_with_actor

_TRACKING = "Tracked by #3913 (manager-side relay) and #3915 (participant side, replay); Concern #3892, ADR-0113."
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
    dl.create(activity)
    event = make_payload(activity, receiving_actor_id=receiving_actor_id)
    return InviteToEmbargoOnCaseReceivedUseCase(
        dl, event, sync_port=SyncActivityAdapter(dl)
    ).execute()


@pytest.mark.xfail(
    strict=True,
    reason=(
        "EP-09-001: the CASE_MANAGER does not move the canonical case to "
        "EM.REVISE on a received revision proposal. " + _TRACKING
    ),
)
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


@pytest.mark.xfail(
    strict=True,
    reason=(
        "EP-09-002: the CASE_MANAGER relays no Invite to the other "
        "participants after committing a revision proposal. " + _TRACKING
    ),
)
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


@pytest.mark.xfail(
    strict=True,
    reason=(
        "EP-09-003: a participant's receive tree moves its own consent to "
        "INVITED on receipt instead of leaving it to the ledger. " + _TRACKING
    ),
)
@pytest.mark.spec("EP-09-003")
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

    _deliver(dl, relayed, make_payload, receiving_actor_id=OTHER_A)

    case = cast(VulnerabilityCase, dl.read(case_id))
    assert case.current_status.em.state == EM.ACTIVE
    assert _pec_of(dl, case_id, OTHER_A) is PEC.UNBOUND


@pytest.mark.xfail(
    strict=True,
    reason=(
        "EP-09-004: the receive tree applies PEC INVITE unconditionally and "
        "faults on a SIGNATORY invitee. " + _TRACKING
    ),
)
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


def _relayed_invites(dl: SqliteDataLayer) -> list[VultronActivity]:
    return [
        a
        for a in (cast(VultronActivity, dl.read(i)) for i in dl.outbox_list())
        if a.type_ == "Invite"
    ]


@pytest.mark.xfail(
    strict=True,
    reason=(
        "EP-09-001: the CASE_MANAGER does not move the canonical case to "
        "EM.PROPOSED on a received first proposal. Tracked by #3913. "
        + _TRACKING_3918
    ),
)
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
        "CM-28-012: no relayed Invite exists yet, so none carries the "
        "CASE_MANAGER-stamped end_time. Tracked by #3961. " + _TRACKING_3918
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


@pytest.mark.xfail(
    strict=True,
    reason=(
        "EP-09-010: resolve_invitee_id accepts a multi-recipient Invite and "
        "picks the receiving actor. Tracked by #3963. " + _TRACKING_3918
    ),
)
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


@pytest.mark.xfail(
    strict=True,
    reason=(
        "EP-09-010: resolve_invitee_id falls back to the receiving actor when "
        "the Invite names no recipient. Tracked by #3963. " + _TRACKING_3918
    ),
)
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
