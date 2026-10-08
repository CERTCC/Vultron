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
"""Planned trigger-side behaviour for joining a case (ADR-0114, ADR-0070).

Strict-``xfail`` tests for the case-joining requirements planned under #4006
(each test names its implementing issue):

- CM-11-006 — the stub Invite creates the invitee's inert participant.
- CM-11-018 — a joined participant never answers the original report Offer.
- PRM-06-006 — an on-behalf status assertion never creates a participant
  (passing since #4047).
- CM-11-014 — a stub Invite carries a deadline; an unanswered invitee does
  not hold up case closure, but a joined one still at RECEIVED does (passing
  since #4049; expiry is in ``test_stub_invite_lifetime.py``).
- CM-11-015 — a re-invite reuses the record; a re-invite to ``CLOSED`` is
  refused (passing since #4049).
- CM-11-016 — an embargo change re-issues an outstanding stub Invite; a
  ``Reject`` of the superseded one is still honoured (passing since #4049).
- CM-10-007 — the stub Invite reaches the inert invitee (passing marker).
- PRM-06-001 — the CASE_MANAGER writes only the invitee's birth status.

Each test asserts observable behaviour and flips to passing once the
implementation lands.  See ``notes/case-joining.md``.
"""

import json
from typing import Any

import pytest

from test.core.use_cases.received.actor.test_case_joining_planned import (
    route_received,
)
from test.core.use_cases.received.conftest import (
    seed_store_owner_as_case_manager,
)
from test.core.use_cases.triggers.embargo.conftest import (
    _build_active_embargo_case,
)
from test.support.embargo_register import activate
from test.support.trigger_results import activity_of
from vultron.adapters.driven.datalayer_sqlite import (
    SqliteDataLayer,
)
from vultron.adapters.driven.sync_activity_adapter import SyncActivityAdapter
from vultron.adapters.driven.trigger_activity_adapter import (
    TriggerActivityAdapter,
)
from vultron.adapters.driven.wire_render.as2 import As2WireRenderAdapter
from vultron.adapters.outbox_sealed_body import read_sealed_body
from vultron.core.models._helpers import days_from_now_utc
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.dimensions import RmDimension
from vultron.core.models.events.actor import OfferActorToCaseReceivedEvent
from vultron.core.models.offer_record import VultronOfferRecord
from vultron.core.models.participant_status import (
    ParticipantStatus,
    participant_status_rm_state,
    participant_status_vf_state,
)
from vultron.core.models.report_case_link import VultronReportCaseLink
from vultron.core.models.use_case_result import HandlerDisposition
from vultron.core.predicates.participants import all_participants_rm_closed
from vultron.core.states.cs import CS_d, CS_vf
from vultron.core.states.participant_embargo_consent import (
    EmbargoConsentState,
)
from vultron.core.states.rm import RM
from vultron.core.use_cases.received.actor.suggest import (
    OfferActorToCaseReceivedUseCase,
)
from vultron.core.use_cases.triggers.actor import SvcInviteActorToCaseUseCase
from vultron.core.use_cases.triggers.case import (
    AddOnBehalfStatusTriggerRequest,
    SvcAddOnBehalfStatusUseCase,
)
from vultron.core.use_cases.triggers.embargo import SvcTerminateEmbargoUseCase
from vultron.core.use_cases.triggers.report import SvcValidateReportUseCase
from vultron.core.use_cases.triggers.requests import (
    InviteActorToCaseTriggerRequest,
    TerminateEmbargoTriggerRequest,
    ValidateReportTriggerRequest,
)
from vultron.enums.roles import CVDRole
from vultron.errors import VultronError
from vultron.semantic_registry import extract_event
from vultron.wire.as2.factories import rm_submit_report_activity
from vultron.wire.as2.vocab.base.objects.activities.base import as_Activity
from vultron.wire.as2.vocab.base.objects.activities.transitive import (
    as_Accept,
    as_Invite,
    as_Reject,
)
from vultron.wire.as2.vocab.objects.embargo_event import as_EmbargoEvent
from vultron.wire.as2.vocab.objects.vulnerability_report import (
    as_VulnerabilityReport,
)


