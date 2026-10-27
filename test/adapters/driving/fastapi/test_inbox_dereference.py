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
"""Fetch-and-defer through the inbox run (AKM-05-007, AKM-05-008).

Each test runs the production inbox run, ``run_inbox_pipeline``, with a fake
fetcher in place of HTTP, so the deferral, the fetch, its settlement and the
replay are exercised as one delivery would exercise them.
"""

import asyncio
import json
import logging
from datetime import timedelta
from typing import Any
from unittest.mock import Mock

import pytest

from test.support.case_manager import (
    CASE_MANAGER_ID,
    make_case_with_case_manager,
)
from test.support.embargo_register import activate
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driven.http_object_fetch import ObjectFetchResult
from vultron.adapters.driving.fastapi import (
    inbox_dereference as deref,
    inbox_orchestration as io,
)
from vultron.adapters.driving.fastapi.inbox_dereference import (
    FastAPIDereferencePort,
    open_fetches,
    parse_fetched_object,
    settle_fetch,
)
from vultron.adapters.inbox_staging import InlineObjectStaging
from vultron.core.models._helpers import now_utc
from vultron.core.models.actor import CoreActor
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.deferred_inbox_activity import DeferredInboxActivity
from vultron.core.models.embargo_event import EmbargoEvent
from vultron.core.models.events import MessageSemantics, VultronEvent
from vultron.core.models.object_fetch import (
    ObjectFetchSource,
    ObjectFetchState,
    ObjectFetchUse,
    ObjectReference,
    PendingObjectFetch,
)
from vultron.core.models.use_case_result import HandlerResult
from vultron.errors import VultronValidationError

_REPLICA = "https://example.org/actors/vendor"
_CASE_ACTOR = "https://example.org/actors/case-actor"
_PUBLISHED = "2026-10-26T12:00:00Z"


class _FakeFetcher:
    """Answers each fetch from a table, recording what it was asked."""

    def __init__(self, answers: dict[str, ObjectFetchResult]) -> None:
        self._answers = answers
        self.asked: list[tuple[ObjectReference, str]] = []

    async def fetch(
        self, reference: ObjectReference, requester_id: str
    ) -> ObjectFetchResult:
        self.asked.append((reference, requester_id))
        return self._answers[reference.object_id]


@pytest.fixture(autouse=True)
def clear_actor_locks():
    """An asyncio.Lock binds to its first loop, and these tests run several."""
    io._actor_inbox_locks.clear()
    yield
    io._actor_inbox_locks.clear()


