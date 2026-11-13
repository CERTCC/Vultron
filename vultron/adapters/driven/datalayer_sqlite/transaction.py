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

"""One SQLite transaction spanning many DataLayer calls.

:meth:`SqliteDataLayer.transaction` opens one connection, starts one SQLite
transaction on it, and registers it here for its engine and thread.  Every
``Session`` the adapter opens on that engine, in that thread, while the block
is open binds to that connection and joins the transaction through a
SAVEPOINT (``join_transaction_mode="create_savepoint"``): a ``commit()``
inside a CRUD helper releases its savepoint, and a ``rollback()`` (or a
failed flush) undoes only that helper's writes.  Every read sees the block's
own writes.  The block commits once, at its end, or rolls everything back
when it raises.

The transaction is opened with ``BEGIN IMMEDIATE`` so it holds the write lock
from the start: a file-backed store's other writers wait for it, rather than
the block failing part-way when another writer committed first.  The block
also holds the in-memory store's session lock for its whole life
(:func:`~.engine.session_guard`): that store has one shared connection, and
any other thread's ``Session`` on it would otherwise run inside this
transaction.

An enqueue callback raised by a write inside the block runs only after the
block commits (:func:`run_after_commit`), so an outbox monitor is never woken
to drain a row another connection cannot yet see, or one that is rolled back.

A block also keeps each object row it reads, as stored
(:attr:`OpenTransaction.rows_read`), so a later read of the same row in the block is not fetched
again (#5344).  The store cannot change under the block except by the block's
own writes: the write lock (file-backed) or the session lock (in-memory) keeps
every other writer out until it ends.  So a kept row stays current until the
block writes it, and every object-row write forgets the rows it touches before
it runs (:func:`forget_rows`).  A SAVEPOINT that rolls back forgets every kept
row, because a row read after a write it undid holds the undone version.
"""

import logging
import threading
from collections.abc import Callable, Iterable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field

from sqlalchemy.engine import Connection, Engine

from .engine import session_guard

logger = logging.getLogger(__name__)


@dataclass
class OpenTransaction:
    """The connection a transaction runs on, and what runs after it commits."""

    connection: Connection
    after_commit: list[Callable[[], None]] = field(default_factory=list)
    #: Each object row read in the block and not written since, keyed by
    #: id: its ``type_`` and its ``data`` as the stored JSON text (#5344).
    rows_read: dict[str, tuple[str, str]] = field(default_factory=dict)


class _Registry(threading.local):
    """Each thread's open transactions, keyed by engine identity."""

    def __init__(self) -> None:
        self.open: dict[int, OpenTransaction] = {}


_REGISTRY = _Registry()


def open_transaction(engine: Engine) -> OpenTransaction | None:
    """The transaction this thread holds open on *engine*, if any."""
    return _REGISTRY.open.get(id(engine))


def run_after_commit(engine: Engine, callback: Callable[[], None]) -> None:
    """Run *callback* after this thread's transaction on *engine* commits.

    With no transaction open, *callback* runs now.  A transaction that rolls
    back drops it.
    """
    state = open_transaction(engine)
    if state is None:
        callback()
    else:
        state.after_commit.append(callback)


def forget_rows(engine: Engine, ids: Iterable[str] | None = None) -> None:
    """Forget the rows this thread's transaction on *engine* kept for *ids*.

    Every write to an object row calls this before it writes, so the block's
    next read of that row fetches what the write left.  *ids* ``None``
    forgets every kept row, for a write that names no single row.  With no
    transaction open, nothing is kept and this does nothing.
    """
    state = open_transaction(engine)
    if state is None:
        return
    if ids is None:
        state.rows_read.clear()
        return
    for object_id in ids:
        state.rows_read.pop(object_id, None)


@contextmanager
def transaction(engine: Engine) -> Iterator[None]:
    """Commit every write inside the block together, or none of them.

    A block opened inside another on the same engine and thread is a
    SAVEPOINT in the outer one: when it raises, its own writes (and the
    after-commit callbacks they registered) are rolled back, and the outer
    block decides the rest; otherwise its writes commit, or roll back, with
    the outer block's.

    Raises:
        Exception: whatever the block raised, after every write in it was
            rolled back.
    """
    outer = open_transaction(engine)
    if outer is not None:
        with _savepoint(outer):
            yield
        return
    with session_guard(engine):
        with engine.connect() as connection:
            # pysqlite defers BEGIN until the first DML statement, and a
            # SAVEPOINT outside a transaction would itself become the
            # transaction (so its RELEASE would commit); begin explicitly.
            connection.exec_driver_sql("BEGIN IMMEDIATE")
            state = OpenTransaction(connection=connection)
            _REGISTRY.open[id(engine)] = state
            try:
                yield
            except BaseException:
                connection.rollback()
                raise
            else:
                connection.commit()
            finally:
                del _REGISTRY.open[id(engine)]
    for callback in state.after_commit:
        # The block has committed: a callback that fails must not make the
        # caller read a committed act as a failed one.
        try:
            callback()
        except Exception:
            logger.exception("after-commit callback %r raised", callback)


@contextmanager
def _savepoint(state: OpenTransaction) -> Iterator[None]:
    """Run a nested block as a SAVEPOINT of the open transaction *state*."""
    nested = state.connection.begin_nested()
    pending = len(state.after_commit)
    try:
        yield
    except BaseException:
        nested.rollback()
        del state.after_commit[pending:]
        # A row read after a write this savepoint undid holds the undone
        # version; which rows those are is not tracked, so forget them all.
        state.rows_read.clear()
        raise
    else:
        nested.commit()


__all__ = [
    "OpenTransaction",
    "forget_rows",
    "open_transaction",
    "run_after_commit",
    "transaction",
]
