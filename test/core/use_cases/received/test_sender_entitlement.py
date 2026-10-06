#  Copyright (c) 2025-2026 Carnegie Mellon University and Contributors.
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
"""Marker tests for the received-side sender-entitlement rules (ADR-0115).

ADR-0115 (``docs/adr/0115-received-handlers-check-sender-entitlement.md``)
and HP-01-006 require a received handler to establish that the *sender* of
an activity is entitled to make its assertion before any write, outbound
activity or ledger commit, and to report ``REFUSED`` when it cannot.  The
receiver's own role (the CASE_MANAGER gate, BT-17-001) never satisfies it.

Each test below sends an activity from an unentitled sender to the real
received use case, with every other precondition for the effect in place,
and asserts ``REFUSED`` with no protocol effect.  None of these handlers
checks its sender yet, so each test is a strict ``xfail``: the handler
applies the change.  The implementation issue that adds a handler's sender
check removes that test's ``xfail`` marker (tracked by #3733).
"""

from typing import Any, cast
from unittest.mock import MagicMock

import pytest

from test.core.use_cases.received.actor.test_offer_case_participant import (
    CASE_ACTOR_ID as RECOMMEND_CASE_MANAGER_ID,
    CASE_ID as RECOMMEND_CASE_ID,
    CASE_OWNER_ID as RECOMMEND_CASE_OWNER_ID,
    _build_offer_activity,
    _case_ref,
    _seed_dl_for_case_actor,
)
from test.core.use_cases.received.conftest import (
    seed_case_manager_participant,
    seed_case_participant,
    seed_store_owner_as_case_manager,
)
from test.core.use_cases.received.test_case_proposal import (
    _VENDOR_URI,
    _make_proposal,
    _seed_vendor_link,
)
from test.core.use_cases.received.test_reject_sync import (
    CASE_ACTOR_URI as SYNC_CASE_MANAGER_ID,
    CASE_URI as SYNC_CASE_ID,
    _make_entry,
    _make_reject_event,
)
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driven.sync_activity_adapter import SyncActivityAdapter
from vultron.adapters.driven.trigger_activity_adapter import (
    TriggerActivityAdapter,
)
from vultron.adapters.driven.wire_render.as2 import As2WireRenderAdapter
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.events.actor import (
    AcceptOfferCaseParticipantReceivedEvent,
    OfferCaseParticipantReceivedEvent,
    RejectOfferCaseParticipantReceivedEvent,
)
from vultron.core.models.replication_state import VultronReplicationState
from vultron.core.models.report_case_link import VultronReportCaseLink
from vultron.core.models.use_case_result import HandlerDisposition
from vultron.core.use_cases.received.actor.invite import (
    AcceptInviteActorToCaseReceivedUseCase,
)
from vultron.core.use_cases.received.actor.offer_case_participant import (
    AcceptOfferCaseParticipantReceivedUseCase,
    OfferCaseParticipantReceivedUseCase,
    RejectOfferCaseParticipantReceivedUseCase,
)
from vultron.core.use_cases.received.actor.ownership import (
    AcceptCaseOwnershipTransferReceivedUseCase,
)
from vultron.core.use_cases.received.case.lifecycle import (
    AddReportToCaseReceivedUseCase,
)
from vultron.core.use_cases.received.case_proposal import (
    AcceptCaseProposalReceivedUseCase,
    RejectCaseProposalReceivedUseCase,
)
from vultron.core.use_cases.received.note import (
    RemoveNoteFromCaseReceivedUseCase,
)
from vultron.core.use_cases.received.sync import (
    RejectLedgerEntryReceivedUseCase,
)
from vultron.enums.roles import CVDRole
from vultron.semantic_registry import extract_event
from vultron.wire.as2.factories import (
    accept_case_ownership_transfer_activity,
    accept_case_participant_offer_activity,
    add_report_to_case_activity,
    offer_case_ownership_transfer_activity,
    reject_case_participant_offer_activity,
    rm_accept_invite_to_case_activity,
    rm_invite_to_case_activity,
)
from vultron.wire.as2.vocab.base.objects.activities.transitive import (
    as_Accept,
    as_Reject,
    as_Remove,
)
from vultron.wire.as2.vocab.base.objects.actors import as_Actor
from vultron.wire.as2.vocab.base.objects.object_types import as_Note
from vultron.wire.as2.vocab.examples._base import gen_report
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
    as_VulnerabilityCaseStub,
)

