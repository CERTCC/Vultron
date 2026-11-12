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

"""``SqliteDataLayer.read`` runs a Core ``select`` on a connection (#4969).

A read used to open an ORM ``Session`` and call ``Session.get``, which was
most of a read's cost.  It now runs one prebuilt primary-key ``select`` on a
bare connection: the transaction's own inside ``dl.transaction()``, a pool
connection under the session lock otherwise.  These tests hold what that
read must still do, on an in-memory and a file-backed store, and that it
opens no ``Session``.
"""

from collections.abc import Iterator
from pathlib import Path

import pytest

from test.support.objects import make
from vultron.adapters.driven.datalayer_sqlite import (
    SqliteDataLayer,
    datalayer as dl_module,
)
from vultron.core.models.note import VultronNote
from vultron.wire.as2.vocab.base.objects.object_types import as_Note

pytestmark = pytest.mark.spec("DL-01-001", "DL-02-008")

_ACTOR = "https://example.org/actors/read-path-actor"


@pytest.fixture(params=["memory", "file"])
def dl(
    request: pytest.FixtureRequest, tmp_path: Path
) -> Iterator[SqliteDataLayer]:
    url = (
        "sqlite:///:memory:"
        if request.param == "memory"
        else f"sqlite:///{tmp_path / 'read.db'}"
    )
    store = SqliteDataLayer(url, actor_id=_ACTOR)
    try:
        yield store
    finally:
        store.close()


def _note(name: str) -> as_Note:
    return make(as_Note, id_=f"https://example.org/notes/{name}", content=name)


def test_a_read_returns_the_stored_object(dl: SqliteDataLayer):
    note = _note("stored")
    dl.save(note)

    got = dl.read(note.id_)

    assert isinstance(got, VultronNote)
    assert got.id_ == note.id_
    assert got.content == "stored"


def test_a_missing_id_reads_none_or_raises(dl: SqliteDataLayer):
    missing = "https://example.org/notes/missing"

    assert dl.read(missing) is None
    with pytest.raises(KeyError, match="missing"):
        dl.read(missing, raise_on_missing=True)


def test_a_read_inside_the_block_sees_a_write_made_earlier_in_it(
    dl: SqliteDataLayer,
):
    note = _note("in-block")
    with dl.transaction():
        dl.save(note)
        got = dl.read(note.id_)
        assert got is not None and got.id_ == note.id_
        dl.save(_note("after-read"))

    assert dl.read(note.id_) is not None
    assert dl.read("https://example.org/notes/after-read") is not None


def test_a_read_inside_the_block_sees_an_overwrite_made_earlier_in_it(
    dl: SqliteDataLayer,
):
    dl.save(_note("rewritten"))
    with dl.transaction():
        dl.save(
            make(
                as_Note,
                id_="https://example.org/notes/rewritten",
                content="second",
            )
        )
        got = dl.read("https://example.org/notes/rewritten")
        assert isinstance(got, VultronNote)
        assert got.content == "second"


def test_a_read_opens_no_session(
    dl: SqliteDataLayer, monkeypatch: pytest.MonkeyPatch
):
    note = _note("no-session")
    dl.save(note)

    def _refuse(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("dl.read opened an ORM Session")

    monkeypatch.setattr(dl_module, "Session", _refuse)

    assert dl.read(note.id_) is not None
    with dl.transaction():
        assert dl.read(note.id_) is not None
