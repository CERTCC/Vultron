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

"""Close the connection a disposed in-memory store opens, and fail its test.

Disposing a store's engine pops it from the engine cache and gives it a fresh
pool.  A ``SqliteDataLayer`` still holding that engine, used afterwards, opens
a new SQLite connection on the fresh pool.  Nothing ever disposes that engine
again, so the connection is closed only when the garbage collector reaches it.
Its ``ResourceWarning: unclosed database`` then fails whichever test is
running at that moment (#6001).

The watch records every connection opened on an in-memory engine that is no
longer cached.  Per-test disposal closes each one, then fails the test it was
opened in, naming the stack that opened it.  A file-backed store is not
watched: its pool closes each connection when its session ends.

A connection whose opening thread is still running is not closed: that thread
may be reading through it, and closing a connection under a read segfaults the
worker (#6148).  It is kept referenced instead, so the garbage collector never
finalizes it and no later test sees its warning; the test still fails.
"""

import sqlite3
import sysconfig
import threading
import traceback
from dataclasses import dataclass
from typing import Any

from sqlalchemy import event
from sqlalchemy.pool import Pool, StaticPool

from vultron.adapters.driven.datalayer_sqlite import engine as sqlite_engine

#: Frames kept from the opening stack, innermost last.
STACK_FRAMES = 12

#: Library and standard-library frames say nothing about who reused the store.
_LIBRARY_PATHS = tuple(
    {sysconfig.get_paths()[key] for key in ("stdlib", "purelib", "platlib")}
)


class OrphanStoreConnectionError(RuntimeError):
    """A disposed in-memory store opened a connection during the test."""


@dataclass(frozen=True)
class OrphanConnection:
    """One connection opened on an engine the cache no longer holds."""

    dbapi_connection: Any
    thread: threading.Thread
    stack: str


_orphans: list[OrphanConnection] = []
_orphans_lock = threading.Lock()

#: Orphans left open because their thread was still running: held here so no
#: garbage-collector pass finalizes them under a later test.
_kept_open: list[OrphanConnection] = []


def _is_cached(pool: Pool) -> bool:
    # list(): another thread may add to the cache while this one reads it.
    return any(
        engine.pool is pool for engine in list(sqlite_engine._ENGINES.values())
    )


def _record_orphan(dbapi_connection: Any, record: Any) -> None:
    # The record keeps its pool name-mangled: _ConnectionRecord.__pool.
    pool = getattr(record, "_ConnectionRecord__pool", None)
    if not isinstance(pool, StaticPool) or _is_cached(pool):
        return
    frames = [
        frame
        for frame in traceback.extract_stack()[:-1]
        if not frame.filename.startswith(_LIBRARY_PATHS)
    ]
    stack = "".join(traceback.format_list(frames[-STACK_FRAMES:]))
    with _orphans_lock:
        _orphans.append(
            OrphanConnection(
                dbapi_connection=dbapi_connection,
                thread=threading.current_thread(),
                stack=stack,
            )
        )


def install_orphan_connection_watch() -> None:
    """Start recording connections opened on disposed in-memory stores.

    Idempotent: the listener is added once per process.
    """
    if not event.contains(Pool, "connect", _record_orphan):
        event.listen(Pool, "connect", _record_orphan)


def close_orphan_connections() -> None:
    """Close every recorded orphan connection, then fail if there was one.

    A connection whose opening thread is another, still-running thread is
    kept open and referenced instead of closed (see the module docstring).

    Raises:
        OrphanStoreConnectionError: a connection was opened on a disposed
            in-memory store since the last call.  Each is closed (or kept)
            first, so no later test fails on its ``ResourceWarning``.
    """
    with _orphans_lock:
        found = list(_orphans)
        _orphans.clear()
    if not found:
        return
    sites = [_settle(orphan) for orphan in found]
    raise OrphanStoreConnectionError(
        f"{len(found)} SQLite connection(s) were opened on an in-memory store"
        " whose engine is no longer cached: something kept a DataLayer past"
        " a reset_datalayer(), close() or per-test disposal and used it"
        " again.  Use a fresh store after a reset, or stop the background"
        " work that holds the old one before the stores are disposed"
        " (#6001).\n" + "\n".join(sites)
    )


def _settle(orphan: OrphanConnection) -> str:
    """Close *orphan*, or keep it if its thread may still read it.

    Returns:
        The orphan's report line: its thread, what was done, and its stack.
    """
    thread = orphan.thread
    if thread is not threading.current_thread() and thread.is_alive():
        _kept_open.append(orphan)
        action = "kept open: its thread is still running"
    else:
        try:
            orphan.dbapi_connection.close()
            action = "closed"
        except sqlite3.Error as error:  # report it; the rest still close
            action = f"close failed: {error!r}"
    return f"--- opened in thread {thread.name!r} ({action}):\n{orphan.stack}"
