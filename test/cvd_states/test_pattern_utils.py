#  Copyright (c) 2023. Carnegie Mellon University
#
#  See LICENSE for details

import unittest
from enum import IntEnum

from vultron.cvd_states.enums.utils import (
    enum_item_in_list,
    enum_list_to_string_list,
    uniq_enum_iter,
    unique_enum_list,
)


class Foo(IntEnum):
    No = 0
    Yes = 1


class Bar(IntEnum):
    No = 0
    Yes = 1


class MyTestCase(unittest.TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_enum_list_to_string_list(self):
        list_of_items = [Foo.No, Bar.Yes]
        results = enum_list_to_string_list(list_of_items)
        self.assertEqual(results, ["Foo.No", "Bar.Yes"])

    def test_enum_item_in_list(self):
        list_of_items = [Foo.No, Bar.Yes]
        for test_item in [Foo.No, Bar.Yes]:
            self.assertTrue(enum_item_in_list(test_item, list_of_items))
        for test_item in [Foo.Yes, Bar.No]:
            self.assertFalse(enum_item_in_list(test_item, list_of_items))

    def test_uniq_enum_iter(self):
        list_of_items = [Foo.No, Bar.Yes, Foo.No, Bar.Yes]
        results = list(uniq_enum_iter(list_of_items))
        self.assertEqual(results, [Foo.No, Bar.Yes])

    def test_unique_enum_list(self):
        list_of_items = [Foo.No, Bar.Yes, Foo.No, Bar.Yes]
        results = unique_enum_list(list_of_items)
        self.assertEqual(results, [Foo.No, Bar.Yes])


if __name__ == "__main__":
    unittest.main()
