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
import re
import unittest

from vultron.api.v2.data import utils

_UUID_PATTERN = re.compile(
    "[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
)


class TestUtils(unittest.TestCase):
    def setUp(self):
        # overwrite the base url for testing
        self.base_url = "https://test.vultron.local/"
        self.base_url_orig = utils.BASE_URL
        utils.BASE_URL = self.base_url

    def tearDown(self):
        pass

    def test_id_prefix(self):
        for object_type in ["Actor", "Activity", "Collection"]:
            expected_prefix = f"{self.base_url}{object_type}/"
            self.assertEqual(utils.id_prefix(object_type), expected_prefix)

    def test_make_id(self):
        for object_type in ["Actor", "Activity", "Collection"]:
            object_id = utils.make_id(object_type)
            self.assertTrue(
                object_id.startswith(f"{self.base_url}{object_type}/")
            )
            self.assertEqual(
                len(object_id.split("/")), 5
            )  # base_url, object_type, uuid
            uuid_part = object_id.split("/")[-1]
            self.assertIsNotNone(_UUID_PATTERN.fullmatch(uuid_part))

    def test_parse_id(self):
        for object_type in ["Actor", "Activity", "Collection"]:
            object_id = utils.make_id(object_type)
            parsed = utils.parse_id(object_id)
            self.assertEqual(parsed["base_url"], self.base_url)
            self.assertEqual(parsed["object_type"], object_type)
            self.assertIsNotNone(_UUID_PATTERN.fullmatch(parsed["object_id"]))

    def test_id_prefix_with_no_trailing_slash(self):
        object_type = "Actor"
        utils.BASE_URL = "https://test.vultron.local"  # no trailing slash
        #  when the BASE_URL has no trailing slash, we should still get a prefix as if it did
        self.assertTrue(self.base_url.endswith("/"))
        expected_prefix = f"{self.base_url}{object_type}/"

        self.assertEqual(utils.id_prefix(object_type), expected_prefix)


if __name__ == "__main__":
    unittest.main()
