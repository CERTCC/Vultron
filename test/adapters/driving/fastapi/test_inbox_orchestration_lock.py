#!/usr/bin/env python
"""Regression test: concurrent inbox BackgroundTasks must serialize per actor.

Two concurrent ``run_inbox_pipeline`` calls for the same actor can interleave
at the asyncio level if the event loop schedules the second task before the
first has finished storing its ledger entry.  When entries arrive in wrong
asyncio-scheduling order, the hash-chain check fails → Reject → Replay loop
that may not converge within the demo timeout (issue #1525).

The fix: ``run_inbox_pipeline`` acquires a per-actor ``asyncio.Lock`` before
calling ``process_payload``.  This test verifies the lock is in place by
forcing a scheduling inversion and confirming both entries are stored.
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

import asyncio
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock

import py_trees
import pytest

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driving.fastapi.inbox_orchestration import (
    _get_actor_lock,
    run_inbox_pipeline,
)
from vultron.core.models.case_ledger import (
    HashChainLedgerRecord,
    compute_genesis_hash,
)
from vultron.core.models.case_ledger_entry import VultronCaseLedgerEntry
from vultron.core.behaviors.sync.nodes.chain import _to_persistable_entry
from vultron.wire.as2.factories import announce_log_entry_activity
from vultron.wire.as2.vocab.objects.case_actor import as_CaseActor
from vultron.wire.as2.vocab.objects.case_participant import as_CaseParticipant
from vultron.wire.as2.vocab.objects.case_ledger_entry import (
    as_CaseLedgerEntry as WireCaseLedgerEntry,
)
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)

_CASE_ACTOR_ID = "https://example.org/actors/case-actor-lock-test"
_PEER_ID = "https://example.org/actors/peer-lock-test"
_CASE_ID = "https://example.org/cases/case-lock-test"


@pytest.fixture(autouse=True)
def clear_blackboard():
    py_trees.blackboard.Blackboard.storage.clear()
    yield
    py_trees.blackboard.Blackboard.storage.clear()


@pytest.fixture(autouse=True)
def clear_actor_locks():
    """Remove any cached per-actor locks between tests."""
    from vultron.adapters.driving.fastapi import inbox_orchestration

    inbox_orchestration._actor_inbox_locks.clear()
    yield
    inbox_orchestration._actor_inbox_locks.clear()


@pytest.fixture
def dl():
    db = SqliteDataLayer("sqlite:///:memory:")
    yield db
    db.close()


@pytest.fixture
def seeded_dl(dl):
    """DataLayer seeded with a case, genesis hash, and two chained entries."""
    created_at = datetime.now(timezone.utc)
    genesis_hash = compute_genesis_hash(
        case_id=_CASE_ID,
        created_at=created_at,
        case_actor_id=_CASE_ACTOR_ID,
    )
    case = as_VulnerabilityCase(id_=_CASE_ID, name="lock-test-case")
    case.genesis_hash = genesis_hash

    case_actor_participant = as_CaseParticipant(
        attributed_to=_CASE_ACTOR_ID, context=_CASE_ID
    )
    peer_participant = as_CaseParticipant(
        attributed_to=_PEER_ID, context=_CASE_ID
    )
    case.case_participants.append(case_actor_participant.id_)
    case.case_participants.append(peer_participant.id_)
    case.actor_participant_index[_CASE_ACTOR_ID] = case_actor_participant.id_
    case.actor_participant_index[_PEER_ID] = peer_participant.id_

    case_actor_svc = as_CaseActor(
        id_=f"{_CASE_ACTOR_ID}/case-actor",
        attributed_to=_CASE_ACTOR_ID,
        context=_CASE_ID,
    )

    dl.save(case_actor_participant)
    dl.save(peer_participant)
    dl.save(case)
    dl.save(case_actor_svc)

    _snapshot = {
        "actor": _CASE_ACTOR_ID,
        "type": "Announce",
        "object": {"type": "VulnerabilityCase"},
        "context": _CASE_ID,
    }
    entry0 = _to_persistable_entry(
        HashChainLedgerRecord(
            case_id=_CASE_ID,
            log_index=0,
            object_id=_CASE_ID,
            event_type="test_event_0",
            payload_snapshot=_snapshot,
            prev_log_hash=genesis_hash,
        )
    )
    entry1 = _to_persistable_entry(
        HashChainLedgerRecord(
            case_id=_CASE_ID,
            log_index=1,
            object_id=_CASE_ID,
            event_type="test_event_1",
            payload_snapshot=_snapshot,
            prev_log_hash=entry0.entry_hash,
        )
    )

    return dl, [entry0, entry1]


def _make_announce_body(entry: VultronCaseLedgerEntry) -> dict[str, Any]:
    wire_entry = WireCaseLedgerEntry.model_validate(
        entry.model_dump(mode="json")
    )
    activity = announce_log_entry_activity(
        entry=wire_entry,
        actor=_CASE_ACTOR_ID,
        to=[_PEER_ID],
    )
    return activity.model_dump(mode="json", by_alias=True, exclude_none=True)


def test_get_actor_lock_returns_same_lock_for_same_actor():
    """_get_actor_lock returns the same asyncio.Lock for the same actor_id."""

    async def _run():
        lock_a = _get_actor_lock("actor-1")
        lock_b = _get_actor_lock("actor-1")
        lock_c = _get_actor_lock("actor-2")
        assert lock_a is lock_b
        assert lock_a is not lock_c
        assert isinstance(lock_a, asyncio.Lock)

    asyncio.run(_run())


def test_get_actor_lock_different_actors_do_not_share_lock():
    """_get_actor_lock returns distinct locks for different actor IDs."""

    async def _run():
        lock_a = _get_actor_lock("actor-alpha")
        lock_b = _get_actor_lock("actor-beta")
        assert lock_a is not lock_b

    asyncio.run(_run())


def test_concurrent_inbox_tasks_serialize_processing(seeded_dl) -> None:
    """Concurrent run_inbox_pipeline calls for the same actor serialize correctly.

    Without the per-actor lock, if the asyncio event loop schedules the
    second task's process_payload before the first task has stored entry0,
    entry1's hash-chain check fails (prev_log_hash != tail_hash).

    With the lock, entry0 is fully stored before entry1 is processed, so
    both entries end up in the peer's DataLayer.

    This test runs both tasks concurrently via asyncio.gather to reproduce
    the race scenario.  The lock guarantees correct ordering.
    """
    dl, entries = seeded_dl
    entry0, entry1 = entries

    actor_dl = dl.clone_for_actor(_PEER_ID)

    body0 = _make_announce_body(entry0)
    body1 = _make_announce_body(entry1)

    null_emitter = AsyncMock()
    null_emitter.emit = AsyncMock()

    from vultron.adapters.driving.fastapi.inbox_handler import make_dispatcher

    dispatcher = make_dispatcher()

    async def _run():
        await asyncio.gather(
            run_inbox_pipeline(
                body0, body0, dl, actor_dl, _PEER_ID, dispatcher, null_emitter
            ),
            run_inbox_pipeline(
                body1, body1, dl, actor_dl, _PEER_ID, dispatcher, null_emitter
            ),
        )

    asyncio.run(_run())

    stored0 = dl.read(entry0.id_)
    stored1 = dl.read(entry1.id_)

    assert (
        stored0 is not None
    ), f"Entry0 (log_index=0) was not stored. hash={entry0.entry_hash[:16]}…"
    assert stored1 is not None, (
        f"Entry1 (log_index=1) was not stored — likely a hash-chain mismatch "
        f"race: entry1 was processed before entry0 was stored (issue #1525). "
        f"hash={entry1.entry_hash[:16]}…"
    )
