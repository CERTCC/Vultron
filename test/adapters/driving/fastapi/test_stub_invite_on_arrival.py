#!/usr/bin/env python
"""An invitee holding no case processes the stub Invite on arrival (#4915).

The stub Invite exists so an invitee can decide whether to join a case before
it holds the case (MV-10-005): the case arrives in an ``Announce`` only after
the invitee accepts.  The inbox used to hold it back with every other activity
naming a case the receiver does not hold, so it reached no use case, intake
never archived it, and the invitee could answer it only from the copy the
inbox kept under the sender's id (PCR-06-005, DL-06-006).

The Invite's trust anchor shares a record with the pre-bootstrap queue, so
these tests also pin that the queue's expiry window opens with the first
activity queued and that an expired queue keeps the anchor that admits the
case's ``Announce`` (PCR-03-004 path b, CBT-03-003).

These tests drive the real FastAPI ingress, dispatch and queue adapters and
the production dispatcher, from the sealed body the CASE_MANAGER's outbox
delivers.
"""

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

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from pydantic import BaseModel

from test.core.use_cases.received.conftest import (
    seed_case_manager_participant,
    seed_case_owner_participant,
    seed_case_participant,
)
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driven.sync_activity_adapter import SyncActivityAdapter
from vultron.adapters.driven.trigger_activity_adapter import (
    TriggerActivityAdapter,
)
from vultron.adapters.driven.wire_render.as2 import As2WireRenderAdapter
from vultron.adapters.driving.fastapi.inbox_handler import make_dispatcher
from vultron.adapters.driving.fastapi.inbox_orchestration import (
    FastAPIDispatchAdapter,
    FastAPIIngressAdapter,
    FastAPIQueuePort,
)
from vultron.adapters.driving.fastapi.inbox_staging import (
    InlineObjectStaging,
)
from vultron.adapters.outbox_sealed_body import read_sealed_body_dict
from vultron.core.behaviors.inbox import (
    InboxOutcome,
    InboxOutcomeStatus,
    process_payload,
)
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.pending_case_inbox import VultronPendingCaseInbox
from vultron.core.models.received_activity_record import (
    ReceivedActivityRecord,
)
from vultron.core.use_cases.triggers.actor import SvcAcceptCaseInviteUseCase
from vultron.core.use_cases.triggers.requests import (
    AcceptCaseInviteTriggerRequest,
)
from vultron.wire.as2.factories import (
    add_note_to_case_activity,
    announce_vulnerability_case_activity,
)
from vultron.wire.as2.vocab.base.objects.actors import as_Actor
from vultron.wire.as2.vocab.base.objects.object_types import as_Note
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)

_CASE_ACTOR_ID = "https://example.org/actors/case-actor-4915"
_IMPOSTER_ID = "https://example.org/actors/imposter-4931"
_VENDOR_ID = "https://example.org/users/vendor-4915"
_INVITEE_ID = "https://example.org/users/invitee-4915"
_CASE_ID = "https://example.org/cases/case-4915"
_PENDING_ID = VultronPendingCaseInbox.build_id(_CASE_ID)


@pytest.fixture(autouse=True)
def clear_actor_locks() -> Iterator[None]:
    from vultron.adapters.driving.fastapi import inbox_orchestration

    inbox_orchestration._actor_inbox_locks.clear()
    yield
    inbox_orchestration._actor_inbox_locks.clear()


def _case() -> as_VulnerabilityCase:
    return as_VulnerabilityCase(
        id_=_CASE_ID,
        name="Widget overflow",
        attributed_to=_VENDOR_ID,
        stub_summary="A memory-safety vul in a widget parser",
    )


@pytest.fixture
def case_actor_dl() -> Iterator[SqliteDataLayer]:
    """The CASE_MANAGER's store: the case and its roster."""
    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=_CASE_ACTOR_ID)
    case = _case()
    seed_case_manager_participant(dl, case, _CASE_ACTOR_ID)
    seed_case_owner_participant(dl, case, _VENDOR_ID)
    dl.create(case)
    yield dl
    dl.close()


@pytest.fixture
def invitee_dl() -> Iterator[SqliteDataLayer]:
    """The invitee's store, which holds no case."""
    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=_INVITEE_ID)
    yield dl
    dl.close()


