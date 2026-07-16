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
import unittest
from typing import Sequence, cast

import vultron.wire.as2.vocab.examples.vocab_examples as examples
from vultron.wire.as2.vocab.activities.actor import _RecommendActorActivity
from vultron.wire.as2.vocab.base.objects.activities.base import as_Activity
from vultron.wire.as2.vocab.base.objects.activities.transitive import (
    as_Accept,
    as_Add,
    as_Create,
    as_Invite,
    as_Offer,
    as_Reject,
    as_Remove,
)
from vultron.wire.as2.vocab.base.objects.actors import as_Service
from vultron.wire.as2.vocab.base.objects.base import as_Object
from vultron.wire.as2.vocab.objects.case_participant import CaseParticipant
from vultron.wire.as2.vocab.objects.case_status import (
    CaseStatus,
    ParticipantStatus,
)
from vultron.core.states.cs import CS_pxa, CS_vfd
from vultron.core.states.em import EM
from vultron.core.states.rm import RM


class TestVocabParticipantExamples(unittest.TestCase):
    def test_case_participant(self):
        obj = examples.case_participant()
        self.assertIsInstance(obj, as_Object)
        self.assertIsInstance(obj, CaseParticipant)

        self.assertIsNotNone(obj.id_)
        self.assertIsNotNone(obj.name)
        self.assertIsNotNone(obj.attributed_to)
        self.assertIsNotNone(obj.context)

        self.assertIsInstance(obj.participant_statuses, Sequence)
        self.assertGreaterEqual(len(obj.participant_statuses), 1)
        for status in obj.participant_statuses:
            self.assertIsInstance(status, ParticipantStatus)

    def test_create_participant(self):
        activity = examples.create_participant()
        self.assertIsInstance(activity, as_Activity)
        vendor = examples.vendor()
        case = examples.case()
        coordinator = examples.coordinator()

        self.assertIsInstance(activity, as_Create)
        self.assertEqual(activity.type_, "Create")

        self.assertEqual(activity.actor, vendor.id_)
        self.assertEqual(activity.context, case.id_)
        participant = cast(CaseParticipant, activity.object_)
        self.assertEqual(participant.attributed_to, coordinator.id_)
        self.assertEqual(participant.context, case.id_)
        self.assertEqual(participant.name, coordinator.name)

    def test_participant_status(self):
        obj = examples.participant_status()
        self.assertIsInstance(obj, as_Object)
        self.assertIsInstance(obj, ParticipantStatus)

        self.assertIsNotNone(obj.attributed_to)
        self.assertIsNotNone(obj.context)

        self.assertIn(obj.rm_state, RM)
        self.assertIn(obj.vfd_state, CS_vfd)

        if obj.case_status is not None:
            self.assertIsInstance(obj.case_status, CaseStatus)
            self.assertIn(obj.case_status.em_state, EM)
            self.assertIn(obj.case_status.pxa_state, CS_pxa)

    def test_create_participant_status(self):
        activity = examples.create_participant_status()
        self.assertIsInstance(activity, as_Activity)
        vendor = examples.vendor()

        self.assertIsInstance(activity, as_Create)
        self.assertEqual(activity.type_, "Create")

        self.assertEqual(activity.actor, vendor.id_)
        self.assertIsInstance(activity.object_, ParticipantStatus)

    def test_add_status_to_participant(self):
        activity = examples.add_status_to_participant()
        self.assertIsInstance(activity, as_Activity)
        vendor = examples.vendor()
        status = examples.participant_status()

        self.assertIsInstance(activity, as_Add)
        self.assertEqual(activity.type_, "Add")

        self.assertEqual(activity.actor, vendor.id_)
        self.assertEqual(activity.target, status.context)
        self.assertEqual(activity.object_, status)

    def test_add_status_to_participant2(self):
        activity = examples.add_status_to_participant()
        self.assertIsInstance(activity, as_Activity)
        vendor = examples.vendor()
        status = examples.participant_status()

        self.assertIsInstance(activity, as_Add)
        self.assertEqual(activity.type_, "Add")

        self.assertEqual(activity.actor, vendor.id_)
        self.assertIsNotNone(activity.target)
        self.assertEqual(activity.object_, status)

    def test_rm_invite_to_case(self):
        activity = examples.rm_invite_to_case()
        self.assertIsInstance(activity, as_Activity)
        vendor = examples.vendor()
        case = examples.case()
        coordinator = examples.coordinator()

        self.assertIsInstance(activity, as_Invite)
        self.assertEqual(activity.type_, "Invite")

        self.assertEqual(activity.actor, vendor.id_)
        self.assertEqual(activity.object_, coordinator)
        self.assertEqual(activity.target, case.id_)
        self.assertEqual(activity.to, coordinator.id_)

    def test_accept_invite_to_case(self):
        activity = examples.accept_invite_to_case()
        self.assertIsInstance(activity, as_Activity)
        vendor = examples.vendor()
        coordinator = examples.coordinator()
        invite = examples.rm_invite_to_case()

        self.assertIsInstance(activity, as_Accept)
        self.assertEqual(activity.type_, "Accept")

        self.assertEqual(activity.actor, coordinator.id_)
        accepted_invite = cast(as_Invite, activity.object_)
        self.assertEqual(accepted_invite.id_, invite.id_)
        self.assertEqual(activity.to, vendor.id_)

    def test_reject_invite_to_case(self):
        activity = examples.reject_invite_to_case()
        self.assertIsInstance(activity, as_Activity)
        vendor = examples.vendor()
        coordinator = examples.coordinator()
        invite = examples.rm_invite_to_case()

        self.assertIsInstance(activity, as_Reject)
        self.assertEqual(activity.type_, "Reject")

        self.assertEqual(activity.actor, coordinator.id_)
        rejected_invite = cast(as_Invite, activity.object_)
        self.assertEqual(rejected_invite.id_, invite.id_)
        self.assertEqual(activity.to, vendor.id_)

    def test_invite_to_case(self):
        activity = examples.invite_to_case()
        self.assertIsInstance(activity, as_Activity)
        vendor = examples.vendor()
        case = examples.case()
        coordinator = examples.coordinator()

        self.assertIsInstance(activity, as_Invite)
        self.assertEqual(activity.type_, "Invite")

        self.assertEqual(activity.actor, vendor.id_)
        self.assertEqual(activity.object_, coordinator)
        self.assertEqual(activity.target, case.id_)
        self.assertEqual(activity.to, coordinator.id_)

    def test_recommend_actor(self):
        activity = examples.recommend_actor()
        self.assertIsInstance(activity, as_Activity)
        vendor = examples.vendor()
        case = examples.case()
        finder = examples.finder()
        coordinator = examples.coordinator()

        self.assertIsInstance(activity, as_Offer)
        self.assertEqual(activity.type_, "Offer")

        self.assertEqual(activity.actor, finder.id_)
        self.assertEqual(activity.object_, coordinator)
        self.assertEqual(activity.target, case.id_)
        self.assertEqual(activity.to, vendor.id_)

    def test_accept_actor_recommendation(self):
        activity = examples.accept_actor_recommendation()
        self.assertIsInstance(activity, as_Activity)
        vendor = examples.vendor()
        case = examples.case()
        finder = examples.finder()

        self.assertIsInstance(activity, as_Accept)
        self.assertEqual(activity.type_, "Accept")

        self.assertEqual(activity.actor, vendor.id_)
        self.assertEqual(activity.context, case.id_)

        self.assertIsInstance(activity.object_, _RecommendActorActivity)
        self.assertEqual(activity.target, case.id_)
        self.assertEqual(activity.to, finder.id_)

    def test_reject_actor_recommendation(self):
        activity = examples.reject_actor_recommendation()
        self.assertIsInstance(activity, as_Activity)
        vendor = examples.vendor()
        case = examples.case()
        finder = examples.finder()

        self.assertIsInstance(activity, as_Reject)
        self.assertEqual(activity.type_, "Reject")

        self.assertEqual(activity.actor, vendor.id_)
        self.assertEqual(activity.context, case.id_)

        self.assertIsInstance(activity.object_, _RecommendActorActivity)
        self.assertEqual(activity.target, case.id_)
        self.assertEqual(activity.to, finder.id_)

    def test_case_actor(self):
        ca = examples.case_actor()
        self.assertIsInstance(ca, as_Service)
        self.assertIsNotNone(ca.id_)
        self.assertIsNotNone(ca.name)

    def test_offer_case_participant(self):
        activity = examples.offer_case_participant()
        self.assertIsInstance(activity, as_Activity)
        ca = examples.case_actor()
        v = examples.vendor()
        coordinator = examples.coordinator()
        c = examples.case()

        self.assertIsInstance(activity, as_Offer)
        self.assertEqual(activity.type_, "Offer")

        # CaseActor sends the transformed offer to the Case Owner
        self.assertEqual(activity.actor, ca.id_)
        self.assertEqual(activity.to, [v.id_])

        participant = cast(CaseParticipant, activity.object_)
        self.assertIsInstance(participant, CaseParticipant)
        attr = participant.attributed_to
        attr_id = getattr(attr, "id_", None) or attr
        self.assertEqual(attr_id, coordinator.id_)
        self.assertEqual(activity.target, c.id_)
        self.assertEqual(activity.context, c.id_)
        self.assertIsNotNone(activity.origin)

    def test_accept_case_participant_offer(self):
        activity = examples.accept_case_participant_offer()
        self.assertIsInstance(activity, as_Activity)
        ca = examples.case_actor()
        v = examples.vendor()
        c = examples.case()

        self.assertIsInstance(activity, as_Accept)
        self.assertEqual(activity.type_, "Accept")

        # Case Owner accepts and sends back to CaseActor
        self.assertEqual(activity.actor, v.id_)
        self.assertEqual(activity.to, [ca.id_])
        self.assertEqual(activity.target, c.id_)
        self.assertEqual(activity.context, c.id_)

        offer = cast(as_Offer, activity.object_)
        self.assertIsInstance(offer, as_Offer)

    def test_reject_case_participant_offer(self):
        activity = examples.reject_case_participant_offer()
        self.assertIsInstance(activity, as_Activity)
        ca = examples.case_actor()
        v = examples.vendor()
        c = examples.case()

        self.assertIsInstance(activity, as_Reject)
        self.assertEqual(activity.type_, "Reject")

        # Case Owner rejects and sends back to CaseActor
        self.assertEqual(activity.actor, v.id_)
        self.assertEqual(activity.to, [ca.id_])
        self.assertEqual(activity.target, c.id_)
        self.assertEqual(activity.context, c.id_)

        offer = cast(as_Offer, activity.object_)
        self.assertIsInstance(offer, as_Offer)

    def test_remove_participant_from_case(self):
        activity = examples.remove_participant_from_case()
        self.assertIsInstance(activity, as_Activity)
        vendor = examples.vendor()
        case = examples.case()
        coord_p = examples.coordinator_participant()

        self.assertIsInstance(activity, as_Remove)
        self.assertEqual(activity.type_, "Remove")

        self.assertEqual(activity.actor, vendor.id_)
        participant = cast(CaseParticipant, activity.object_)
        self.assertEqual(participant.attributed_to, coord_p.attributed_to)
        self.assertEqual(participant.name, coord_p.name)
        self.assertEqual(participant.context, case.id_)
        self.assertEqual(activity.origin, case.id_)


if __name__ == "__main__":
    unittest.main()
