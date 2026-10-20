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

"""``SqliteDataLayer.transaction()``: many calls, one commit (ADR-0146).

Every write inside the block commits together, or none of them does; reads
inside the block see its own writes; a block inside another joins it; and an
outbox enqueue callback fires only once the block has committed.  Run on an
in-memory store (one shared connection, ``StaticPool``) and on a file-backed
one (one connection per ``Session``, ``NullPool``), whose transaction
mechanics differ.
"""

import threading
from collections.abc import Iterator
from pathlib import Path

import pytest

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.wire.as2.vocab.base.objects.object_types import as_Note

_ACTOR = "https://example.org/actors/tx-actor"


class _Boom(Exception):
    """The failure a test block raises part-way."""


@pytest.fixture(params=["memory", "file"])
def dl(
    request: pytest.FixtureRequest, tmp_path: Path
) -> Iterator[SqliteDataLayer]:
    url = (
        "sqlite:///:memory:"
        if request.param == "memory"
        else f"sqlite:///{tmp_path / 'tx.db'}"
    )
    store = SqliteDataLayer(url, actor_id=_ACTOR)
    try:
        yield store
    finally:
        store.close()


def _note(name: str) -> as_Note:
    return as_Note(id_=f"https://example.org/notes/{name}", content=name)


def test_every_write_in_the_block_commits_together(dl: SqliteDataLayer):
    first, second = _note("first"), _note("second")

    with dl.transaction():
        dl.save(first)
        dl.outbox_append(first.id_)
        dl.save_many([second])

    assert dl.read(first.id_) is not None
    assert dl.read(second.id_) is not None
    assert dl.outbox_list() == [first.id_]


def test_a_block_that_raises_writes_nothing(dl: SqliteDataLayer):
    kept = _note("kept")
    dl.save(kept)
    first, second = _note("first"), _note("second")

    with pytest.raises(_Boom):
        with dl.transaction():
            dl.save(first)
            dl.outbox_append(first.id_)
            dl.save_many([second])
            assert dl.delete(kept.type_, kept.id_)
            raise _Boom

    assert dl.read(first.id_) is None
    assert dl.read(second.id_) is None
    assert dl.read(kept.id_) is not None
    assert dl.outbox_list() == []


def test_reads_inside_the_block_see_its_own_writes(dl: SqliteDataLayer):
    note = _note("seen")

    with dl.transaction():
        dl.save(note)
        assert dl.read(note.id_) is not None
        assert note.id_ in {obj.id_ for obj in dl.list_objects(note.type_)}


def test_another_instance_on_the_same_store_joins_the_block(
    dl: SqliteDataLayer,
):
    """Every call on the store from this thread is in the block, not only
    the instance that opened it (a nested tree may clone the store)."""
    note = _note("clone")

    with pytest.raises(_Boom):
        with dl.transaction():
            clone = dl.clone_for_actor(_ACTOR)
            clone.save(note)
            assert dl.read(note.id_) is not None
            raise _Boom

    assert dl.read(note.id_) is None


def test_a_block_inside_another_joins_it(dl: SqliteDataLayer):
    inner, outer = _note("inner"), _note("outer")

    with pytest.raises(_Boom):
        with dl.transaction():
            with dl.transaction():
                dl.save(inner)
            dl.save(outer)
            raise _Boom

    assert dl.read(inner.id_) is None
    assert dl.read(outer.id_) is None


def test_a_helper_rollback_undoes_only_that_helpers_writes(
    dl: SqliteDataLayer,
):
    """``save_if_unchanged`` rolls back its own session when the record
    moved; the block's other writes stand (SAVEPOINT join)."""
    note = _note("cas")
    dl.save(note)
    stale = note.model_copy(update={"content": "stale"})
    other = _note("other")

    with dl.transaction():
        dl.save(other)
        assert (
            dl.save_if_unchanged(
                note.model_copy(update={"content": "new"}), stale
            )
            is False
        )
        dl.save(_note("after"))

    assert dl.read(other.id_) is not None
    assert dl.read(_note("after").id_) is not None


def test_the_enqueue_callback_fires_only_after_the_commit(
    dl: SqliteDataLayer,
):
    calls: list[str] = []
    dl.set_enqueue_callback(calls.append)
    note = _note("queued")

    with dl.transaction():
        assert dl.outbox_append(note.id_)
        assert calls == []

    assert calls == [_ACTOR]


def test_a_rolled_back_block_fires_no_enqueue_callback(dl: SqliteDataLayer):
    calls: list[str] = []
    dl.set_enqueue_callback(calls.append)

    with pytest.raises(_Boom):
        with dl.transaction():
            dl.outbox_append(_note("dropped").id_)
            raise _Boom

    assert calls == []
    assert dl.outbox_list() == []


def test_another_thread_does_not_see_or_join_an_open_block(
    dl: SqliteDataLayer,
):
    """A second thread's read neither runs inside the block nor sees its
    uncommitted writes; it sees them once the block commits."""
    note = _note("threaded")
    seen: list[bool] = []
    errors: list[BaseException] = []

    def reader() -> None:
        try:
            seen.append(dl.read(note.id_) is not None)
        except BaseException as exc:  # noqa: BLE001 — surfaced below
            errors.append(exc)

    with dl.transaction():
        dl.save(note)
        thread = threading.Thread(target=reader)
        thread.start()
        # The in-memory store's reader waits on the session lock until the
        # block ends; a file-backed reader runs now on its own connection.
        thread.join(timeout=2)
    thread.join(timeout=5)

    assert errors == []
    # In memory the reader waited for the commit; on file it read the last
    # committed state, without the block's write.
    assert seen == ([True] if ":memory:" in dl.db_url else [False])
    assert dl.read(note.id_) is not None
