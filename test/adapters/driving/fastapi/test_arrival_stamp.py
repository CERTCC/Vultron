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
"""A received message is judged at its arrival stamp (ADR-0176).

The inbox reads the act clock once when a message arrives, before it queues
for the tree lock, and every act that processes the message runs at that
stamp: its first processing, a replay after a hold, a retry.  The
pre-bootstrap queue window opens at the first waiter's stamp and is judged at
the instant of the act that asks, so a message that arrived inside the window
is on time however late it is processed (CBT-03-003, CBT-03-007).

Spec: CS-13-002, CS-13-010, CBT-03-003, CBT-03-007, CLP-10-018, ID-04-004.
"""

import asyncio
import json
from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from test.support.act_clock import CountingClock, tree_lock_held
from test.support.case_owner import CASE_OWNER_ID
from test.support.inbox_replay import hold_activity
from test.support.objects import authored_at, make
from test.support.received import delivered_body
from test.support.signing import serve_published_profiles
from vultron.adapters.driven.actor_hosts import canonical_actor_uri
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driven.db_record import object_to_record
from vultron.adapters.driving.fastapi.app import create_app
from vultron.adapters.driving.fastapi.deps import get_act_clock, get_actor_dl
from vultron.adapters.driving.fastapi.inbox_orchestration import (
    FastAPIDispatchAdapter,
    FastAPIIngressAdapter,
    FastAPIQueuePort,
    FastAPIReceivedOutcomePort,
    pipeline as io,
)
from vultron.adapters.driving.fastapi.inbox_pending_queue import (
    _expire_pending_case_activities,
    _replay_pending_case_activities,
)
from vultron.adapters.driving.fastapi.inbox_startup_replay import (
    rerun_left_in_holding,
)
from vultron.adapters.inbox_staging import InlineObjectStaging
from vultron.core.behaviors.bridge.act_instant import read_act_instant
from vultron.core.behaviors.inbox import InboxOutcomeStatus, process_payload
from vultron.core.models.actor import CoreActor
from vultron.core.models.pending_case_inbox import VultronPendingCaseInbox
from vultron.core.models.received_activity_record import (
    ReceivedActivityRecord,
    ReceivedStage,
)
from vultron.core.models.use_case_result import HandlerResult
from vultron.wire.as2.factories import (
    add_note_to_case_activity,
    rm_create_report_activity,
)
from vultron.wire.as2.parser import parse_activity
from vultron.wire.as2.vocab.base.objects.activities.base import as_Activity
from vultron.wire.as2.vocab.base.objects.object_types import as_Note
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)
from vultron.wire.as2.vocab.objects.vulnerability_report import (
    as_VulnerabilityReport,
)

_SLUG = "arrival-stamp-test-actor"
_RECEIVER = canonical_actor_uri(_SLUG)
_SENDER = "https://example.org/actors/case-actor"
_CASE = "https://example.org/cases/arrival-stamp"
_API = "/api/v2"

#: The 11:59 / 12:00 / 12:02 story: a window that opened at 11:55 and lasts
#: 300 seconds closes at 12:00; a message arrives at 11:59 and the receiver's
#: backlog lets it run only at 12:02.
_OPENED = datetime(2026, 3, 1, 11, 55, tzinfo=UTC)
_ARRIVED = datetime(2026, 3, 1, 11, 59, tzinfo=UTC)
_DEADLINE = datetime(2026, 3, 1, 12, 0, tzinfo=UTC)
_PROCESSED = datetime(2026, 3, 1, 12, 2, tzinfo=UTC)
_WINDOW_SECONDS = 300


@pytest.fixture(autouse=True)
def _clear_actor_locks() -> Generator[None, None, None]:
    io._actor_inbox_locks.clear()
    yield
    io._actor_inbox_locks.clear()


@pytest.fixture
def dl() -> Generator[SqliteDataLayer, None, None]:
    store = SqliteDataLayer("sqlite:///:memory:", actor_id=_RECEIVER)
    try:
        yield store
    finally:
        store.close()


