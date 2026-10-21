"""The production inbox replay's bounded retry and dead letter (IE-06-004).

``run_inbox_pipeline`` replays every item queued in the receiving actor's
inbox.  An attempt that raises is re-queued, unanswered, up to
``AppConfig.max_inbox_retry_attempts``, then dead-lettered and answered with
one internal-error ``Create(ProcessingFault)`` (ASK-07-010): a fault sent on
a retried attempt would be false if a later attempt succeeded (ASK-07-007).
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

import asyncio
import logging
from collections.abc import Callable
from types import SimpleNamespace
from typing import Any
from unittest.mock import Mock

import pytest

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driving.fastapi import (
    inbox_orchestration as io,
    inbox_replay as replay,
)
from vultron.adapters.inbox_staging import InlineObjectStaging, hold_activity
from vultron.adapters.outbox_sealed_body import read_sealed_body_dict
from vultron.core.behaviors.inbox import InboxOutcome, InboxOutcomeStatus
from vultron.core.models.fault_classes import (
    VULTRON_FAILURE_INTERNAL_PROCESSING_ERROR,
)
from vultron.core.models.use_case_result import HandlerResult
from vultron.errors import VultronProtocolViolationError, VultronWiringError
from vultron.wire.as2.factories import (
    add_note_to_case_activity,
    create_processing_fault_activity,
)
from vultron.wire.as2.vocab.base.objects.activities.base import as_Activity
from vultron.wire.as2.vocab.base.objects.object_types import as_Note
from vultron.wire.as2.vocab.objects.processing_fault import as_ProcessingFault
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)

_RECEIVER = "https://example.org/actors/participant"
_SENDER = "https://example.org/actors/case-actor"
_CASE = "https://example.org/cases/case-replay-retry"


@pytest.fixture
def dl() -> SqliteDataLayer:
    """The receiver's store, holding the case so a replay is not deferred."""
    store = SqliteDataLayer("sqlite:///:memory:", actor_id=_RECEIVER)
    store.save(as_VulnerabilityCase(id_=_CASE, name="Replica"))
    return store


