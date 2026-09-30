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

"""Per-recipient ordered delivery from one actor's outbox (ADR-0112).

The CASE_MANAGER fans a ledger entry out as one outbox row per recipient, and
its outbox is drained by every inbound activity's background task *and* by the
``OutboxMonitor``.  Before ADR-0112 those drains ran concurrently on one FIFO,
each popping the next row and awaiting its POST, so the order in which rows
*completed* delivery bore no relation to the order in which they were
enqueued: a replica saw entry 4 before entry 1, buffered a forward gap, sent a
``Reject``, and the CASE_MANAGER replayed the whole suffix — into the same
queue, ahead of the next entry's fan-out to every other peer (#3602, #3033,
#2898).

These tests pin the delivery contract that closes that loop:

- OX-01-004: one drain per actor outbox at a time.
- OX-01-005: per-recipient enqueue order is preserved at delivery.
- OX-01-006: at most one in-flight delivery per (actor, recipient); distinct
  recipients proceed concurrently.
- OX-13-012: a failed row is re-queued ahead of every later row sharing a
  recipient with it (#3878).

Module under test: ``vultron/adapters/driving/fastapi/outbox_handler.py``
"""

import asyncio
import json
import time
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from vultron.adapters.driving.fastapi import outbox_handler as oh
from vultron.adapters.outbox_sealed_body import (
    SealedOutboundBody,
    sealed_body_id,
)

ACTOR = "https://example.org/actors/case-manager"
PEER_A = "https://example.org/actors/a"
PEER_B = "https://example.org/actors/b"


def _sealed_for(activity_id: str, row: SimpleNamespace) -> SealedOutboundBody:
    """The sealed body ``lane_keys`` reads a row's recipients from."""
    return SealedOutboundBody(
        id_=sealed_body_id(activity_id),
        activity_id=activity_id,
        body=json.dumps(
            {"id": activity_id, "type": row.type_, "to": list(row.to)}
        ),
    )


def _mock_dl(
    queue: list[str], activities: dict[str, SimpleNamespace]
) -> MagicMock:
    """A DataLayer double whose ``read`` resolves queued rows' sealed bodies.

    Any other id (the actor's own id) resolves to a bare actor stub so
    ``outbox_handler``'s actor lookup succeeds.
    """
    actor = SimpleNamespace(id_=ACTOR)
    sealed = {
        sealed_body_id(aid): _sealed_for(aid, row)
        for aid, row in activities.items()
    }
    dl = MagicMock()
    dl.read.side_effect = lambda id_: sealed.get(id_, actor)
    dl.find_actor_by_short_id.return_value = actor
    dl.outbox_list.side_effect = lambda: list(queue)
    dl.outbox_pop.side_effect = lambda: queue.pop(0) if queue else None
    dl.outbox_append.side_effect = lambda x: queue.append(x)
    dl.get_outbox_attempt_count.return_value = 0
    return dl


def _row(recipient: str | list[str]) -> SimpleNamespace:
    to = recipient if isinstance(recipient, list) else [recipient]
    return SimpleNamespace(type_="Announce", to=list(to))


class _Recorder:
    """Stand-in for ``handle_outbox_item`` with per-row latency and failures.

    Records ``(activity_id, recipient)`` in the order deliveries *complete*
    (what the recipient observes), plus how many rows were in flight at once
    per recipient.
    """

    def __init__(
        self,
        activities: dict[str, SimpleNamespace],
        *,
        latency: dict[str, float] | None = None,
        failing: set[str] | None = None,
    ) -> None:
        self._activities = activities
        self._latency = latency or {}
        self._failing = failing or set()
        self.completed: list[tuple[str, str]] = []
        self.attempted: list[str] = []
        self.completed_at: dict[str, float] = {}
        self._inflight: dict[str, int] = {}
        self.max_inflight: dict[str, int] = {}

    async def __call__(self, actor_id, activity_id, dl, emitter) -> None:
        self.attempted.append(activity_id)
        recipients = list(self._activities[activity_id].to)
        for r in recipients:
            self._inflight[r] = self._inflight.get(r, 0) + 1
            self.max_inflight[r] = max(
                self.max_inflight.get(r, 0), self._inflight[r]
            )
        try:
            await asyncio.sleep(self._latency.get(activity_id, 0.0))
            if activity_id in self._failing:
                raise RuntimeError(f"{activity_id} undeliverable")
        finally:
            for r in recipients:
                self._inflight[r] -= 1
        self.completed_at[activity_id] = time.monotonic()
        for r in recipients:
            self.completed.append((activity_id, r))

    def order_for(self, recipient: str) -> list[str]:
        return [a for a, r in self.completed if r == recipient]