def _participant_of(
    dl: SqliteDataLayer, case_id: str, actor_id: str
) -> CaseParticipant:
    case = dl.read_case(case_id)
    assert case is not None
    participant_id = case.actor_participant_index.get(actor_id)
    assert participant_id is not None, (
        f"{actor_id} has no participant in {case_id}"
    )
    participant = dl.read(participant_id)
    assert isinstance(participant, CaseParticipant)
    return participant


def _hold_case_owner(dl: SqliteDataLayer, case_id: str, actor_id: str) -> None:
    """Give *actor_id*'s participant record ``CVDRole.CASE_OWNER``.

    The invite trigger is the Case Owner's action, and the CASE_MANAGER emits
    the Invite directly only for an Offer whose sender holds CASE_OWNER on the
    roster (CM-17-007).  The store-owner seeds here name the CASE_MANAGER;
    this adds the ownership the trigger presumes.
    """
    case = dl.read_case(case_id)
    assert case is not None
    participant_id = case.actor_participant_index.get(actor_id)
    assert participant_id is not None, f"{actor_id} is not on the roster"
    participant = dl.read(participant_id)
    assert isinstance(participant, CaseParticipant)
    if CVDRole.CASE_OWNER not in participant.case_roles:
        participant.add_role(CVDRole.CASE_OWNER)
        dl.save(participant)


def _send_stub_invite(
    dl: SqliteDataLayer, actor_id: str, case_id: str, invitee_id: str
) -> dict[str, Any]:
    """Invite *invitee_id* as the owner *actor_id*; return the Invite emitted.

    The owner's trigger sends its own ``Offer(Actor, Case)`` to the
    CASE_MANAGER; the CASE_MANAGER emits the Invite (CM-17-007, ADR-0109).
    *actor_id* is both here — the store's owner holds CASE_MANAGER — so the
    Offer is delivered to the same store, as ADR-0109 lets an owner that is
    also the CASE_MANAGER address it to itself.
    """
    _hold_case_owner(dl, case_id, actor_id)
    offer = activity_of(
        SvcInviteActorToCaseUseCase(
            dl,
            InviteActorToCaseTriggerRequest(
                actor_id=actor_id,
                case_id=case_id,
                invitee_id=invitee_id,
                roles=[CVDRole.VENDOR],
            ),
            trigger_activity=TriggerActivityAdapter(dl),
            sync_port=SyncActivityAdapter(dl),
            wire_render_port=As2WireRenderAdapter(),
        ).execute()
    )
    already_queued = set(dl.outbox_list())
    stored_offer = dl.read(offer["id"])
    assert isinstance(stored_offer, as_Activity)
    event = extract_event(stored_offer).model_copy(
        update={"receiving_actor_id": actor_id}
    )
    assert isinstance(event, OfferActorToCaseReceivedEvent)
    result = OfferActorToCaseReceivedUseCase(
        dl,
        event,
        trigger_activity=TriggerActivityAdapter(dl),
        sync_port=SyncActivityAdapter(dl),
        wire_render_port=As2WireRenderAdapter(),
    ).execute()
    assert result.disposition is HandlerDisposition.APPLIED, result
    for item in dl.outbox_list():
        if item in already_queued:
            continue
        sealed = read_sealed_body(dl, item)
        if sealed is None:
            continue
        body: dict[str, Any] = json.loads(sealed.body)
        if body["type"] == "Invite":
            return body
    raise AssertionError("the CASE_MANAGER emitted no Invite")


def _vendor_participant(
    case_id: str, actor_id: str, rm_state: RM
) -> CaseParticipant:
    """A VENDOR participant record whose only status is at *rm_state*."""
    return CaseParticipant(
        attributed_to=actor_id,
        context=case_id,
        case_roles=[CVDRole.VENDOR],
        participant_statuses=[
            ParticipantStatus(
                context=case_id,
                attributed_to=actor_id,
                rm=RmDimension(state=rm_state),
                cvd_role=[CVDRole.VENDOR],
            )
        ],
    )


