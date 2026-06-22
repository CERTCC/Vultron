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
from typing import cast

import vultron.wire.as2.vocab.examples.vocab_examples as examples
from vultron.wire.as2.vocab.base.objects.activities.base import as_Activity
from vultron.wire.as2.vocab.base.objects.activities.transitive import (
    as_Accept,
    as_Add,
    as_Create,
    as_Ignore,
    as_Join,
    as_Leave,
    as_Offer,
    as_Reject,
    as_Undo,
    as_Update,
)
from vultron.wire.as2.vocab.base.objects.base import as_Object
from vultron.wire.as2.vocab.base.objects.object_types import as_Note
from vultron.wire.as2.vocab.objects.case_participant import CaseParticipant
from vultron.wire.as2.vocab.objects.case_status import CaseStatus
from vultron.wire.as2.vocab.objects.vulnerability_case import VulnerabilityCase
from vultron.core.states.cs import CS_pxa
from vultron.core.states.em import EM


class TestVocabCaseObjectExamples(unittest.TestCase):
    def test_case(self):
        case = examples.case()
        self.assertIsInstance(case, as_Object)
        self.assertIsInstance(case, VulnerabilityCase)

        self.assertTrue(hasattr(case, "to_json"))
        json = case.to_json()
        self.assertIsInstance(json, str)

    def test_case_has_genesis_hash(self):
        case = examples.case()
        self.assertIsInstance(case, VulnerabilityCase)
        self.assertTrue(
            case.genesis_hash,
            "examples.case() genesis_hash must be non-empty (CLP-08-003)",
        )

    def test_case_random_id_has_genesis_hash(self):
        case = examples.case(random_id=True)
        self.assertIsInstance(case, VulnerabilityCase)
        self.assertTrue(
            case.genesis_hash,
            "examples.case(random_id=True) genesis_hash must be non-empty (CLP-08-003)",
        )

    def test_create_case(self):
        create_case = examples.create_case()
        self.assertIsInstance(create_case, as_Activity)
        vendor = examples.vendor()
        case = examples.case()
        report = examples.gen_report()

        self.assertIsInstance(create_case, as_Create)
        self.assertEqual(create_case.type_, "Create")
        self.assertEqual(create_case.actor, vendor.id_)

        case_from_activity = cast(VulnerabilityCase, create_case.object_)
        self.assertEqual(case_from_activity.id_, case.id_)
        self.assertEqual(
            case_from_activity.vulnerability_reports[0], report.id_
        )
        participant = cast(
            CaseParticipant, case_from_activity.case_participants[0]
        )
        self.assertEqual(participant.attributed_to, vendor.id_)

    def test_add_report_to_case(self):
        add_report_to_case = examples.add_report_to_case()
        self.assertIsInstance(add_report_to_case, as_Activity)
        vendor = examples.vendor()
        case = examples.case()
        report = examples.gen_report()

        self.assertIsInstance(add_report_to_case, as_Add)
        self.assertEqual(add_report_to_case.type_, "Add")
        self.assertEqual(add_report_to_case.actor, vendor.id_)
        self.assertEqual(add_report_to_case.object_, report)
        self.assertEqual(add_report_to_case.target, case.id_)


