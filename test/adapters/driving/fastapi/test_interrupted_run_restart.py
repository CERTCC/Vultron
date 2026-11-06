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

"""A run interrupted mid-tree is picked up and finished on restart (ADR-0154).

A process stop part-way through the handling tree leaves the message's record
in holding with its sealed body: the act rolled back and kept nothing
(ADR-0151), and the outcome stage never ran (CLP-10-074).  At startup no run
is in progress, so the startup replay runs every such record again
(``rerun_left_in_holding``).  The re-run reads the record, so what its first
run already did is not done again, and the record reaches its outcome.

The interrupt is a ``BaseException`` raised from the ledger commit after the
commit has written: the tree's nodes catch ``Exception`` only, so it escapes
the run as a process stop would.
"""

import asyncio
import json
import logging
from types import SimpleNamespace
from typing import Any

import pytest

from test.core.use_cases.received._ledger_network import (
    MANAGER,
    OWNER,
    LedgerNetwork,
)
from test.support.emitter import RecordingEmitter
from test.support.ledger import ledger_entries
from test.support.received import delivered_body
from test.support.rerun_from_holding import effects
from vultron.adapters.driving.fastapi import inbox_startup_replay
from vultron.adapters.driving.fastapi.inbox_handler import make_dispatcher
from vultron.adapters.driving.fastapi.inbox_orchestration import (
    pipeline,
    run_inbox_pipeline,
)
from vultron.core.behaviors.case.nodes.lifecycle import (
    CommitCaseLedgerEntryNode,
)
from vultron.core.models.received_activity_record import (
    ReceivedActivityRecord,
    ReceivedStage,
)
from vultron.core.services.received_holding import records_left_in_holding
from vultron.wire.as2.factories import add_note_to_case_activity
from vultron.wire.as2.vocab.base.objects.object_types import as_Note

pytestmark = pytest.mark.integration

CASE_ID = "https://example.org/cases/interrupted-run"


class _ProcessStop(BaseException):
    """Stands in for a process stop: no node catches it."""


def _add_note_body(net: LedgerNetwork) -> dict[str, Any]:
    activity = add_note_to_case_activity(
        as_Note(
            id_=f"{CASE_ID}/notes/interrupted",
            content="interrupted",
            context=CASE_ID,
        ),
        target=CASE_ID,
        actor=OWNER,
        to=[MANAGER],
    )
    return net.stamp(delivered_body(activity), receiver=MANAGER)


def _kind(row: tuple[str, str]) -> tuple[str, str]:
    """An outbox row's activity type and the type of the object it carries."""
    activity = json.loads(row[1])
    return activity["type_"], activity["object_"]["type_"]


def _record(net: LedgerNetwork, activity_id: str) -> ReceivedActivityRecord:
    record = net.stores[MANAGER].read(
        ReceivedActivityRecord.build_id(activity_id)
    )
    assert isinstance(record, ReceivedActivityRecord)
    return record


