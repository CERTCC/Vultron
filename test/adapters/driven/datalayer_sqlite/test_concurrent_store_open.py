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

"""Two openers of one new actor store at the same moment both succeed.

A node's request thread and its background timers (the sender-sequence hold
sweep, the ledger position statements) can open the same actor's store at
once: the request creates the store's file, and the next timer round finds
the file and opens it too.  ``create_all`` checks for each table and then
creates it, so two openers that both checked before either created failed
one of them with ``table vultron_objects already exists`` — a 500 on the
request (#5999, #6761).

The race window is widened deterministically here: the first ``has_table``
check of each opener waits on a barrier, so without serialisation both
openers have checked before either creates.  With serialisation the first
opener's wait times out (the second cannot reach the check), and the test
pays that timeout once.
"""

import threading
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy.dialects.sqlite.base import SQLiteDialect

import vultron.adapters.driven.datalayer_sqlite as datalayer_package
from vultron.adapters.driven.datalayer_sqlite import (
    SqliteDataLayer,
    datalayer as datalayer_module,
    engine as engine_module,
    fresh_memory_url,
    get_datalayer,
    reset_datalayer,
)

ACTOR_ID = "https://example.org/actors/race-actor"
OPENERS = 2
#: How long one opener waits at the check for the other.  Long enough that
#: an unserialised second opener always arrives; paid once when serialised.
BARRIER_WAIT_SECONDS = 1.0


@pytest.fixture(autouse=True)
def _fresh_registry() -> Iterator[None]:
    reset_datalayer()
    yield
    reset_datalayer()