#: The receiving store's owner, seeded as the case's CASE_MANAGER, so every
#: receiver-side gate passes and only the sender check can refuse.
_CASE_MANAGER_ID = "https://example.org/actors/case-manager"
_OWNER_ID = "https://example.org/actors/case-owner"
#: An actor with no standing for any of the assertions below.
_IMPOSTOR_ID = "https://example.org/actors/impostor"


@pytest.fixture
def cm_store() -> SqliteDataLayer:
    """The CASE_MANAGER's own store (the case is seeded by each test)."""
    return SqliteDataLayer("sqlite:///:memory:", actor_id=_CASE_MANAGER_ID)


@pytest.fixture
def owned_case(cm_store: SqliteDataLayer) -> as_VulnerabilityCase:
    """A case owned by ``_OWNER_ID`` and managed by the store's owner."""
    case = as_VulnerabilityCase(
        id_="https://example.org/cases/sender-entitlement",
        name="Sender entitlement",
        attributed_to=_OWNER_ID,
    )
    seed_store_owner_as_case_manager(cm_store, case)
    return case


def _reload_case(dl: SqliteDataLayer, case_id: str) -> VulnerabilityCase:
    case = dl.read(case_id)
    assert isinstance(case, VulnerabilityCase)
    return case


def _ref_id(ref: Any) -> str:
    return ref if isinstance(ref, str) else ref.id_


def _report_id(report: Any) -> str:
    report_id = getattr(report, "id_", None)
    assert isinstance(report_id, str)
    return report_id


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="CM-21-011: ownership Accept from a non-transferee is applied. Tracked by #4070.",
)
@pytest.mark.spec("CM-21-011")
@pytest.mark.spec("HP-01-006")
def test_ownership_accept_from_non_transferee_is_refused(
    cm_store, owned_case, make_payload
):
    """The recorded Offer names another transferee; the impostor accepts it."""
    cm_store.create(owned_case)
    offer = offer_case_ownership_transfer_activity(
        owned_case,
        # Inline, as the inbox rehydrates it: the ledger commit refuses a
        # bare-id target (VultronCanonicalEntryError).
        target=as_Actor(id_="https://example.org/actors/transferee"),
        actor=_OWNER_ID,
        id_="https://example.org/activities/offer-ownership-se",
    )
    cm_store.create(offer)
    event = make_payload(
        accept_case_ownership_transfer_activity(offer, actor=_IMPOSTOR_ID),
        receiving_actor_id=_CASE_MANAGER_ID,
    )

    result = AcceptCaseOwnershipTransferReceivedUseCase(
        cm_store,
        event,
        sync_port=SyncActivityAdapter(cm_store),
        wire_render_port=As2WireRenderAdapter(),
    ).execute()

    assert result.disposition is HandlerDisposition.REFUSED
    assert _reload_case(cm_store, owned_case.id_).attributed_to == _OWNER_ID
    assert cm_store.outbox_list() == []


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="CM-11-017: Accept of an Invite never recorded admits the sender. Tracked by #4071.",
)
@pytest.mark.spec("CM-11-017")
def test_accept_of_unrecorded_invite_is_refused(
    cm_store, owned_case, make_payload
):
    """The CASE_MANAGER never sent or recorded the Invite being accepted."""
    cm_store.create(owned_case)
    invite = rm_invite_to_case_activity(
        as_Actor(id_=_IMPOSTOR_ID),
        target=as_VulnerabilityCaseStub(case_id=owned_case.id_),
        actor=_OWNER_ID,
        id_=f"{owned_case.id_}/invitations/forged",
    )
    event = make_payload(
        rm_accept_invite_to_case_activity(invite, actor=_IMPOSTOR_ID)
    )

    result = AcceptInviteActorToCaseReceivedUseCase(
        cm_store,
        event,
        sync_port=MagicMock(),
        wire_render_port=As2WireRenderAdapter(),
    ).execute()

    assert result.disposition is HandlerDisposition.REFUSED
    case = _reload_case(cm_store, owned_case.id_)
    assert _IMPOSTOR_ID not in case.actor_participant_index
    assert cm_store.outbox_list() == []


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="CM-11-017: roles are taken from the Invite embedded in the reply. Tracked by #4071.",
)
@pytest.mark.spec("CM-11-017")
def test_accept_of_invite_takes_roles_from_recorded_invite(
    cm_store, owned_case, make_payload
):
    """The invitee's reply embeds a copy of its Invite with a forged role."""
    invitee_id = "https://example.org/actors/invitee"
    invite_id = f"{owned_case.id_}/invitations/recorded"
    cm_store.create(owned_case)
    cm_store.create(
        rm_invite_to_case_activity(
            as_Actor(id_=invitee_id),
            target=as_VulnerabilityCaseStub(case_id=owned_case.id_),
            roles=[CVDRole.VENDOR],
            actor=_OWNER_ID,
            id_=invite_id,
        )
    )
    forged = rm_invite_to_case_activity(
        as_Actor(id_=invitee_id),
        target=as_VulnerabilityCaseStub(case_id=owned_case.id_),
        roles=[CVDRole.VENDOR, CVDRole.CASE_OWNER],
        actor=_OWNER_ID,
        id_=invite_id,
    )
    event = make_payload(
        rm_accept_invite_to_case_activity(forged, actor=invitee_id)
    )

    AcceptInviteActorToCaseReceivedUseCase(
        cm_store,
        event,
        sync_port=MagicMock(),
        wire_render_port=As2WireRenderAdapter(),
    ).execute()

    case = _reload_case(cm_store, owned_case.id_)
    participant = cm_store.read(case.actor_participant_index[invitee_id])
    assert isinstance(participant, CaseParticipant)
    assert CVDRole.CASE_OWNER not in participant.case_roles


