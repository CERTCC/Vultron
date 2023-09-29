#  Copyright (c) 2023 Carnegie Mellon University and Contributors.
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
from enum import IntEnum

from vultron.case_states.enums.utils import (
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
