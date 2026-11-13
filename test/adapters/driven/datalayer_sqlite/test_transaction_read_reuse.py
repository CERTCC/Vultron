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

"""A ``dl.transaction()`` block fetches each row it reads once (#5344).

Inside a block nothing but the block's own writes can change the store, so a
row it read stays current until the block writes it.  These tests hold that a
second read of a row is not fetched again, that every kind of object-row
write makes the next read fetch what the write left, that a SAVEPOINT which
rolls back leaves no read of an undone write behind, and that nothing kept
outlives the block.  Each runs on an in-memory and a file-backed store.
"""

from collections import Counter
from collections.abc import Callable

import pytest

from test.support.objects import make
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer, crud
from vultron.adapters.driven.db_record import object_to_record
from vultron.core.models.note import VultronNote
from vultron.core.ports.datalayer import StorableRecord
from vultron.wire.as2.vocab.base.objects.object_types import as_Note

pytestmark = pytest.mark.spec("DL-02-008", "DL-02-011")

_ID = "https://example.org/notes/kept"


class _Boom(Exception):
    """Raised inside a block to make it roll back."""


@pytest.fixture
def fetches(monkeypatch: pytest.MonkeyPatch) -> Counter[str]:
    """How many times each id is fetched from the store, by any read."""
    counts: Counter[str] = Counter()
    original = crud._select_row

    def _counting(connection, object_id):
        counts[object_id] += 1
        return original(connection, object_id)

    monkeypatch.setattr(crud, "_select_row", _counting)
    return counts


def _note(content: str) -> as_Note:
    return make(as_Note, id_=_ID, content=content)


def _content(dl: SqliteDataLayer) -> str | None:
    got = dl.read(_ID)
    if got is None:
        return None
    assert isinstance(got, VultronNote)
    return got.content


def test_a_row_read_twice_in_a_block_is_fetched_once(
    dl: SqliteDataLayer, fetches: Counter[str]
):
    dl.save(_note("first"))

    with dl.transaction():
        assert _content(dl) == "first"
        assert _content(dl) == "first"
        assert _content(dl) == "first"

    assert fetches[_ID] == 1


def test_a_read_outside_a_block_fetches_every_time(
    dl: SqliteDataLayer, fetches: Counter[str]
):
    dl.save(_note("first"))

    _content(dl)
    _content(dl)

    assert fetches[_ID] == 2


def test_nothing_kept_outlives_the_block(
    dl: SqliteDataLayer, fetches: Counter[str]
):
    dl.save(_note("first"))
    with dl.transaction():
        _content(dl)
    dl.save(_note("after the block"))

    with dl.transaction():
        assert _content(dl) == "after the block"

    assert fetches[_ID] == 2


def test_a_missing_row_is_fetched_again_once_written(dl: SqliteDataLayer):
    with dl.transaction():
        assert dl.read(_ID) is None
        dl.create(_note("created"))
        assert _content(dl) == "created"


def _save(dl: SqliteDataLayer) -> None:
    dl.save(_note("written"))


def _save_many(dl: SqliteDataLayer) -> None:
    dl.save_many([_note("written")])


def _update(dl: SqliteDataLayer) -> None:
    rec = object_to_record(_note("written"))
    assert dl.update(
        _ID, StorableRecord(id_=rec.id_, type_=rec.type_, data_=rec.data_)
    )


def _save_if_unchanged(dl: SqliteDataLayer) -> None:
    current = dl.read(_ID)
    assert current is not None
    assert dl.save_if_unchanged(_note("written"), current)


def _delete(dl: SqliteDataLayer) -> None:
    assert dl.delete("Note", _ID)


def _clear_table(dl: SqliteDataLayer) -> None:
    dl.clear_table("Note")


def _clear_all(dl: SqliteDataLayer) -> None:
    dl.clear_all()


@pytest.mark.parametrize(
    ("write", "after"),
    [
        (_save, "written"),
        (_save_many, "written"),
        (_update, "written"),
        (_save_if_unchanged, "written"),
        (_delete, None),
        (_clear_table, None),
        (_clear_all, None),
    ],
    ids=lambda value: getattr(value, "__name__", str(value)),
)
def test_a_read_after_a_write_in_the_block_returns_what_the_write_left(
    dl: SqliteDataLayer,
    write: Callable[[SqliteDataLayer], None],
    after: str | None,
):
    dl.save(_note("before"))

    with dl.transaction():
        assert _content(dl) == "before"
        write(dl)
        assert _content(dl) == after

    assert _content(dl) == after


def test_a_read_after_a_rolled_back_savepoint_returns_the_row_it_undid(
    dl: SqliteDataLayer,
):
    dl.save(_note("before"))

    with dl.transaction():
        assert _content(dl) == "before"
        with pytest.raises(_Boom):
            with dl.transaction():
                dl.save(_note("undone"))
                assert _content(dl) == "undone"
                raise _Boom
        assert _content(dl) == "before"


def test_a_write_by_another_instance_on_the_store_is_seen(
    dl: SqliteDataLayer,
):
    other = dl.clone_for_actor(dl.actor_id)
    dl.save(_note("before"))

    with dl.transaction():
        assert _content(dl) == "before"
        other.save(_note("by the other instance"))
        assert _content(dl) == "by the other instance"


def test_each_read_of_a_kept_row_decodes_its_own_data(dl: SqliteDataLayer):
    """A caller that changes the dict it is handed changes no later read."""
    dl.save(_note("before"))

    with dl.transaction(), dl._connection() as connection:
        first = crud._stored_row(dl, connection, _ID)
        assert first is not None
        first.data["content"] = "changed by a caller"
        second = crud._stored_row(dl, connection, _ID)

    assert second is not None
    assert second.data["content"] == "before"
