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
from vultron.adapters.driving.fastapi import inbox_orchestration as io
from vultron.adapters.driving.fastapi.inbox_dereference import (
    FastAPIDereferencePort,
    open_fetches,
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