def _case_with_invitee_record(
    dl: SqliteDataLayer, manager_id: str, invitee_id: str, rm_state: RM
) -> tuple[VulnerabilityCase, CaseParticipant]:
    """A case the store owner manages, already holding *invitee_id*'s record.

    This is where CM-11-006 leaves a case after an earlier stub Invite.
    """
    case = VulnerabilityCase(
        attributed_to=manager_id,
        name="Re-invite",
        content="Content",
        stub_summary="Re-invite summary",
    )
    seed_store_owner_as_case_manager(dl, case)
    record = _vendor_participant(case.id_, invitee_id, rm_state)
    # The record an earlier stub Invite created is inert until it accepts.
    record.joined = False
    dl.create(record)
    case.case_participants.append(record.id_)
    case.actor_participant_index[invitee_id] = record.id_
    dl.create(case)
    return case, record


@pytest.mark.spec("CM-11-006")
def test_stub_invite_creates_inert_invitee_participant(actor_store) -> None:
    """The CASE_MANAGER records the invitee the moment it invites it.

    A VENDOR invitee to a case with an active embargo is a participant at RM
    ``RECEIVED``, VF ``v`` and consent ``INVITED`` straight after the stub
    Invite is sent, and the creation is on the case ledger.  Today the
    participant is created only when the invitee's ``Accept`` arrives.
    """
    manager, dl = actor_store("CaseManager")
    invitee, _ = actor_store("Vendor")
    dl.create(invitee)
    case = VulnerabilityCase(
        attributed_to=manager.id_,
        name="Joining",
        content="Content",
        stub_summary="Joining summary",
    )
    embargo = as_EmbargoEvent(
        id_=f"{case.id_}/embargo/e1",
        content="Active embargo",
        context=case.id_,
        end_time=days_from_now_utc(45),
    )
    dl.create(embargo)
    activate(case, embargo.id_)
    seed_store_owner_as_case_manager(dl, case)
    dl.create(case)

    _send_stub_invite(dl, manager.id_, case.id_, invitee.id_)

    participant = _participant_of(dl, case.id_, invitee.id_)
    assert CVDRole.VENDOR in participant.case_roles
    latest = participant.participant_statuses[-1]
    assert participant_status_rm_state(latest) == RM.RECEIVED
    assert participant_status_vf_state(latest) == CS_vf.vf
    assert participant.consent_for(embargo.id_) == EmbargoConsentState.INVITED

    creation_entries = [
        e
        for e in dl.list_objects("CaseLedgerEntry")
        if isinstance(e, CaseLedgerEntry)
        and e.case_id == case.id_
        and "participant" in e.event_type
        and invitee.id_ in json.dumps(e.payload_snapshot, default=str)
    ]
    assert creation_entries, "the participant's creation must be committed"