async def _no_sleep(_seconds: float) -> None:
    return None


@pytest.mark.spec("OX-01-004")
@pytest.mark.spec("OX-01-005")
def test_concurrent_drains_deliver_each_recipient_in_enqueue_order(
    monkeypatch,
):
    """Two drains of one outbox must not let a later row overtake an earlier one.

    Reproduces the CI mechanism: drain 1 pops row ``a1`` (slow POST), drain 2
    pops ``a2`` to the same recipient and completes first.  With one drain
    per actor (OX-01-004) and one in-flight row per recipient (OX-01-006) the
    recipient sees ``a1`` then ``a2``.
    """
    activities = {
        "urn:test:a1": _row(PEER_A),
        "urn:test:a2": _row(PEER_A),
        "urn:test:a3": _row(PEER_A),
    }
    queue = list(activities)
    dl = _mock_dl(queue, activities)
    rec = _Recorder(activities, latency={"urn:test:a1": 0.05})
    monkeypatch.setattr(oh, "handle_outbox_item", rec)

    async def two_drains() -> None:
        await asyncio.gather(
            oh.outbox_handler(ACTOR, dl), oh.outbox_handler(ACTOR, dl)
        )

    asyncio.run(two_drains())

    assert rec.order_for(PEER_A) == list(activities)
    assert rec.max_inflight[PEER_A] == 1
    assert queue == []


@pytest.mark.spec("OX-01-006")
def test_slow_recipient_does_not_delay_another_recipient(monkeypatch):
    """A slow POST to recipient A must not hold back the row queued behind it for B.

    Sequenced with events rather than wall-clock: A's delivery does not
    complete until B's has, so a serial drain (B behind A) would never finish
    and the ``wait_for`` would fail — no timing luck either way.
    """
    activities = {
        "urn:test:a1": _row(PEER_A),
        "urn:test:b1": _row(PEER_B),
    }
    queue = list(activities)
    dl = _mock_dl(queue, activities)
    b1_done = asyncio.Event()
    order: list[str] = []

    async def gated(actor_id, activity_id, dl_, emitter):
        if activity_id == "urn:test:a1":
            await asyncio.wait_for(b1_done.wait(), timeout=2.0)
        order.append(activity_id)
        if activity_id == "urn:test:b1":
            b1_done.set()

    monkeypatch.setattr(oh, "handle_outbox_item", gated)

    asyncio.run(asyncio.wait_for(oh.outbox_handler(ACTOR, dl), timeout=5.0))

    assert order == ["urn:test:b1", "urn:test:a1"]
    assert queue == []


@pytest.mark.spec("OX-01-005")
@pytest.mark.spec("OX-01-006")
def test_multi_recipient_row_joins_every_lane_it_addresses(monkeypatch):
    """A row addressed to A and B waits for A's earlier row and holds B's later row."""
    activities = {
        "urn:test:a1": _row(PEER_A),
        "urn:test:ab": _row([PEER_A, PEER_B]),
        "urn:test:b1": _row(PEER_B),
    }
    queue = list(activities)
    dl = _mock_dl(queue, activities)
    rec = _Recorder(activities, latency={"urn:test:a1": 0.05})
    monkeypatch.setattr(oh, "handle_outbox_item", rec)

    asyncio.run(oh.outbox_handler(ACTOR, dl))

    assert rec.order_for(PEER_A) == ["urn:test:a1", "urn:test:ab"]
    assert rec.order_for(PEER_B) == ["urn:test:ab", "urn:test:b1"]
    assert rec.max_inflight[PEER_A] == 1
    assert rec.max_inflight[PEER_B] == 1


@pytest.mark.spec("OX-13-012")
def test_failed_row_is_requeued_ahead_of_later_rows_to_same_recipient(
    monkeypatch,
):
    """#3878: a failing row keeps its place in its recipient's order.

    ``a1`` (to A) fails past the per-pass cap; ``a2`` (to A) is queued behind
    it and ``b1`` (to B) behind that.  ``b1`` is delivered — B is a different
    lane — but ``a2`` is not attempted this pass, and the queue afterwards
    reads ``[a1, a2]`` so the next pass retries them in enqueue order.  Before
    ADR-0112 the failure re-queued ``a1`` at the *tail*, so ``a2`` overtook it.
    """
    activities = {
        "urn:test:a1": _row(PEER_A),
        "urn:test:a2": _row(PEER_A),
        "urn:test:b1": _row(PEER_B),
    }
    queue = list(activities)
    dl = _mock_dl(queue, activities)
    rec = _Recorder(activities, failing={"urn:test:a1"})
    monkeypatch.setattr(oh, "handle_outbox_item", rec)
    monkeypatch.setattr(oh.asyncio, "sleep", _no_sleep)

    asyncio.run(oh.outbox_handler(ACTOR, dl))

    assert rec.order_for(PEER_B) == ["urn:test:b1"]
    assert "urn:test:a2" not in rec.attempted
    assert queue == ["urn:test:a1", "urn:test:a2"]