@pytest.fixture(autouse=True)
def no_outbox_drain(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep anything queued in the outbox, with no HTTP delivery."""

    async def _drain(*_args: object, **_kwargs: object) -> None:
        return None

    monkeypatch.setattr(io, "outbox_handler", _drain)


def _replica() -> tuple[SqliteDataLayer, VulnerabilityCase]:
    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=_REPLICA)
    return dl, make_case_with_case_manager(dl)


def _embargo(case_id: str) -> EmbargoEvent:
    return EmbargoEvent(
        context=case_id, end_time=now_utc() + timedelta(days=30)
    )


def _revision(
    case_id: str, revision: EmbargoEvent, n: int = 1
) -> dict[str, Any]:
    """The CASE_MANAGER's ``Announce`` of a revision, carried inline."""
    return {
        "type": "Announce",
        "id": f"https://example.org/activities/announce-{n}",
        "published": _PUBLISHED,
        "actor": CASE_MANAGER_ID,
        "object": _body(revision),
        "context": case_id,
        "to": [_REPLICA],
    }


def _bare_accept(case_id: str, object_id: str) -> dict[str, Any]:
    """An activity no pattern matches while its ``object`` is a bare id."""
    return {
        "type": "Accept",
        "id": "https://example.org/activities/accept-1",
        "published": _PUBLISHED,
        "actor": CASE_MANAGER_ID,
        "object": object_id,
        "context": case_id,
        "to": [_REPLICA],
    }


def _replica_missing_its_active_embargo() -> tuple[
    SqliteDataLayer, VulnerabilityCase, EmbargoEvent
]:
    """A replica whose case names an active embargo it holds no record of."""
    dl, case = _replica()
    replaced = _embargo(case.id_)
    activate(case, replaced.id_)
    dl.save(case)
    return dl, case, replaced


def _body(obj: EmbargoEvent | CoreActor) -> dict[str, Any]:
    return obj.model_dump(mode="json", by_alias=True, exclude_none=True)


def _run(
    dl: SqliteDataLayer,
    actor_id: str,
    payload: dict[str, Any],
    fetcher: _FakeFetcher,
    dispatcher: Any = None,
) -> None:
    asyncio.run(
        io.run_inbox_pipeline(
            payload, dl, actor_id, dispatcher, None, fetcher=fetcher
        )
    )


def _fetches(dl: SqliteDataLayer) -> list[PendingObjectFetch]:
    return [
        r
        for r in dl.list_objects("PendingObjectFetch")
        if isinstance(r, PendingObjectFetch)
    ]


def _held(dl: SqliteDataLayer, activity_id: str) -> bool:
    return isinstance(
        dl.read(DeferredInboxActivity.build_id(activity_id)),
        DeferredInboxActivity,
    )


@pytest.mark.spec("EMB-18-007")
@pytest.mark.spec("AKM-05-010")
@pytest.mark.spec("AKM-05-003")
@pytest.mark.spec("AKM-05-007")
@pytest.mark.spec("EMB-18-003")
def test_a_replaced_embargo_the_replica_lacks_is_fetched_kept_and_replayed():
    """The revision waits on the fetch of the embargo it replaces, the
    fetched embargo is stored, and the replay dispatches the revision."""
    dl, case, replaced = _replica_missing_its_active_embargo()
    payload = _revision(case.id_, _embargo(case.id_))
    fetcher = _FakeFetcher(
        {replaced.id_: ObjectFetchResult(_body(replaced), None, 1)}
    )
    seen: list[VultronEvent] = []

    def _record(event: VultronEvent, _dl: Any) -> HandlerResult:
        seen.append(event)
        assert isinstance(_dl.read(replaced.id_), EmbargoEvent)
        return HandlerResult.applied()

    dispatcher = Mock()
    dispatcher.dispatch.side_effect = _record

    _run(dl, _REPLICA, payload, fetcher, dispatcher)

    assert fetcher.asked == [
        (
            ObjectReference(
                object_id=replaced.id_,
                source=ObjectFetchSource.CASE_HOST,
                host_actor_id=CASE_MANAGER_ID,
                case_id=case.id_,
                use=ObjectFetchUse.STORE,
            ),
            _REPLICA,
        )
    ]
    (event,) = seen
    assert (
        event.semantic_type is MessageSemantics.ANNOUNCE_EMBARGO_EVENT_TO_CASE
    )
    assert _fetches(dl) == []
    assert not _held(dl, payload["id"])
    assert dl.inbox_list() == []


@pytest.mark.spec("AKM-05-007")
def test_an_unclassifiable_activity_is_replayed_with_its_object_resolved():
    """An activity no pattern could match for want of its object is replayed
    once the fetched object is held, and rehydrates it."""
    dl, case = _replica()
    embargo = _embargo(case.id_)
    payload = _bare_accept(case.id_, embargo.id_)
    fetcher = _FakeFetcher(
        {embargo.id_: ObjectFetchResult(_body(embargo), None, 1)}
    )
    seen: list[VultronEvent] = []

    def _record(event: VultronEvent, _dl: Any) -> HandlerResult:
        seen.append(event)
        return HandlerResult.applied()

    dispatcher = Mock()
    dispatcher.dispatch.side_effect = _record

    _run(dl, _REPLICA, payload, fetcher, dispatcher)

    (event,) = seen
    assert isinstance(event.object_, EmbargoEvent)
    assert isinstance(dl.read(embargo.id_), EmbargoEvent)
    assert _fetches(dl) == []


@pytest.mark.spec("AKM-05-010")
@pytest.mark.spec("AKM-05-007")
def test_the_activity_is_deferred_not_dropped_while_the_fetch_is_open():
    """Before any fetch is made the activity is held whole and waits."""
    dl, case, _ = _replica_missing_its_active_embargo()
    payload = _revision(case.id_, _embargo(case.id_))
    run = io._InboxRun(dl, _REPLICA, None)

    outcome = io.process_payload(
        payload,
        run.ingress,
        run.dispatch,
        run.queue,
        dereference_port=run.dereference,
    )

    assert outcome.status.value == "deferred"
    (fetch,) = _fetches(dl)
    assert fetch.state is ObjectFetchState.PENDING
    assert fetch.waiting_activity_ids == [payload["id"]]
    assert _held(dl, payload["id"])


@pytest.mark.spec("AKM-05-014")
@pytest.mark.spec("AKM-05-015")
@pytest.mark.spec("AKM-05-008")
def test_a_failed_fetch_is_a_warning_and_the_activity_goes_on_without_it(
    caplog: pytest.LogCaptureFixture,
):
    """The waiting activity is replayed with its reference unresolved, so it
    is handled as it was before dereference existed."""
    dl, case = _replica()
    missing = "urn:uuid:nobody-holds-this"
    payload = _bare_accept(case.id_, missing)
    fetcher = _FakeFetcher(
        {missing: ObjectFetchResult(None, "GET … answered HTTP 404", 1)}
    )
    seen: list[VultronEvent] = []

    def _record(event: VultronEvent, _dl: Any) -> HandlerResult:
        seen.append(event)
        return HandlerResult.applied()

    dispatcher = Mock()
    dispatcher.dispatch.side_effect = _record

    with caplog.at_level(logging.WARNING):
        _run(dl, _REPLICA, payload, fetcher, dispatcher)

    assert any(
        r.levelno == logging.WARNING
        and "AKM-05-008" in r.getMessage()
        and missing in r.getMessage()
        for r in caplog.records
    )
    (event,) = seen
    assert event.semantic_type is MessageSemantics.UNKNOWN_UNRESOLVABLE_OBJECT
    assert _fetches(dl) == [], "a settled fetch nothing waits on is removed"
    assert not _held(dl, payload["id"])


@pytest.mark.spec("AKM-05-007")
def test_two_activities_naming_one_object_wait_on_one_fetch():
    dl, case, replaced = _replica_missing_its_active_embargo()
    run = io._InboxRun(dl, _REPLICA, None)
    for n in (1, 2):
        io.process_payload(
            _revision(case.id_, _embargo(case.id_), n),
            run.ingress,
            run.dispatch,
            run.queue,
            dereference_port=run.dereference,
        )

    (fetch,) = _fetches(dl)
    assert fetch.waiting_activity_ids == [
        "https://example.org/activities/announce-1",
        "https://example.org/activities/announce-2",
    ]

    queued = settle_fetch(
        dl,
        _REPLICA,
        replaced.id_,
        ObjectFetchResult(_body(replaced), None, 1),
    )

    assert queued == fetch.waiting_activity_ids
    assert dl.inbox_list() == queued


@pytest.mark.spec("AKM-05-007")
def test_an_activity_waiting_on_two_fetches_replays_once_both_settle():
    dl, case = _replica()
    port = FastAPIDereferencePort(dl, _REPLICA, InlineObjectStaging(dl))
    first, second = (
        ObjectReference(
            object_id=f"urn:uuid:obj-{n}",
            source=ObjectFetchSource.CASE_HOST,
            host_actor_id=CASE_MANAGER_ID,
            case_id=case.id_,
            use=ObjectFetchUse.STORE,
        )
        for n in (1, 2)
    )
    activity_id = "https://example.org/activities/waits-on-two"
    for reference in (first, second):
        dl.save(
            PendingObjectFetch.for_reference(reference).model_copy(
                update={"waiting_activity_ids": [activity_id]}
            )
        )
    dl.create(
        DeferredInboxActivity(
            activity_id=activity_id,
            received_body=json.dumps({"id": activity_id}),
        )
    )
    failed = ObjectFetchResult(None, "unreachable", 3)

    assert settle_fetch(dl, _REPLICA, first.object_id, failed) == []
    assert settle_fetch(dl, _REPLICA, second.object_id, failed) == [
        activity_id
    ]
    assert {f.state for f in _fetches(dl)} == {ObjectFetchState.FAILED}
    assert port.fetch_of(first.object_id) is not None


@pytest.mark.spec("CP-01-014")
@pytest.mark.spec("CP-01-017")
@pytest.mark.spec("CP-01-009")
@pytest.mark.spec("CP-01-010")
def test_a_proposers_profile_is_handed_to_the_proposal_and_never_stored():
    """The CASE_MANAGER fetches the profile from the proposer, the event it
    dispatches carries it, and its store keeps no copy (CP-01-010)."""
    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=_CASE_ACTOR)
    profile = CoreActor.model_validate(
        {
            "type": "Organization",
            "id": _REPLICA,
            "name": "Vendor",
            "embargoPolicy": {
                "type": "EmbargoPolicy",
                "actorId": _REPLICA,
                "inbox": f"{_REPLICA}/inbox",
                "preferredDuration": "P45D",
            },
        }
    )
    payload = {
        "type": "Create",
        "id": "https://example.org/activities/create-proposal",
        "published": _PUBLISHED,
        "actor": _REPLICA,
        "to": [_CASE_ACTOR],
        "object": {
            "type": "CaseProposal",
            "id": "https://example.org/proposals/p-1",
            "attributedTo": _REPLICA,
            "object": {
                "type": "VulnerabilityReport",
                "id": "https://example.org/reports/r-1",
                "name": "A report",
                "content": "Details",
                "attributedTo": _REPLICA,
            },
            "target": _CASE_ACTOR,
        },
    }
    fetcher = _FakeFetcher(
        {_REPLICA: ObjectFetchResult(_body(profile), None, 1)}
    )
    seen: list[VultronEvent] = []

    def _record(event: VultronEvent, _dl: Any) -> HandlerResult:
        seen.append(event)
        return HandlerResult.applied()

    dispatcher = Mock()
    dispatcher.dispatch.side_effect = _record

    _run(dl, _CASE_ACTOR, payload, fetcher, dispatcher)

    ((reference, requester),) = fetcher.asked
    assert reference.source is ObjectFetchSource.ACTOR_PROFILE
    assert requester == _CASE_ACTOR
    (event,) = seen
    handed = getattr(event, "proposer_profile", None)
    assert isinstance(handed, CoreActor)
    assert handed.embargo_policy is not None
    assert handed.embargo_policy.preferred_duration == timedelta(days=45)
    assert dl.read(_REPLICA) is None, "the profile is not stored"
    assert _fetches(dl) == [], "the handed-off body is released"


