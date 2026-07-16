#  Copyright (c) 2026 Carnegie Mellon University and Contributors.
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
"""
Per-function unit tests for the six actor vocab example functions in
``vultron.wire.as2.vocab.examples.actor``.

Each test asserts:
- Return type matches the declared return annotation.
- ``actor`` field is set to the expected actor ID.
- ``to`` field is set to the expected recipient(s).
- ``object_`` references the expected actor or CaseParticipant.
"""

import unittest
from typing import cast

from vultron.wire.as2.vocab.activities.actor import (
    _OfferCaseParticipantActivity,
    _RecommendActorActivity,
)
from vultron.wire.as2.vocab.base.objects.activities.transitive import (
    as_Accept,
    as_Offer,
    as_Reject,
)
from vultron.wire.as2.vocab.objects.case_participant import CaseParticipant
from vultron.wire.as2.vocab.examples._base import (
    _CASE_ACTOR,
    _COORDINATOR,
    case,
    finder,
    vendor,
)
from vultron.wire.as2.vocab.examples.actor import (
    accept_actor_recommendation,
    accept_case_participant_offer,
    offer_case_participant,
    recommend_actor,
    reject_actor_recommendation,
    reject_case_participant_offer,
)


class TestRecommendActor(unittest.TestCase):
    def setUp(self):
        self.activity = recommend_actor()
        self.finder = finder()
        self.vendor = vendor()
        self.coordinator = _COORDINATOR
        self.case = case()

    def test_return_type(self):
        self.assertIsInstance(self.activity, as_Offer)

    def test_actor_is_finder(self):
        self.assertEqual(self.activity.actor, self.finder.id_)

    def test_to_is_vendor(self):
        self.assertEqual(self.activity.to, self.vendor.id_)

    def test_object_is_recommended_actor(self):
        self.assertEqual(self.activity.object_, self.coordinator)

    def test_target_is_case(self):
        self.assertEqual(self.activity.target, self.case.id_)


class TestAcceptActorRecommendation(unittest.TestCase):
    def setUp(self):
        self.activity = accept_actor_recommendation()
        self.vendor = vendor()
        self.finder = finder()
        self.case = case()

    def test_return_type(self):
        self.assertIsInstance(self.activity, as_Accept)

    def test_actor_is_vendor(self):
        self.assertEqual(self.activity.actor, self.vendor.id_)

    def test_to_is_finder(self):
        self.assertEqual(self.activity.to, self.finder.id_)

    def test_object_is_recommendation_offer(self):
        self.assertIsInstance(self.activity.object_, _RecommendActorActivity)

    def test_target_is_case(self):
        self.assertEqual(self.activity.target, self.case.id_)


class TestRejectActorRecommendation(unittest.TestCase):
    def setUp(self):
        self.activity = reject_actor_recommendation()
        self.vendor = vendor()
        self.finder = finder()
        self.case = case()

    def test_return_type(self):
        self.assertIsInstance(self.activity, as_Reject)

    def test_actor_is_vendor(self):
        self.assertEqual(self.activity.actor, self.vendor.id_)

    def test_to_is_finder(self):
        self.assertEqual(self.activity.to, self.finder.id_)

    def test_object_is_recommendation_offer(self):
        self.assertIsInstance(self.activity.object_, _RecommendActorActivity)

    def test_target_is_case(self):
        self.assertEqual(self.activity.target, self.case.id_)


class TestOfferCaseParticipant(unittest.TestCase):
    def setUp(self):
        self.activity = offer_case_participant()
        self.case_actor = _CASE_ACTOR
        self.vendor = vendor()
        self.coordinator = _COORDINATOR
        self.case = case()

    def test_return_type(self):
        self.assertIsInstance(self.activity, as_Offer)

    def test_actor_is_case_actor(self):
        self.assertEqual(self.activity.actor, self.case_actor.id_)

    def test_to_is_vendor(self):
        self.assertEqual(self.activity.to, [self.vendor.id_])

    def test_object_is_case_participant(self):
        participant = cast(CaseParticipant, self.activity.object_)
        self.assertIsInstance(participant, CaseParticipant)

    def test_participant_attributed_to_coordinator(self):
        participant = cast(CaseParticipant, self.activity.object_)
        attr = participant.attributed_to
        attr_id = getattr(attr, "id_", None) or attr
        self.assertEqual(attr_id, self.coordinator.id_)

    def test_target_is_case(self):
        self.assertEqual(self.activity.target, self.case.id_)

    def test_origin_is_set(self):
        self.assertIsNotNone(self.activity.origin)


class TestAcceptCaseParticipantOffer(unittest.TestCase):
    def setUp(self):
        self.activity = accept_case_participant_offer()
        self.vendor = vendor()
        self.case_actor = _CASE_ACTOR
        self.case = case()

    def test_return_type(self):
        self.assertIsInstance(self.activity, as_Accept)

    def test_actor_is_vendor(self):
        self.assertEqual(self.activity.actor, self.vendor.id_)

    def test_to_is_case_actor(self):
        self.assertEqual(self.activity.to, [self.case_actor.id_])

    def test_object_is_case_participant_offer(self):
        self.assertIsInstance(
            self.activity.object_, _OfferCaseParticipantActivity
        )

    def test_target_is_case(self):
        self.assertEqual(self.activity.target, self.case.id_)


class TestRejectCaseParticipantOffer(unittest.TestCase):
    def setUp(self):
        self.activity = reject_case_participant_offer()
        self.vendor = vendor()
        self.case_actor = _CASE_ACTOR
        self.case = case()

    def test_return_type(self):
        self.assertIsInstance(self.activity, as_Reject)

    def test_actor_is_vendor(self):
        self.assertEqual(self.activity.actor, self.vendor.id_)

    def test_to_is_case_actor(self):
        self.assertEqual(self.activity.to, [self.case_actor.id_])

    def test_object_is_case_participant_offer(self):
        self.assertIsInstance(
            self.activity.object_, _OfferCaseParticipantActivity
        )

    def test_target_is_case(self):
        self.assertEqual(self.activity.target, self.case.id_)


if __name__ == "__main__":
    unittest.main()