def _report_activity() -> as_Activity:
    return rm_create_report_activity(
        report=make(
            as_VulnerabilityReport, name="Arrival stamp", content="body"
        ),
        actor="https://example.org/actors/finder",
        to=[_RECEIVER],
        at=authored_at(),
    )


def _note_activity(content: str) -> as_Activity:
    return add_note_to_case_activity(
        make(as_Note, content=content, context=_CASE),
        target=_CASE,
        context=_CASE,
        actor=_SENDER,
        to=[_RECEIVER],
        at=authored_at(),
    )


def _record(dl: SqliteDataLayer, activity_id: str) -> ReceivedActivityRecord:
    record = dl.read(ReceivedActivityRecord.build_id(activity_id))
    assert isinstance(record, ReceivedActivityRecord)
    return record


def _open_window(dl: SqliteDataLayer) -> as_Activity:
    """A first message waiting on the unknown case, its window opened at 11:55."""
    first = _note_activity("first waiter")
    staging = InlineObjectStaging(dl)
    staging.rehydrate_parsed(parse_activity(delivered_body(first)))
    staging.hold_for_replay(
        first.id_, received_at=_OPENED, awaiting_case_id=_CASE
    )
    dl.save(
        VultronPendingCaseInbox(
            case_id=_CASE, case_actor_id=_SENDER, queued_at=_OPENED
        )
    )
    return first


class _InstantProbe:
    """A dispatcher that notes each act's instant and lock, then applies."""

    def __init__(self) -> None:
        self.instants: list[datetime] = []
        self.locked: list[bool] = []

    def dispatch(self, event: Any, dl: Any) -> HandlerResult:
        self.instants.append(read_act_instant())
        self.locked.append(tree_lock_held())
        return HandlerResult.applied()


# ---------------------------------------------------------------------------
# The inbox stamps arrival once, before the lock (CS-13-002, CS-13-010)
# ---------------------------------------------------------------------------


@pytest.fixture
def route() -> Generator[tuple[TestClient, SqliteDataLayer, CountingClock]]:
    """The real inbox route, its act clock pinned to 11:59, then 12:02.

    The senders' profiles are served, so the verification stage reads each
    author's key and admits the signed body (SIG-02-002).
    """
    app = create_app(docs_url=None, openapi_url=None)
    clock = CountingClock(_ARRIVED, _PROCESSED)
    app.dependency_overrides[get_act_clock] = lambda: clock
    serve_published_profiles(app)
    with TestClient(app) as client:
        store: SqliteDataLayer = app.dependency_overrides[get_actor_dl](_SLUG)
        store.create(
            object_to_record(
                make(
                    CoreActor,
                    id_=_RECEIVER,
                    name="Arrival Stamp Test Actor",
                    inbox=f"{_RECEIVER}/inbox",
                    outbox=f"{_RECEIVER}/outbox",
                )
            )
        )
        yield client, store, clock


@pytest.mark.spec("CS-13-002", "CS-13-010")
def test_the_inbox_reads_the_act_clock_once_on_arrival_outside_the_lock(
    route: tuple[TestClient, SqliteDataLayer, CountingClock],
) -> None:
    client, _store, clock = route
    probe = _InstantProbe()
    dispatcher = Mock()
    dispatcher.dispatch.side_effect = probe.dispatch
    app = client.app
    app.state.dispatcher = dispatcher  # type: ignore[attr-defined]
    body = delivered_body(_report_activity())

    response = client.post(f"{_API}/actors/{_SLUG}/inbox/", json=body)

    assert response.status_code == 202
    # One read, taken before the delivery queued for the tree lock.
    assert clock.reads == 1
    assert clock.locked_at_read == [False]
    # The delivery's act runs at that read, the 11:59 one, never the 12:02
    # a second read would have given.
    assert probe.instants == [_ARRIVED]
    assert probe.locked == [True]