def _stub_invite_body(
    case_actor_dl: SqliteDataLayer,
    actor: str = _CASE_ACTOR_ID,
    id_: str | None = None,
) -> tuple[str, dict]:
    """The sealed stub Invite *actor*'s outbox delivers."""
    invite_id, _ = TriggerActivityAdapter(case_actor_dl).invite_actor_to_case(
        invitee_id=_INVITEE_ID,
        case_id=_CASE_ID,
        actor=actor,
        to=[_INVITEE_ID],
        id_=id_,
    )
    body = read_sealed_body_dict(case_actor_dl, invite_id)
    assert body is not None
    return invite_id, body


def _wire_body(activity: BaseModel) -> dict[str, Any]:
    return activity.model_dump(mode="json", by_alias=True, exclude_none=True)


def _deliver(dl: SqliteDataLayer, body: dict[str, Any]) -> InboxOutcome:
    """Run one delivery through the adapters ``run_inbox_pipeline`` builds.

    The ingress and queue ports share one staging, as there, so a deferred
    delivery is held for its replay (DL-06-006).
    """
    staging = InlineObjectStaging(dl)
    return process_payload(
        body,
        FastAPIIngressAdapter(dl=dl, staging=staging),
        FastAPIDispatchAdapter(
            dl=dl, actor_id=_INVITEE_ID, dispatcher=make_dispatcher()
        ),
        FastAPIQueuePort(
            dl=dl, actor_dl=dl, actor_id=_INVITEE_ID, staging=staging
        ),
    )


def _note_body(note_id: str, actor: str = _CASE_ACTOR_ID) -> dict[str, Any]:
    """A case-scoped activity the invitee cannot process before the case."""
    note = as_Note(id_=note_id, content="pre-bootstrap", context=_CASE_ID)
    add = add_note_to_case_activity(
        note,
        target=_CASE_ID,
        context=_CASE_ID,
        actor=actor,
        to=[_INVITEE_ID],
    )
    return _wire_body(add)


def _pending(dl: SqliteDataLayer) -> VultronPendingCaseInbox:
    pending = dl.read(_PENDING_ID)
    assert isinstance(pending, VultronPendingCaseInbox)
    return pending


def _age_queue(dl: SqliteDataLayer, by: timedelta) -> None:
    pending = _pending(dl)
    dl.save(
        VultronPendingCaseInbox.model_validate(
            {
                **pending.model_dump(),
                "queued_at": datetime.now(UTC) - by,
            }
        )
    )


_LONG_AGO = timedelta(hours=1)


def _announce_body(case_manager_dl: SqliteDataLayer, actor: str) -> dict:
    """``Announce(VulnerabilityCase)`` of the case *case_manager_dl* holds."""
    case = case_manager_dl.read(_CASE_ID)
    assert isinstance(case, VulnerabilityCase)
    seed_case_participant(case_manager_dl, case, _INVITEE_ID)
    case_manager_dl.save(case)
    return _wire_body(
        announce_vulnerability_case_activity(
            case, actor=actor, to=[_INVITEE_ID]
        )
    )


@pytest.mark.spec("PCR-06-005", "CLP-10-017", "PCR-03-004")
def test_stub_invite_is_processed_on_arrival_and_archived(
    case_actor_dl, invitee_dl
):
    """AC-1: processed, archived by intake and anchored — not deferred."""
    invite_id, body = _stub_invite_body(case_actor_dl)

    outcome = _deliver(invitee_dl, body)

    assert outcome.status is InboxOutcomeStatus.PROCESSED, (
        outcome.failure_reason
    )
    record = invitee_dl.read(ReceivedActivityRecord.build_id(invite_id))
    assert isinstance(record, ReceivedActivityRecord)
    assert not isinstance(invitee_dl.read(_CASE_ID), VulnerabilityCase)
    pending = _pending(invitee_dl)
    assert pending.activity_ids == [], "nothing is held back for replay"
    assert pending.case_actor_id == _CASE_ACTOR_ID
    assert pending.invite_anchored
    # PCR-06-005: the intake archive and the anchor are the only writes;
    # ingress holds nothing under the sender's id (DL-06-006).
    stored = {
        type_: count
        for type_, count in invitee_dl.count_all().items()
        if count
    }
    assert stored == {"ReceivedActivityRecord": 1, "PendingCaseInbox": 1}


