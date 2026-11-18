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
from collections.abc import Callable, Coroutine, Iterator
from datetime import timedelta
from types import SimpleNamespace
from typing import Any, cast

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
from vultron.adapters.driving.fastapi.app import (
    _finish_background_work,
    create_app,
)
from vultron.adapters.driving.fastapi.deps import (
    app_node_deployment,
    get_actor_dl,
)
from vultron.config import (
    AppConfig,
    app_config_scope,
    get_config,
    holding_app_config,
)
from vultron.core.ports.datalayer import DataLayer
from vultron.demo.in_process import (
    InProcessRouter,
    IsolatedActorApp,
    create_isolated_actor_app,
)
from vultron.errors import VultronConfigScopeLostError, VultronWiringError

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
    """Each round's hold, read in the round's worker thread, is its app's."""
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
            others = [
                _task_of(other, node.app)
                for other in _LOST_SCOPE_POINTS
                if other != path
            ]

    # Every other task was stopped and awaited too, not left running while
    # the stores closed; the teardown still ran, and the hold is gone.
    # Stopped by the lifespan, not cancelled when the test client's loop
    # closed: a task left running would read as cancelled here.
    assert all(
        task is not None and task.done() and not task.cancelled()
        for task in others
    )
    assert node.app.state.dispatcher is None
    assert node.app.state.outbox_monitor is None
    assert held_app_configs() == holds_before


def test_a_rerun_that_lost_its_scope_is_not_logged_as_one_records_failure(
    monkeypatch,
) -> None:
    """The per-record boundary of the startup re-run re-raises the refusal.

    A re-run that fails is logged and the next record is run; a lost scope
    is no one record's failure, so it raises out of the re-run instead.
    """
    record = SimpleNamespace(activity_id="urn:uuid:held", received_at=None)
    reruns: list[str] = []

    async def _lost_scope_pipeline(*_args: Any, **_kwargs: Any) -> None:
        reruns.append("run")
        _lost_scope_read()

    monkeypatch.setattr(
        inbox_startup_replay,
        "records_left_in_holding",
        lambda _dl: [record, record],
    )
    monkeypatch.setattr(
        inbox_startup_replay, "_rerun_budget_left", lambda *_args: True
    )
    monkeypatch.setattr(
        inbox_startup_replay, "sealed_body_of", lambda _r: "{}"
    )
    monkeypatch.setattr(
        inbox_startup_replay,
        "run_delivery_without_replay",
        _lost_scope_pipeline,
    )

    with holding_app_config(own_app_config()):
        with pytest.raises(VultronWiringError, match="ADR-0206"):
            asyncio.run(
                inbox_startup_replay.rerun_left_in_holding(
                    cast(DataLayer, object()), "urn:uuid:actor", None, None
                )
            )
    # The second record was not run: the refusal ended the re-runs.
    assert reruns == ["run"]


def test_a_monitor_loop_that_ended_on_another_error_is_logged(
    caplog,
) -> None:
    """``stop()`` logs a loop crash it read, so asyncio's report is not lost."""

    def _failing_factory() -> dict:
        raise RuntimeError("the store listing failed")

    async def _run() -> None:
        monitor = outbox_monitor.OutboxMonitor(
            poll_interval=0.01, actor_datalayers_factory=_failing_factory
        )
        monitor.start()
        task = monitor._task
        assert task is not None
        await asyncio.wait({task})
        monitor.stop()

    with caplog.at_level("ERROR", logger=outbox_monitor.__name__):
        asyncio.run(_run())

    assert "drain loop ended on an error" in caplog.text
    assert "the store listing failed" in caplog.text


def test_an_apps_background_work_shares_its_routes_store_instances() -> None:
    """With the app's own store registry, one instance per actor serves both.

    An enqueue through a route then wakes the app's outbox monitor, which
    registers its wakeup on the instances it drains, and the app's teardown
    closes every store the work opened.
    """
    config = own_app_config()
    app = create_app(config=config)
    with TestClient(app) as client, app_config_scope(config):
        # The test body is work of the app too, so it reads in its scope.
        client.get("/api/v2/actors/vendor")
        registry: dict[str, Any] = app.state.actor_dls
        (actor_id,) = registry
        node = app_node_deployment(app)

        assert node.opened is not None
        assert node.opened is registry
        assert node.store(actor_id) is registry[actor_id]
        assert node.stores() == {actor_id: registry[actor_id]}

        # A store the work opens first is the one a route is handed later.
        other = f"{actor_id.rsplit('/', 1)[0]}/other"
        opened = node.store(other)
        assert registry[other] is opened


# ---------------------------------------------------------------------------
# Only a lost scope ends the work; any other wiring fault stays one actor's
# ---------------------------------------------------------------------------


class _FakeNode:
    """Two hosted actors, each with a store that holds one outbox item."""

    actors = ("urn:uuid:first", "urn:uuid:second")

    def actor_ids(self) -> list[str]:
        return list(self.actors)

    def store(self, actor_id: str) -> Any:
        return SimpleNamespace(
            actor_id=actor_id,
            inbox_list=lambda: [],
            outbox_list=lambda: ["queued"],
        )

    def stores(self) -> dict[str, Any]:
        return {actor_id: self.store(actor_id) for actor_id in self.actors}


