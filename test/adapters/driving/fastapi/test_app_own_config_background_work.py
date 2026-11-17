"""Work an app runs outside a request reads its own app's config (ADR-0206).

Two nodes run in one process, each built by ``create_isolated_actor_app``
with its own ``AppConfig``, each hosting one actor.  For every path that runs
outside a request (``BackgroundTasks``, the outbox monitor, the
sender-sequence hold timer, the ledger position statements and the startup
inbox replay) each node's work reads only its own node's config, and works
only on its own node's stores.  A path that loses its app's scope raises
``VultronWiringError``; it never reads the process-wide config instead.

Each path's own work is replaced by a recorder at the point where the real
work reads its config, so the record shows the config that read would get,
in the task, thread or worker the real path runs it in.
"""

#  Copyright (c) 2026 Carnegie Mellon University and Contributors.
#  - see Contributors.md for a full list of Contributors
#  - see ContributionInstructions.md for information on how you can Contribute
#    to this project
#  Vultron Multiparty Coordinated Vulnerability Disclosure Protocol Prototype
#  is licensed under a MIT (SEI)-style license, please see LICENSE.md
#  distributed with this Software or contact permission@sei.cmu.edu for full
#  terms.
#  Created, in part, with funding and support from the United States Government
#  (see Acknowledgments file). This program may include and/or can make use of
#  certain third party source code, object code, documentation and other files
#  ("Third Party Software"). See LICENSE.md for more details.
#  Carnegie Mellon®, CERT® and CERT Coordination Center® are registered in the
#  U.S. Patent and Trademark Office by Carnegie Mellon University

import asyncio
import contextvars
import threading
import time
from collections.abc import Callable, Iterator
from datetime import timedelta
from typing import Any

import pytest
from fastapi import BackgroundTasks, FastAPI
from fastapi.testclient import TestClient

from test.support.app_configs import held_app_configs, own_app_config
from vultron.adapters.driving.fastapi import (
    inbox_startup_replay,
    ledger_position_statements,
    outbox_monitor,
    sender_sequence_holds,
)
from vultron.adapters.driving.fastapi.app import create_app
from vultron.config import AppConfig, get_config
from vultron.demo.in_process import (
    InProcessRouter,
    IsolatedActorApp,
    create_isolated_actor_app,
)
from vultron.errors import VultronWiringError

_WAIT_SECONDS = 10.0

#: Each node's config differs in every value a path reads.
_NODE_VALUES: dict[str, dict[str, Any]] = {
    "http://vendor-node.test": {
        "retries": 3,
        "hold_seconds": 0.2,
        "interval": 3600,
    },
    "http://reporter-node.test": {
        "retries": 8,
        "hold_seconds": 0.4,
        "interval": 7200,
    },
}


def _node_config(values: dict[str, Any]) -> AppConfig:
    ledger = AppConfig().ledger.model_copy(
        update={
            "sender_sequence_hold_seconds": values["hold_seconds"],
            "position_statement_interval_seconds": values["interval"],
        }
    )
    return own_app_config(
        max_inbox_retry_attempts=values["retries"], ledger=ledger
    )


def _wait_for(condition: Callable[[], bool], what: str) -> None:
    deadline = time.monotonic() + _WAIT_SECONDS
    while not condition():
        if time.monotonic() > deadline:
            pytest.fail(f"timed out waiting for {what}")
        time.sleep(0.02)


@pytest.fixture
def nodes() -> Iterator[list[IsolatedActorApp]]:
    """Two nodes in one process, each hosting one actor, not yet started."""
    router = InProcessRouter()
    built = [
        create_isolated_actor_app(base, router, config=_node_config(values))
        for base, values in _NODE_VALUES.items()
    ]
    for node in built:
        # Opening the store makes the node host its actor (DL-07-011).
        node.dl.outbox_append(f"{node.actor_id}/activities/queued")
    yield built
    for node in built:
        node.close()


