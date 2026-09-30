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

"""An in-memory store's one shared connection is safe across threads.

``make_engine`` gives an in-memory SQLite database a ``StaticPool`` — every
``Session`` uses the *same* DB-API connection — and ``check_same_thread=False``
so that connection may be used from any thread.  Nothing else stopped two
threads from interleaving logical transactions on it, and SQLAlchemy resets
(rolls back) the connection when a ``Session`` returns it to the pool: one
thread's ``Session.close()`` discarded another thread's uncommitted insert.

That is how an inbound ``Reject(CaseLedgerEntry)`` stored by the CaseActor's
inbox worker thread vanished before the same pipeline re-read it ("Object …
not found in data layer") while the CaseActor's outbox drain was reading the
same store on the event loop (#3602).  The engine now holds one lock from
connection checkout to checkin, so a ``Session`` on one thread cannot see or
reset another thread's transaction.

The scenario here is the minimal deterministic form: thread A inserts and
flushes but has not committed; thread B opens and closes a ``Session`` on the
same engine; A commits.  Without the lock B's checkin rolls A back.
"""

import threading

from sqlmodel import select

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driven.datalayer_sqlite.schema import (
    VultronObjectRecord as DBRecord,
)


def _record(id_: str) -> DBRecord:
    return DBRecord(id_=id_, type_="Note", data={"id": id_, "type": "Note"})


def test_session_on_another_thread_cannot_roll_back_an_open_transaction():
    dl = SqliteDataLayer(
        "sqlite:///:memory:", actor_id="https://example.org/actors/a"
    )

    a_flushed = threading.Event()
    b_done = threading.Event()
    errors: list[BaseException] = []

    def writer() -> None:
        try:
            with dl._session() as session:
                session.add(_record("urn:test:kept"))
                session.flush()  # in the transaction, not yet committed
                a_flushed.set()
                # Give B every chance to run while A's transaction is open.
                b_done.wait(timeout=0.5)
                session.commit()
        except BaseException as exc:  # noqa: BLE001 — surfaced below
            errors.append(exc)

    def other() -> None:
        try:
            a_flushed.wait(timeout=5)
            with dl._session() as session:
                session.exec(select(DBRecord)).all()
            # On the unguarded shared connection this checkin rolled A back.
        except BaseException as exc:  # noqa: BLE001
            errors.append(exc)
        finally:
            b_done.set()

    threads = [threading.Thread(target=writer), threading.Thread(target=other)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10)
    assert not [t for t in threads if t.is_alive()], "threads deadlocked"
    assert not errors, errors

    with dl._session() as session:
        kept = session.get(DBRecord, "urn:test:kept")
    assert kept is not None, (
        "thread B's Session.close() rolled back thread A's uncommitted"
        " insert on the shared in-memory connection"
    )


def test_nested_read_sessions_on_one_thread_do_not_deadlock():
    """The guard is re-entrant: a session opened inside another proceeds.

    Only *reads* are nested here.  Two sessions on one ``StaticPool``
    connection still share a transaction, so a write in the outer session
    and a close of the inner one is unsafe with or without the guard; the
    adapter does not nest writes, and the guard is not what makes that so.
    """
    dl = SqliteDataLayer(
        "sqlite:///:memory:", actor_id="https://example.org/actors/b"
    )
    with dl._session() as outer:
        outer.exec(select(DBRecord)).all()
        with dl._session() as inner:
            inner.exec(select(DBRecord)).all()