@pytest.mark.spec("OX-13-012")
def test_row_arriving_during_a_stalled_pass_queues_behind_the_stalled_rows(
    monkeypatch,
):
    """A row enqueued while its recipient's lane is stalled lands behind the stall.

    The re-queue of a stalled lane must not let a row that arrived *during*
    the pass overtake the rows that were already waiting: the queue left for
    the next pass is the lane's enqueue order.
    """
    activities = {
        "urn:test:a1": _row(PEER_A),
        "urn:test:a2": _row(PEER_A),
        "urn:test:a3": _row(PEER_A),
    }
    queue = ["urn:test:a1", "urn:test:a2"]
    dl = _mock_dl(queue, activities)
    rec = _Recorder(activities, failing={"urn:test:a1"})
    monkeypatch.setattr(oh, "handle_outbox_item", rec)

    # The first backoff sleep is the moment a producer appends a3.
    appended = False

    async def append_once(_seconds: float) -> None:
        nonlocal appended
        if not appended:
            appended = True
            queue.append("urn:test:a3")

    monkeypatch.setattr(oh.asyncio, "sleep", append_once)

    asyncio.run(oh.outbox_handler(ACTOR, dl))

    assert queue == ["urn:test:a1", "urn:test:a2", "urn:test:a3"]
    assert rec.attempted.count("urn:test:a2") == 0
    assert rec.attempted.count("urn:test:a3") == 0


@pytest.mark.spec("OX-13-009")
def test_dead_lettered_row_releases_its_lane(monkeypatch):
    """Exhausting the total budget removes the row, so later rows to A proceed."""
    activities = {
        "urn:test:a1": _row(PEER_A),
        "urn:test:a2": _row(PEER_A),
    }
    queue = list(activities)
    dl = _mock_dl(queue, activities)
    dl.get_outbox_attempt_count.return_value = oh.MAX_TOTAL_ATTEMPTS - 1
    rec = _Recorder(activities, failing={"urn:test:a1"})
    monkeypatch.setattr(oh, "handle_outbox_item", rec)
    monkeypatch.setattr(oh.asyncio, "sleep", _no_sleep)

    asyncio.run(oh.outbox_handler(ACTOR, dl))

    dl.dead_letter_append.assert_called_once()
    assert rec.order_for(PEER_A) == ["urn:test:a2"]
    assert queue == []


@pytest.mark.spec("OX-01-004")
def test_second_drain_does_not_pop_while_the_first_holds_the_outbox(
    monkeypatch,
):
    """While one drain holds the actor's outbox, another drain does not pop from it."""
    activities = {
        "urn:test:a1": _row(PEER_A),
        "urn:test:b1": _row(PEER_B),
    }
    queue = list(activities)
    dl = _mock_dl(queue, activities)
    pops_during_first: list[int] = []
    rec = _Recorder(activities, latency={"urn:test:a1": 0.05})
    monkeypatch.setattr(oh, "handle_outbox_item", rec)

    async def first_then_second() -> None:
        first = asyncio.ensure_future(oh.outbox_handler(ACTOR, dl))
        await asyncio.sleep(0.01)  # first drain is mid-delivery
        pops_before = dl.outbox_pop.call_count
        second = asyncio.ensure_future(oh.outbox_handler(ACTOR, dl))
        await asyncio.sleep(0.01)
        pops_during_first.append(dl.outbox_pop.call_count - pops_before)
        await asyncio.gather(first, second)

    asyncio.run(first_then_second())

    assert pops_during_first == [0]
    assert queue == []