@pytest.mark.spec("PCR-06-005", "DL-06-006")
def test_accept_reads_the_invite_from_the_receiver_keyed_record(
    case_actor_dl, invitee_dl
):
    """AC-2: the Accept is built with no sender-keyed copy of the Invite."""
    invite_id, body = _stub_invite_body(case_actor_dl)
    assert _deliver(invitee_dl, body).status is InboxOutcomeStatus.PROCESSED

    # Ingress holds nothing under the sender's id, so the receiver-keyed
    # archive is the only copy (DL-06-006).
    assert invitee_dl.read(invite_id) is None

    accept_id, _ = TriggerActivityAdapter(invitee_dl).accept_case_invite(
        invite_id=invite_id, actor=_INVITEE_ID
    )

    accept = read_sealed_body_dict(invitee_dl, accept_id)
    assert accept is not None
    assert accept["object"]["id"] == invite_id
    assert accept["object"]["target"]["type"] == "VulnerabilityCaseStub"


@pytest.mark.spec("PCR-06-002", "PCR-06-005")
def test_an_activity_presupposing_the_unknown_case_is_still_deferred(
    invitee_dl,
):
    """AC-4: only the stub Invite is exempt; a case-scoped Note is held."""
    outcome = _deliver(invitee_dl, _note_body("https://example.org/notes/n1"))

    assert outcome.status is InboxOutcomeStatus.DEFERRED
    assert len(_pending(invitee_dl).activity_ids) == 1


@pytest.mark.spec("CBT-03-001", "PCR-03-004")
def test_the_expiry_window_opens_with_the_first_activity_queued(
    case_actor_dl, invitee_dl
):
    """Time spent deciding on the Invite is not charged to the queue."""
    _, body = _stub_invite_body(case_actor_dl)
    assert _deliver(invitee_dl, body).status is InboxOutcomeStatus.PROCESSED
    # The invitee took an hour to answer: the anchor is an hour old.
    _age_queue(invitee_dl, _LONG_AGO)

    outcome = _deliver(invitee_dl, _note_body("https://example.org/notes/n2"))

    assert outcome.status is InboxOutcomeStatus.DEFERRED, (
        outcome.failure_reason
    )
    pending = _pending(invitee_dl)
    assert len(pending.activity_ids) == 1
    assert datetime.now(UTC) - pending.queued_at < timedelta(minutes=5)


@pytest.mark.spec("CBT-03-003", "PCR-03-004")
def test_announce_after_queue_expiry_is_admitted_from_the_anchored_sender(
    case_actor_dl, invitee_dl
):
    """An expired queue drops what it held but keeps the Invite's anchor."""
    _, body = _stub_invite_body(case_actor_dl)
    assert _deliver(invitee_dl, body).status is InboxOutcomeStatus.PROCESSED
    assert (
        _deliver(invitee_dl, _note_body("https://example.org/notes/n3")).status
        is InboxOutcomeStatus.DEFERRED
    )
    _age_queue(invitee_dl, _LONG_AGO)

    expired = _deliver(invitee_dl, _note_body("https://example.org/notes/n4"))

    assert expired.status is InboxOutcomeStatus.REJECTED
    pending = _pending(invitee_dl)
    assert pending.activity_ids == [], "the expired queue is dropped"
    assert pending.case_actor_id == _CASE_ACTOR_ID
    assert pending.invite_anchored

    # The invitee accepted; the CASE_MANAGER announces the case to it.
    case = case_actor_dl.read(_CASE_ID)
    assert isinstance(case, VulnerabilityCase)
    seed_case_participant(case_actor_dl, case, _INVITEE_ID)
    case_actor_dl.save(case)
    announce = announce_vulnerability_case_activity(
        case_actor_dl.read(_CASE_ID),
        actor=_CASE_ACTOR_ID,
        to=[_INVITEE_ID],
    )

    outcome = _deliver(invitee_dl, _wire_body(announce))

    assert outcome.status is InboxOutcomeStatus.PROCESSED, (
        outcome.failure_reason
    )
    assert isinstance(invitee_dl.read(_CASE_ID), VulnerabilityCase)


