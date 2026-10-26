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

"""A hosted participant states its ledger positions after a restart (SYNC-17-007).

The app lifespan starts the statements once at startup and, when
``ledger.position_statement_interval_seconds`` is set, again on that
interval; the interval is off by default.
"""

import asyncio
from types import SimpleNamespace

import pytest

from test.core.behaviors.sync.nodes._embargo_gate_support import (
    MANAGER_ID,
    SIGNATORY_ID,
    seed_case,
    seed_ledger,
)
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driven.sync_activity_adapter import SyncActivityAdapter
from vultron.adapters.driving.fastapi import ledger_position_statements as lps
from vultron.config.ledger import LedgerConfig
from vultron.core.models._helpers import _as_id
from vultron.wire.as2.vocab.base.objects.activities.transitive import (
    as_Read,
)


@pytest.fixture
def participant_dl() -> SqliteDataLayer:
    """SIGNATORY_ID's replica of a case managed by MANAGER_ID, two entries."""
    store = SqliteDataLayer("sqlite:///:memory:", actor_id=SIGNATORY_ID)
    seed_case(store, embargo_active=False)
    seed_ledger(store, 2)
    return store


@pytest.fixture
def hosted(monkeypatch: pytest.MonkeyPatch, participant_dl) -> list[str]:
    """Host SIGNATORY_ID only, and record each outbox drain requested."""
    from vultron.adapters.driving.fastapi import inbox_orchestration as io

    drains: list[str] = []

    async def _drain(actor_id: str, *_args: object, **_kwargs: object) -> None:
        drains.append(actor_id)

    monkeypatch.setattr(io, "outbox_handler", _drain)
    monkeypatch.setattr(
        lps.actor_hosts, "hosted_actor_ids", lambda: [SIGNATORY_ID]
    )
    monkeypatch.setattr(lps, "get_datalayer", lambda _actor_id: participant_dl)
    return drains


def _queued_reads(store: SqliteDataLayer) -> list[as_Read]:
    reads = [store.read(activity_id) for activity_id in store.outbox_list()]
    return [read for read in reads if isinstance(read, as_Read)]


@pytest.mark.spec("SYNC-17-007")
def test_restart_queues_one_read_naming_the_tail(
    participant_dl, hosted
) -> None:
    """After a restart the participant queues one Read naming its tail."""
    total = asyncio.run(lps.state_hosted_ledger_positions())

    assert total == 1
    reads = _queued_reads(participant_dl)
    assert len(reads) == 1
    read = reads[0]
    tail = max(
        participant_dl.list_objects("CaseLedgerEntry"),
        key=lambda entry: entry.log_index,
    )
    assert _as_id(read.object_) == tail.id_
    assert read.to == [MANAGER_ID]
    assert read.ledger_position is not None
    assert read.ledger_position.entry_hash == tail.entry_hash
    assert hosted == [SIGNATORY_ID]  # its outbox is drained after


@pytest.mark.spec("SYNC-17-007")
def test_one_actor_failing_does_not_stop_the_round(
    monkeypatch: pytest.MonkeyPatch, participant_dl, hosted
) -> None:
    broken = "https://example.org/actors/broken"
    stores = {broken: None, SIGNATORY_ID: participant_dl}
    monkeypatch.setattr(lps.actor_hosts, "hosted_actor_ids", lambda: [*stores])
    monkeypatch.setattr(lps, "get_datalayer", stores.__getitem__)

    assert asyncio.run(lps.state_hosted_ledger_positions()) == 1


@pytest.mark.spec("SYNC-17-007")
def test_each_statement_is_a_new_activity(participant_dl) -> None:
    """A second statement of the same tail is not a redelivery of the first.

    The CASE_MANAGER's ledger may have grown since, so it must answer the
    second one; a reused id would make it a repeat it skips.
    """
    adapter = SyncActivityAdapter(participant_dl)
    tail = max(
        participant_dl.list_objects("CaseLedgerEntry"),
        key=lambda entry: entry.log_index,
    )

    adapter.send_read_ledger_entry(tail, SIGNATORY_ID, [MANAGER_ID])
    adapter.send_read_ledger_entry(tail, SIGNATORY_ID, [MANAGER_ID])

    reads = _queued_reads(participant_dl)
    assert len(reads) == 2
    assert reads[0].id_ != reads[1].id_


@pytest.mark.spec("SYNC-17-007")
@pytest.mark.spec("SYNC-05-003")
def test_the_interval_is_off_by_default() -> None:
    assert LedgerConfig().position_statement_interval_seconds is None