@pytest.mark.spec("CM-16-019")
@pytest.mark.spec("HP-01-006")
def test_recommendation_accept_from_non_owner_is_refused():
    """The Accept comes from a participant that is not the Case Owner.

    Seeding the sender as a participant shows the check is about ownership,
    not case membership.
    """
    dl, _ = _seed_dl_for_case_actor()
    _seed_impostor_participant(dl)
    accept = accept_case_participant_offer_activity(
        _build_offer_activity(),
        target=_case_ref(RECOMMEND_CASE_ID),
        actor=_IMPOSTOR_ID,
        to=[RECOMMEND_CASE_MANAGER_ID],
    )
    event = cast(
        AcceptOfferCaseParticipantReceivedEvent, extract_event(accept)
    )

    result = AcceptOfferCaseParticipantReceivedUseCase(
        dl,
        event,
        trigger_activity=TriggerActivityAdapter(dl),
        sync_port=SyncActivityAdapter(dl),
        wire_render_port=As2WireRenderAdapter(),
    ).execute()

    assert result.disposition is HandlerDisposition.REFUSED
    assert "Case Owner" in (result.reason or "")
    assert dl.outbox_list() == []


def _seed_impostor_participant(dl: SqliteDataLayer) -> None:
    """Make the impostor a plain participant of the recommendation's case."""
    case = _reload_case(dl, RECOMMEND_CASE_ID)
    seed_case_participant(dl, case, _IMPOSTOR_ID, [CVDRole.VENDOR])
    dl.save(case)


