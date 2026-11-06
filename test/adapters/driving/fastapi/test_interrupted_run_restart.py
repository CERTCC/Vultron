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


@pytest.mark.spec("CLP-10-074")
def test_the_startup_replay_finishes_what_a_run_left(monkeypatch):
    """The production startup runs the held records before the queue."""
    calls: list[str] = []

    async def _rerun(actor_dl, actor_id, dispatcher, emitter) -> int:
        calls.append(actor_id)
        return 0

    monkeypatch.setattr(inbox_startup_replay, "rerun_left_in_holding", _rerun)
    monkeypatch.setattr(
        inbox_startup_replay.actor_hosts,
        "hosted_actor_ids",
        lambda: [MANAGER],
    )
    net = LedgerNetwork(f"{CASE_ID}-startup")
    monkeypatch.setattr(
        inbox_startup_replay,
        "get_datalayer",
        lambda actor_id: net.stores[MANAGER],
    )

    asyncio.run(inbox_startup_replay.replay_hosted_inbox_queues())

    assert calls == [MANAGER]