@pytest.mark.spec("AKM-05-014")
@pytest.mark.spec("AKM-05-008")
def test_a_fetched_body_that_is_not_the_object_asked_for_fails_the_fetch():
    dl, case = _replica()
    asked = _embargo(case.id_)
    other = _embargo(case.id_)
    reference = ObjectReference(
        object_id=asked.id_,
        source=ObjectFetchSource.CASE_HOST,
        host_actor_id=CASE_MANAGER_ID,
        case_id=case.id_,
        use=ObjectFetchUse.STORE,
    )
    dl.save(PendingObjectFetch.for_reference(reference))

    settle_fetch(
        dl, _REPLICA, asked.id_, ObjectFetchResult(_body(other), None, 1)
    )

    (fetch,) = _fetches(dl)
    assert fetch.state is ObjectFetchState.FAILED
    assert fetch.failure_reason is not None
    assert "is not the" in fetch.failure_reason
    assert dl.read(other.id_) is None


@pytest.mark.spec("AKM-05-012")
@pytest.mark.spec("AKM-05-007")
def test_a_fetched_object_never_replaces_one_already_held():
    """A copy held meanwhile is kept, never overwritten (MV-10-003)."""
    dl, case = _replica()
    held = _embargo(case.id_)
    dl.save(held)
    fetched = held.model_copy(update={"summary": "fetched copy"})
    reference = ObjectReference(
        object_id=held.id_,
        source=ObjectFetchSource.CASE_HOST,
        host_actor_id=CASE_MANAGER_ID,
        case_id=case.id_,
        use=ObjectFetchUse.STORE,
    )
    dl.save(PendingObjectFetch.for_reference(reference))

    settle_fetch(
        dl, _REPLICA, held.id_, ObjectFetchResult(_body(fetched), None, 1)
    )

    kept = dl.read(held.id_)
    assert isinstance(kept, EmbargoEvent)
    assert kept.summary is None
    assert open_fetches(dl) == []