@pytest.mark.spec("SYNC-17-007")
def test_with_no_interval_the_statements_run_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rounds: list[int] = []

    async def _round(emitter: object = None) -> int:
        rounds.append(1)
        return 0

    monkeypatch.setattr(lps, "state_hosted_ledger_positions", _round)

    async def _run() -> None:
        statements = lps.start_ledger_position_statements(None)
        await statements.task
        await lps.finish_ledger_position_statements(statements)

    asyncio.run(_run())

    assert rounds == [1]


@pytest.mark.spec("SYNC-17-007")
def test_a_configured_interval_repeats_until_shutdown(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """With an interval the statements repeat; shutdown ends the wait."""
    rounds: list[int] = []
    second = asyncio.Event()

    async def _round(emitter: object = None) -> int:
        rounds.append(1)
        if len(rounds) == 2:
            second.set()
        return 0

    monkeypatch.setattr(lps, "state_hosted_ledger_positions", _round)

    def _config() -> SimpleNamespace:
        return SimpleNamespace(
            ledger=LedgerConfig(position_statement_interval_seconds=1)
        )

    monkeypatch.setattr(lps, "get_config", _config)

    async def _run() -> None:
        statements = lps.start_ledger_position_statements(None)
        await asyncio.wait_for(second.wait(), timeout=10)
        await asyncio.wait_for(
            lps.finish_ledger_position_statements(statements), timeout=5
        )
        assert statements.task.done()

    asyncio.run(_run())

    assert len(rounds) == 2


def test_finish_without_a_start_is_a_no_op() -> None:
    asyncio.run(lps.finish_ledger_position_statements(None))


@pytest.mark.spec("SYNC-17-007")
def test_the_server_lifespan_starts_and_finishes_the_statements(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The serving app states positions at startup and stops them on exit."""
    from fastapi.testclient import TestClient

    from vultron.adapters.driving.fastapi import app as app_module

    events: list[str] = []
    handle = object()

    def _start(emitter: object, after: object = None) -> object:
        events.append("start")
        assert after is not None  # it waits for the startup replay
        return handle

    async def _finish(statements: object) -> None:
        assert statements is handle
        events.append("finish")

    monkeypatch.setattr(app_module, "start_ledger_position_statements", _start)
    monkeypatch.setattr(
        app_module, "finish_ledger_position_statements", _finish
    )

    with TestClient(app_module.app_v2):
        assert events == ["start"]

    assert events == ["start", "finish"]


@pytest.mark.spec("SYNC-17-007")
def test_the_first_round_waits_for_the_startup_replay(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A participant states its tail only after its queue has been applied."""
    order: list[str] = []

    async def _round(emitter: object = None) -> int:
        order.append("statements")
        return 0

    monkeypatch.setattr(lps, "state_hosted_ledger_positions", _round)

    async def _replay() -> int:
        await asyncio.sleep(0.05)
        order.append("replay")
        return 0

    async def _run() -> None:
        replay = asyncio.create_task(_replay())
        statements = lps.start_ledger_position_statements(None, after=replay)
        await statements.task
        await lps.finish_ledger_position_statements(statements)

    asyncio.run(_run())

    assert order == ["replay", "statements"]


@pytest.mark.spec("SYNC-17-007")
def test_a_shutdown_during_the_startup_replay_states_nothing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A server told to stop while its queue replays sends no statements."""
    order: list[str] = []

    async def _round(emitter: object = None) -> int:
        order.append("statements")
        return 0

    monkeypatch.setattr(lps, "state_hosted_ledger_positions", _round)

    async def _replay() -> int:
        await asyncio.sleep(0.05)
        order.append("replay")
        return 0

    async def _run() -> None:
        replay = asyncio.create_task(_replay())
        statements = lps.start_ledger_position_statements(None, after=replay)
        await lps.finish_ledger_position_statements(statements)

    asyncio.run(_run())

    assert order == ["replay"]


@pytest.mark.spec("SYNC-17-007")
def test_a_round_that_raises_neither_ends_the_loop_nor_the_shutdown(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """A failing round is logged; the next round runs and shutdown returns."""
    rounds: list[int] = []
    second = asyncio.Event()

    async def _round(emitter: object = None) -> int:
        rounds.append(1)
        if len(rounds) == 2:
            second.set()
        raise RuntimeError("cannot list hosted actors")

    def _config() -> SimpleNamespace:
        return SimpleNamespace(
            ledger=LedgerConfig(position_statement_interval_seconds=1)
        )

    monkeypatch.setattr(lps, "state_hosted_ledger_positions", _round)
    monkeypatch.setattr(lps, "get_config", _config)

    async def _run() -> None:
        statements = lps.start_ledger_position_statements(None)
        await asyncio.wait_for(second.wait(), timeout=10)
        await asyncio.wait_for(
            lps.finish_ledger_position_statements(statements), timeout=5
        )

    asyncio.run(_run())

    assert len(rounds) == 2
    assert "round raised" in caplog.text