@pytest.fixture
def outbox_drains(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Keep queued faults in the outbox, where the tests read them, and
    record each outbox drain the inbox run requests."""
    drains: list[str] = []

    async def _drain(actor_id: str, *_args: object, **_kwargs: object) -> None:
        drains.append(actor_id)

    monkeypatch.setattr(io, "outbox_handler", _drain)
    return drains


def _max_attempts(monkeypatch: pytest.MonkeyPatch, count: int) -> None:
    monkeypatch.setattr(
        io,
        "get_config",
        lambda: SimpleNamespace(max_inbox_retry_attempts=count),
    )


def _queue(dl: SqliteDataLayer, item: as_Activity) -> as_Activity:
    """Hold *item* and queue it for the inbox replay."""
    assert hold_activity(dl, item)
    dl.inbox_append(item.id_)
    return item


def _queued_item(dl: SqliteDataLayer) -> as_Activity:
    """An extractable activity held and queued for the inbox replay."""
    return _queue(
        dl,
        add_note_to_case_activity(
            as_Note(content="replayed", context=_CASE),
            target=_CASE,
            context=_CASE,
            actor=_SENDER,
            to=[_RECEIVER],
        ),
    )


def _faults_queued(dl: SqliteDataLayer) -> list[dict[str, Any]]:
    """Every ``Create(ProcessingFault)`` waiting in *dl*'s outbox."""
    bodies = [read_sealed_body_dict(dl, item) for item in dl.outbox_list()]
    return [
        body
        for body in bodies
        if body is not None
        and body.get("type") == "Create"
        and isinstance(body.get("object"), dict)
        and body["object"].get("type") == "ProcessingFault"
    ]


def _dispatcher(
    side_effect: Callable[..., HandlerResult],
) -> Mock:
    dispatcher = Mock()
    dispatcher.dispatch.side_effect = side_effect
    return dispatcher


def _raises(_event: Any, _dl: Any) -> HandlerResult:
    raise RuntimeError("the use case raised")


def _run(dl: SqliteDataLayer, dispatcher: Mock) -> None:
    """One production inbox run: an unparseable body, then the replays."""
    asyncio.run(io.run_inbox_pipeline({}, dl, _RECEIVER, dispatcher, None))


def _rebuild_raises(monkeypatch: pytest.MonkeyPatch, error: Exception) -> None:
    def _raise(self: InlineObjectStaging, _pending: Any) -> Any:
        raise error

    monkeypatch.setattr(InlineObjectStaging, "_rebuild_from", _raise)


def _logged(caplog: pytest.LogCaptureFixture, *parts: str) -> bool:
    """Whether one ERROR record names every one of *parts*."""
    return any(
        r.levelno == logging.ERROR
        and all(part in r.getMessage() for part in parts)
        for r in caplog.records
    )


@pytest.mark.spec("IE-06-004")
@pytest.mark.spec("ASK-07-010")
@pytest.mark.usefixtures("outbox_drains")
def test_a_failing_replay_is_answered_only_when_dead_lettered(
    dl: SqliteDataLayer, monkeypatch: pytest.MonkeyPatch, caplog
) -> None:
    """Every attempt but the last is re-queued unanswered; the last is
    dead-lettered and answered with one internal-error fault.  Each one is
    logged at ERROR with the item and the receiving actor."""
    _max_attempts(monkeypatch, 3)
    item = _queued_item(dl)
    faults_seen: list[int] = []

    def _raise(event: Any, store: Any) -> HandlerResult:
        faults_seen.append(len(_faults_queued(dl)))
        return _raises(event, store)

    with caplog.at_level(logging.ERROR, logger=replay.__name__):
        _run(dl, _dispatcher(_raise))

    assert faults_seen == [0, 0, 0], "a retried attempt is not answered"
    (entry,) = dl.inbox_dead_letter_list()
    assert entry.activity_id == item.id_
    assert entry.total_attempts == 3
    assert entry.reason == "processing_error"
    assert entry.last_error == "the use case raised"
    assert dl.inbox_list() == []
    assert dl.get_inbox_attempt_count(item.id_) == 0
    assert _logged(caplog, item.id_, _RECEIVER, "re-queuing for retry")
    assert _logged(caplog, item.id_, _RECEIVER, "moved to dead letter")
    (fault,) = _faults_queued(dl)
    assert fault["actor"] == _RECEIVER
    assert fault["to"] == [_SENDER]
    assert fault["object"]["failureClass"] == (
        VULTRON_FAILURE_INTERNAL_PROCESSING_ERROR
    )
    assert fault["object"]["inReplyTo"] == item.id_
    assert "the use case raised" not in str(fault), "no diagnostics"


@pytest.mark.spec("IE-06-004")
@pytest.mark.usefixtures("outbox_drains")
def test_the_attempt_count_persists_across_runs(
    dl: SqliteDataLayer, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A count an earlier run stored counts toward the budget."""
    _max_attempts(monkeypatch, 3)
    item = _queued_item(dl)
    dl.set_inbox_attempt_count(item.id_, 2)
    dispatcher = _dispatcher(_raises)

    _run(dl, dispatcher)

    dispatcher.dispatch.assert_called_once()
    (entry,) = dl.inbox_dead_letter_list()
    assert entry.total_attempts == 3


@pytest.mark.spec("IE-06-004", "DL-06-006")
@pytest.mark.usefixtures("outbox_drains")
def test_a_dead_lettered_item_stays_held(
    dl: SqliteDataLayer, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The rebuild released the item's record; the dead letter holds it
    again, so an operator can still read the activity."""
    _max_attempts(monkeypatch, 1)
    item = _queued_item(dl)

    _run(dl, _dispatcher(_raises))

    assert InlineObjectStaging(dl).held(item.id_) is not None
    assert dl.read(item.id_) is None


@pytest.mark.spec("IE-06-004")
@pytest.mark.spec("ASK-07-010")
@pytest.mark.usefixtures("outbox_drains")
def test_a_retry_that_succeeds_is_never_answered(
    dl: SqliteDataLayer, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A retry re-runs the whole act; when it succeeds, no fault was sent
    and the attempt count is cleared."""
    _max_attempts(monkeypatch, 3)
    item = _queued_item(dl)
    calls: list[str] = []

    def _fail_once(event: Any, store: Any) -> HandlerResult:
        calls.append(event.activity_id)
        if len(calls) == 1:
            return _raises(event, store)
        return HandlerResult.applied()

    _run(dl, _dispatcher(_fail_once))

    assert calls == [item.id_, item.id_]
    assert _faults_queued(dl) == []
    assert dl.inbox_dead_letter_list() == []
    assert dl.get_inbox_attempt_count(item.id_) == 0
    assert dl.inbox_list() == []


@pytest.mark.spec("IE-06-004")
@pytest.mark.usefixtures("outbox_drains")
def test_a_success_clears_a_count_an_earlier_run_stored(
    dl: SqliteDataLayer, monkeypatch: pytest.MonkeyPatch
) -> None:
    _max_attempts(monkeypatch, 3)
    item = _queued_item(dl)
    dl.set_inbox_attempt_count(item.id_, 2)

    _run(dl, _dispatcher(Mock(return_value=HandlerResult.applied())))

    assert dl.get_inbox_attempt_count(item.id_) == 0
    assert dl.inbox_dead_letter_list() == []


@pytest.mark.spec("IE-06-004")
@pytest.mark.usefixtures("outbox_drains")
def test_a_refused_replay_is_final(
    dl: SqliteDataLayer, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A handler's verdict is not a failure of the attempt: no retry."""
    _max_attempts(monkeypatch, 3)
    _queued_item(dl)
    dispatcher = _dispatcher(
        Mock(return_value=HandlerResult.refused("not the case owner"))
    )

    _run(dl, dispatcher)

    dispatcher.dispatch.assert_called_once()
    assert dl.inbox_dead_letter_list() == []
    assert _faults_queued(dl) == []


@pytest.mark.spec("IE-06-004")
@pytest.mark.spec("ASK-07-010")
@pytest.mark.usefixtures("outbox_drains")
def test_a_protocol_violation_is_dropped_and_answered_at_once(
    dl: SqliteDataLayer, monkeypatch: pytest.MonkeyPatch, caplog
) -> None:
    """A permanent failure is not retried, so its sender is answered now."""
    _max_attempts(monkeypatch, 3)
    item = _queued_item(dl)
    dl.set_inbox_attempt_count(item.id_, 1)
    dispatcher = _dispatcher(
        Mock(side_effect=VultronProtocolViolationError("never valid"))
    )

    with caplog.at_level(logging.ERROR, logger=replay.__name__):
        _run(dl, dispatcher)

    dispatcher.dispatch.assert_called_once()
    assert dl.inbox_list() == []
    assert dl.inbox_dead_letter_list() == []
    assert dl.get_inbox_attempt_count(item.id_) == 0
    (fault,) = _faults_queued(dl)
    assert fault["object"]["inReplyTo"] == item.id_
    assert _logged(caplog, item.id_, _RECEIVER, "permanent failure")


@pytest.mark.spec("IE-06-004")
@pytest.mark.usefixtures("outbox_drains")
def test_a_replay_that_does_not_rebuild_is_retried_then_dead_lettered(
    dl: SqliteDataLayer, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A raise while rebuilding the held activity is retried like a raised
    dispatch; with no event to answer, no fault is sent."""
    _max_attempts(monkeypatch, 2)
    item = _queued_item(dl)
    _rebuild_raises(monkeypatch, RuntimeError("rebuild failed"))
    dispatcher = _dispatcher(Mock(return_value=HandlerResult.applied()))

    _run(dl, dispatcher)

    dispatcher.dispatch.assert_not_called()
    (entry,) = dl.inbox_dead_letter_list()
    assert entry.activity_id == item.id_
    assert entry.reason == "rehydration_error"
    assert entry.total_attempts == 2
    assert _faults_queued(dl) == []


@pytest.mark.spec("IE-06-004")
@pytest.mark.usefixtures("outbox_drains")
def test_a_protocol_violation_in_the_rebuild_is_dropped(
    dl: SqliteDataLayer, monkeypatch: pytest.MonkeyPatch
) -> None:
    _max_attempts(monkeypatch, 3)
    _queued_item(dl)
    _rebuild_raises(monkeypatch, VultronProtocolViolationError("never valid"))

    _run(dl, _dispatcher(Mock(return_value=HandlerResult.applied())))

    assert dl.inbox_list() == []
    assert dl.inbox_dead_letter_list() == []
    assert _faults_queued(dl) == []


@pytest.mark.spec("IE-06-004")
@pytest.mark.usefixtures("outbox_drains")
def test_a_replay_rejected_before_dispatch_is_not_lost(
    dl: SqliteDataLayer, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Extraction catches its own raise and rejects the item.  The rebuild
    already released the record, so the rejection is retried and then
    dead-lettered, not dropped."""
    from vultron.core.behaviors.inbox.nodes import pipeline

    _max_attempts(monkeypatch, 2)
    item = _queued_item(dl)

    def _extract_raises(*_args: Any, **_kwargs: Any) -> Any:
        raise RuntimeError("extraction failed")

    monkeypatch.setattr(pipeline, "extract_event", _extract_raises)
    dispatcher = _dispatcher(Mock(return_value=HandlerResult.applied()))

    _run(dl, dispatcher)

    dispatcher.dispatch.assert_not_called()
    (entry,) = dl.inbox_dead_letter_list()
    assert entry.activity_id == item.id_
    assert "extraction failed" in entry.last_error
    assert InlineObjectStaging(dl).held(item.id_) is not None


def test_a_rejection_with_no_reason_is_still_a_failure() -> None:
    """The pipeline records no reason when no node wrote an outcome."""
    attempt = replay.ReplayAttempt()
    attempt.rebuilt = True

    attempt.settle_rejection(InboxOutcome(status=InboxOutcomeStatus.REJECTED))

    assert attempt.failure == ("processing_error", "rejected before dispatch")


@pytest.mark.spec("ASK-07-010")
@pytest.mark.usefixtures("outbox_drains")
def test_a_failure_after_an_applied_dispatch_is_neither_retried_nor_answered(
    dl: SqliteDataLayer, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The post-bootstrap replay raising is no failure of the item's act."""
    from vultron.core.behaviors.inbox.nodes import dispatch as dispatch_node

    _max_attempts(monkeypatch, 3)
    _queued_item(dl)
    monkeypatch.setattr(dispatch_node, "is_case_bootstrap", lambda _e: True)

    def _replay_raises(*_args: Any, **_kwargs: Any) -> None:
        raise RuntimeError("replay storage fault")

    monkeypatch.setattr(io.FastAPIQueuePort, "replay", _replay_raises)
    dispatcher = _dispatcher(Mock(return_value=HandlerResult.applied()))

    _run(dl, dispatcher)

    dispatcher.dispatch.assert_called_once()
    assert dl.inbox_dead_letter_list() == []
    assert _faults_queued(dl) == []


@pytest.mark.spec("ASK-07-010")
@pytest.mark.usefixtures("outbox_drains")
def test_a_dead_lettered_fault_is_not_answered_with_a_fault(
    dl: SqliteDataLayer, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Two peers failing alike must not answer each other's faults."""
    _max_attempts(monkeypatch, 1)
    item = _queue(
        dl,
        create_processing_fault_activity(
            actor=_SENDER,
            fault=as_ProcessingFault(
                failure_class=VULTRON_FAILURE_INTERNAL_PROCESSING_ERROR,
                in_reply_to="https://example.org/activities/earlier",
            ),
            to=[_RECEIVER],
        ),
    )
    dispatcher = _dispatcher(_raises)

    _run(dl, dispatcher)

    dispatcher.dispatch.assert_called_once()
    assert [e.activity_id for e in dl.inbox_dead_letter_list()] == [item.id_]
    assert _faults_queued(dl) == []


@pytest.mark.spec("ASK-07-010")
@pytest.mark.usefixtures("outbox_drains")
def test_a_dead_letter_fault_that_cannot_be_queued_is_logged(
    dl: SqliteDataLayer, monkeypatch: pytest.MonkeyPatch, caplog
) -> None:
    """The item is already dead-lettered; the fault's failure only logs."""
    _max_attempts(monkeypatch, 1)
    item = _queued_item(dl)

    def _outbox_fails(*_args: Any, **_kwargs: Any) -> str:
        raise RuntimeError("outbox write failed")

    monkeypatch.setattr(io, "emit_processing_fault", _outbox_fails)

    with caplog.at_level(logging.ERROR, logger=replay.__name__):
        _run(dl, _dispatcher(_raises))

    assert [e.activity_id for e in dl.inbox_dead_letter_list()] == [item.id_]
    assert any(
        "ProcessingFault not queued" in r.getMessage()
        and r.exc_info is not None
        for r in caplog.records
    )


def test_the_outbox_drains_when_settling_a_replay_raises(
    dl: SqliteDataLayer,
    monkeypatch: pytest.MonkeyPatch,
    outbox_drains: list[str],
) -> None:
    """A store write that raises while settling stops the run, but the
    outbox still drains what the run had already queued."""
    _max_attempts(monkeypatch, 3)
    _queued_item(dl)

    def _write_fails(*_args: Any, **_kwargs: Any) -> None:
        raise RuntimeError("store write failed")

    monkeypatch.setattr(dl, "set_inbox_attempt_count", _write_fails)

    with pytest.raises(RuntimeError, match="store write failed"):
        _run(dl, _dispatcher(_raises))

    assert outbox_drains == [_RECEIVER]


@pytest.mark.spec("DL-06-006", "CBT-03-001")
def test_the_queue_port_queues_nothing_when_the_hold_fails(
    dl: SqliteDataLayer,
) -> None:
    """The record is the activity's only copy, so a hold that raises leaves
    no queued id with nothing behind it."""
    from vultron.core.models.pending_case_inbox import VultronPendingCaseInbox

    case_id = "https://example.org/cases/case-unheld"
    queue = io.FastAPIQueuePort(
        dl=dl,
        actor_dl=dl,
        actor_id=_RECEIVER,
        staging=InlineObjectStaging(dl),
    )

    with pytest.raises(VultronWiringError):
        queue.queue("https://example.org/activities/unstaged", case_id)

    assert dl.read(VultronPendingCaseInbox.build_id(case_id)) is None


def test_a_replay_ingress_with_no_attempt_still_raises(
    dl: SqliteDataLayer, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Without a drain's attempt record the rebuild's raise is only re-raised,
    so ``ParsePayloadNode`` rejects it as before."""
    item = _queued_item(dl)
    _rebuild_raises(monkeypatch, RuntimeError("rebuild failed"))

    with pytest.raises(RuntimeError, match="rebuild failed"):
        replay.StoredActivityIngressAdapter(dl=dl).parse(item.id_)