@pytest.mark.spec("DL-06-006")
@pytest.mark.spec("AKM-05-008")
def test_a_fetched_activity_is_never_kept_under_its_own_id():
    """A replica keeps no activity under the id its sender chose."""
    dl, case = _replica()
    activity_id = "https://example.org/activities/manager-note"
    activity = {
        "type": "Add",
        "id": activity_id,
        "published": _PUBLISHED,
        "actor": CASE_MANAGER_ID,
        "object": {"type": "Note", "id": "urn:uuid:n-1", "content": "x"},
        "target": case.id_,
        "context": case.id_,
    }
    reference = ObjectReference(
        object_id=activity_id,
        source=ObjectFetchSource.CASE_HOST,
        host_actor_id=CASE_MANAGER_ID,
        case_id=case.id_,
        use=ObjectFetchUse.STORE,
    )
    dl.save(PendingObjectFetch.for_reference(reference))

    settle_fetch(
        dl, _REPLICA, activity_id, ObjectFetchResult(activity, None, 1)
    )

    (fetch,) = _fetches(dl)
    assert fetch.state is ObjectFetchState.FAILED
    assert "DL-06-006" in (fetch.failure_reason or "")
    assert dl.read(activity_id) is None


def _store_reference(case_id: str, object_id: str) -> ObjectReference:
    return ObjectReference(
        object_id=object_id,
        source=ObjectFetchSource.CASE_HOST,
        host_actor_id=CASE_MANAGER_ID,
        case_id=case_id,
        use=ObjectFetchUse.STORE,
    )