@pytest.mark.spec("CS-13-010")
def test_intake_records_the_arrival_stamp_as_the_time_of_receipt(
    route: tuple[TestClient, SqliteDataLayer, CountingClock],
) -> None:
    """The real tree runs; intake writes the 11:59 stamp, not 12:02."""
    client, store, clock = route
    body = delivered_body(_report_activity())

    response = client.post(f"{_API}/actors/{_SLUG}/inbox/", json=body)

    assert response.status_code == 202
    assert clock.reads == 1
    record = _record(store, body["id"])
    # Applied and archived with its body: intake ran and wrote the record,
    # not a door's bodiless receipt stub (CLP-10-018, CLP-10-073).
    assert record.stage is ReceivedStage.ARCHIVED
    assert record.received_at == _ARRIVED


@pytest.mark.spec("CS-13-010")
def test_a_delivery_runs_at_its_arrival_stamp_under_the_tree_lock(
    dl: SqliteDataLayer,
) -> None:
    probe = _InstantProbe()

    process_payload(
        delivered_body(_report_activity()),
        FastAPIIngressAdapter(dl=dl),
        FastAPIDispatchAdapter(dl=dl, actor_id=_RECEIVER, dispatcher=probe),  # type: ignore[arg-type]
        arrived_at=_ARRIVED,
    )

    assert probe.instants == [_ARRIVED]
    assert probe.locked == [True]


# ---------------------------------------------------------------------------
# A held message replays at the stamp it arrived with (CS-13-010)
# ---------------------------------------------------------------------------


@pytest.mark.spec("CS-13-010")
def test_a_held_message_replays_at_its_original_arrival_stamp(
    dl: SqliteDataLayer, monkeypatch: pytest.MonkeyPatch
) -> None:
    dl.save(make(as_VulnerabilityCase, attributed_to=CASE_OWNER_ID, id_=_CASE))
    held = _note_activity("held")
    assert hold_activity(dl, held, received_at=_ARRIVED)
    dl.inbox_append(held.id_)
    probe = _InstantProbe()
    dispatcher = Mock()
    dispatcher.dispatch.side_effect = probe.dispatch

    async def _no_outbox(*_args: object, **_kwargs: object) -> None:
        return None

    monkeypatch.setattr(io, "outbox_handler", _no_outbox)
    # A later delivery, at 12:02, releases the replay; the replay is its own
    # act and runs at 11:59, the stamp its record carries.
    asyncio.run(
        io.run_inbox_pipeline(
            {}, dl, _RECEIVER, dispatcher, None, arrived_at=_PROCESSED
        )
    )

    assert probe.instants == [_ARRIVED]
    assert dl.inbox_list() == []


@pytest.mark.spec("CS-13-010")
def test_a_message_held_again_keeps_its_first_arrival_stamp(
    dl: SqliteDataLayer,
) -> None:
    held = _note_activity("retried")
    assert hold_activity(dl, held, received_at=_ARRIVED)
    staging = InlineObjectStaging(dl)
    assert staging.rehydrate_deferred(held.id_) is not None

    # A retry holds it again inside a later act; the stamp is the first one.
    assert staging.hold_again(held.id_, received_at=_PROCESSED)

    assert _record(dl, held.id_).received_at == _ARRIVED


# ---------------------------------------------------------------------------
# The pre-bootstrap window is judged at the asking act's instant (CBT-03-007)
# ---------------------------------------------------------------------------


@pytest.mark.spec("CBT-03-003", "CBT-03-007")
@pytest.mark.parametrize(
    ("at", "expired"),
    [
        (_DEADLINE - timedelta(microseconds=1), False),
        (_DEADLINE, True),
    ],
    ids=["one-microsecond-before", "at-the-deadline"],
)
def test_the_window_expires_once_its_opening_stamp_plus_the_interval_is_reached(
    dl: SqliteDataLayer, at: datetime, expired: bool
) -> None:
    _open_window(dl)

    assert (
        _expire_pending_case_activities(
            case_id=_CASE,
            queue_dl=dl,
            timeout_seconds=_WINDOW_SECONDS,
            at=at,
        )
        is expired
    )


