#  Copyright (c) 2024-2025 Carnegie Mellon University and Contributors.
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
import json
import os
import tempfile
import unittest

import vultron.wire.as2.vocab.examples.vocab_examples as examples
from vultron.wire.as2.vocab.base.base import as_Base


class Foo(as_Base):
    bar: str = "baz"


class TestVocabUtils(unittest.TestCase):
    def test_json2md(self):
        foo = Foo(bar="baz")

        txt = examples.json2md(foo)
        self.assertTrue(txt.startswith("```json"))
        self.assertTrue(txt.endswith("```"))
        self.assertTrue("bar" in txt)
        self.assertTrue("baz" in txt)

    def test_obj_to_file(self):
        foo = Foo(bar="baz")
        with tempfile.TemporaryDirectory() as tmpdirname:
            filename = tmpdirname + "/test.md"
            self.assertFalse(os.path.exists(filename))
            examples.obj_to_file(foo, filename)
            self.assertTrue(os.path.exists(filename))

            with open(filename, "r") as f:
                obj = json.load(f)
            self.assertEqual(obj["bar"], "baz")


if __name__ == "__main__":
    unittest.main()
