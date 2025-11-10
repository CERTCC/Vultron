#  Copyright (c) 2025 Carnegie Mellon University and Contributors.
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

import unittest

from vultron.api.v2.data import store
from vultron.as_vocab.base.base import as_Base


class MyTestCase(unittest.TestCase):
    def setUp(self):
        self.ds = store.DataStore()

    def tearDown(self):
        self.ds.clear()

    def test_get_datalayer(self):
        ds = store.get_datalayer()
        self.assertIsInstance(ds, store.DataStore)

    def test_datastore_crud(self):
        test_obj = as_Base(name="Test Name")

        obj_id = test_obj.as_id
        # Create
        self.ds.create(test_obj)
        self.assertIn(test_obj.as_id, self.ds)

        # Read
        retrieved = self.ds.read(obj_id)
        self.assertEqual(retrieved.name, "Test Name")

        # Update
        test_obj.name = "Updated Name"
        self.ds.update(obj_id, test_obj.model_dump())
        updated = self.ds.read(obj_id)
        self.assertEqual(updated.name, "Updated Name")

        # Delete
        self.ds.delete(obj_id)
        self.assertIsNone(self.ds.read(obj_id))

    def test_datastore_duplicate_create(self):
        test_obj = as_Base(name="Test Name")
        self.ds.create(test_obj)

        with self.assertRaises(KeyError):
            self.ds.create(test_obj)  # Attempt to create duplicate

    def test_delete_nonexistent(self):
        with self.assertRaises(KeyError):
            self.ds.delete("nonexistent_id")

    def test_update_nonexistent(self):
        with self.assertRaises(KeyError):
            self.ds.update("nonexistent_id", {"name": "New Name"})

    def test_all(self):
        test_obj1 = as_Base(name="Test One")
        test_obj2 = as_Base(name="Test Two")

        self.ds.create(test_obj1)
        self.ds.create(test_obj2)

        all_items = self.ds.all()
        self.assertEqual(len(all_items), 2)
        self.assertIn(test_obj1.as_id, all_items)
        self.assertIn(test_obj2.as_id, all_items)


if __name__ == "__main__":
    unittest.main()
