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
import datetime
import unittest
from typing import Sequence, cast

import vultron.wire.as2.vocab.examples.vocab_examples as examples
from vultron.wire.as2.vocab.activities.embargo import (
    _ChoosePreferredEmbargoActivity,
)
from vultron.wire.as2.vocab.base.objects.activities.base import as_Activity
from vultron.wire.as2.vocab.base.objects.activities.intransitive import (
    as_Question,
)
from vultron.wire.as2.vocab.base.objects.activities.transitive import (
    as_Accept,
    as_Add,
    as_Announce,
    as_Invite,
    as_Offer,
    as_Reject,
    as_Remove,
)
from vultron.wire.as2.vocab.base.objects.base import as_Object
from vultron.wire.as2.vocab.base.objects.object_types import as_Event


class TestVocabEmbargoExamples(unittest.TestCase):
    def test_embargo_event(self):
        obj = examples.embargo_event()
        self.assertIsInstance(obj, as_Object)
        self.assertIsInstance(obj, as_Event)

        self.assertIsNotNone(obj.id_)
        self.assertIsNotNone(obj.name)
        self.assertIsNotNone(obj.context)

        self.assertIsNotNone(obj.end_time)
        self.assertIsInstance(obj.end_time, datetime.datetime)
        self.assertIsNotNone(obj.end_time.tzinfo)

        if obj.start_time is not None:
            self.assertIsNotNone(obj.start_time)
            self.assertIsInstance(obj.start_time, datetime.datetime)
            self.assertIsNotNone(obj.start_time.tzinfo)
            self.assertLessEqual(obj.start_time, obj.end_time)

    def test_propose_embargo(self):
        activity = examples.propose_embargo()
        self.assertIsInstance(activity, as_Activity)
        vendor = examples.vendor()
        case = examples.case()
        embargo = examples.embargo_event()

        self.assertIsInstance(activity, as_Invite)
        self.assertEqual(activity.type_, "Invite")

        self.assertEqual(activity.actor, vendor.id_)
        self.assertEqual(activity.object_, embargo)
        self.assertEqual(activity.context, case.id_)

    def test_choose_preferred_embargo(self):
        activity = examples.choose_preferred_embargo()
        self.assertIsInstance(activity, as_Activity)
        case = examples.case()
        examples.embargo_event()
        coordinator = examples.coordinator()

        self.assertIsInstance(activity, as_Question)

        self.assertEqual(activity.actor, coordinator.id_)
        assert activity.context is not None
        self.assertIn(case.id_, activity.context)

        assert isinstance(activity, _ChoosePreferredEmbargoActivity)
        assert activity.one_of is not None
        self.assertIsInstance(activity.one_of, Sequence)
        self.assertGreaterEqual(len(activity.one_of), 1)
        for obj in activity.one_of:
            self.assertIsInstance(obj, as_Event)

    def test_accept_embargo(self):
        activity = examples.accept_embargo()
        self.assertIsInstance(activity, as_Activity)
        vendor = examples.vendor()
        proposal = examples.propose_embargo()

        self.assertIsInstance(activity, as_Accept)
        self.assertEqual(activity.type_, "Accept")

        self.assertEqual(activity.actor, vendor.id_)
        self.assertIsNotNone(activity.context)
        self.assertIsNotNone(activity.to)
        accepted_proposal = cast(as_Offer, activity.object_)
        self.assertEqual(accepted_proposal.id_, proposal.id_)

    def test_reject_embargo(self):
        activity = examples.reject_embargo()
        self.assertIsInstance(activity, as_Activity)
        vendor = examples.vendor()
        proposal = examples.propose_embargo()

        self.assertIsInstance(activity, as_Reject)
        self.assertEqual(activity.type_, "Reject")

        self.assertEqual(activity.actor, vendor.id_)
        self.assertIsNotNone(activity.context)
        self.assertIsNotNone(activity.to)
        rejected_proposal = cast(as_Offer, activity.object_)
        self.assertEqual(rejected_proposal.id_, proposal.id_)

    def test_add_embargo_to_case(self):
        activity = examples.add_embargo_to_case()
        self.assertIsInstance(activity, as_Activity)
        vendor = examples.vendor()
        case = examples.case()
        embargo = examples.embargo_event()

        self.assertIsInstance(activity, as_Add)
        self.assertEqual(activity.type_, "Add")

        self.assertEqual(activity.actor, vendor.id_)
        self.assertEqual(activity.target, case.id_)
        self.assertEqual(activity.object_, embargo)

    def test_activate_embargo(self):
        activity = examples.activate_embargo()
        self.assertIsInstance(activity, as_Activity)
        vendor = examples.vendor()
        case = examples.case()
        embargo = examples.embargo_event()

        self.assertIsInstance(activity, as_Add)
        self.assertEqual(activity.type_, "Add")

        self.assertEqual(activity.actor, vendor.id_)
        self.assertEqual(activity.target, case.id_)
        self.assertEqual(activity.object_, embargo)

    def test_announce_embargo(self):
        activity = examples.announce_embargo()
        self.assertIsInstance(activity, as_Activity)
        vendor = examples.vendor()
        case = examples.case()
        embargo = examples.embargo_event(days=90)

        self.assertIsInstance(activity, as_Announce)
        self.assertEqual(activity.type_, "Announce")

        self.assertEqual(activity.actor, vendor.id_)
        self.assertEqual(activity.context, case.id_)
        self.assertEqual(activity.object_, embargo)
        self.assertIsNotNone(activity.to)

    def test_remove_embargo(self):
        activity = examples.remove_embargo()
        self.assertIsInstance(activity, as_Activity)
        vendor = examples.vendor()
        case = examples.case()

        self.assertIsInstance(activity, as_Remove)
        self.assertEqual(activity.type_, "Remove")

        self.assertEqual(activity.actor, vendor.id_)
        self.assertEqual(activity.origin, case.id_)
        self.assertIsNone(activity.target)
        # Extract the embargo from the returned activity rather than
        # recreating it independently to avoid flakiness from time-based
        # ID generation (BUG-FLAKY-1).
        embargo_raw = activity.object_
        self.assertIsNotNone(embargo_raw)
        self.assertIsInstance(embargo_raw, as_Object)
        embargo = cast(as_Object, embargo_raw)
        self.assertEqual(embargo.context, case.id_)


if __name__ == "__main__":
    unittest.main()