@pytest.mark.xfail(
    strict=True,
    reason=(
        "CM-11-018: a participant that joined through an Invite never"
        " answers the original Offer(VulnerabilityReport). Tracked by #4051."
    ),
)
@pytest.mark.spec("CM-11-018")
def test_joined_participant_never_answers_the_original_report_offer(
    actor_store,
) -> None:
    """A late-joining vendor judges the case, not the report submission.

    The joiner's store holds what the ledger replay gives it today: the
    finder's ``Offer(VulnerabilityReport)`` to the *original* vendor and the
    ``VultronOfferRecord`` that ``ApplyOfferReportFromLedgerNode`` builds
    from it.  Running ``validate-report`` as the joiner must not put an
    activity whose object is that Offer in its outbox — the Offer was never
    sent to it (ADR-0070).  Today the trigger emits ``Accept(Offer)``.
    """
    joiner, dl = actor_store("Vendor Two")
    original_vendor, _ = actor_store("Vendor One")
    finder, _ = actor_store("Finder")
    case_actor, _ = actor_store("Case Actor")

    report = as_VulnerabilityReport(
        name="CVE-JOIN",
        content="Vulnerability report content",
        attributed_to=finder.id_,
    )
    dl.create(report)
    offer = rm_submit_report_activity(
        report, original_vendor.id_, actor=finder.id_
    )
    dl.create(offer)
    dl.create(
        VultronOfferRecord(
            offer_id=offer.id_,
            report_id=report.id_,
            offer_actor_id=finder.id_,
            offer_to=[original_vendor.id_],
        )
    )

    embargo = as_EmbargoEvent(
        context="urn:placeholder", end_time=days_from_now_utc(45)
    )
    dl.create(embargo)
    case = VulnerabilityCase(name="Joined Case", attributed_to=case_actor.id_)
    activate(case, embargo.id_)
    case.vulnerability_reports.append(report.id_)
    manager = CaseParticipant(
        attributed_to=case_actor.id_,
        context=case.id_,
        case_roles=[CVDRole.CASE_MANAGER],
    )
    joined = _vendor_participant(case.id_, joiner.id_, RM.RECEIVED)
    for actor_id, participant in (
        (case_actor.id_, manager),
        (joiner.id_, joined),
    ):
        dl.create(participant)
        case.case_participants.append(participant.id_)
        case.actor_participant_index[actor_id] = participant.id_
    dl.create(case)
    dl.create(
        VultronReportCaseLink(report_id=report.id_, rm_state=RM.RECEIVED)
    )

    before = set(dl.outbox_list())
    try:
        SvcValidateReportUseCase(
            dl,
            ValidateReportTriggerRequest(
                actor_id=joiner.id_, offer_id=offer.id_
            ),
            trigger_activity=TriggerActivityAdapter(dl),
            sync_port=SyncActivityAdapter(dl),
        ).execute()
    except VultronError:
        # Refusing the trigger outright also satisfies CM-11-018.  The setup
        # is otherwise complete (today the trigger succeeds and emits
        # Accept(Offer)), so a raise here is the refusal, not a broken fixture.
        pass

    replies_to_offer = []
    for activity_id in set(dl.outbox_list()) - before:
        activity = dl.read(activity_id)
        obj = getattr(activity, "object_", None)
        if getattr(obj, "id_", obj) == offer.id_:
            replies_to_offer.append(getattr(activity, "type_", activity_id))
    assert replies_to_offer == [], (
        f"joined participant answered the report Offer: {replies_to_offer}"
    )


@pytest.mark.spec("PRM-06-006")
@pytest.mark.parametrize(
    "dimension",
    [{"vf_state": CS_vf.Vf}, {"d_state": CS_d.D}],
    ids=["v-to-V", "d-to-D"],
)
def test_on_behalf_assertion_for_absent_target_is_refused(
    actor_store, dimension: dict[str, Any]
) -> None:
    """A status update is never a way into a case.

    The Case Manager asserts ``v→V`` or ``d→D`` on behalf of an actor that is
    not a participant.  The trigger must refuse before any write and leave
    the roster exactly as it was.  It used to mint a participant for the
    absent target (and, for ``d→D``, leave it behind when the RM↔D
    entailment then refused the status write).
    """
    manager, dl = actor_store("CaseManager")
    outsider, _ = actor_store("Outsider")
    case = VulnerabilityCase(name="On-behalf", attributed_to=manager.id_)
    seed_store_owner_as_case_manager(dl, case)
    dl.create(case)
    roster_before = dict(case.actor_participant_index)
    participants_before = list(case.case_participants)

    with pytest.raises(VultronError):
        SvcAddOnBehalfStatusUseCase(
            dl,
            AddOnBehalfStatusTriggerRequest(
                actor_id=manager.id_,
                case_id=case.id_,
                target_actor_id=outsider.id_,
                **dimension,
            ),
            trigger_activity=TriggerActivityAdapter(dl),
            sync_port=SyncActivityAdapter(dl),
        ).execute()

    after = dl.read_case(case.id_)
    assert after is not None
    assert dict(after.actor_participant_index) == roster_before
    assert list(after.case_participants) == participants_before