@pytest.fixture
def check_rendezvous(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make each opener's first table check wait for the other opener."""
    barrier = threading.Barrier(OPENERS, timeout=BARRIER_WAIT_SECONDS)
    seen = threading.local()
    original = SQLiteDialect.has_table

    def has_table(
        self: SQLiteDialect,
        connection: Any,
        table_name: str,
        schema: str | None = None,
        **kw: Any,
    ) -> bool:
        if not getattr(seen, "waited", False):
            seen.waited = True
            try:
                barrier.wait()
            except threading.BrokenBarrierError:
                pass  # serialised: the other opener cannot reach the check
        return bool(
            original(self, connection, table_name, schema=schema, **kw)
        )

    monkeypatch.setattr(SQLiteDialect, "has_table", has_table)


def _run_concurrently(
    open_store: Callable[[], SqliteDataLayer],
) -> tuple[list[SqliteDataLayer], list[BaseException]]:
    """Run *open_store* on ``OPENERS`` threads released together."""
    start = threading.Barrier(OPENERS)
    stores: list[SqliteDataLayer] = []
    errors: list[BaseException] = []
    lock = threading.Lock()

    def opener() -> None:
        start.wait()
        try:
            store = open_store()
        except BaseException as exc:  # noqa: BLE001 — surfaced below
            with lock:
                errors.append(exc)
        else:
            with lock:
                stores.append(store)

    threads = [threading.Thread(target=opener) for _ in range(OPENERS)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)
    assert not any(t.is_alive() for t in threads), "an opener hung"
    return stores, errors


@pytest.mark.usefixtures("check_rendezvous")
def test_get_datalayer_concurrent_first_open_returns_one_store(
    tmp_path: Path,
) -> None:
    template = f"sqlite:///{tmp_path / 'vultron.db'}"

    stores, errors = _run_concurrently(
        lambda: get_datalayer(ACTOR_ID, db_url=template)
    )

    assert errors == []
    assert len(stores) == OPENERS
    assert all(store is stores[0] for store in stores)
    assert stores[0].ping()


@pytest.mark.usefixtures("check_rendezvous")
def test_concurrent_store_open_on_new_file_both_succeed(
    tmp_path: Path,
) -> None:
    template = f"sqlite:///{tmp_path / 'vultron.db'}"

    stores, errors = _run_concurrently(
        lambda: SqliteDataLayer(db_url=template, actor_id=ACTOR_ID)
    )
    try:
        assert errors == []
        assert len(stores) == OPENERS
        assert all(store.ping() for store in stores)
    finally:
        for store in stores:
            store.close()


@pytest.mark.parametrize("kind", ["file", "memory"])
def test_get_actor_engine_concurrent_first_call_returns_one_engine(
    kind: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Two in-memory engines for one URL are two databases; two file engines
    # would hold two schema locks.  Each caller's engine build waits for the
    # other's, so without the cache lock both build one.
    template = (
        f"sqlite:///{tmp_path / 'vultron.db'}"
        if kind == "file"
        else fresh_memory_url("engine-race")
    )
    barrier = threading.Barrier(OPENERS, timeout=BARRIER_WAIT_SECONDS)
    original = engine_module.make_engine

    def make_engine(db_url: str) -> Any:
        try:
            barrier.wait()
        except threading.BrokenBarrierError:
            pass  # serialised: the other caller cannot reach the build
        return original(db_url)

    monkeypatch.setattr(engine_module, "make_engine", make_engine)
    engines: list[Any] = []
    lock = threading.Lock()

    def caller() -> None:
        found = engine_module.get_actor_engine(template, ACTOR_ID)
        with lock:
            engines.append(found)

    threads = [threading.Thread(target=caller) for _ in range(OPENERS)]
    try:
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=30)
        assert not any(t.is_alive() for t in threads), "a caller hung"
        assert len(engines) == OPENERS
        assert all(found is engines[0] for found in engines)
    finally:
        engine_module.dispose_actor_engines(template, ACTOR_ID)


def test_transaction_holder_opening_its_store_does_not_wait_on_an_opener(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # The holder has a transaction open on an in-memory store it opened
    # directly, so the store is not cached.  An opener calls get_datalayer,
    # takes the store's open lock and waits on the session lock the holder's
    # transaction holds.  The holder then calls get_datalayer for the same
    # store: it must not wait on the opener's open lock.
    template = fresh_memory_url("tx-open")
    opener_waiting = threading.Event()
    real_session_guard = datalayer_module.session_guard

    def session_guard(engine: Any) -> Any:
        if threading.current_thread().name == "opener":
            opener_waiting.set()
        return real_session_guard(engine)

    monkeypatch.setattr(datalayer_module, "session_guard", session_guard)
    holder = SqliteDataLayer(db_url=template, actor_id=ACTOR_ID)
    in_transaction = threading.Event()
    results: dict[str, SqliteDataLayer] = {}

    def hold() -> None:
        with holder.transaction():
            in_transaction.set()
            assert opener_waiting.wait(timeout=10)
            results["holder"] = get_datalayer(ACTOR_ID, db_url=template)

    def open_store() -> None:
        assert in_transaction.wait(timeout=10)
        results["opener"] = get_datalayer(ACTOR_ID, db_url=template)

    threads = [
        threading.Thread(target=hold, name="holder", daemon=True),
        threading.Thread(target=open_store, name="opener", daemon=True),
    ]
    try:
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=10)
        assert not any(t.is_alive() for t in threads), "deadlocked"
        assert results["holder"] is results["opener"]
    finally:
        holder.close()


def test_reset_during_an_open_does_not_open_the_store_twice(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # A reset that runs while a store is opening must not let the next
    # caller open the same store beside the opener still running.
    template = f"sqlite:///{tmp_path / 'vultron.db'}"
    entered = threading.Event()
    release = threading.Event()
    seen = threading.local()
    original = SQLiteDialect.has_table

    def has_table(
        self: SQLiteDialect,
        connection: Any,
        table_name: str,
        schema: str | None = None,
        **kw: Any,
    ) -> bool:
        if threading.current_thread().name == "first" and not getattr(
            seen, "waited", False
        ):
            seen.waited = True
            entered.set()
            release.wait(timeout=10)
        return bool(
            original(self, connection, table_name, schema=schema, **kw)
        )

    monkeypatch.setattr(SQLiteDialect, "has_table", has_table)
    opens: list[str] = []

    class CountingDataLayer(SqliteDataLayer):
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            opens.append(threading.current_thread().name)
            super().__init__(*args, **kwargs)

    monkeypatch.setattr(
        datalayer_package, "SqliteDataLayer", CountingDataLayer
    )
    results: dict[str, SqliteDataLayer] = {}

    def open_as(name: str) -> threading.Thread:
        def run() -> None:
            results[name] = get_datalayer(ACTOR_ID, db_url=template)

        thread = threading.Thread(target=run, name=name, daemon=True)
        thread.start()
        return thread

    first = open_as("first")
    assert entered.wait(timeout=10)
    reset_datalayer()
    second = open_as("second")
    # Give the second caller time to reach the open lock; arriving late
    # finds the store cached, which can only hide a regression.
    second.join(timeout=0.2)
    release.set()
    for thread in (first, second):
        thread.join(timeout=30)
    assert not first.is_alive() and not second.is_alive(), "an opener hung"
    assert opens == ["first"]
    assert results["first"] is results["second"]
