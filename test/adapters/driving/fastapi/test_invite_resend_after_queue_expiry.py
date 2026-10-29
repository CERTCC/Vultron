#!/usr/bin/env python
"""A joiner's dropped Invites come back with its post-seed position (ADR-0163).

ADR-0163 § Validation, driven through both actors' inbox pipelines, from the
sealed bodies each outbox delivers:

1. A joiner is admitted while a first embargo proposal is open.  The
   CASE_MANAGER queues the case copy, the full-case Invite (CM-11-010) and
   the relayed ``Invite(EmbargoEvent)`` (EP-09-011).
2. The two Invites reach the joiner first, wait in its pre-bootstrap queue,
   and are dropped when the queue expires (CBT-03-003).
3. Before the copy arrives the owner activates the proposal, so the joiner,
   which has not agreed to it, is now inert (CM-10-004).
4. The case copy seeds the joiner's replica, and the joiner states its
   position in ``Read(CaseLedgerEntry)`` (SYNC-17-008).
5. The CASE_MANAGER refuses the inert joiner's statement (SYNC-17-002) but
   resends both Invites as first sent (SYNC-20-001, SYNC-20-003).
6. The joiner receives the resent embargo Invite and accepts it before its
   RSVP deadline, and the CASE_MANAGER records its consent.
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
from typing import Any, cast

import pytest

from test.core.use_cases.received.test_embargo_revision_relay import (
    MANAGER,
    _consent_of,
)
from test.core.use_cases.received.test_invite_resend import (
    _drain,
    _embargo_invite,
    _first_proposal,
    _full_case_invite,
)
from test.core.use_cases.received.test_joiner_revision_relay import (
    JOINER,
    _accept,
    _invited_joiner,
)
from test.support.embargo_register import activate
from test.support.received import delivered_body, received_event
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driven.trigger_activity_adapter import (
    TriggerActivityAdapter,
)
from vultron.adapters.driving.fastapi.inbox_handler import make_dispatcher
from vultron.adapters.driving.fastapi.inbox_orchestration import (
    FastAPIDispatchAdapter,
    FastAPIIngressAdapter,
    FastAPIQueuePort,
)
from vultron.adapters.inbox_staging import InlineObjectStaging
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
from vultron.core.models.replication_state import VultronReplicationState
from vultron.core.states.participant_embargo_consent import (
    EmbargoConsentState,
)
from vultron.wire.as2.vocab.base.objects.activities.base import as_Activity

_CASE_ID = "https://example.org/cases/resend-after-expiry"


@pytest.fixture(autouse=True)
def clear_actor_locks() -> Iterator[None]:
    from vultron.adapters.driving.fastapi import inbox_orchestration

    inbox_orchestration._actor_inbox_locks.clear()
    yield
    inbox_orchestration._actor_inbox_locks.clear()


@pytest.fixture
def joiner_dl() -> Iterator[SqliteDataLayer]:
    """The joiner's store, which holds no case yet."""
    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=JOINER)
    yield dl
    dl.close()


def _deliver(
    dl: SqliteDataLayer, actor_id: str, body: dict[str, Any]
) -> InboxOutcome:
    """Run one delivery through the adapters ``run_inbox_pipeline`` builds."""
    staging = InlineObjectStaging(dl)
    return process_payload(
        body,
        FastAPIIngressAdapter(dl=dl, staging=staging),
        FastAPIDispatchAdapter(
            dl=dl, actor_id=actor_id, dispatcher=make_dispatcher()
        ),
        FastAPIQueuePort(dl=dl, actor_dl=dl, staging=staging),
    )


def _sealed(dl: SqliteDataLayer, activity_id: str) -> dict[str, Any]:
    body = read_sealed_body_dict(dl, activity_id)
    assert body is not None, f"no sealed body for {activity_id}"
    return body


def _queued_bodies(dl: SqliteDataLayer) -> list[dict[str, Any]]:
    return [_sealed(dl, activity_id) for activity_id in dl.outbox_list()]


def _expire_pending_queue(dl: SqliteDataLayer) -> None:
    """Age the joiner's pre-bootstrap queue past its window (CBT-03-001)."""
    pending = dl.read(VultronPendingCaseInbox.build_id(_CASE_ID))
    assert isinstance(pending, VultronPendingCaseInbox)
    assert len(pending.activity_ids) == 2
    dl.save(
        VultronPendingCaseInbox.model_validate(
            {
                **pending.model_dump(),
                "queued_at": datetime.now(UTC) - timedelta(hours=1),
            }
        )
    )


def _received(dl: SqliteDataLayer, activity_id: str) -> bool:
    return dl.read(ReceivedActivityRecord.build_id(activity_id)) is not None


