#  Copyright (c) 2023-2024 Carnegie Mellon University and Contributors.
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

from vultron.as_vocab.base.objects.activities.transitive import as_Create


class MyTestCase(unittest.TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_something(self):
        data = {
            "@context": "https://www.w3.org/ns/activitystreams",
            "type": "Create",
            "actor": "https://example.com/actor",
            "object": {"type": "Note", "content": "Hello, World!"},
        }
        del data["@context"]
        del data["type"]
        # data["as_type"] = data.pop("type")
        data["as_object"] = data.pop("object")
        create = as_Create(**data)
        print(create)


if __name__ == "__main__":
    unittest.main()