def _run_boundary(path: str, error: Exception, monkeypatch) -> list[str]:
    """Run *path* over two actors whose first raises *error*; list reached."""
    reached: list[str] = []
    node = cast(Any, _FakeNode())

    async def _work(
        actor_dl: Any, actor_id: str, *_args: Any, **_kw: Any
    ) -> None:
        reached.append(actor_id)
        if actor_id == _FakeNode.actors[0]:
            raise error

    run: Coroutine[Any, Any, Any]
    if path == "startup replay":
        monkeypatch.setattr(
            inbox_startup_replay, "rerun_left_in_holding", _work
        )
        run = inbox_startup_replay.replay_hosted_inbox_queues(node=node)
    elif path == "position statements":
        monkeypatch.setattr(
            ledger_position_statements, "run_serialised_actor_work", _work
        )
        run = ledger_position_statements.state_hosted_ledger_positions(
            node=node
        )
    elif path == "hold timer":
        monkeypatch.setattr(
            sender_sequence_holds, "run_actor_work_then_replay", _work
        )
        run = sender_sequence_holds.end_hosted_expired_holds(node=node)
    else:

        async def _drain(actor_id: str, actor_dl: Any, **_kw: Any) -> None:
            await _work(actor_dl, actor_id)

        monkeypatch.setattr(outbox_monitor, "outbox_handler", _drain)
        monitor = outbox_monitor.OutboxMonitor(
            actor_datalayers_factory=node.stores
        )
        run = monitor.drain_all()
    asyncio.run(run)
    return reached


_BOUNDARIES = [
    "startup replay",
    "position statements",
    "hold timer",
    "outbox monitor",
]


@pytest.mark.parametrize("path", _BOUNDARIES)
def test_another_wiring_fault_stays_one_actors_failure(
    path: str, monkeypatch
) -> None:
    """A ``VultronWiringError`` that is not a lost scope is logged, as before.

    The production boundaries logged one actor's miswiring and went on to
    the next actor; only a lost config scope is every actor's failure.
    """
    reached = _run_boundary(
        path, VultronWiringError("one actor's missing port"), monkeypatch
    )

    assert reached == list(_FakeNode.actors)


@pytest.mark.parametrize("path", _BOUNDARIES)
def test_a_lost_scope_ends_the_boundary_at_the_first_actor(
    path: str, monkeypatch
) -> None:
    with pytest.raises(VultronConfigScopeLostError):
        _run_boundary(
            path, VultronConfigScopeLostError("lost scope"), monkeypatch
        )


# ---------------------------------------------------------------------------
# The app's own dispatcher, emitter and stores reach its background work
# ---------------------------------------------------------------------------


def test_the_replay_and_hold_timer_use_the_apps_own_dispatcher(
    nodes: list[IsolatedActorApp], monkeypatch
) -> None:
    seen: dict[str, Any] = {}

    async def _record_rerun(
        _dl: Any, actor_id: str, dispatcher: Any, *_args: Any
    ) -> None:
        seen.setdefault(f"replay {actor_id}", dispatcher)

    async def _record_round(
        _dl: Any, actor_id: str, dispatcher: Any, *_args: Any
    ) -> None:
        seen.setdefault(f"hold timer {actor_id}", dispatcher)

    monkeypatch.setattr(
        inbox_startup_replay, "rerun_left_in_holding", _record_rerun
    )
    monkeypatch.setattr(
        sender_sequence_holds, "run_actor_work_then_replay", _record_round
    )
    node = nodes[0]
    with node.client:
        _wait_for(lambda: len(seen) == 2, "the replay and a hold round")
        own = node.app.state.dispatcher

    assert own is not None
    assert seen == {
        f"replay {node.actor_id}": own,
        f"hold timer {node.actor_id}": own,
    }


def test_the_monitor_uses_the_emitter_its_host_set() -> None:
    emitter = cast(Any, object())
    app = create_app(config=own_app_config())
    app.state.emitter = emitter
    with TestClient(app):
        assert app.state.outbox_monitor._emitter is emitter


def test_an_override_without_a_declared_template_is_refused() -> None:
    """The work would otherwise read the configured deployment's stores."""
    app = create_app(config=own_app_config())
    app.dependency_overrides[get_actor_dl] = lambda actor_id: None
    holds_before = held_app_configs()

    with pytest.raises(VultronWiringError, match=r"app\.state\.db_url"):
        with TestClient(app):
            pass
    assert held_app_configs() == holds_before


def test_the_monitor_task_has_ended_once_the_lifespan_has() -> None:
    """The monitor is awaited, not only cancelled, before the stores close."""
    app = create_app(config=own_app_config())
    with TestClient(app):
        task = app.state.outbox_monitor._task
    assert task is not None
    assert task.done()


# ---------------------------------------------------------------------------
# Shutdown awaits every task and loses no error
# ---------------------------------------------------------------------------


def _finish(log: list[str], name: str, error: BaseException | None):
    async def _run() -> None:
        log.append(name)
        if error is not None:
            raise error

    return _run()


def test_every_finish_is_awaited_and_extra_errors_are_logged(caplog) -> None:
    log: list[str] = []
    application = FastAPI()
    for name in ("one", "two", "three"):
        setattr(application.state, name, "running")
    finishes = (
        ("one", _finish(log, "one", RuntimeError("first"))),
        ("two", _finish(log, "two", ValueError("second"))),
        ("three", _finish(log, "three", None)),
    )

    with caplog.at_level("ERROR"):
        with pytest.raises(RuntimeError, match="first"):
            asyncio.run(_finish_background_work(application, finishes))

    assert log == ["one", "two", "three"]
    assert all(
        getattr(application.state, name) is None
        for name in ("one", "two", "three")
    )
    assert "second" in caplog.text


def test_a_cancellation_does_not_skip_the_later_finishes() -> None:
    log: list[str] = []
    application = FastAPI()
    finishes = (
        ("one", _finish(log, "one", RuntimeError("first"))),
        ("two", _finish(log, "two", asyncio.CancelledError())),
        ("three", _finish(log, "three", None)),
    )

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(_finish_background_work(application, finishes))

    assert log == ["one", "two", "three"]