@pytest.mark.spec("CM-16-019")
@pytest.mark.spec("HP-01-006")
def test_recommendation_reject_from_non_owner_is_refused():
    """The Reject comes from a participant that is not the Case Owner.

    The recommender must not be told the recommendation was rejected by
    someone with no standing to decide it.
    """
    dl, _ = _seed_dl_for_case_actor()
    _seed_impostor_participant(dl)
    reject = reject_case_participant_offer_activity(
        _build_offer_activity(),
        target=_case_ref(RECOMMEND_CASE_ID),
        actor=_IMPOSTOR_ID,
        to=[RECOMMEND_CASE_MANAGER_ID],
    )
    event = cast(
        RejectOfferCaseParticipantReceivedEvent, extract_event(reject)
    )

    result = RejectOfferCaseParticipantReceivedUseCase(
        dl,
        event,
        trigger_activity=TriggerActivityAdapter(dl),
        sync_port=SyncActivityAdapter(dl),
        wire_render_port=As2WireRenderAdapter(),
    ).execute()

    assert result.disposition is HandlerDisposition.REFUSED
    assert "Case Owner" in (result.reason or "")
    assert dl.outbox_list() == []
    assert dl.list_objects("CaseLedgerEntry") == []


@pytest.mark.spec("CM-16-004")
@pytest.mark.spec("HP-01-006")
def test_offer_case_participant_from_non_case_manager_is_refused():
    """The Case Owner receives an Offer(CaseParticipant) a stranger sent.

    Only the CASE_MANAGER forwards a recommendation to the owner (CM-16-004),
    so an Offer from any other actor is not the owner's to decide.
    """
    dl = SqliteDataLayer(
        "sqlite:///:memory:", actor_id=RECOMMEND_CASE_OWNER_ID
    )
    case = as_VulnerabilityCase(
        id_=RECOMMEND_CASE_ID,
        name="Sender entitlement",
        attributed_to=RECOMMEND_CASE_OWNER_ID,
    )
    seed_case_manager_participant(dl, case, RECOMMEND_CASE_MANAGER_ID)
    dl.create(case)
    offer = _build_offer_activity(
        actor=_IMPOSTOR_ID, to=[RECOMMEND_CASE_OWNER_ID]
    )
    event = cast(OfferCaseParticipantReceivedEvent, extract_event(offer))

    result = OfferCaseParticipantReceivedUseCase(
        dl,
        event,
        trigger_activity=TriggerActivityAdapter(dl),
        sync_port=SyncActivityAdapter(dl),
        wire_render_port=As2WireRenderAdapter(),
    ).execute()

    assert result.disposition is HandlerDisposition.REFUSED
    assert "CASE_MANAGER" in (result.reason or "")
    assert dl.outbox_list() == []


@pytest.mark.spec("CP-06-005")
def test_case_proposal_accept_from_non_addressee_is_refused(make_payload):
    """The vendor addressed the proposal to another case actor."""
    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=_VENDOR_URI)
    proposal = _make_proposal()
    _seed_vendor_link(dl, proposal)
    report = proposal.object_
    assert report is not None
    link_id = VultronReportCaseLink.build_id(_report_id(report))
    event = make_payload(
        as_Accept(actor=_IMPOSTOR_ID, object_=proposal, to=[_VENDOR_URI]),
        receiving_actor_id=_VENDOR_URI,
    )

    result = AcceptCaseProposalReceivedUseCase(dl, event).execute()

    assert result.disposition is HandlerDisposition.REFUSED
    link = dl.read(link_id)
    assert isinstance(link, VultronReportCaseLink)
    assert link.case_manager_id is None
    assert dl.outbox_list() == []


@pytest.mark.spec("CP-06-005")
def test_case_proposal_reject_from_non_addressee_is_refused(make_payload):
    """A Reject from an actor the proposal was not addressed to is refused."""
    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=_VENDOR_URI)
    proposal = _make_proposal()
    _seed_vendor_link(dl, proposal)
    report = proposal.object_
    assert report is not None
    link_id = VultronReportCaseLink.build_id(_report_id(report))
    event = make_payload(
        as_Reject(actor=_IMPOSTOR_ID, object_=proposal, to=[_VENDOR_URI]),
        receiving_actor_id=_VENDOR_URI,
    )

    result = RejectCaseProposalReceivedUseCase(dl, event).execute()

    assert result.disposition is HandlerDisposition.REFUSED
    link = dl.read(link_id)
    assert isinstance(link, VultronReportCaseLink)
    assert link.proposal_rejected is False
    assert link.rejection_reason is None
    assert dl.outbox_list() == []


