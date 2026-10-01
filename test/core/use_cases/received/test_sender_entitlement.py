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

import py_trees
import pytest

from test.core.use_cases.received.actor.test_offer_case_participant import (
    CASE_ACTOR_ID as RECOMMEND_CASE_MANAGER_ID,
    CASE_ID as RECOMMEND_CASE_ID,
    _build_offer_activity,
    _case_ref,
    _seed_dl_for_case_actor,
)
from test.core.use_cases.received.conftest import (
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
from vultron.core.models.events.actor import (
    AcceptOfferCaseParticipantReceivedEvent,
)
from vultron.core.models.replication_state import VultronReplicationState
from vultron.core.models.report_case_link import VultronReportCaseLink
from vultron.core.models.use_case_result import HandlerDisposition
from vultron.core.use_cases.received.actor.invite import (
    AcceptInviteActorToCaseReceivedUseCase,
)
from vultron.core.use_cases.received.actor.offer_case_participant import (
    AcceptOfferCaseParticipantReceivedUseCase,
)
from vultron.core.use_cases.received.actor.ownership import (
    AcceptCaseOwnershipTransferReceivedUseCase,
)
from vultron.core.use_cases.received.case.lifecycle import (
    AddReportToCaseReceivedUseCase,
)
from vultron.core.use_cases.received.case_proposal import (
    AcceptCaseProposalReceivedUseCase,
)
from vultron.core.use_cases.received.note import (
    RemoveNoteFromCaseReceivedUseCase,
)
from vultron.core.use_cases.received.sync import (
    RejectLedgerEntryReceivedUseCase,
)
from vultron.semantic_registry import extract_event
from vultron.wire.as2.factories import (
    accept_case_ownership_transfer_activity,
    accept_case_participant_offer_activity,
    add_report_to_case_activity,
    offer_case_ownership_transfer_activity,
    rm_accept_invite_to_case_activity,
    rm_invite_to_case_activity,
)
from vultron.wire.as2.vocab.base.objects.activities.transitive import (
    as_Accept,
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


@pytest.fixture(autouse=True)
def _clear_blackboard():
    py_trees.blackboard.Blackboard.storage.clear()
    yield
    py_trees.blackboard.Blackboard.storage.clear()


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
        cm_store, event, wire_render_port=As2WireRenderAdapter()
    ).execute()

    assert result.disposition is HandlerDisposition.REFUSED
    assert _reload_case(cm_store, owned_case.id_).attributed_to == _OWNER_ID


@pytest.mark.xfail(
    strict=True,
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
        target=as_VulnerabilityCaseStub(id_=owned_case.id_),
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


@pytest.mark.xfail(
    strict=True,
    reason="CM-16-019: Accept(Offer(CaseParticipant)) from a non-owner invites. Tracked by #4073.",
)
@pytest.mark.spec("CM-16-019")
def test_recommendation_accept_from_non_owner_is_refused():
    """The recommendation is recorded; the Accept's sender is not the owner."""
    dl, _ = _seed_dl_for_case_actor()
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
        wire_render_port=As2WireRenderAdapter(),
    ).execute()

    assert result.disposition is HandlerDisposition.REFUSED
    assert dl.outbox_list() == []


@pytest.mark.xfail(
    strict=True,
    reason="CP-06-005: Accept(CaseProposal) from a non-addressee is recorded. Tracked by #4072.",
)
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
    assert link.trusted_case_actor_id is None


@pytest.mark.xfail(
    strict=True,
    reason="CM-30-001: Remove(Note) from neither author nor owner is applied. Tracked by #4074.",
)
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


@pytest.mark.xfail(
    strict=True,
    reason="CM-30-002: Add(VulnerabilityReport) from a non-owner is applied. Tracked by #4074.",
)
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


@pytest.mark.xfail(
    strict=True,
    reason="SYNC-03-005: Reject(CaseLedgerEntry) from a non-participant replays. Tracked by #4075.",
)
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
