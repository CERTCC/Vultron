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

from vultron.adapters.driven.datalayer_sqlite import (
    SqliteDataLayer,
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