@pytest.mark.spec("CM-11-014")
def test_stub_invite_has_deadline_and_unanswered_invitee_never_blocks_closure(
    actor_store,
) -> None:
    """An invitee that never answers stays at ``RECEIVED`` and is not counted.

    The stub Invite names a reply deadline (``endTime``, as an embargo Invite
    does).  The record the Invite created stays inert at ``RECEIVED`` — the
    CASE_MANAGER cannot judge the case for it — so a case whose joined
    participants have all closed counts as closed.  Today the stub Invite
    has no deadline (and no record exists until the invitee accepts).
    """
    manager, dl = actor_store("CaseManager")
    invitee, _ = actor_store("Vendor")
    dl.create(invitee)
    case = VulnerabilityCase(
        attributed_to=manager.id_,
        name="Unanswered",
        content="Content",
        stub_summary="Unanswered summary",
    )
    manager_record = seed_store_owner_as_case_manager(dl, case)
    dl.create(case)

    invite = _send_stub_invite(dl, manager.id_, case.id_, invitee.id_)

    assert invite.get("endTime") is not None, "stub Invite needs a deadline"
    unanswered = _participant_of(dl, case.id_, invitee.id_)
    assert (
        participant_status_rm_state(unanswered.participant_statuses[-1])
        == RM.RECEIVED
    )
    closed_manager = manager_record.model_copy(
        update={
            "participant_statuses": [
                ParticipantStatus(
                    context=case.id_,
                    attributed_to=manager.id_,
                    rm=RmDimension(state=RM.CLOSED),
                    cvd_role=[CVDRole.CASE_MANAGER],
                )
            ]
        }
    )
    assert all_participants_rm_closed([closed_manager, unanswered])


@pytest.mark.spec("CM-11-015")
def test_reinvite_reuses_the_invitee_record_with_a_new_deadline(
    actor_store,
) -> None:
    """Re-inviting an unanswered invitee adds no second record.

    Today no re-invite goes out at all: the CASE_MANAGER's recommend-actor
    tree finds the invitee already on the roster and answers the owner's
    Offer from its already-participant branch, ahead of the owner-direct
    branch that emits the Invite (#3821).
    """
    manager, dl = actor_store("CaseManager")
    invitee, _ = actor_store("Vendor")
    dl.create(invitee)
    case, record = _case_with_invitee_record(
        dl, manager.id_, invitee.id_, RM.RECEIVED
    )

    invite = _send_stub_invite(dl, manager.id_, case.id_, invitee.id_)

    assert invite.get("endTime") is not None, "re-invite needs a deadline"
    after = dl.read_case(case.id_)
    assert after is not None
    assert after.actor_participant_index[invitee.id_] == record.id_
    assert list(after.case_participants).count(record.id_) == 1
    assert len(after.case_participants) == len(case.case_participants)


@pytest.mark.spec("CM-11-015")
def test_reinvite_to_closed_participant_is_refused(actor_store) -> None:
    """``CLOSED`` is terminal with no rejoin; the trigger refuses the Invite.

    Today the trigger accepts the request and queues the owner's Offer; the
    CASE_MANAGER then answers it from its already-participant branch and
    sends no Invite (#3821), so nothing refuses it.
    """
    manager, dl = actor_store("CaseManager")
    invitee, _ = actor_store("Vendor")
    dl.create(invitee)
    case, _ = _case_with_invitee_record(
        dl, manager.id_, invitee.id_, RM.CLOSED
    )
    before = set(dl.outbox_list())

    with pytest.raises(VultronError):
        _send_stub_invite(dl, manager.id_, case.id_, invitee.id_)

    assert set(dl.outbox_list()) == before


def _invites_to(dl: SqliteDataLayer, invitee_id: str) -> list[as_Invite]:
    return [
        obj
        for obj in dl.list_objects("Invite")
        if isinstance(obj, as_Invite)
        and getattr(obj.object_, "id_", obj.object_) == invitee_id
    ]


