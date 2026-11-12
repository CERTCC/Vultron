#!/usr/bin/env python

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

"""An invitee's inbox, before and after it holds the case it is invited to.

Shared by the stub-Invite arrival tests
(``test/adapters/driving/fastapi/test_stub_invite_on_arrival.py``) and the
full-case Invite inbox tests (``test/core/behaviors/inbox/
test_process_payload.py``).  Every delivery runs the real FastAPI ingress,
dispatch, queue and outcome adapters and the production dispatcher, from the
sealed body the CASE_MANAGER's outbox delivers, so a case-scoped activity
the invitee cannot yet process is held for its replay (DL-06-006).

Import the fixtures (``case_actor_dl``, ``invitee_dl`` and
``clear_actor_locks``) into the test module that uses them, and request
``clear_actor_locks`` for every test that delivers through the pipeline.
"""

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from typing import Any, cast

import pytest
from pydantic import BaseModel

from test.core.use_cases.received.conftest import (
    seed_case_manager_participant,
    seed_case_owner_participant,
    seed_case_participant,
)
from test.support.objects import authored_at, make
from test.support.received import delivered_body
from vultron.adapters.driven.clock import SystemClock
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driven.trigger_activity_adapter import (
    TriggerActivityAdapter,
)
from vultron.adapters.driving.fastapi.inbox_handler import make_dispatcher
from vultron.adapters.driving.fastapi.inbox_orchestration import (
    FastAPIDispatchAdapter,
    FastAPIIngressAdapter,
    FastAPIQueuePort,
    FastAPIReceivedOutcomePort,
    pipeline,
)
from vultron.adapters.inbox_staging import InlineObjectStaging
from vultron.adapters.outbox_sealed_body import read_sealed_body_dict
from vultron.core.behaviors.inbox import InboxOutcome, process_payload
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.pending_case_inbox import VultronPendingCaseInbox
from vultron.core.services.received_holding import records_awaiting_case
from vultron.wire.as2.factories import add_note_to_case_activity
from vultron.wire.as2.vocab.base.objects.activities.base import as_Activity
from vultron.wire.as2.vocab.base.objects.object_types import as_Note
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)

CASE_ACTOR_ID = "https://example.org/actors/case-actor-4915"
IMPOSTER_ID = "https://example.org/actors/imposter-4931"
VENDOR_ID = "https://example.org/users/vendor-4915"
INVITEE_ID = "https://example.org/users/invitee-4915"
CASE_ID = "https://example.org/cases/case-4915"
PENDING_ID = VultronPendingCaseInbox.build_id(CASE_ID)

#: Older than any pre-bootstrap queue's expiry window (CBT-03-003).
LONG_AGO = timedelta(hours=1)


def stub_case() -> as_VulnerabilityCase:
    """The case the invitee is invited to."""
    return make(
        as_VulnerabilityCase,
        id_=CASE_ID,
        name="Widget overflow",
        attributed_to=VENDOR_ID,
        stub_summary="A memory-safety vul in a widget parser",
    )


@pytest.fixture
def case_actor_dl() -> Iterator[SqliteDataLayer]:
    """The CASE_MANAGER's store: the case and its roster."""
    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=CASE_ACTOR_ID)
    case = stub_case()
    seed_case_manager_participant(dl, case, CASE_ACTOR_ID)
    seed_case_owner_participant(dl, case, VENDOR_ID)
    dl.create(case)
    yield dl
    dl.close()


@pytest.fixture
def invitee_dl() -> Iterator[SqliteDataLayer]:
    """The invitee's store, which holds no case."""
    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=INVITEE_ID)
    yield dl
    dl.close()


@pytest.fixture
def clear_actor_locks() -> Iterator[None]:
    """Clear the pipeline's process-global per-actor inbox locks."""
    pipeline._actor_inbox_locks.clear()
    yield
    pipeline._actor_inbox_locks.clear()


def stub_invite_body(
    case_actor_dl: SqliteDataLayer,
    actor: str = CASE_ACTOR_ID,
    id_: str | None = None,
) -> tuple[str, dict]:
    """The sealed stub Invite *actor*'s outbox delivers, and its id."""
    invite_id, _ = TriggerActivityAdapter(case_actor_dl).invite_actor_to_case(
        invitee_id=INVITEE_ID,
        case_id=CASE_ID,
        actor=actor,
        to=[INVITEE_ID],
        id_=id_,
        at=authored_at(),
    )
    body = read_sealed_body_dict(case_actor_dl, invite_id)
    assert body is not None
    return invite_id, body