def _interrupt_after_the_commit(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Raise a process stop from the next ledger commit, after it writes."""
    real = CommitCaseLedgerEntryNode.update
    stopped: list[str] = []

    def update(self: CommitCaseLedgerEntryNode) -> Any:
        status = real(self)
        if not stopped:
            stopped.append(self.name)
            raise _ProcessStop
        return status

    monkeypatch.setattr(CommitCaseLedgerEntryNode, "update", update)
    return stopped


@pytest.mark.spec("IE-06-014")
@pytest.mark.spec("IE-06-015")
@pytest.mark.spec("CLP-10-074")
@pytest.mark.spec("CLP-07-015")
@pytest.mark.spec("ID-04-004")
def test_an_interrupted_run_is_finished_on_restart_with_nothing_twice(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
):
    net = LedgerNetwork(CASE_ID)
    dl = net.stores[MANAGER]
    emitter = RecordingEmitter()
    dispatcher = make_dispatcher()
    body = _add_note_body(net)
    before = effects(dl)

    with monkeypatch.context() as mp:
        stopped = _interrupt_after_the_commit(mp)
        with pytest.raises(_ProcessStop):
            asyncio.run(
                run_inbox_pipeline(body, dl, MANAGER, dispatcher, emitter)
            )
    assert stopped, "the run was not interrupted mid-tree"

    # The act rolled back, so nothing is committed; the ledger position
    # answer ran ahead of the act and stands (a re-seed of the sender, whose
    # stated position this ledger does not hold).  The record stays in
    # holding with its body.
    interrupted = effects(dl)
    assert interrupted.ledger == before.ledger
    assert [_kind(row) for row in interrupted.outbox] == [
        ("Announce", "VulnerabilityCase")
    ]
    left = _record(net, body["id"])
    assert (left.stage, left.replay_owed) == (ReceivedStage.HELD, False)
    assert [r.activity_id for r in records_left_in_holding(dl)] == [body["id"]]

    with caplog.at_level(logging.INFO):
        rerun = asyncio.run(
            inbox_startup_replay.rerun_left_in_holding(
                dl, MANAGER, dispatcher, emitter
            )
        )

    assert rerun == 1
    # The restart's intake read the record as a re-run (ADR-0154).
    assert any(
        body["id"] in r.getMessage() and "left by a run" in r.getMessage()
        for r in caplog.records
    )
    assert _record(net, body["id"]).stage is ReceivedStage.ARCHIVED
    recorded = [
        e for e in ledger_entries(dl, CASE_ID) if e.log_object_id == body["id"]
    ]
    assert len(recorded) == 1, "the act is committed exactly once"
    assert records_left_in_holding(dl) == []
    assert dl.get_inbox_attempt_count(body["id"]) == 0, (
        "a finished re-run still counts against the retry budget"
    )
    finished = effects(dl)
    # What the interrupted run queued stands, unchanged and not queued again:
    # the restart read the record as a re-run and did not answer the ledger
    # position a second time (SYNC-18-009).  What it added is the act's own
    # fan-out of its one entry.
    assert finished.outbox[: len(interrupted.outbox)] == interrupted.outbox
    added = finished.outbox[len(interrupted.outbox) :]
    assert added, "the restart sent nothing"
    assert {_kind(row) for row in added} == {("Announce", "CaseLedgerEntry")}
    sent = [json.dumps(b, sort_keys=True) for b, _ in emitter.sent]
    assert len(sent) == len(set(sent)), "a message was sent twice"
    assert (
        asyncio.run(
            inbox_startup_replay.rerun_left_in_holding(
                dl, MANAGER, dispatcher, emitter
            )
        )
        == 0
    )
    assert effects(dl) == finished


@pytest.mark.spec("IE-06-014")
@pytest.mark.spec("CLP-10-074")
@pytest.mark.spec("IE-06-006")
def test_the_startup_runs_the_held_records_then_the_queue(monkeypatch):
    """The production startup finishes what a run left, then replays the queue."""
    calls: list[str] = []

    async def _rerun(actor_dl, actor_id, dispatcher, emitter) -> int:
        calls.append("rerun")
        return 0

    async def _replay(actor_dl, actor_id, dispatcher, emitter) -> None:
        calls.append("queue")

    net = LedgerNetwork(f"{CASE_ID}-startup")
    net.stores[MANAGER].inbox_append(f"{CASE_ID}/activities/queued")
    monkeypatch.setattr(inbox_startup_replay, "rerun_left_in_holding", _rerun)
    monkeypatch.setattr(inbox_startup_replay, "replay_inbox_queue", _replay)
    monkeypatch.setattr(
        inbox_startup_replay.actor_hosts,
        "hosted_actor_ids",
        lambda: [MANAGER],
    )
    monkeypatch.setattr(
        inbox_startup_replay,
        "get_datalayer",
        lambda actor_id: net.stores[MANAGER],
    )

    asyncio.run(inbox_startup_replay.replay_hosted_inbox_queues())

    assert calls == ["rerun", "queue"]


@pytest.mark.spec("IE-06-014")
@pytest.mark.spec("CLP-10-074")
def test_one_failing_rerun_does_not_keep_the_others_back(
    monkeypatch, caplog: pytest.LogCaptureFixture
):
    """A re-run that raises is logged; the next record still runs.

    That the queue replay still follows is the startup order test's.
    """
    net = LedgerNetwork(f"{CASE_ID}-failing")
    dl = net.stores[MANAGER]
    first, second = (
        ReceivedActivityRecord(
            activity_id=f"{CASE_ID}/activities/{name}",
            received_body=json.dumps({"id": name, "type": "Add"}),
            stage=ReceivedStage.HELD,
        )
        for name in ("first", "second")
    )
    dl.create(first)
    dl.create(second.model_copy(update={"received_at": first.received_at}))
    ran: list[str] = []

    async def _pipeline(payload, *args, **kwargs) -> None:
        ran.append(payload["id"])
        if payload["id"] == "first":
            raise RuntimeError("store fault")
        _settle(dl, payload["id"])

    monkeypatch.setattr(
        inbox_startup_replay, "run_delivery_without_replay", _pipeline
    )

    with caplog.at_level(logging.ERROR):
        finished = asyncio.run(
            inbox_startup_replay.rerun_left_in_holding(dl, MANAGER, None, None)
        )

    assert sorted(ran) == ["first", "second"]
    assert finished == 1
    assert any(
        first.activity_id in r.getMessage() and r.levelno == logging.ERROR
        for r in caplog.records
    )


def _settle(dl, name: str) -> None:
    """Archive the record of *name*, as a re-run that applied it does."""
    record = _stored(dl, name)
    dl.save(record.model_copy(update={"stage": ReceivedStage.ARCHIVED}))


def _stored(dl, name: str) -> ReceivedActivityRecord:
    record = dl.read(
        ReceivedActivityRecord.build_id(f"{CASE_ID}/activities/{name}")
    )
    assert isinstance(record, ReceivedActivityRecord)
    return record


def _left(dl, name: str, **fields: Any) -> ReceivedActivityRecord:
    """Store a record in holding under *name*, with *fields* set on it."""
    record = ReceivedActivityRecord(
        activity_id=f"{CASE_ID}/activities/{name}",
        received_body=json.dumps({"id": name, "type": "Add"}),
        **fields,
    )
    dl.create(record)
    return record


@pytest.mark.spec("IE-06-014")
@pytest.mark.spec("CLP-10-074")
def test_the_startup_reruns_only_records_owing_no_replay(monkeypatch):
    """A record waiting for its case, or for any replay, is not run again."""
    net = LedgerNetwork(f"{CASE_ID}-scope")
    dl = net.stores[MANAGER]
    _left(dl, "held", stage=ReceivedStage.HELD)
    _left(dl, "handled", stage=ReceivedStage.HANDLED)
    _left(dl, "waiting", stage=ReceivedStage.HELD, replay_owed=True)
    _left(
        dl,
        "awaiting-case",
        stage=ReceivedStage.HELD,
        replay_owed=True,
        awaiting_case_id=f"{CASE_ID}/not-yet-here",
    )
    _left(dl, "archived", stage=ReceivedStage.ARCHIVED)
    ran: list[str] = []

    async def _pipeline(payload, *args, **kwargs) -> None:
        ran.append(payload["id"])

    monkeypatch.setattr(
        inbox_startup_replay, "run_delivery_without_replay", _pipeline
    )

    asyncio.run(
        inbox_startup_replay.rerun_left_in_holding(dl, MANAGER, None, None)
    )

    assert sorted(ran) == ["handled", "held"]


@pytest.mark.spec("IE-06-015")
@pytest.mark.spec("IE-06-004")
def test_a_message_that_stops_the_process_is_dead_lettered_not_rerun_forever(
    monkeypatch, caplog: pytest.LogCaptureFixture
):
    """A re-run that stops the process each start uses up its budget."""
    net = LedgerNetwork(f"{CASE_ID}-poison")
    dl = net.stores[MANAGER]
    poison = _left(dl, "poison", stage=ReceivedStage.HANDLED)
    ran: list[str] = []

    async def _pipeline(payload, *args, **kwargs) -> None:
        ran.append(payload["id"])
        raise _ProcessStop

    monkeypatch.setattr(
        inbox_startup_replay, "run_delivery_without_replay", _pipeline
    )
    monkeypatch.setattr(
        inbox_startup_replay,
        "get_config",
        lambda: SimpleNamespace(max_inbox_retry_attempts=2),
    )

    def _start() -> int:
        return asyncio.run(
            inbox_startup_replay.rerun_left_in_holding(dl, MANAGER, None, None)
        )

    for _ in range(2):
        with pytest.raises(_ProcessStop):
            _start()
    assert dl.get_inbox_attempt_count(poison.activity_id) == 2
    with caplog.at_level(logging.ERROR):
        assert _start() == 0
        assert _start() == 0

    assert ran == ["poison", "poison"], "the budget did not stop the re-runs"
    dead = [
        entry
        for entry in dl.inbox_dead_letter_list()
        if entry.activity_id == poison.activity_id
    ]
    assert [(e.reason, e.total_attempts) for e in dead] == [
        (inbox_startup_replay.RERUN_BUDGET_SPENT, 2)
    ], "the spent record is dead-lettered exactly once"
    assert any(
        poison.activity_id in r.getMessage() and r.levelno == logging.ERROR
        for r in caplog.records
    )
    # Left in holding, so a resend is still answered by its door.
    assert [r.activity_id for r in records_left_in_holding(dl)] == [
        poison.activity_id
    ]


@pytest.mark.spec("IE-06-015")
@pytest.mark.spec("CLP-10-074")
def test_a_rerun_that_ends_still_in_holding_keeps_its_count(
    monkeypatch, caplog: pytest.LogCaptureFixture
):
    """A handler failure the pipeline settles without raising is no finish.

    The record is still left in holding, so the count stands and the next
    start runs it again until the budget is spent.
    """
    net = LedgerNetwork(f"{CASE_ID}-unfinished")
    dl = net.stores[MANAGER]
    stuck = _left(dl, "stuck", stage=ReceivedStage.HANDLED)

    async def _pipeline(payload, *args, **kwargs) -> None:
        return None

    monkeypatch.setattr(
        inbox_startup_replay, "run_delivery_without_replay", _pipeline
    )

    with caplog.at_level(logging.ERROR):
        finished = asyncio.run(
            inbox_startup_replay.rerun_left_in_holding(dl, MANAGER, None, None)
        )

    assert finished == 0
    assert dl.get_inbox_attempt_count(stuck.activity_id) == 1
    assert any(
        stuck.activity_id in r.getMessage() and r.levelno == logging.ERROR
        for r in caplog.records
    )


@pytest.mark.spec("IE-06-014")
def test_every_held_record_runs_before_any_queued_item(monkeypatch):
    """A startup re-run replays no queue, so the queue waits for them all."""
    calls: list[str] = []

    def _process(run, payload) -> None:
        calls.append(f"process {payload['id']}")

    def _drain(self) -> None:
        calls.append("queue")

    monkeypatch.setattr(pipeline, "_process_one", _process)
    monkeypatch.setattr(pipeline._InboxRun, "drain_queue", _drain)
    net = LedgerNetwork(f"{CASE_ID}-order")
    dl = net.stores[MANAGER]
    first = _left(dl, "first", stage=ReceivedStage.HELD)
    _left(
        dl,
        "second",
        stage=ReceivedStage.HANDLED,
        received_at=first.received_at,
    )

    asyncio.run(
        inbox_startup_replay.rerun_left_in_holding(dl, MANAGER, None, None)
    )
    assert calls == ["process first", "process second"]

    # The control: a delivery replays the queue after itself.
    asyncio.run(
        run_inbox_pipeline({"id": "delivered"}, dl, MANAGER, None, None)
    )
    assert calls[2:] == ["process delivered", "queue"]