class TestVocabCaseParticipantExamples(unittest.TestCase):
    def test_add_vendor_participant_to_case(self):
        activity = examples.add_vendor_participant_to_case()
        self.assertIsInstance(activity, as_Activity)
        vendor = examples.vendor()
        case = examples.case()

        self.assertIsInstance(activity, as_Add)
        self.assertEqual(activity.type_, "Add")

        self.assertEqual(activity.actor, vendor.id_)
        self.assertEqual(activity.target, case.id_)

        participant = cast(CaseParticipant, activity.object_)
        self.assertEqual(participant.attributed_to, vendor.id_)
        self.assertEqual(participant.name, vendor.name)
        self.assertEqual(participant.context, case.id_)

    def test_add_finder_participant_to_case(self):
        activity = examples.add_finder_participant_to_case()
        self.assertIsInstance(activity, as_Activity)
        vendor = examples.vendor()
        finder = examples.finder()
        case = examples.case()

        self.assertIsInstance(activity, as_Add)
        self.assertEqual(activity.type_, "Add")

        self.assertEqual(activity.actor, vendor.id_)
        self.assertEqual(activity.target, case.id_)

        participant = cast(CaseParticipant, activity.object_)
        self.assertEqual(participant.attributed_to, finder.id_)
        self.assertEqual(participant.name, finder.name)
        self.assertEqual(participant.context, case.id_)

    def test_add_coordinator_participant_to_case(self):
        activity = examples.add_coordinator_participant_to_case()
        self.assertIsInstance(activity, as_Activity)
        vendor = examples.vendor()
        coordinator = examples.coordinator()
        case = examples.case()

        self.assertIsInstance(activity, as_Add)
        self.assertEqual(activity.type_, "Add")

        self.assertEqual(activity.actor, vendor.id_)
        self.assertEqual(activity.target, case.id_)

        participant = cast(CaseParticipant, activity.object_)
        self.assertEqual(participant.attributed_to, coordinator.id_)
        self.assertEqual(participant.name, coordinator.name)
        self.assertEqual(participant.context, case.id_)


class TestVocabCaseLifecycleExamples(unittest.TestCase):
    def test_engage_case(self):
        activity = examples.engage_case()
        self.assertIsInstance(activity, as_Activity)
        vendor = examples.vendor()
        case = examples.case()

        self.assertIsInstance(activity, as_Join)
        self.assertEqual(activity.type_, "Join")

        self.assertEqual(activity.actor, vendor.id_)
        self.assertEqual(activity.object_, case)

    def test_close_case(self):
        activity = examples.close_case()
        self.assertIsInstance(activity, as_Activity)
        vendor = examples.vendor()
        case = examples.case()

        self.assertIsInstance(activity, as_Leave)
        self.assertEqual(activity.type_, "Leave")

        self.assertEqual(activity.actor, vendor.id_)
        self.assertEqual(activity.object_, case)

    def test_defer_case(self):
        activity = examples.defer_case()
        self.assertIsInstance(activity, as_Activity)
        vendor = examples.vendor()
        case = examples.case()

        self.assertIsInstance(activity, as_Ignore)
        self.assertEqual(activity.type_, "Ignore")

        self.assertEqual(activity.actor, vendor.id_)
        self.assertEqual(activity.object_, case)

    def test_reengage_case(self):
        activity = examples.reengage_case()
        self.assertIsInstance(activity, as_Activity)
        vendor = examples.vendor()
        case = examples.case()

        self.assertIsInstance(activity, as_Undo)
        self.assertEqual(activity.type_, "Undo")

        self.assertEqual(activity.actor, vendor.id_)
        inner_activity = cast(as_Ignore, activity.object_)
        self.assertEqual(inner_activity.type_, "Ignore")
        self.assertEqual(inner_activity.actor, vendor.id_)
        self.assertEqual(inner_activity.object_, case)

        self.assertEqual(activity.context, case.id_)

    def test_update_case(self):
        activity = examples.update_case()
        self.assertIsInstance(activity, as_Activity)
        vendor = examples.vendor()
        case = examples.case()

        self.assertIsInstance(activity, as_Update)
        self.assertEqual(activity.type_, "Update")

        self.assertEqual(activity.actor, vendor.id_)
        self.assertEqual(activity.object_, case)