@pytest.mark.spec("CP-06-005")
def test_case_proposal_reply_with_no_recorded_addressee_is_refused(
    make_payload,
):
    """A link that records nobody entitles nobody."""
    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=_VENDOR_URI)
    proposal = _make_proposal()
    report = proposal.object_
    assert report is not None
    link_id = VultronReportCaseLink.build_id(_report_id(report))
    dl.create(VultronReportCaseLink(report_id=_report_id(report)))
    event = make_payload(
        as_Accept(actor=_IMPOSTOR_ID, object_=proposal, to=[_VENDOR_URI]),
        receiving_actor_id=_VENDOR_URI,
    )

    result = AcceptCaseProposalReceivedUseCase(dl, event).execute()

    assert result.disposition is HandlerDisposition.REFUSED
    link = dl.read(link_id)
    assert isinstance(link, VultronReportCaseLink)
    assert link.case_manager_id is None


@pytest.mark.spec("CP-06-005")
def test_case_proposal_accept_after_case_established_keeps_case_manager(
    make_payload,
):
    """Once a case is established, even the addressee's reply replaces nothing."""
    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=_VENDOR_URI)
    proposal = _make_proposal()
    _seed_vendor_link(dl, proposal)
    report = proposal.object_
    assert report is not None
    link_id = VultronReportCaseLink.build_id(_report_id(report))
    link = dl.read(link_id)
    assert isinstance(link, VultronReportCaseLink)
    link.case_id = "https://example.org/cases/established"
    link.case_manager_id = _CASE_MANAGER_ID
    dl.save(link)
    event = make_payload(
        as_Accept(
            actor=link.case_creator_id, object_=proposal, to=[_VENDOR_URI]
        ),
        receiving_actor_id=_VENDOR_URI,
    )

    AcceptCaseProposalReceivedUseCase(dl, event).execute()

    reloaded = dl.read(link_id)
    assert isinstance(reloaded, VultronReportCaseLink)
    assert reloaded.case_manager_id == _CASE_MANAGER_ID


@pytest.mark.spec("CP-06-005")
def test_case_proposal_reject_after_case_established_leaves_link_unchanged(
    make_payload,
):
    """A late Reject from the addressee must not re-open the proposal."""
    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=_VENDOR_URI)
    proposal = _make_proposal()
    _seed_vendor_link(dl, proposal)
    report = proposal.object_
    assert report is not None
    link_id = VultronReportCaseLink.build_id(_report_id(report))
    link = dl.read(link_id)
    assert isinstance(link, VultronReportCaseLink)
    link.case_id = "https://example.org/cases/established"
    dl.save(link)
    event = make_payload(
        as_Reject(
            actor=link.case_creator_id, object_=proposal, to=[_VENDOR_URI]
        ),
        receiving_actor_id=_VENDOR_URI,
    )

    RejectCaseProposalReceivedUseCase(dl, event).execute()

    reloaded = dl.read(link_id)
    assert isinstance(reloaded, VultronReportCaseLink)
    assert reloaded.proposal_rejected is False
    assert reloaded.rejection_reason is None


@pytest.mark.spec("CP-06-005")
def test_case_proposal_accept_from_addressee_with_trailing_slash_is_applied(
    make_payload,
):
    """The addressee is recognised whichever way the id is written."""
    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=_VENDOR_URI)
    proposal = _make_proposal()
    _seed_vendor_link(dl, proposal)
    report = proposal.object_
    assert report is not None
    link_id = VultronReportCaseLink.build_id(_report_id(report))
    link = dl.read(link_id)
    assert isinstance(link, VultronReportCaseLink)
    assert link.case_creator_id is not None
    sender = link.case_creator_id + "/"
    event = make_payload(
        as_Accept(actor=sender, object_=proposal, to=[_VENDOR_URI]),
        receiving_actor_id=_VENDOR_URI,
    )

    result = AcceptCaseProposalReceivedUseCase(dl, event).execute()

    assert result.disposition is HandlerDisposition.APPLIED
    reloaded = dl.read(link_id)
    assert isinstance(reloaded, VultronReportCaseLink)
    assert reloaded.case_manager_id == sender