@pytest.mark.spec("AKM-05-007")
@pytest.mark.spec("IE-06-006")
def test_the_startup_replay_makes_a_fetch_an_earlier_run_left_open():
    """A fetch recorded before a restart is made by the startup replay."""
    dl, case, replaced = _replica_missing_its_active_embargo()
    run = io._InboxRun(dl, _REPLICA, None)
    payload = _revision(case.id_, _embargo(case.id_))
    io.process_payload(
        payload,
        run.ingress,
        run.dispatch,
        run.queue,
        dereference_port=run.dereference,
    )
    fetcher = _FakeFetcher(
        {replaced.id_: ObjectFetchResult(_body(replaced), None, 1)}
    )
    dispatcher = Mock()
    dispatcher.dispatch.side_effect = lambda *_: HandlerResult.applied()

    asyncio.run(
        io.replay_inbox_queue(dl, _REPLICA, dispatcher, None, fetcher=fetcher)
    )

    assert [r.object_id for r, _ in fetcher.asked] == [replaced.id_]
    assert isinstance(dl.read(replaced.id_), EmbargoEvent)
    dispatcher.dispatch.assert_called_once()
    assert _fetches(dl) == []


def test_settling_a_fetch_that_is_not_open_changes_nothing():
    dl, _ = _replica()

    assert (
        settle_fetch(
            dl,
            _REPLICA,
            "urn:uuid:never-asked",
            ObjectFetchResult({}, None, 1),
        )
        == []
    )
    assert _fetches(dl) == []