def wire_body(activity: BaseModel) -> dict[str, Any]:
    """The body a sender delivers for *activity*."""
    return delivered_body(cast(as_Activity, activity))


def deliver(dl: SqliteDataLayer, body: dict[str, Any]) -> InboxOutcome:
    """Run one delivery through the adapters ``run_inbox_pipeline`` builds.

    The ingress and queue ports share one staging, as there, so a deferred
    delivery is held for its replay (DL-06-006).
    """
    staging = InlineObjectStaging(dl)
    return process_payload(
        body,
        FastAPIIngressAdapter(dl=dl, staging=staging),
        FastAPIDispatchAdapter(
            dl=dl, actor_id=INVITEE_ID, dispatcher=make_dispatcher()
        ),
        FastAPIQueuePort(dl=dl, actor_dl=dl, staging=staging),
        received_outcome_port=FastAPIReceivedOutcomePort(dl),
        arrived_at=SystemClock().now(),
    )


def drain(dl: SqliteDataLayer) -> None:
    """Run what a bootstrap's replay queued, as the inbox loop does next.

    The release only queues the held activities (IE-06-004); the drain
    after the delivery is what processes them.
    """
    pipeline._InboxRun(dl, INVITEE_ID, make_dispatcher()).drain_queue()


def note_body(note_id: str, actor: str = CASE_ACTOR_ID) -> dict[str, Any]:
    """A case-scoped activity the invitee cannot process before the case."""
    note = make(as_Note, id_=note_id, content="pre-bootstrap", context=CASE_ID)
    add = add_note_to_case_activity(
        note,
        target=CASE_ID,
        context=CASE_ID,
        actor=actor,
        to=[INVITEE_ID],
        at=authored_at(),
    )
    return wire_body(add)


def pending_record(dl: SqliteDataLayer) -> VultronPendingCaseInbox:
    """The invitee's pre-bootstrap record for the case."""
    record = dl.read(PENDING_ID)
    assert isinstance(record, VultronPendingCaseInbox)
    return record


def awaiting(dl: SqliteDataLayer) -> list[str]:
    """The ids of the activities waiting on the case, in arrival order.

    Which activities wait is read from their own held records
    (``awaiting_case_id``, ADR-0154), not from the per-case record.
    """
    return [
        record.activity_id for record in records_awaiting_case(dl, CASE_ID)
    ]


def age_queue(dl: SqliteDataLayer, by: timedelta) -> None:
    """Move the queue's expiry window back by *by*."""
    record = pending_record(dl)
    dl.save(
        VultronPendingCaseInbox.model_validate(
            {**record.model_dump(), "queued_at": datetime.now(UTC) - by}
        )
    )


def enrol_invitee(case_manager_dl: SqliteDataLayer) -> VulnerabilityCase:
    """Add the invitee to the case *case_manager_dl* holds, as its Accept does."""
    case = case_manager_dl.read(CASE_ID)
    assert isinstance(case, VulnerabilityCase)
    seed_case_participant(case_manager_dl, case, INVITEE_ID)
    case_manager_dl.save(case)
    stored = case_manager_dl.read(CASE_ID)
    assert isinstance(stored, VulnerabilityCase)
    return stored


def sealed_announce_body(case_manager_dl: SqliteDataLayer) -> dict[str, Any]:
    """The sealed ``Announce(VulnerabilityCase)`` the CASE_MANAGER sends.

    Built by its trigger adapter, so the case carries its roster inline as
    the invitee receives it (CBT-05-005, AKM-02-004): the replica names its
    CASE_MANAGER before any ledger entry arrives.
    """
    enrol_invitee(case_manager_dl)
    announce_id = TriggerActivityAdapter(
        case_manager_dl
    ).announce_vulnerability_case(
        case_id=CASE_ID,
        actor=CASE_ACTOR_ID,
        context_id=CASE_ID,
        to=[INVITEE_ID],
        at=authored_at(),
    )
    body = read_sealed_body_dict(case_manager_dl, announce_id)
    assert body is not None
    return body