@pytest.mark.spec("CBT-03-003")
def test_an_expired_queue_without_an_invite_anchor_is_deleted(invitee_dl):
    """A queue no stub Invite anchored is dropped whole, as before."""
    assert (
        _deliver(invitee_dl, _note_body("https://example.org/notes/n5")).status
        is InboxOutcomeStatus.DEFERRED
    )
    _age_queue(invitee_dl, _LONG_AGO)

    outcome = _deliver(invitee_dl, _note_body("https://example.org/notes/n6"))

    assert outcome.status is InboxOutcomeStatus.REJECTED
    assert invitee_dl.read(_PENDING_ID) is None


@pytest.mark.spec("CBT-03-003", "PCR-03-004")
def test_a_bootstrap_after_queue_expiry_drops_the_anchored_record(
    case_actor_dl, invitee_dl
):
    """Once the case is held, the anchor has done its job and goes.

    The bootstrap finds the queue expired: what was queued is dropped, and
    the anchored record goes with it, since the case now names its
    CASE_MANAGER itself.
    """
    _, body = _stub_invite_body(case_actor_dl)
    assert _deliver(invitee_dl, body).status is InboxOutcomeStatus.PROCESSED
    assert (
        _deliver(invitee_dl, _note_body("https://example.org/notes/n7")).status
        is InboxOutcomeStatus.DEFERRED
    )
    _age_queue(invitee_dl, _LONG_AGO)

    case = case_actor_dl.read(_CASE_ID)
    assert isinstance(case, VulnerabilityCase)
    seed_case_participant(case_actor_dl, case, _INVITEE_ID)
    case_actor_dl.save(case)
    announce = announce_vulnerability_case_activity(
        case_actor_dl.read(_CASE_ID),
        actor=_CASE_ACTOR_ID,
        to=[_INVITEE_ID],
    )

    outcome = _deliver(invitee_dl, _wire_body(announce))

    assert outcome.status is InboxOutcomeStatus.PROCESSED, (
        outcome.failure_reason
    )
    assert isinstance(invitee_dl.read(_CASE_ID), VulnerabilityCase)
    assert invitee_dl.read(_PENDING_ID) is None


@pytest.fixture
def imposter_dl() -> Iterator[SqliteDataLayer]:
    """A forger's store: a copy of the case naming the forger CASE_MANAGER."""
    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=_IMPOSTER_ID)
    case = _case()
    seed_case_manager_participant(dl, case, _IMPOSTER_ID)
    dl.create(case)
    yield dl
    dl.close()


@pytest.mark.spec("PCR-03-004", "CBT-03-004", "PCR-06-002")
def test_announce_from_queue_recorded_sender_is_refused(
    imposter_dl, invitee_dl
):
    """#4931 AC-1: a deferred activity's sender is no trust anchor.

    The queue records the sender of the first deferred activity as its
    replay target (CBT-03-004).  An imposter that sends one first must not
    then be admitted as CASE_MANAGER of a case it announces.
    """
    assert (
        _deliver(
            invitee_dl,
            _note_body("https://example.org/notes/n9", _IMPOSTER_ID),
        ).status
        is InboxOutcomeStatus.DEFERRED
    )
    assert _pending(invitee_dl).case_actor_id == _IMPOSTER_ID

    outcome = _deliver(invitee_dl, _announce_body(imposter_dl, _IMPOSTER_ID))

    assert outcome.status is not InboxOutcomeStatus.PROCESSED
    assert invitee_dl.read(_CASE_ID) is None


@pytest.mark.spec("PCR-03-004", "CBT-03-004")
def test_stub_invite_anchors_after_another_senders_deferred_activity(
    case_actor_dl, invitee_dl
):
    """#4931 AC-2: an earlier third-party activity does not pre-empt it."""
    assert (
        _deliver(
            invitee_dl,
            _note_body("https://example.org/notes/n10", _IMPOSTER_ID),
        ).status
        is InboxOutcomeStatus.DEFERRED
    )
    _, body = _stub_invite_body(case_actor_dl)

    invited = _deliver(invitee_dl, body)

    assert invited.status is InboxOutcomeStatus.PROCESSED, (
        invited.failure_reason
    )
    pending = _pending(invitee_dl)
    assert pending.case_actor_id == _CASE_ACTOR_ID
    assert pending.invite_anchored

    outcome = _deliver(
        invitee_dl, _announce_body(case_actor_dl, _CASE_ACTOR_ID)
    )

    assert outcome.status is InboxOutcomeStatus.PROCESSED, (
        outcome.failure_reason
    )
    assert isinstance(invitee_dl.read(_CASE_ID), VulnerabilityCase)