def test_a_waiter_not_held_for_replay_is_logged_and_skipped(
    caplog: pytest.LogCaptureFixture,
):
    dl, case = _replica()
    reference = _store_reference(case.id_, "urn:uuid:obj")
    dl.save(
        PendingObjectFetch.for_reference(reference).model_copy(
            update={"waiting_activity_ids": ["https://example.org/a/lost"]}
        )
    )

    with caplog.at_level(logging.WARNING):
        queued = settle_fetch(
            dl, _REPLICA, reference.object_id, ObjectFetchResult(None, "x", 1)
        )

    assert queued == []
    assert any(
        r.levelno == logging.WARNING and "not held" in r.getMessage()
        for r in caplog.records
    )
    assert _fetches(dl) == [], "a record nothing can wait on is removed"


def _hold(dl: SqliteDataLayer, activity_id: str) -> None:
    dl.create(
        DeferredInboxActivity(
            activity_id=activity_id,
            received_body=json.dumps({"id": activity_id}),
        )
    )


def _await(
    dl: SqliteDataLayer, reference: ObjectReference, waiters: list[str]
) -> None:
    dl.save(
        PendingObjectFetch.for_reference(reference).model_copy(
            update={"waiting_activity_ids": waiters}
        )
    )


def test_an_unheld_waiter_on_two_fetches_is_kept_by_no_settled_fetch():
    """An unheld waiter is dropped even while another fetch is still open."""
    dl, case = _replica()
    unheld = "https://example.org/a/lost"
    held = "https://example.org/a/held"
    _hold(dl, held)
    first = _store_reference(case.id_, "urn:uuid:first")
    second = _store_reference(case.id_, "urn:uuid:second")
    _await(dl, first, [held, unheld])
    _await(dl, second, [unheld])

    settle_fetch(
        dl, _REPLICA, first.object_id, ObjectFetchResult(None, "x", 1)
    )

    (settled,) = [f for f in _fetches(dl) if f.object_id == first.object_id]
    assert settled.waiting_activity_ids == [held], (
        "the unheld waiter is dropped though the second fetch is open"
    )

    settle_fetch(
        dl, _REPLICA, second.object_id, ObjectFetchResult(None, "x", 1)
    )

    assert not any(
        unheld in f.waiting_activity_ids
        for f in _fetches(dl)
        if f.state is not ObjectFetchState.PENDING
    ), "no settled fetch keeps the unheld waiter"


def test_a_settled_fetch_keeps_only_its_held_waiter_and_replays_it():
    dl, case = _replica()
    held = "https://example.org/a/held"
    unheld = "https://example.org/a/lost"
    _hold(dl, held)
    reference = _store_reference(case.id_, "urn:uuid:obj")
    _await(dl, reference, [held, unheld])

    queued = settle_fetch(
        dl, _REPLICA, reference.object_id, ObjectFetchResult(None, "x", 1)
    )

    assert queued == [held]
    assert held in dl.inbox_list()
    assert unheld not in dl.inbox_list()
    (fetch,) = _fetches(dl)
    assert fetch.state is ObjectFetchState.FAILED
    assert fetch.waiting_activity_ids == [held]