@pytest.mark.spec("CM-11-016")
def test_embargo_change_reissues_outstanding_stub_invite(actor_store) -> None:
    """Terminating the embargo re-issues the stub Invite with current terms.

    The replacement goes to the same invitee and names the Invite it
    supersedes; an ``Accept`` of the superseded Invite is then refused, and
    the refusal names the replacement.
    """
    owner, dl = actor_store("Vendor Owner")
    finder, _ = actor_store("Finder")
    invitee, _ = actor_store("Vendor Two")
    dl.create(finder)
    dl.create(invitee)
    case, _, _ = _build_active_embargo_case(dl, owner.id_, finder.id_)
    original_id = _send_stub_invite(dl, owner.id_, case.id_, invitee.id_)["id"]

    SvcTerminateEmbargoUseCase(
        dl,
        TerminateEmbargoTriggerRequest(actor_id=owner.id_, case_id=case.id_),
        trigger_activity=TriggerActivityAdapter(dl),
        sync_port=SyncActivityAdapter(dl),
        wire_render_port=As2WireRenderAdapter(),
    ).execute()

    replacements = [
        invite
        for invite in _invites_to(dl, invitee.id_)
        if invite.id_ != original_id
        and original_id
        in invite.model_dump_json(by_alias=True, exclude={"id_"})
    ]
    assert replacements, "no replacement stub Invite names the superseded one"

    original = dl.read(original_id)
    assert isinstance(original, as_Invite)
    result = route_received(
        dl,
        as_Accept(
            actor=invitee.id_, object_=original, in_reply_to=original_id
        ),
        receiving_actor_id=owner.id_,
    )
    assert result.disposition is HandlerDisposition.REFUSED
    assert result.reason is not None
    assert any(r.id_ in result.reason for r in replacements), result.reason


def _accept_stub_invite(
    dl: SqliteDataLayer, manager_id: str, invitee_id: str, invite_id: str
) -> None:
    """Deliver the invitee's ``Accept`` of the stub Invite to the CASE_MANAGER."""
    invite = dl.read(invite_id)
    assert isinstance(invite, as_Invite)
    result = route_received(
        dl,
        as_Accept(actor=invitee_id, object_=invite, in_reply_to=invite_id),
        receiving_actor_id=manager_id,
    )
    assert result.disposition is HandlerDisposition.APPLIED, result.reason


@pytest.mark.spec("CM-11-014")
def test_closure_check_skips_only_participants_that_never_joined(
    actor_store,
) -> None:
    """``RECEIVED`` is not the test — having joined is.

    Two vendors are invited; one accepts its stub Invite and is still at
    ``RECEIVED``, the other never answers.  Only the unanswered one is left
    out of the closure check, so the joined vendor keeps the case open.  A
    directly seated participant that has not closed keeps it open too.  This
    is what tells "count only joined participants" apart from "skip every
    ``RECEIVED`` participant".  Today the stub Invite creates no record.
    """
    manager, dl = actor_store("CaseManager")
    silent, _ = actor_store("Silent Vendor")
    joiner, _ = actor_store("Joining Vendor")
    for invitee in (silent, joiner):
        dl.create(invitee)
    case = VulnerabilityCase(
        attributed_to=manager.id_,
        name="Closure",
        content="Content",
        stub_summary="Closure summary",
    )
    manager_record = seed_store_owner_as_case_manager(dl, case)
    dl.create(case)

    _send_stub_invite(dl, manager.id_, case.id_, silent.id_)
    joiner_invite = _send_stub_invite(dl, manager.id_, case.id_, joiner.id_)
    unanswered = _participant_of(dl, case.id_, silent.id_)
    _accept_stub_invite(dl, manager.id_, joiner.id_, joiner_invite["id"])
    joined = _participant_of(dl, case.id_, joiner.id_)
    assert (
        participant_status_rm_state(joined.participant_statuses[-1])
        == RM.RECEIVED
    )

    closed_manager = manager_record.model_copy(
        update={
            "participant_statuses": [
                ParticipantStatus(
                    context=case.id_,
                    attributed_to=manager.id_,
                    rm=RmDimension(state=RM.CLOSED),
                    cvd_role=[CVDRole.CASE_MANAGER],
                )
            ]
        }
    )
    seated_open = _vendor_participant(
        case.id_, "https://example.org/actors/seated", RM.ACCEPTED
    )
    assert all_participants_rm_closed([closed_manager, unanswered])
    assert not all_participants_rm_closed([closed_manager, unanswered, joined])
    assert not all_participants_rm_closed(
        [closed_manager, unanswered, seated_open]
    )


