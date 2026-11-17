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

"""A disposed in-memory store's new connection fails its own test (#6001).

A ``SqliteDataLayer`` used after its engine was disposed opens a connection
nothing closes.  Left alone, its ``ResourceWarning`` fails whichever later
test the garbage collector lands in.  Per-test disposal closes it and fails
the test that opened it instead, naming the stack.
"""

import gc
import sqlite3
import threading
import warnings

import pytest
from sqlalchemy.exc import OperationalError

from test.support import hold_timers, orphan_store_connections
from test.support.hold_timers import (
    HoldTimerLeakedError,
    dispose_actor_stores_between_tests,
)
from test.support.orphan_store_connections import (
    OrphanConnection,
    OrphanStoreConnectionError,
    close_orphan_connections,
    install_orphan_connection_watch,
)
from vultron.adapters.driven.datalayer_sqlite import (
    SqliteDataLayer,
    dispose_actor_engines,
)

_ACTOR = "https://example.org/actors/orphan-store"


def _reuse_after_disposal(db_url: str) -> None:
    """Open a store, dispose its engine, then read through the old instance."""
    dl = SqliteDataLayer(db_url, actor_id=_ACTOR)
    dispose_actor_engines()
    # The fresh pool has an empty database, so the read itself fails; the
    # connection it opened is what matters here.
    with pytest.raises(OperationalError, match="no such table"):
        dl.read("https://example.org/objects/absent")


def _unclosed_database_warnings() -> list[warnings.WarningMessage]:
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", ResourceWarning)
        gc.collect()
    return [
        w
        for w in caught
        if issubclass(w.category, ResourceWarning)
        and "unclosed database" in str(w.message)
    ]


def test_disposal_fails_the_test_that_reused_a_disposed_memory_store():
    _reuse_after_disposal("sqlite:///:memory:")

    with pytest.raises(OrphanStoreConnectionError) as raised:
        dispose_actor_stores_between_tests()

    message = str(raised.value)
    assert "1 SQLite connection(s)" in message
    assert "_reuse_after_disposal" in message


def test_the_orphan_connection_is_closed_before_the_failure():
    _reuse_after_disposal("sqlite:///:memory:")

    with pytest.raises(OrphanStoreConnectionError):
        close_orphan_connections()

    assert _unclosed_database_warnings() == []


def test_an_orphan_left_unclosed_does_warn_when_collected():
    # Control for the test above: with the guard's close skipped, the same
    # connection reaches the collector and warns, so "no warning" there is
    # the close's doing, not a reference that kept the connection alive.
    _reuse_after_disposal("sqlite:///:memory:")
    orphan_store_connections._orphans.clear()

    assert len(_unclosed_database_warnings()) == 1


def test_an_orphan_whose_thread_still_runs_is_kept_open(monkeypatch):
    # Closing a connection under another thread's read segfaults the worker
    # (#6148), so a live thread's orphan is kept referenced, never closed.
    kept: list[OrphanConnection] = []
    monkeypatch.setattr(orphan_store_connections, "_kept_open", kept)
    opened = threading.Event()
    release = threading.Event()

    def _holder() -> None:
        _reuse_after_disposal("sqlite:///:memory:")
        opened.set()
        release.wait()

    thread = threading.Thread(target=_holder, name="store-holder")
    thread.start()
    try:
        assert opened.wait(10)
        with pytest.raises(OrphanStoreConnectionError, match="kept open"):
            close_orphan_connections()
        (orphan,) = kept
        orphan.dbapi_connection.execute("SELECT 1")  # still open
    finally:
        release.set()
        thread.join(10)
    orphan.dbapi_connection.close()


def test_a_close_that_fails_still_closes_and_reports_the_rest():
    class _Unclosable:
        def close(self) -> None:
            raise sqlite3.ProgrammingError("cannot close")

    _reuse_after_disposal("sqlite:///:memory:")
    orphan_store_connections._orphans.insert(
        0, OrphanConnection(_Unclosable(), threading.current_thread(), "")
    )

    with pytest.raises(OrphanStoreConnectionError) as raised:
        close_orphan_connections()

    message = str(raised.value)
    assert "2 SQLite connection(s)" in message
    assert "close failed: ProgrammingError('cannot close')" in message
    assert "(closed)" in message
    assert _unclosed_database_warnings() == []


def test_a_leaked_timer_and_an_orphan_both_reach_the_failure(monkeypatch):
    monkeypatch.setattr(
        hold_timers, "running_sender_sequence_hold_timers", lambda: [object()]
    )
    monkeypatch.setattr(
        hold_timers, "stop_hold_timer_from_another_thread", lambda timer: None
    )
    _reuse_after_disposal("sqlite:///:memory:")

    with pytest.raises(HoldTimerLeakedError) as raised:
        dispose_actor_stores_between_tests()

    assert isinstance(raised.value.__context__, OrphanStoreConnectionError)
    assert _unclosed_database_warnings() == []


def test_installing_the_watch_again_records_each_connection_once():
    install_orphan_connection_watch()
    install_orphan_connection_watch()
    _reuse_after_disposal("sqlite:///:memory:")

    with pytest.raises(OrphanStoreConnectionError, match=r"^1 SQLite"):
        close_orphan_connections()


def test_disposal_passes_when_no_disposed_store_was_reused():
    SqliteDataLayer("sqlite:///:memory:", actor_id=_ACTOR)

    dispose_actor_stores_between_tests()

    close_orphan_connections()


def test_a_file_store_reused_after_disposal_is_not_an_orphan(tmp_path):
    # A file store's pool closes each connection when its session ends, so
    # reusing it after disposal leaks nothing.
    db_url = f"sqlite:///{tmp_path / 'store.db'}"
    dl = SqliteDataLayer(db_url, actor_id=_ACTOR)
    dispose_actor_engines()
    dl.count_all()

    close_orphan_connections()