def test_release_keeps_a_settled_fetch_others_still_wait_on():
    dl, case = _replica()
    port = FastAPIDereferencePort(dl, _REPLICA, InlineObjectStaging(dl))
    reference = _store_reference(case.id_, "urn:uuid:obj")
    dl.save(
        PendingObjectFetch.for_reference(reference).model_copy(
            update={
                "state": ObjectFetchState.FAILED,
                "failure_reason": "unreachable",
                "waiting_activity_ids": [
                    "https://example.org/a/1",
                    "https://example.org/a/2",
                ],
            }
        )
    )

    port.release(reference.object_id, "https://example.org/a/1")

    (fetch,) = _fetches(dl)
    assert fetch.waiting_activity_ids == ["https://example.org/a/2"]
    port.release(reference.object_id, "https://example.org/a/2")
    assert _fetches(dl) == []


@pytest.mark.parametrize(
    "body, match",
    [
        ({"id": "urn:uuid:x"}, "names no type"),
        ({"type": "NoSuchType", "id": "urn:uuid:x"}, "not a valid"),
    ],
    ids=["untyped", "unknown-type"],
)
def test_a_fetched_body_the_vocabulary_cannot_type_is_refused(
    body: dict[str, Any], match: str
):
    with pytest.raises(VultronValidationError, match=match):
        parse_fetched_object(body, "urn:uuid:x")


def test_a_hand_off_record_without_its_body_is_unreadable():
    dl, case = _replica()
    port = FastAPIDereferencePort(dl, _REPLICA, InlineObjectStaging(dl))
    record = PendingObjectFetch.for_reference(
        _store_reference(case.id_, "urn:uuid:obj")
    )

    with pytest.raises(VultronValidationError, match="no fetched body"):
        port.fetched_object(record)


def test_the_default_fetcher_takes_its_limits_from_the_config(
    monkeypatch: pytest.MonkeyPatch,
):
    from types import SimpleNamespace

    monkeypatch.setattr(
        deref,
        "get_config",
        lambda: SimpleNamespace(
            max_object_fetch_attempts=7, object_fetch_timeout_seconds=1.5
        ),
    )

    fetcher = deref.default_object_fetcher()

    assert fetcher._max_attempts == 7
    assert fetcher._timeout == 1.5


def _open_fetch_and_held_waiter(
    dl: SqliteDataLayer, case: VulnerabilityCase, object_id: str
) -> str:
    """An open fetch of *object_id* and the held activity waiting on it."""
    activity_id = f"https://example.org/activities/waits-on-{object_id[-5:]}"
    dl.save(
        PendingObjectFetch.for_reference(
            _store_reference(case.id_, object_id)
        ).model_copy(update={"waiting_activity_ids": [activity_id]})
    )
    dl.create(
        DeferredInboxActivity(
            activity_id=activity_id,
            received_body=json.dumps({"id": activity_id}),
        )
    )
    return activity_id


async def _no_lock(work: Any) -> None:
    work()


@pytest.mark.spec("AKM-05-008")
def test_the_default_fetcher_is_built_only_when_something_is_open(
    monkeypatch: pytest.MonkeyPatch,
):
    dl, case = _replica()
    _open_fetch_and_held_waiter(dl, case, "urn:uuid:obj-1")
    fake = _FakeFetcher(
        {"urn:uuid:obj-1": ObjectFetchResult(None, "unreachable", 1)}
    )
    built: list[int] = []

    def _default() -> _FakeFetcher:
        built.append(1)
        return fake

    monkeypatch.setattr(deref, "default_object_fetcher", _default)

    asyncio.run(
        deref.resolve_open_fetches(dl, _REPLICA, _no_lock, lambda: None)
    )
    asyncio.run(
        deref.resolve_open_fetches(dl, _REPLICA, _no_lock, lambda: None)
    )

    assert built == [1], "built for the open fetch, not for the empty run"
    assert len(fake.asked) == 1