def _expected(nodes: list[IsolatedActorApp], key: str) -> set[tuple]:
    return {
        (node.actor_id, _NODE_VALUES[node.base_url][key]) for node in nodes
    }


def _run_until_recorded(
    nodes: list[IsolatedActorApp], records: set[tuple], want: set[tuple]
) -> None:
    a, b = nodes
    with a.client, b.client:
        _wait_for(lambda: want <= records, "each node's record")


# ---------------------------------------------------------------------------
# AC-2: each path reads its own app's config
# ---------------------------------------------------------------------------


def _with_background_probe(app: FastAPI, reads: list[tuple]) -> FastAPI:
    """Add a route whose background tasks, async and sync, read the config."""

    async def _async_task(tag: str) -> None:
        reads.append((tag, "async", get_config().max_inbox_retry_attempts))

    def _sync_task(tag: str) -> None:
        # A sync background task runs in a worker thread.
        reads.append((tag, "sync", get_config().max_inbox_retry_attempts))

    @app.post("/probe/background/{tag}")
    async def _probe(tag: str, background_tasks: BackgroundTasks) -> None:
        background_tasks.add_task(_async_task, tag)
        background_tasks.add_task(_sync_task, tag)

    return app


def test_background_tasks_read_their_own_apps_config() -> None:
    reads: list[tuple] = []
    a = _with_background_probe(
        create_app(config=own_app_config(max_inbox_retry_attempts=3)), reads
    )
    b = _with_background_probe(
        create_app(config=own_app_config(max_inbox_retry_attempts=8)), reads
    )

    with TestClient(a) as client_a, TestClient(b) as client_b:
        client_a.post("/probe/background/a")
        client_b.post("/probe/background/b")
        client_a.post("/probe/background/a")

    assert sorted(set(reads)) == [
        ("a", "async", 3),
        ("a", "sync", 3),
        ("b", "async", 8),
        ("b", "sync", 8),
    ]


def test_outbox_monitor_drains_its_own_nodes_stores_in_its_own_scope(
    nodes: list[IsolatedActorApp], monkeypatch
) -> None:
    """Each node's monitor drains only its own outboxes, with its config."""
    records: set[tuple] = set()

    async def _record_drain(actor_id: str, dl: Any, emitter: Any = None):
        records.add((actor_id, get_config().max_inbox_retry_attempts))

    monkeypatch.setattr(outbox_monitor, "outbox_handler", _record_drain)

    want = _expected(nodes, "retries")
    _run_until_recorded(nodes, records, want)

    # A monitor that drained the other node's store would add a mismatch.
    assert records == want


def test_hold_timer_reads_its_own_apps_hold_in_its_worker_thread(
    nodes: list[IsolatedActorApp], monkeypatch
) -> None:
    """The timer's interval and each round's hold are its own app's."""
    records: set[tuple] = set()

    def _record_round(persistence: Any, at: Any, hold: timedelta) -> int:
        records.add((persistence.actor_id, hold.total_seconds()))
        return 0

    monkeypatch.setattr(
        sender_sequence_holds,
        "end_expired_sender_sequence_holds",
        _record_round,
    )

    want = _expected(nodes, "hold_seconds")
    _run_until_recorded(nodes, records, want)

    assert records == want


def test_position_statements_read_their_own_apps_interval(
    nodes: list[IsolatedActorApp], monkeypatch
) -> None:
    records: set[tuple] = set()

    def _record_statements(dl: Any, actor_id: str, *_ports: Any) -> int:
        records.add(
            (actor_id, get_config().ledger.position_statement_interval_seconds)
        )
        return 0

    monkeypatch.setattr(
        ledger_position_statements,
        "state_ledger_positions_trigger",
        _record_statements,
    )

    want = _expected(nodes, "interval")
    _run_until_recorded(nodes, records, want)

    assert records == want


