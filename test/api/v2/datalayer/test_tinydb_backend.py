#  Copyright (c) 2026 Carnegie Mellon University and Contributors.
#  - see Contributors.md for a full list of Contributors
#  - see ContributionInstructions.md for information on how you can Contribute to this project
#  Vultron Multiparty Coordinated Vulnerability Disclosure Protocol Prototype is
#  licensed under a MIT (SEI)-style license, please see LICENSE.md distributed
#  with this Software or contact permission@sei.cmu.edu for full terms.
#  Created, in part, with funding and support from the United States Government
#  (see Acknowledgments file). This program may include and/or can make use of
#  certain third party source code, object code, documentation and other files
#  (“Third Party Software”). See LICENSE.md for more details.
#  Carnegie Mellon®, CERT® and CERT Coordination Center® are registered in the
#  U.S. Patent and Trademark Office by Carnegie Mellon University

import os

import pytest
from tinydb.queries import QueryInstance
from tinydb.table import Table

from vultron.api.v2.datalayer.db_record import Record
from vultron.api.v2.datalayer.tinydb_backend import TinyDbDataLayer


# Fixtures
@pytest.fixture
def tmp_db_file(tmp_path):
    db_path = tmp_path / "test_tinydb.json"
    # don't need to create the file; TinyDB will create it when opened
    return db_path


@pytest.fixture
def dl(tmp_db_file):
    # setup
    dl = TinyDbDataLayer(db_path=str(tmp_db_file))
    yield dl
    # teardown
    dl.clear_all()
    try:
        dl._db.close()
    except Exception:
        pass
    # remove db file if present
    if tmp_db_file.exists():
        tmp_db_file.unlink()
    assert not tmp_db_file.exists()


# New: record factory to DRY Record creation across tests
@pytest.fixture
def record_factory():
    def _make(id_="12345", type_="test_table", data_=None):
        data = {"field": "value"} if data_ is None else data_
        return Record(id_=id_, type_=type_, data_=data)

    return _make


# New fixture: create and persist a default record in the datastore
@pytest.fixture
def created_record(dl, record_factory):
    rec = record_factory()
    dl.create(rec)
    return rec


# Tests (split into focused test functions)
def test_init(dl):
    assert isinstance(dl, TinyDbDataLayer)
    assert hasattr(dl, "_db_path")

    # ensure db file is created on initialization
    assert os.path.exists(dl._db_path)
    # ensure tables are empty
    assert len(dl._db.tables()) == 0


def test_table(dl):
    table_name = "test_table"
    table = dl._table(table_name)
    assert table is not None
    assert isinstance(table, Table)
    assert table.name == table_name


def test_id_query(dl):
    test_id = "12345"
    query = dl._id_query(test_id)
    assert query is not None
    assert isinstance(query, QueryInstance)


def test_create(dl, record_factory):
    record = record_factory()
    # table is not in db yet
    assert record.type_ not in dl._db.tables()

    # record is not in db yet
    table = dl._table(record.type_)
    assert not table.contains(dl._id_query(record.id_))
    # create record
    dl.create(record)

    # table should now exist
    assert record.type_ in dl._db.tables()
    # record should now exist
    got_record = table.get(dl._id_query(record.id_))
    assert got_record is not None
    assert got_record["id_"] == record.id_
    assert got_record["type_"] == record.type_
    assert got_record["data_"] == record.data_


# GET tests split
def test_get_nonexistent_table(dl):
    assert "nonexistent_table" not in dl._db.tables()
    assert dl.get("nonexistent_table", "no_id") is None


def test_get_existing_record(dl, record_factory):
    record = record_factory()
    dl.create(record)
    got = dl.get(record.type_, record.id_)
    assert got is not None
    assert got["id_"] == record.id_
    assert got["type_"] == record.type_
    assert got["data_"] == record.data_


def test_get_missing_id(dl, record_factory):
    record = record_factory()
    dl.create(record)
    assert dl.get(record.type_, "no_such_id") is None


# UPDATE tests split
def test_update_existing(dl, record_factory, created_record):
    # created_record already inserted
    rec = created_record
    new_data = rec.data_.copy()
    new_data["field"] = "new_value"
    updated_record = Record(id_=rec.id_, type_=rec.type_, data_=new_data)

    updated = dl.update(id_=updated_record.id_, record=updated_record)
    assert updated
    got = dl.get(updated_record.type_, updated_record.id_)
    assert got is not None
    assert got["data_"]["field"] == "new_value"


def test_update_non_existing(dl, record_factory):
    non_existing = record_factory(id_="no_such_id")
    updated2 = dl.update(id_=non_existing.id_, record=non_existing)
    assert not updated2


def test_delete(dl, record_factory):
    record = record_factory()
    dl.create(record)
    # confirm record exists
    got = dl.get(record.type_, record.id_)
    assert got is not None

    deleted = dl.delete(record.type_, record.id_)
    assert deleted
    got_after_delete = dl.get(record.type_, record.id_)
    assert got_after_delete is None


def test_all(dl, record_factory):
    # create two records
    record1 = record_factory(id_="id1", data_={"field": "value1"})
    record2 = record_factory(id_="id2", data_={"field": "value2"})
    dl.create(record1)
    dl.create(record2)

    # all() should return both
    all_records = dl.all("test_table")
    assert len(all_records) == 2
    ids = {rec.id_ for rec in all_records}
    assert "id1" in ids
    assert "id2" in ids

    # confirm that each is a valid record
    for rec in all_records:
        assert isinstance(rec, Record)


def test_clear_table(dl, record_factory):
    # create a record
    record = record_factory()
    dl.create(record)
    # confirm record exists
    got = dl.get(record.type_, record.id_)
    assert got is not None
    # clear the table
    dl.clear_table(record.type_)
    # confirm record is gone
    got_after_clear = dl.get(record.type_, record.id_)
    assert got_after_clear is None
    # confirm table is empty
    all_records = dl.all(record.type_)
    assert len(all_records) == 0


def test_clear_all(dl, record_factory):
    # create records in two tables
    record1 = record_factory(
        id_="id1", type_="table1", data_={"field": "value1"}
    )
    record2 = record_factory(
        id_="id2", type_="table2", data_={"field": "value2"}
    )
    dl.create(record1)
    dl.create(record2)
    # confirm records exist
    got1 = dl.get(record1.type_, record1.id_)
    got2 = dl.get(record2.type_, record2.id_)
    assert got1 is not None
    assert got2 is not None
    # confirm both tables exist
    assert record1.type_ in dl._db.tables()
    assert record2.type_ in dl._db.tables()

    # clear all
    dl.clear_all()
    # confirm both records are gone
    got1_after = dl.get(record1.type_, record1.id_)
    got2_after = dl.get(record2.type_, record2.id_)
    assert got1_after is None
    assert got2_after is None
    # confirm no tables exist
    assert len(dl._db.tables()) == 0


# EXISTS tests split
def test_exists_nonexistent_table(dl):
    assert not dl.exists("nonexistent_table", "no_id")


def test_exists_after_create(dl, record_factory):
    record = record_factory()
    dl.create(record)
    assert dl.exists(record.type_, record.id_)


def test_exists_missing_id(dl, record_factory):
    record = record_factory()
    dl.create(record)
    assert not dl.exists(record.type_, "no_such_id")


def test_exists_after_delete(dl, record_factory):
    record = record_factory()
    dl.create(record)
    dl.delete(record.type_, record.id_)
    assert not dl.exists(record.type_, record.id_)