@pytest.mark.spec("CM-11-016")
def test_reject_of_superseded_stub_invite_is_honoured(actor_store) -> None:
    """A hard no does not depend on which version of the ask it answers.

    After an embargo change re-issues the stub Invite, the invitee rejects
    the *original*.  The CASE_MANAGER honours it: the record moves to RM
    ``CLOSED`` (CM-11-007) rather than being refused as stale.  Today no
    replacement is issued and the Reject leaves no record to close.
    """
    owner, dl = actor_store("Vendor Owner")
    finder, _ = actor_store("Finder")
    invitee, _ = actor_store("Vendor Two")
    dl.create(finder)
    dl.create(invitee)
    case, _, _ = _build_active_embargo_case(dl, owner.id_, finder.id_)
    original_id = _send_stub_invite(dl, owner.id_, case.id_, invitee.id_)["id"]

    SvcTerminateEmbargoUseCase(
        dl,
        TerminateEmbargoTriggerRequest(actor_id=owner.id_, case_id=case.id_),
        trigger_activity=TriggerActivityAdapter(dl),
        sync_port=SyncActivityAdapter(dl),
        wire_render_port=As2WireRenderAdapter(),
    ).execute()
    assert [
        invite
        for invite in _invites_to(dl, invitee.id_)
        if invite.id_ != original_id
    ], "the embargo change must have superseded the original stub Invite"

    original = dl.read(original_id)
    assert isinstance(original, as_Invite)
    result = route_received(
        dl,
        as_Reject(
            actor=invitee.id_, object_=original, in_reply_to=original_id
        ),
        receiving_actor_id=owner.id_,
    )

    assert result.disposition is HandlerDisposition.APPLIED, result.reason
    record = _participant_of(dl, case.id_, invitee.id_)
    assert (
        participant_status_rm_state(record.participant_statuses[-1])
        == RM.CLOSED
    )


@pytest.mark.spec("CM-10-007")
def test_stub_invite_is_addressed_to_the_inert_invitee(actor_store) -> None:
    """An Invite asking an actor to join is not case content.

    The active-participant filter (CM-10-004) must not swallow it: the stub
    Invite reaches the invitee even though, with an embargo active and no
    consent yet, the invitee is inert.
    """
    owner, dl = actor_store("Vendor Owner")
    finder, _ = actor_store("Finder")
    invitee, _ = actor_store("Vendor Two")
    dl.create(finder)
    dl.create(invitee)
    case, _, _ = _build_active_embargo_case(dl, owner.id_, finder.id_)

    invite = _send_stub_invite(dl, owner.id_, case.id_, invitee.id_)

    to = invite.get("to")
    recipients = [to] if isinstance(to, str) else list(to or [])
    assert invitee.id_ in recipients


@pytest.mark.spec("PRM-06-001")
def test_stub_invite_writes_only_the_invitee_birth_status(
    actor_store,
) -> None:
    """Status is self-declared; the CASE_MANAGER writes only the record's birth.

    Straight after the stub Invite the invitee's record holds exactly one
    participant status, at RM ``RECEIVED``; every later status is the
    participant's own.  Today the stub Invite creates no record at all.
    """
    manager, dl = actor_store("CaseManager")
    invitee, _ = actor_store("Vendor")
    dl.create(invitee)
    case = VulnerabilityCase(
        attributed_to=manager.id_,
        name="Birth",
        content="Content",
        stub_summary="Birth summary",
    )
    seed_store_owner_as_case_manager(dl, case)
    dl.create(case)

    _send_stub_invite(dl, manager.id_, case.id_, invitee.id_)

    statuses = _participant_of(dl, case.id_, invitee.id_).participant_statuses
    assert [participant_status_rm_state(s) for s in statuses] == [RM.RECEIVED]
