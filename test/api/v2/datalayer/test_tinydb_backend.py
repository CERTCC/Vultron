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

import os.path
import unittest
from tempfile import TemporaryDirectory, TemporaryFile

from tinydb.queries import QueryInstance
from tinydb.table import Table

from vultron.api.v2.datalayer.db_record import Record
from vultron.api.v2.datalayer.tinydb_backend import TinyDbDataLayer


class MyTestCase(unittest.TestCase):
    def setUp(self) -> None:
        # temp dir for db file
        self.tmpdir = TemporaryDirectory()
        self.dbfile = TemporaryFile(dir=self.tmpdir.name)
        self.dbfile.close()
        self.dl = TinyDbDataLayer(db_path=str(self.dbfile.name))

    def tearDown(self) -> None:
        self.dl.clear_all()
        self.dl._db.close()
        self.tmpdir.cleanup()
        self.assertFalse(os.path.exists(self.tmpdir.name))

    def test_init(self):
        self.assertIsInstance(self.dl, TinyDbDataLayer)
        self.assertTrue(hasattr(self.dl, "_db_path"))

        # ensure db file is created on initialization
        self.assertTrue(os.path.exists(self.dl._db_path))
        # ensure tables are empty
        self.assertEqual(len(self.dl._db.tables()), 0)

    def test_table(self):
        table_name = "test_table"
        table = self.dl._table(table_name)
        self.assertIsNotNone(table)
        self.assertIsInstance(table, Table)
        self.assertEqual(table.name, table_name)

    def test_id_query(self):
        test_id = "12345"
        query = self.dl._id_query(test_id)
        self.assertIsNotNone(query)
        self.assertIsInstance(query, QueryInstance)

    def test_create(self):
        record = Record(
            id_="12345", type_="test_table", data_={"field": "value"}
        )
        # table is not in db yet
        self.assertNotIn(record.type_, self.dl._db.tables())

        # record is not in db yet
        table = self.dl._table(record.type_)
        self.assertFalse(table.contains(self.dl._id_query(record.id_)))
        # create record
        self.dl.create(record)

        # table should now exist
        self.assertIn(record.type_, self.dl._db.tables())
        # record should now exist
        got_record = table.get(self.dl._id_query(record.id_))
        self.assertIsNotNone(got_record)
        self.assertEqual(got_record["id_"], record.id_)
        self.assertEqual(got_record["type_"], record.type_)
        self.assertEqual(got_record["data_"], record.data_)

    def test_get(self):
        # test get non-existing
        self.assertNotIn("nonexistent_table", self.dl._db.tables())
        got_none = self.dl.get("nonexistent_table", "no_id")
        self.assertIsNone(got_none)

        record = Record(
            id_="12345", type_="test_table", data_={"field": "value"}
        )
        self.dl.create(record)

        got = self.dl.get(record.type_, record.id_)
        self.assertIsNotNone(got)
        self.assertEqual(got["id_"], record.id_)
        self.assertEqual(got["type_"], record.type_)
        self.assertEqual(got["data_"], record.data_)

        # test get existing table, non-existing id
        self.assertIn(record.type_, self.dl._db.tables())
        got_none2 = self.dl.get(record.type_, "no_such_id")
        self.assertIsNone(got_none2)

    def test_update(self):
        record = Record(
            id_="12345", type_="test_table", data_={"field": "value"}
        )
        self.dl.create(record)
        # update existing record
        new_data = record.data_.copy()
        new_data["field"] = "new_value"

        updated_record = Record(
            id_=record.id_, type_=record.type_, data_=new_data
        )
        updated = self.dl.update(id_=updated_record.id_, record=updated_record)
        self.assertTrue(updated)
        got = self.dl.get(updated_record.type_, updated_record.id_)
        self.assertIsNotNone(got)
        self.assertEqual(got["data_"]["field"], "new_value")
        # update non-existing record
        non_existing_record = Record(
            id_="no_such_id", type_="test_table", data_={"field": "value"}
        )
        updated2 = self.dl.update(
            id_=non_existing_record.id_, record=non_existing_record
        )
        self.assertFalse(updated2)

    def test_delete(self):
        record = Record(
            id_="12345", type_="test_table", data_={"field": "value"}
        )
        self.dl.create(record)
        # confirm record exists
        got = self.dl.get(record.type_, record.id_)
        self.assertIsNotNone(got)

        deleted = self.dl.delete(record.type_, record.id_)
        self.assertTrue(deleted)
        got_after_delete = self.dl.get(record.type_, record.id_)
        self.assertIsNone(got_after_delete)

    def test_all(self):
        # create two records
        record1 = Record(
            id_="id1", type_="test_table", data_={"field": "value1"}
        )
        record2 = Record(
            id_="id2", type_="test_table", data_={"field": "value2"}
        )
        self.dl.create(record1)
        self.dl.create(record2)

        # all() should return both
        all_records = self.dl.all("test_table")
        self.assertEqual(len(all_records), 2)
        ids = {rec.id_ for rec in all_records}
        self.assertIn("id1", ids)
        self.assertIn("id2", ids)

        # confirm that each is a valid record
        for rec in all_records:
            self.assertIsInstance(rec, Record)

    def test_clear_table(self):
        # create a record
        record = Record(
            id_="12345", type_="test_table", data_={"field": "value"}
        )
        self.dl.create(record)
        # confirm record exists
        got = self.dl.get(record.type_, record.id_)
        self.assertIsNotNone(got)
        # clear the table
        self.dl.clear_table(record.type_)
        # confirm record is gone
        got_after_clear = self.dl.get(record.type_, record.id_)
        self.assertIsNone(got_after_clear)
        # confirm table is empty
        all_records = self.dl.all(record.type_)
        self.assertEqual(len(all_records), 0)

    def test_clear_all(self):
        # create records in two tables
        record1 = Record(id_="id1", type_="table1", data_={"field": "value1"})
        record2 = Record(id_="id2", type_="table2", data_={"field": "value2"})
        self.dl.create(record1)
        self.dl.create(record2)
        # confirm records exist
        got1 = self.dl.get(record1.type_, record1.id_)
        got2 = self.dl.get(record2.type_, record2.id_)
        self.assertIsNotNone(got1)
        self.assertIsNotNone(got2)
        # confirm both tables exist
        self.assertIn(record1.type_, self.dl._db.tables())
        self.assertIn(record2.type_, self.dl._db.tables())

        # clear all
        self.dl.clear_all()
        # confirm both records are gone
        got1_after = self.dl.get(record1.type_, record1.id_)
        got2_after = self.dl.get(record2.type_, record2.id_)
        self.assertIsNone(got1_after)
        self.assertIsNone(got2_after)
        # confirm no tables exist
        self.assertEqual(len(self.dl._db.tables()), 0)

    def test_exists(self):
        # test non-existing
        self.assertFalse(self.dl.exists("nonexistent_table", "no_id"))
        record = Record(
            id_="12345", type_="test_table", data_={"field": "value"}
        )
        self.dl.create(record)
        # test existing
        self.assertTrue(self.dl.exists(record.type_, record.id_))
        # test existing table, non-existing id
        self.assertFalse(self.dl.exists(record.type_, "no_such_id"))
        # remove record and test again
        self.dl.delete(record.type_, record.id_)
        self.assertFalse(self.dl.exists(record.type_, record.id_))


if __name__ == "__main__":
    unittest.main()