@pytest.mark.spec(
    "SYNC-20-001",
    "SYNC-20-003",
    "SYNC-17-008",
    "SYNC-17-002",
    "CBT-03-003",
    "EP-09-011",
)
def test_an_inert_joiners_post_seed_read_brings_its_dropped_invites_back(
    joiner_dl,
):
    # 1. The CASE_MANAGER admits the joiner while a first proposal is open.
    cm_dl, proposal_id = _first_proposal(_CASE_ID, received_event)
    accept_stub = _invited_joiner(cm_dl, _CASE_ID, received_event)
    stub_invite = cm_dl.read(f"{_CASE_ID}/invitations/joiner")
    assert stub_invite is not None
    _drain(cm_dl)
    assert _accept(cm_dl, accept_stub).reason is None
    embargo_invite = _embargo_invite(cm_dl)
    full_case_invite = _full_case_invite(cm_dl)
    queued = {body["id"]: body for body in _queued_bodies(cm_dl)}
    (announce,) = [
        body
        for body in queued.values()
        if body["type"] == "Announce"
        and isinstance(body["object"], dict)
        and body["object"].get("type") == "VulnerabilityCase"
    ]
    _drain(cm_dl)

    # The joiner holds the stub Invite that anchors its CASE_MANAGER.
    stub_body = delivered_body(cast(as_Activity, stub_invite))
    assert _deliver(joiner_dl, JOINER, stub_body).status is (
        InboxOutcomeStatus.PROCESSED
    )

    # 2. Both Invites arrive before the case copy and wait, then expire.
    for invite_id in (full_case_invite, embargo_invite):
        outcome = _deliver(joiner_dl, JOINER, queued[invite_id])
        assert outcome.status is InboxOutcomeStatus.DEFERRED, (
            outcome.failure_reason
        )
    _expire_pending_queue(joiner_dl)

    # 3. The owner activates the proposal: the joiner has not agreed, so it
    # is inert while that embargo is in force (CM-10-004).
    case = cast(VulnerabilityCase, cm_dl.read(_CASE_ID))
    activate(case, proposal_id)
    cm_dl.save(case)
    assert _consent_of(cm_dl, _CASE_ID, JOINER, proposal_id) is (
        EmbargoConsentState.INVITED
    )

    # 4. The case copy seeds the replica; the queued Invites are dropped and
    # the joiner states its position (SYNC-17-008).
    seeded = _deliver(joiner_dl, JOINER, announce)
    assert seeded.status is InboxOutcomeStatus.PROCESSED, seeded.failure_reason
    assert isinstance(joiner_dl.read(_CASE_ID), VulnerabilityCase)
    assert not _received(joiner_dl, embargo_invite)
    assert not _received(joiner_dl, full_case_invite)
    (read,) = [b for b in _queued_bodies(joiner_dl) if b["type"] == "Read"]

    # 5. The CASE_MANAGER refuses the inert joiner's statement, recording
    # nothing for it, and resends both Invites as first sent.
    stated = _deliver(cm_dl, MANAGER, read)
    assert stated.status is InboxOutcomeStatus.REJECTED
    state_id = VultronReplicationState(case_id=_CASE_ID, peer_id=JOINER).id_
    assert cm_dl.read(state_id) is None
    assert set(cm_dl.outbox_list()) == {embargo_invite, full_case_invite}
    resent = {body["id"]: body for body in _queued_bodies(cm_dl)}
    assert resent[embargo_invite] == queued[embargo_invite]
    assert resent[full_case_invite] == queued[full_case_invite]

    # 6. The joiner now handles the resent Invites as new and accepts the
    # embargo before its RSVP deadline.
    for invite_id in (full_case_invite, embargo_invite):
        outcome = _deliver(joiner_dl, JOINER, resent[invite_id])
        assert outcome.status is InboxOutcomeStatus.PROCESSED, (
            outcome.failure_reason
        )
        assert _received(joiner_dl, invite_id)
    deadline = datetime.fromisoformat(resent[embargo_invite]["endTime"])
    assert datetime.now(UTC) < deadline

    accept_id, _ = TriggerActivityAdapter(joiner_dl).accept_embargo(
        proposal_id=embargo_invite,
        case_id=_CASE_ID,
        actor=JOINER,
        to=[MANAGER],
    )
    accepted = _deliver(cm_dl, MANAGER, _sealed(joiner_dl, accept_id))
    assert accepted.status is InboxOutcomeStatus.PROCESSED, (
        accepted.failure_reason
    )
    assert _consent_of(cm_dl, _CASE_ID, JOINER, proposal_id) is (
        EmbargoConsentState.AGREED
    )
