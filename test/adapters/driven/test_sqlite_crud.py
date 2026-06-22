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

"""Tests for SqliteDataLayer CRUD operations.

Covers: create, read, update, delete, save, exists, ping, all, get_all,
by_type, count_all, clear_table, and clear_all.
Fixtures (dl, record_factory, created_record, tmp_db_url) come from conftest.
"""

import os

import pytest

from vultron.adapters.driven.db_record import Record
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer

# ---------------------------------------------------------------------------
# Initialisation
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_database_initialization_creates_db_file(tmp_db_url):
    """Creating a file-backed SqliteDataLayer creates the SQLite file."""
    instance = SqliteDataLayer(tmp_db_url)
    db_path = tmp_db_url.replace("sqlite:///", "")
    assert os.path.exists(db_path)
    instance.close()


def test_database_initialization_in_memory():
    """In-memory DataLayer can be created and is operational."""
    instance = SqliteDataLayer("sqlite:///:memory:")
    assert instance.ping()
    instance.close()


# ---------------------------------------------------------------------------
# create / read / get
# ---------------------------------------------------------------------------


def test_create_inserts_record(dl, record_factory):
    record = record_factory()
    dl.create(record)
    got = dl.get(record.type_, record.id_)
    assert got is not None
    assert got["id_"] == record.id_
    assert got["type_"] == record.type_
    assert got["data_"] == record.data_


def test_create_raises_on_duplicate_id(dl, record_factory):
    record = record_factory()
    dl.create(record)
    with pytest.raises(ValueError):
        dl.create(record)


def test_get_returns_none_for_nonexistent_type(dl):
    assert dl.get("nonexistent_table", "no_id") is None


def test_get_returns_none_for_missing_id(dl, record_factory):
    record = record_factory()
    dl.create(record)
    assert dl.get(record.type_, "no_such_id") is None


def test_read_returns_object(dl, record_factory):
    from vultron.wire.as2.vocab.base.objects.object_types import as_Note

    note = as_Note(content="Test Content")
    dl.save(note)
    result = dl.read(note.id_)
    assert result is not None
    assert result.id_ == note.id_  # type: ignore[union-attr]


def test_read_returns_none_for_missing_id(dl):
    assert dl.read("urn:uuid:does-not-exist") is None


def test_read_supports_bare_uuid(dl):
    from vultron.wire.as2.vocab.base.objects.object_types import as_Note

    note = as_Note(content="Bare UUID test")
    dl.save(note)
    bare = note.id_.replace("urn:uuid:", "")
    result = dl.read(bare)
    assert result is not None
    assert result.id_ == note.id_  # type: ignore[union-attr]


# ---------------------------------------------------------------------------
# update / save / delete
# ---------------------------------------------------------------------------


def test_update_updates_existing_record_data(dl, created_record):
    rec = created_record
    new_data = rec.data_.copy()
    new_data["field"] = "new_value"
    updated_record = Record(id_=rec.id_, type_=rec.type_, data_=new_data)

    updated = dl.update(id_=updated_record.id_, record=updated_record)
    assert updated
    got = dl.get(updated_record.type_, updated_record.id_)
    assert got is not None
    assert got["data_"]["field"] == "new_value"


def test_update_returns_false_for_non_existing_id(dl, record_factory):
    non_existing = record_factory(id_="no_such_id")
    updated = dl.update(id_=non_existing.id_, record=non_existing)
    assert not updated


def test_save_inserts_new_object(dl):
    from vultron.wire.as2.vocab.base.objects.object_types import as_Note

    note = as_Note(content="Save test")
    dl.save(note)
    result = dl.read(note.id_)
    assert result is not None


def test_save_overwrites_existing_object(dl):
    from vultron.wire.as2.vocab.base.objects.object_types import as_Note

    note = as_Note(content="Original content")
    dl.save(note)
    note2 = as_Note(id_=note.id_, content="Updated content")
    dl.save(note2)
    result = dl.read(note.id_)
    assert result is not None
    assert result.content == "Updated content"  # type: ignore[union-attr]


def test_delete_removes_record_and_returns_true(dl, record_factory):
    record = record_factory()
    dl.create(record)
    deleted = dl.delete(record.type_, record.id_)
    assert deleted
    assert dl.get(record.type_, record.id_) is None


def test_delete_returns_false_for_nonexistent_record(dl, record_factory):
    record = record_factory()
    assert not dl.delete(record.type_, record.id_)


# ---------------------------------------------------------------------------
# all / get_all / by_type / count_all
# ---------------------------------------------------------------------------


def test_all_returns_all_records_for_table(dl, record_factory):
    record1 = record_factory(id_="id1", data_={"field": "value1"})
    record2 = record_factory(id_="id2", data_={"field": "value2"})
    dl.create(record1)
    dl.create(record2)

    all_records = dl.all("test_table")
    assert len(all_records) == 2
    ids = {rec.id_ for rec in all_records}  # type: ignore[union-attr]
    assert "id1" in ids
    assert "id2" in ids
    for rec in all_records:
        assert isinstance(rec, Record)


def test_all_without_table_returns_dict_of_objects(dl):
    from vultron.wire.as2.vocab.base.objects.object_types import as_Note

    note = as_Note(content="All test")
    dl.save(note)
    result = dl.all()
    assert isinstance(result, dict)
    assert note.id_ in result


def test_get_all_returns_list_of_dicts(dl, record_factory):
    rec = record_factory()
    dl.create(rec)
    result = dl.get_all("test_table")
    assert isinstance(result, list)
    assert len(result) == 1
    assert result[0]["id_"] == rec.id_


def test_by_type_returns_dict(dl, record_factory):
    rec = record_factory()
    dl.create(rec)
    result = dl.by_type("test_table")
    assert isinstance(result, dict)
    assert rec.id_ in result


def test_count_all_returns_dict_with_counts(dl, record_factory):
    rec = record_factory()
    dl.create(rec)
    counts = dl.count_all()
    assert isinstance(counts, dict)
    assert "_default" in counts
    assert counts["test_table"] == 1


# ---------------------------------------------------------------------------
# clear_table / clear_all
# ---------------------------------------------------------------------------


def test_clear_table_removes_all_records(dl, record_factory):
    record = record_factory()
    dl.create(record)
    dl.clear_table(record.type_)
    assert dl.get(record.type_, record.id_) is None
    assert len(dl.all(record.type_)) == 0


def test_clear_all_removes_all_records(dl, record_factory):
    record1 = record_factory(id_="id1", type_="table1")
    record2 = record_factory(id_="id2", type_="table2")
    dl.create(record1)
    dl.create(record2)
    dl.clear_all()
    assert dl.get(record1.type_, record1.id_) is None
    assert dl.get(record2.type_, record2.id_) is None


# ---------------------------------------------------------------------------
# exists / ping
# ---------------------------------------------------------------------------


def test_exists_returns_false_for_nonexistent_type(dl):
    assert not dl.exists("nonexistent_table", "no_id")


def test_exists_returns_true_after_create(dl, record_factory):
    record = record_factory()
    dl.create(record)
    assert dl.exists(record.type_, record.id_)


def test_exists_returns_false_for_missing_id(dl, record_factory):
    record = record_factory()
    dl.create(record)
    assert not dl.exists(record.type_, "no_such_id")


def test_exists_returns_false_after_delete(dl, record_factory):
    record = record_factory()
    dl.create(record)
    dl.delete(record.type_, record.id_)
    assert not dl.exists(record.type_, record.id_)


def test_ping_returns_true(dl):
    assert dl.ping() is True
