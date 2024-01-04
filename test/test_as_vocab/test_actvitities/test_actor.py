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
import json
import unittest
from typing import Type

import vultron.as_vocab.activities.actor as actor  # noqa: F401
from vultron.as_vocab.base.objects.activities.base import as_Activity
from vultron.as_vocab.base.objects.activities.transitive import (
    as_Accept,
    as_Offer,
    as_Reject,
    as_TransitiveActivity,
)
from vultron.as_vocab.base.objects.actors import (
    as_Application,
    as_Group,
    as_Organization,
    as_Person,
    as_Service,
)
from vultron.as_vocab.objects.vulnerability_case import VulnerabilityCase

ACTOR_CLASSES = [
    as_Application,
    as_Group,
    as_Person,
    as_Service,
    as_Organization,
]


class MyTestCase(unittest.TestCase):
    def test_recommend_actor(self):
        cls = actor.RecommendActor
        expect_class = as_Offer
        expect_type = "Offer"
        self._test_base_actor_activity(cls, expect_class, expect_type)

    def test_accept_actor_recommendation(self):
        cls = actor.AcceptActorRecommendation
        expect_class = as_Accept
        expect_type = "Accept"
        self._test_base_actor_activity(cls, expect_class, expect_type)

    def test_reject_actor_recommendation(self):
        cls = actor.RejectActorRecommendation
        expect_class = as_Reject
        expect_type = "Reject"
        self._test_base_actor_activity(cls, expect_class, expect_type)

    def _test_base_actor_activity(
        self,
        cls: Type[as_TransitiveActivity],
        expect_class: Type[as_TransitiveActivity],
        expect_type: str,
    ):
        for actor_class in ACTOR_CLASSES:
            _actor = actor_class()
            _case = VulnerabilityCase()
            _object = cls(as_object=_actor, target=_case)

            # check activity is correct type
            self.assertIsInstance(_object, as_Activity)
            self.assertIsInstance(_object, expect_class)
            self.assertIsInstance(_object, cls)
            # check the _object of the activity is correct instance
            self.assertEqual(_object.as_object, _actor)

            # check json
            _json = _object.to_json()
            self.assertIn("object", _json)
            self.assertIn("type", _json)
            self.assertIn("target", _json)

            # check json loads back in correctly
            reloaded = json.loads(_json)
            # the type should be Reject, not RejectActorRecommendation
            self.assertEqual(reloaded["type"], expect_type)
            self.assertEqual(reloaded["object"], json.loads(_actor.to_json()))
            self.assertEqual(reloaded["target"], json.loads(_case.to_json()))


if __name__ == "__main__":
    unittest.main()