@pytest.mark.spec("CBT-03-003", "CBT-03-007")
def test_a_bootstrap_that_arrived_inside_the_window_releases_the_queue(
    dl: SqliteDataLayer, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The bootstrap arrived at 11:59 and is processed after 12:00.

    It releases the queue: the release is judged at its arrival stamp, not
    at the time the backlog let it run (the wall clock is later still).
    """
    first = _open_window(dl)
    monkeypatch.setattr(
        "vultron.adapters.driving.fastapi.inbox_pending_queue.get_config",
        lambda: Mock(pre_bootstrap_queue_timeout_seconds=_WINDOW_SECONDS),
    )
    dl.save(make(as_VulnerabilityCase, attributed_to=CASE_OWNER_ID, id_=_CASE))

    _replay_pending_case_activities(
        case_id=_CASE, dl=dl, queue_dl=dl, at=_ARRIVED
    )

    assert dl.inbox_list() == [first.id_]
    assert _record(dl, first.id_).received_at == _OPENED


@pytest.mark.spec("CBT-03-003", "CBT-03-007", "CS-13-010")
@pytest.mark.parametrize(
    ("arrived_at", "status"),
    [
        (_ARRIVED, InboxOutcomeStatus.DEFERRED),
        (_PROCESSED, InboxOutcomeStatus.REJECTED),
    ],
    ids=["arrived-1159-on-time", "arrived-1202-late"],
)
def test_a_deadline_is_judged_at_arrival_not_at_processing(
    dl: SqliteDataLayer,
    monkeypatch: pytest.MonkeyPatch,
    arrived_at: datetime,
    status: InboxOutcomeStatus,
) -> None:
    """A message that arrived at 11:59 against a 12:00 deadline is on time.

    It is processed after the deadline, as every run here is (the wall clock
    is long past 12:00), and is still judged at its 11:59 stamp: it joins
    the queue.  The same message stamped 12:02 arrived late, and the
    expired queue refuses it.
    """
    _open_window(dl)
    monkeypatch.setattr(
        "vultron.adapters.driving.fastapi.inbox_pending_queue.get_config",
        lambda: Mock(pre_bootstrap_queue_timeout_seconds=_WINDOW_SECONDS),
    )
    staging = InlineObjectStaging(dl)
    second = _note_activity("second waiter")

    outcome = process_payload(
        delivered_body(second),
        FastAPIIngressAdapter(dl=dl, staging=staging),
        FastAPIDispatchAdapter(dl=dl, actor_id=_RECEIVER),
        FastAPIQueuePort(dl=dl, actor_dl=dl, staging=staging),
        received_outcome_port=FastAPIReceivedOutcomePort(dl),
        arrived_at=arrived_at,
    )

    assert outcome.status is status
    if status is InboxOutcomeStatus.DEFERRED:
        assert _record(dl, second.id_).received_at == _ARRIVED


# ---------------------------------------------------------------------------
# Every hand-off of the stamp: drain, retry, receipt stub, restart re-run
# ---------------------------------------------------------------------------


@pytest.fixture
def no_outbox(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _no_outbox(*_args: object, **_kwargs: object) -> None:
        return None

    monkeypatch.setattr(io, "outbox_handler", _no_outbox)


@pytest.mark.spec("DL-06-006", "IE-06-004")
@pytest.mark.usefixtures("no_outbox")
def test_a_queued_item_with_nothing_held_is_refused_before_any_act(
    dl: SqliteDataLayer,
) -> None:
    """With no record there is no body to rebuild and no stamp to run at."""
    item = "https://example.org/activities/nothing-held"
    dl.inbox_append(item)
    dl.set_inbox_attempt_count(item, 2)
    dispatcher = Mock()

    asyncio.run(
        io.run_inbox_pipeline(
            {}, dl, _RECEIVER, dispatcher, None, arrived_at=_PROCESSED
        )
    )

    dispatcher.dispatch.assert_not_called()
    assert dl.inbox_list() == []
    assert dl.get_inbox_attempt_count(item) == 0
    assert dl.inbox_dead_letter_list() == []


@pytest.mark.spec("CS-13-010", "IE-06-004")
@pytest.mark.usefixtures("no_outbox")
def test_every_retry_of_a_replay_runs_at_the_first_arrival_stamp(
    dl: SqliteDataLayer, monkeypatch: pytest.MonkeyPatch
) -> None:
    dl.save(make(as_VulnerabilityCase, attributed_to=CASE_OWNER_ID, id_=_CASE))
    held = _note_activity("retried in the drain")
    assert hold_activity(dl, held, received_at=_ARRIVED)
    dl.inbox_append(held.id_)
    monkeypatch.setattr(
        io, "get_config", lambda: Mock(max_inbox_retry_attempts=2)
    )
    instants: list[datetime] = []

    def _raise(_event: Any, _dl: Any) -> HandlerResult:
        instants.append(read_act_instant())
        raise RuntimeError("the use case raised")

    dispatcher = Mock()
    dispatcher.dispatch.side_effect = _raise

    asyncio.run(
        io.run_inbox_pipeline(
            {}, dl, _RECEIVER, dispatcher, None, arrived_at=_PROCESSED
        )
    )

    # Two attempts, both at 11:59; the record held again for the dead letter
    # keeps that stamp.
    assert instants == [_ARRIVED, _ARRIVED]
    assert _record(dl, held.id_).received_at == _ARRIVED


@pytest.mark.spec("CS-13-010", "CLP-10-018")
def test_a_receipt_stub_with_no_record_behind_it_records_the_arrival_stamp(
    dl: SqliteDataLayer,
) -> None:
    dispatcher = Mock()
    dispatcher.dispatch.return_value = HandlerResult.refused("refused here")
    body = delivered_body(_report_activity())

    process_payload(
        body,
        FastAPIIngressAdapter(dl=dl),
        FastAPIDispatchAdapter(
            dl=dl, actor_id=_RECEIVER, dispatcher=dispatcher
        ),
        received_outcome_port=FastAPIReceivedOutcomePort(dl),
        arrived_at=_ARRIVED,
    )

    stub = _record(dl, body["id"])
    assert stub.is_receipt_stub
    assert stub.received_at == _ARRIVED


@pytest.mark.spec("CS-13-010", "ID-04-004")
@pytest.mark.usefixtures("no_outbox")
def test_a_restart_re_run_runs_at_the_stamp_its_record_carries(
    dl: SqliteDataLayer,
) -> None:
    body = delivered_body(_report_activity())
    dl.save(
        ReceivedActivityRecord(
            activity_id=body["id"],
            received_body=json.dumps(body),
            stage=ReceivedStage.HELD,
            replay_owed=False,
            received_at=_ARRIVED,
        )
    )
    probe = _InstantProbe()
    dispatcher = Mock()
    dispatcher.dispatch.side_effect = probe.dispatch

    asyncio.run(rerun_left_in_holding(dl, _RECEIVER, dispatcher, None))

    assert probe.instants == [_ARRIVED]


@pytest.mark.spec("CS-13-001", "CS-13-010")
def test_a_stored_stamp_reads_back_aware(dl: SqliteDataLayer) -> None:
    """A naive stamp is written with a UTC offset (CS-13-007), so the stamp a
    drain reads back can always open an act; none is left stuck."""
    held = _note_activity("naive")
    assert hold_activity(dl, held, received_at=_ARRIVED.replace(tzinfo=None))

    assert _record(dl, held.id_).received_at == _ARRIVED