@pytest.mark.spec("CM-30-001")
def test_note_removal_by_stranger_is_refused(
    cm_store, owned_case, make_payload
):
    """The note's author and the case owner are both somebody else."""
    note = as_Note(
        id_="https://example.org/notes/sender-entitlement",
        content="A note",
        attributed_to="https://example.org/actors/note-author",
    )
    owned_case.notes.append(note.id_)
    cm_store.create(note)
    cm_store.create(owned_case)
    event = make_payload(
        as_Remove(actor=_IMPOSTOR_ID, object_=note, target=owned_case.id_)
    )

    result = RemoveNoteFromCaseReceivedUseCase(
        cm_store, event, wire_render_port=As2WireRenderAdapter()
    ).execute()

    assert result.disposition is HandlerDisposition.REFUSED
    case = _reload_case(cm_store, owned_case.id_)
    assert note.id_ in [_ref_id(n) for n in case.notes]
    assert cm_store.outbox_list() == []


@pytest.mark.spec("CM-30-002")
def test_report_addition_by_non_owner_is_refused(
    cm_store, owned_case, make_payload
):
    """Only the Case Owner may add a report to the case."""
    cm_store.create(owned_case)
    report = gen_report()
    event = make_payload(
        add_report_to_case_activity(
            report, target=owned_case.id_, actor=_IMPOSTOR_ID
        )
    )

    result = AddReportToCaseReceivedUseCase(cm_store, event).execute()

    assert result.disposition is HandlerDisposition.REFUSED
    case = _reload_case(cm_store, owned_case.id_)
    assert report.id_ not in [_ref_id(r) for r in case.vulnerability_reports]
    assert cm_store.outbox_list() == []


@pytest.mark.spec("SYNC-03-005")
def test_ledger_reject_from_non_participant_is_refused():
    """A stranger claims an empty ledger, asking for a replay from genesis."""
    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=SYNC_CASE_MANAGER_ID)
    entry0 = _make_entry(SYNC_CASE_ID, 0, "0" * 64)
    dl.save(entry0)
    case = as_VulnerabilityCase(id_=SYNC_CASE_ID, name="Reject Sync Case")
    seed_store_owner_as_case_manager(dl, case)
    dl.create(case)
    event = _make_reject_event(entry0, "", _IMPOSTOR_ID)

    result = RejectLedgerEntryReceivedUseCase(
        dl, event, sync_port=SyncActivityAdapter(dl)
    ).execute()

    assert result.disposition is HandlerDisposition.REFUSED
    assert dl.outbox_list() == []
    assert not dl.by_type("Announce")
    state_id = VultronReplicationState(
        case_id=SYNC_CASE_ID, peer_id=_IMPOSTOR_ID
    ).id_
    assert dl.read(state_id) is None


@pytest.mark.spec("SYNC-03-005")
def test_ledger_reject_for_unknown_case_is_refused():
    """With no case there is no participant, so nothing is written or sent."""
    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=SYNC_CASE_MANAGER_ID)
    entry0 = _make_entry(SYNC_CASE_ID, 0, "0" * 64)
    dl.save(entry0)
    event = _make_reject_event(entry0, "", _IMPOSTOR_ID)

    result = RejectLedgerEntryReceivedUseCase(
        dl, event, sync_port=SyncActivityAdapter(dl)
    ).execute()

    assert result.disposition is HandlerDisposition.REFUSED
    assert dl.outbox_list() == []
    state_id = VultronReplicationState(
        case_id=SYNC_CASE_ID, peer_id=_IMPOSTOR_ID
    ).id_
    assert dl.read(state_id) is None