class TestVocabCaseNoteExamples(unittest.TestCase):
    def test_note(self):
        note = examples.note()
        self.assertIsInstance(note, as_Object)
        self.assertIsInstance(note, as_Note)

        self.assertTrue(hasattr(note, "to_json"))
        self.assertIn("This is a note", note.content)

    def test_add_note_to_case(self):
        activity = examples.add_note_to_case()
        self.assertIsInstance(activity, as_Activity)
        finder = examples.finder()
        case = examples.case()
        note = examples.note()

        self.assertIsInstance(activity, as_Add)
        self.assertEqual(activity.type_, "Add")

        self.assertEqual(activity.actor, finder.id_)
        self.assertEqual(activity.target, case.id_)

        add_note = cast(as_Note, activity.object_)
        self.assertEqual(add_note.context, case.id_)
        self.assertEqual(add_note.content, note.content)

    def test_create_note(self):
        activity = examples.create_note()
        self.assertIsInstance(activity, as_Activity)
        vendor = examples.vendor()
        case = examples.case()
        note = examples.note()

        self.assertIsInstance(activity, as_Create)
        self.assertEqual(activity.type_, "Create")

        self.assertEqual(activity.actor, vendor.id_)
        self.assertEqual(activity.target, case.id_)
        self.assertEqual(activity.object_, note)


class TestVocabCaseOwnershipExamples(unittest.TestCase):
    def test_offer_case_ownership_transfer(self):
        activity = examples.offer_case_ownership_transfer()
        self.assertIsInstance(activity, as_Activity)
        vendor = examples.vendor()
        coordinator = examples.coordinator()
        case = examples.case()

        self.assertIsInstance(activity, as_Offer)
        self.assertEqual(activity.type_, "Offer")

        self.assertEqual(activity.actor, vendor.id_)
        self.assertEqual(activity.target, coordinator.id_)

        transfer_case = cast(VulnerabilityCase, activity.object_)
        for k, v in transfer_case.to_dict().items():
            if isinstance(v, list):
                continue
            self.assertEqual(v, case.to_dict()[k])

    def test_accept_case_ownership_transfer(self):
        activity = examples.accept_case_ownership_transfer()
        self.assertIsInstance(activity, as_Activity)
        coordinator = examples.coordinator()

        self.assertIsInstance(activity, as_Accept)
        self.assertEqual(activity.type_, "Accept")

        self.assertEqual(activity.actor, coordinator.id_)
        self.assertIsInstance(activity.object_, as_Offer)

    def test_reject_case_ownership_transfer(self):
        activity = examples.reject_case_ownership_transfer()
        self.assertIsInstance(activity, as_Activity)
        coordinator = examples.coordinator()

        self.assertIsInstance(activity, as_Reject)
        self.assertEqual(activity.type_, "Reject")

        self.assertEqual(activity.actor, coordinator.id_)
        self.assertIsInstance(activity.object_, as_Offer)


class TestVocabCaseStatusExamples(unittest.TestCase):
    def test_case_status(self):
        obj = examples.case_status()
        self.assertIsInstance(obj, as_Object)
        self.assertIsInstance(obj, CaseStatus)
        self.assertIn(obj.em_state, EM)
        self.assertIn(obj.pxa_state, CS_pxa)

    def test_create_case_status(self):
        activity = examples.create_case_status()
        self.assertIsInstance(activity, as_Activity)
        vendor = examples.vendor()
        case = examples.case()
        status = examples.case_status()

        self.assertIsInstance(activity, as_Create)
        self.assertEqual(activity.type_, "Create")

        self.assertEqual(activity.actor, vendor.id_)
        self.assertEqual(activity.context, case.id_)
        self.assertEqual(activity.object_, status)

    def test_add_case_status_to_case(self):
        activity = examples.add_status_to_case()
        self.assertIsInstance(activity, as_Activity)
        vendor = examples.vendor()
        case = examples.case()
        status = examples.case_status()

        self.assertIsInstance(activity, as_Add)
        self.assertEqual(activity.type_, "Add")

        self.assertEqual(activity.actor, vendor.id_)
        self.assertEqual(activity.target, case.id_)
        self.assertEqual(activity.object_, status)


if __name__ == "__main__":
    unittest.main()
