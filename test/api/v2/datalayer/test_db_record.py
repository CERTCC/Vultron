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

import unittest

from vultron.api.v2.datalayer.db_record import Record


class MyTestCase(unittest.TestCase):
    def setUp(self) -> None:
        pass

    def tearDown(self) -> None:
        pass

    def test_record_attributes(self):
        # record should have an id_, type_, and data_ attributes
        record = Record(id_="123", type_="TestType", data={"key": "value"})
        self.assertEqual(record.id_, "123")
        self.assertEqual(record.type_, "TestType")
        self.assertEqual(record.data_, {"key": "value"})

    def test_object_to_record(self):
        from vultron.as_vocab.base.base import as_Base

        obj = as_Base(
            as_id="test-id", as_type="BaseObject", name="Test Object"
        )

        from vultron.api.v2.datalayer.db_record import object_to_record

        record = object_to_record(obj)
        self.assertEqual(record.id_, obj.as_id)
        self.assertEqual(record.type_, obj.as_type)
        self.assertEqual(record.data_, obj.model_dump())

    def test_record_to_object(self):
        from vultron.as_vocab.base.objects.object_types import as_Note

        obj = as_Note(content="Test Content")

        from vultron.api.v2.datalayer.db_record import (
            object_to_record,
            record_to_object,
        )

        record = object_to_record(obj)
        self.assertIsInstance(record, Record)

        reconstructed_obj = record_to_object(record)
        self.assertIsInstance(reconstructed_obj, as_Note)

        self.assertEqual(reconstructed_obj.as_id, obj.as_id)
        self.assertEqual(reconstructed_obj.as_type, obj.as_type)
        self.assertEqual(reconstructed_obj.model_dump(), obj.model_dump())


if __name__ == "__main__":
    unittest.main()