@pytest.mark.spec("AKM-05-008")
def test_a_fetch_still_open_after_the_round_cap_waits_for_the_next_run(
    monkeypatch: pytest.MonkeyPatch,
):
    """A settlement that leaves the fetch open bounds the run, not loops it."""
    dl, case = _replica()
    _open_fetch_and_held_waiter(dl, case, "urn:uuid:obj-1")
    fake = _FakeFetcher(
        {"urn:uuid:obj-1": ObjectFetchResult(None, "unreachable", 1)}
    )
    monkeypatch.setattr(deref, "settle_fetch", lambda *_: [])

    asyncio.run(
        deref.resolve_open_fetches(dl, _REPLICA, _no_lock, lambda: None, fake)
    )

    assert len(fake.asked) == deref.MAX_FETCH_ROUNDS
    (fetch,) = _fetches(dl)
    assert fetch.state is ObjectFetchState.PENDING


@pytest.mark.spec("AKM-05-008")
def test_a_fetcher_that_raises_fails_the_fetch_and_the_run_goes_on(
    caplog: pytest.LogCaptureFixture,
):
    dl, case = _replica()
    first = _open_fetch_and_held_waiter(dl, case, "urn:uuid:obj-1")
    second = _open_fetch_and_held_waiter(dl, case, "urn:uuid:obj-2")

    class _Raises:
        def __init__(self) -> None:
            self.asked: list[str] = []

        async def fetch(
            self, reference: ObjectReference, requester_id: str
        ) -> ObjectFetchResult:
            self.asked.append(reference.object_id)
            raise RuntimeError("the client refused the URL")

    fetcher = _Raises()
    with caplog.at_level(logging.WARNING):
        asyncio.run(
            deref.resolve_open_fetches(
                dl, _REPLICA, _no_lock, lambda: None, fetcher
            )
        )

    assert sorted(fetcher.asked) == ["urn:uuid:obj-1", "urn:uuid:obj-2"]
    assert {f.state for f in _fetches(dl)} == {ObjectFetchState.FAILED}
    assert sorted(dl.inbox_list()) == sorted([first, second])
    assert any("the fetcher raised" in r.getMessage() for r in caplog.records)


@pytest.mark.spec("AKM-05-007")
@pytest.mark.spec("IE-10-001")
def test_a_redelivery_of_a_waiting_activity_waits_once():
    """The same activity delivered again is held once and waits once."""
    dl, case, replaced = _replica_missing_its_active_embargo()
    payload = _revision(case.id_, _embargo(case.id_))
    for _ in range(2):
        run = io._InboxRun(dl, _REPLICA, None)
        outcome = io.process_payload(
            payload,
            run.ingress,
            run.dispatch,
            run.queue,
            dereference_port=run.dereference,
        )
        assert outcome.status.value == "deferred"

    (fetch,) = _fetches(dl)
    assert fetch.object_id == replaced.id_
    assert fetch.waiting_activity_ids == [payload["id"]]
    held = [
        r
        for r in dl.list_objects("DeferredInboxActivity")
        if isinstance(r, DeferredInboxActivity)
    ]
    assert [r.activity_id for r in held] == [payload["id"]]


def test_release_with_no_record_changes_nothing():
    dl, _ = _replica()
    port = FastAPIDereferencePort(dl, _REPLICA, InlineObjectStaging(dl))

    port.release("urn:uuid:never-fetched", "https://example.org/a/1")

    assert _fetches(dl) == []


def test_a_handed_off_body_that_is_not_a_core_object_is_unreadable():
    dl, _ = _replica()
    port = FastAPIDereferencePort(dl, _REPLICA, InlineObjectStaging(dl))
    record = PendingObjectFetch.for_reference(
        ObjectReference(
            object_id="urn:uuid:img",
            source=ObjectFetchSource.ACTOR_PROFILE,
            host_actor_id=CASE_MANAGER_ID,
            use=ObjectFetchUse.HAND_OFF,
        )
    ).model_copy(
        update={
            "state": ObjectFetchState.FETCHED,
            "fetched_body": json.dumps(
                {"type": "Image", "id": "urn:uuid:img"}
            ),
        }
    )

    with pytest.raises(VultronValidationError, match="not a core object"):
        port.fetched_object(record)