@pytest.mark.spec("OX-01-004")
def test_nested_drain_request_returns_and_the_holder_looks_again(monkeypatch):
    """A drain re-entered for the same actor must neither deadlock nor lose rows.

    Under Starlette's ``TestClient`` a recipient's BackgroundTask runs inside
    the sender's POST, so a round-trip delivery calls ``outbox_handler`` for
    the sending actor *from within* its own drain.  Here the delivery of
    ``a1`` appends ``a2`` and re-enters the drain, exactly as a Reject
    arriving mid-fan-out would.  The nested call returns at once, and the
    outer drain delivers ``a2`` before it finishes — including when ``a2`` was
    appended after the outer drain's last look at the queue.
    """
    activities = {
        "urn:test:a1": _row(PEER_A),
        "urn:test:a2": _row(PEER_A),
    }
    queue = ["urn:test:a1"]
    dl = _mock_dl(queue, activities)
    rec = _Recorder(activities)
    delivered_a1 = asyncio.Event()

    async def reentrant(actor_id, activity_id, dl_, emitter):
        await rec(actor_id, activity_id, dl_, emitter)
        if activity_id == "urn:test:a1":
            delivered_a1.set()
            # Let the outer drain reach its "queue is empty" look first, so
            # the append below lands in the window the rerun flag closes.
            await asyncio.sleep(0)
            queue.append("urn:test:a2")
            await asyncio.wait_for(oh.outbox_handler(ACTOR, dl), timeout=1.0)

    monkeypatch.setattr(oh, "handle_outbox_item", reentrant)

    asyncio.run(asyncio.wait_for(oh.outbox_handler(ACTOR, dl), timeout=5.0))

    assert rec.order_for(PEER_A) == ["urn:test:a1", "urn:test:a2"]
    assert queue == []


@pytest.mark.spec("OX-01-004")
def test_short_and_canonical_actor_ids_share_one_drain_slot(monkeypatch):
    """The slot is the store's, not the spelling's.

    A trigger route forwards the URL segment (a short id) while the inbox
    path passes the canonical URI; both resolve to the same actor and must
    not drain the same outbox concurrently.
    """
    activities = {
        "urn:test:a1": _row(PEER_A),
        "urn:test:a2": _row(PEER_A),
    }
    queue = list(activities)
    dl = _mock_dl(queue, activities)
    rec = _Recorder(activities, latency={"urn:test:a1": 0.05})
    monkeypatch.setattr(oh, "handle_outbox_item", rec)

    async def two_spellings() -> None:
        await asyncio.gather(
            oh.outbox_handler("case-manager", dl), oh.outbox_handler(ACTOR, dl)
        )

    asyncio.run(two_spellings())

    assert rec.order_for(PEER_A) == list(activities)
    assert rec.max_inflight[PEER_A] == 1


@pytest.mark.spec("OX-01-003")
def test_escaping_delivery_error_requeues_every_undelivered_row(monkeypatch):
    """An error the retry ladder cannot bookkeep interrupts the batch, loses nothing.

    ``_deliver_row`` never raises on a delivery failure, so the interruption
    here is forced one level up: the row task itself blows up while another
    lane's row is in flight and a third row waits behind it.  Every row that
    was not delivered comes back to the queue, in pop order, and the slot is
    free again.
    """
    activities = {
        "urn:test:a1": _row(PEER_A),
        "urn:test:b1": _row(PEER_B),
        "urn:test:a2": _row(PEER_A),
    }
    queue = list(activities)
    dl = _mock_dl(queue, activities)
    started_a1 = asyncio.Event()

    async def exploding_row(actor_id, activity_id, dl_, emitter, retry, errs):
        if activity_id == "urn:test:a1":
            started_a1.set()
            await asyncio.sleep(10)  # in flight until cancelled
        if activity_id == "urn:test:b1":
            await started_a1.wait()
            raise RuntimeError("bookkeeping blew up")
        return oh.RowOutcome.DELIVERED

    monkeypatch.setattr(oh, "_deliver_row", exploding_row)

    with pytest.raises(oh.BatchInterrupted):
        asyncio.run(oh.outbox_handler(ACTOR, dl))

    assert queue == ["urn:test:a1", "urn:test:b1", "urn:test:a2"]
    assert oh._drain_slot(ACTOR).busy is False


@pytest.mark.spec("OX-01-003")
def test_cancelling_the_drain_requeues_in_flight_and_waiting_rows(monkeypatch):
    """``OutboxMonitor.stop()`` cancels a drain mid-batch; the rows go back."""
    activities = {
        "urn:test:a1": _row(PEER_A),
        "urn:test:a2": _row(PEER_A),
    }
    queue = list(activities)
    dl = _mock_dl(queue, activities)
    started = asyncio.Event()

    async def slow(actor_id, activity_id, dl_, emitter):
        started.set()
        await asyncio.sleep(10)

    monkeypatch.setattr(oh, "handle_outbox_item", slow)

    async def cancel_mid_flight() -> None:
        task = asyncio.ensure_future(oh.outbox_handler(ACTOR, dl))
        await started.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(cancel_mid_flight())

    assert queue == ["urn:test:a1", "urn:test:a2"]
    assert oh._drain_slot(ACTOR).busy is False
