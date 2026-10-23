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

"""``SqliteDataLayer.save_if_unchanged`` — the store's compare-and-set (#4102).

A read-modify-write through ``save()`` has an unguarded window: a write that
lands between the read and the save is overwritten without anyone being told.
These tests interleave a second writer at each point in that window and assert
the compare-and-set refuses rather than overwriting it (EP-02-004).
"""

import pytest

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.models.actor import CoreActor, VultronOrganization

_ACTOR_ID = "https://test.example/api/v2/actors/test-actor"


def _stored(dl: SqliteDataLayer) -> CoreActor:
    record = dl.read(_ACTOR_ID)
    assert isinstance(record, CoreActor)
    return record


def _renamed(actor: CoreActor, name: str) -> CoreActor:
    return actor.model_copy(update={"name": name})


@pytest.fixture
def seeded(dl: SqliteDataLayer) -> CoreActor:
    """The profile as a caller reads it before modifying it."""
    dl.save(VultronOrganization(id_=_ACTOR_ID, name="Original"))
    return _stored(dl)


class TestSaveIfUnchanged:
    @pytest.mark.spec("DL-02-003")
    @pytest.mark.spec("EP-02-004")
    def test_writes_when_the_stored_record_is_the_one_read(self, dl, seeded):
        assert dl.save_if_unchanged(_renamed(seeded, "Mine"), seeded) is True
        assert _stored(dl).name == "Mine"

    @pytest.mark.spec("DL-02-003")
    @pytest.mark.spec("EP-02-004")
    def test_refuses_and_keeps_a_write_that_landed_after_the_read(
        self, dl, seeded
    ):
        dl.save(_renamed(seeded, "Theirs"))

        assert dl.save_if_unchanged(_renamed(seeded, "Mine"), seeded) is False
        assert _stored(dl).name == "Theirs"

    @pytest.mark.spec("DL-02-003")
    def test_refuses_a_record_that_is_not_stored(self, dl):
        absent = VultronOrganization(id_=_ACTOR_ID, name="Original")

        assert dl.save_if_unchanged(_renamed(absent, "Mine"), absent) is False
        assert dl.read(_ACTOR_ID) is None

    @pytest.mark.spec("DL-02-003")
    def test_rejects_a_replacement_for_a_different_record(self, dl, seeded):
        other = VultronOrganization(
            id_="https://test.example/api/v2/actors/other", name="Other"
        )

        with pytest.raises(ValueError, match="different records"):
            dl.save_if_unchanged(other, seeded)
        assert _stored(dl).name == "Original"


@pytest.mark.spec("DL-02-003")
@pytest.mark.spec("EP-02-004")
def test_refuses_a_write_committed_between_its_own_read_and_write(
    file_dl: SqliteDataLayer, monkeypatch
):
    """A file-backed store opens one connection per ``Session``.

    So another writer can commit after the compare-and-set has read and
    compared the row but before its ``UPDATE`` runs.  The hook lands that
    write at exactly that point — ``_from_row`` is what the compare-and-set
    calls between the two — and the conditional ``UPDATE`` must then match no
    row, so the concurrent write survives.
    """
    file_dl.save(VultronOrganization(id_=_ACTOR_ID, name="Original"))
    expected = _stored(file_dl)
    real_from_row = file_dl._from_row
    interleaved: list[bool] = []

    def from_row_then_concurrent_write(row):
        current = real_from_row(row)
        if not interleaved:
            interleaved.append(True)
            file_dl.save(_renamed(expected, "Theirs"))
        return current

    monkeypatch.setattr(file_dl, "_from_row", from_row_then_concurrent_write)

    refused = file_dl.save_if_unchanged(_renamed(expected, "Mine"), expected)

    monkeypatch.undo()
    assert interleaved == [True]
    assert refused is False
    assert _stored(file_dl).name == "Theirs"