def test_startup_replay_reads_its_own_apps_retry_budget(
    nodes: list[IsolatedActorApp], monkeypatch
) -> None:
    """The re-run budget read before the records are listed is the app's."""
    records: set[tuple] = set()

    def _record_listing(persistence: Any) -> list:
        records.add(
            (persistence.actor_id, get_config().max_inbox_retry_attempts)
        )
        return []

    monkeypatch.setattr(
        inbox_startup_replay, "records_left_in_holding", _record_listing
    )

    want = _expected(nodes, "retries")
    _run_until_recorded(nodes, records, want)

    assert records == want


def test_an_app_with_no_config_starts_no_background_work() -> None:
    """A ``create_app`` app with no config runs none of a node's work."""
    app = create_app()
    with TestClient(app):
        assert getattr(app.state, "outbox_monitor", None) is None
        assert app.state.sender_sequence_hold_timer is None
        assert app.state.ledger_position_statements is None
        assert app.state.startup_inbox_replay is None


# ---------------------------------------------------------------------------
# AC-3: a path that loses its app's scope raises, never falls back
# ---------------------------------------------------------------------------


def _lost_scope_read() -> None:
    """A config read in a context that did not carry the app's scope."""
    contextvars.Context().run(get_config)


def test_a_background_task_that_lost_its_scope_raises() -> None:
    app = create_app(config=own_app_config(max_inbox_retry_attempts=3))

    @app.post("/probe/lost")
    async def _probe(background_tasks: BackgroundTasks) -> None:
        background_tasks.add_task(_lost_scope_read)

    with TestClient(app) as client:
        with pytest.raises(VultronWiringError, match="ADR-0206"):
            client.post("/probe/lost")


def _task_of(path: str, app: FastAPI) -> asyncio.Task | None:
    """The task the lifespan started for *path*, or ``None`` before it."""
    state = app.state
    task: asyncio.Task | None
    if path == "outbox monitor":
        monitor = getattr(state, "outbox_monitor", None)
        task = monitor._task if monitor is not None else None
    elif path == "hold timer":
        task = state.sender_sequence_hold_timer.task
    elif path == "position statements":
        task = state.ledger_position_statements.task
    else:
        task = state.startup_inbox_replay
    return task


#: Where each path's work reads its config, and the recorder signature.
_LOST_SCOPE_POINTS: dict[str, tuple[object, str]] = {
    "outbox monitor": (outbox_monitor, "outbox_handler"),
    "hold timer": (sender_sequence_holds, "end_expired_sender_sequence_holds"),
    "position statements": (
        ledger_position_statements,
        "state_ledger_positions_trigger",
    ),
    "startup replay": (inbox_startup_replay, "records_left_in_holding"),
}


@pytest.mark.parametrize("path", list(_LOST_SCOPE_POINTS))
def test_lifespan_work_that_lost_its_scope_raises_at_shutdown(
    path: str, nodes: list[IsolatedActorApp], monkeypatch
) -> None:
    """The refusal ends the task and surfaces; it is not logged and skipped.

    Each path's boundary catches one actor's failure and goes on, so without
    a re-raise a lost scope would be a log line and the work would carry on.
    The lifespan's teardown still runs, and the app's hold is released.
    """
    module, name = _LOST_SCOPE_POINTS[path]
    reached = threading.Event()
    node = nodes[0]
    holds_before = held_app_configs()

    def _lose_scope(*_args: Any, **_kwargs: Any) -> Any:
        reached.set()
        _lost_scope_read()

    async def _lose_scope_async(*_args: Any, **_kwargs: Any) -> Any:
        _lose_scope()

    monkeypatch.setattr(
        module,
        name,
        _lose_scope_async if path == "outbox monitor" else _lose_scope,
    )

    with pytest.raises(VultronWiringError, match="ADR-0206"):
        with node.client:
            _wait_for(reached.is_set, f"the {path} to read its config")
            _wait_for(
                lambda: (
                    (task := _task_of(path, node.app)) is not None
                    and task.done()
                ),
                f"the {path} task to end",
            )

    # The teardown after the failed task still ran, and the hold is gone.
    assert node.app.state.dispatcher is None
    assert node.app.state.outbox_monitor is None
    assert held_app_configs() == holds_before