def _forged_invite_body(imposter_dl: SqliteDataLayer) -> dict:
    """A stub Invite to the case, forged by an actor naming itself."""
    _, body = _stub_invite_body(
        imposter_dl,
        actor=_IMPOSTER_ID,
        id_="https://example.org/activities/forged-invite-4931",
    )
    return body


def _accept_invite(invitee_dl: SqliteDataLayer, invite_id: str) -> None:
    """The invitee accepts *invite_id* through the trigger use case."""
    if invitee_dl.read(_INVITEE_ID) is None:
        invitee_dl.create(as_Actor(id_=_INVITEE_ID, name="invitee"))
    accepted = SvcAcceptCaseInviteUseCase(
        invitee_dl,
        AcceptCaseInviteTriggerRequest(
            actor_id=_INVITEE_ID, invite_id=invite_id
        ),
        trigger_activity=TriggerActivityAdapter(invitee_dl),
        sync_port=SyncActivityAdapter(invitee_dl),
        wire_render_port=As2WireRenderAdapter(),
    ).execute()
    assert accepted.activity is not None


@pytest.mark.spec("PCR-03-004")
def test_the_real_invite_replaces_a_forged_unaccepted_anchor(
    case_actor_dl, imposter_dl, invitee_dl
):
    """A forged stub Invite does not lock out the real CASE_MANAGER (#4931).

    Its anchor is replaced by the real Invite, which no Accept had followed;
    the invitee's Accept then fixes the real anchor, so the forger's
    Announce is refused and the CASE_MANAGER's is admitted.
    """
    forged = _deliver(invitee_dl, _forged_invite_body(imposter_dl))
    assert forged.status is InboxOutcomeStatus.PROCESSED, forged.failure_reason
    assert _pending(invitee_dl).case_actor_id == _IMPOSTER_ID

    invite_id, body = _stub_invite_body(case_actor_dl)
    invited = _deliver(invitee_dl, body)

    assert invited.status is InboxOutcomeStatus.PROCESSED, (
        invited.failure_reason
    )
    pending = _pending(invitee_dl)
    assert pending.case_actor_id == _CASE_ACTOR_ID
    assert not pending.invite_accepted

    _accept_invite(invitee_dl, invite_id)
    assert _pending(invitee_dl).invite_accepted

    forged_announce = _deliver(
        invitee_dl, _announce_body(imposter_dl, _IMPOSTER_ID)
    )
    assert forged_announce.status is not InboxOutcomeStatus.PROCESSED
    assert invitee_dl.read(_CASE_ID) is None

    announced = _deliver(
        invitee_dl, _announce_body(case_actor_dl, _CASE_ACTOR_ID)
    )
    assert announced.status is InboxOutcomeStatus.PROCESSED, (
        announced.failure_reason
    )
    case = invitee_dl.read(_CASE_ID)
    assert isinstance(case, VulnerabilityCase)


@pytest.mark.spec("PCR-03-004")
def test_an_invite_after_the_accept_cannot_replace_the_anchor(
    case_actor_dl, imposter_dl, invitee_dl
):
    """Once the invitee accepts, a conflicting Invite is refused."""
    invite_id, body = _stub_invite_body(case_actor_dl)
    assert _deliver(invitee_dl, body).status is InboxOutcomeStatus.PROCESSED
    _accept_invite(invitee_dl, invite_id)

    forged = _deliver(invitee_dl, _forged_invite_body(imposter_dl))

    assert forged.status is not InboxOutcomeStatus.PROCESSED
    pending = _pending(invitee_dl)
    assert pending.case_actor_id == _CASE_ACTOR_ID
    assert pending.invite_accepted
