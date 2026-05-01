#  Copyright (c) 2024-2025 Carnegie Mellon University and Contributors.
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
import datetime
import json
import os
import tempfile
import unittest
from typing import cast, Sequence

import vultron.wire.as2.vocab.examples.vocab_examples as examples
from vultron.wire.as2.vocab.base.base import as_Base
from vultron.wire.as2.vocab.base.objects.activities.base import as_Activity
from vultron.wire.as2.vocab.base.objects.activities.intransitive import (
    as_Question,
)
from vultron.wire.as2.vocab.base.objects.activities.transitive import (
    as_Accept,
    as_Add,
    as_Announce,
    as_Create,
    as_Ignore,
    as_Invite,
    as_Join,
    as_Leave,
    as_Offer,
    as_Read,
    as_Reject,
    as_Remove,
    as_Undo,
    as_Update,
    as_TentativeReject,
)
from vultron.wire.as2.vocab.base.objects.actors import (
    as_Actor,
    as_Organization,
)
from vultron.wire.as2.vocab.base.objects.base import as_Object
from vultron.wire.as2.vocab.base.objects.object_types import as_Event, as_Note
from vultron.wire.as2.vocab.activities.embargo import (
    _ChoosePreferredEmbargoActivity,
)
from vultron.wire.as2.vocab.objects.case_participant import CaseParticipant
from vultron.wire.as2.vocab.objects.case_status import (
    CaseStatus,
    ParticipantStatus,
)
from vultron.wire.as2.vocab.objects.vulnerability_case import VulnerabilityCase
from vultron.wire.as2.vocab.objects.vulnerability_report import (
    VulnerabilityReport,
)
from vultron.core.states.em import EM
from vultron.core.states.rm import RM
from vultron.core.states.cs import CS_pxa, CS_vfd


class Foo(as_Base):
    bar: str = "baz"


class TestVocabExamples(unittest.TestCase):
    def test_json2md(self):
        # an object with a to_json method

        foo = Foo(bar="baz")

        txt = examples.json2md(foo)
        self.assertTrue(txt.startswith("```json"))
        self.assertTrue(txt.endswith("```"))
        self.assertTrue("bar" in txt)
        self.assertTrue("baz" in txt)

    def test_obj_to_file(self):
        foo = Foo(bar="baz")
        # open a temporary file
        with tempfile.TemporaryDirectory() as tmpdirname:
            filename = tmpdirname + "/test.md"
            self.assertFalse(os.path.exists(filename))
            examples.obj_to_file(foo, filename)
            self.assertTrue(os.path.exists(filename))

            # read the file
            with open(filename, "r") as f:
                obj = json.load(f)
            self.assertEqual(obj["bar"], "baz")

    def test_finder(self):
        finder = examples.finder()
        self.assertIsInstance(finder, as_Actor)

    def test_vendor(self):
        vendor = examples.vendor()
        self.assertIsInstance(vendor, as_Actor)

    def test_report(self):
        report = examples.gen_report()
        self.assertIsInstance(report, as_Object)
        self.assertIsInstance(report, VulnerabilityReport)

        self.assertTrue(hasattr(report, "to_json"))
        json = report.to_json()
        self.assertIsInstance(json, str)

    def test_create_report(self):
        # is it an activity?
        create_report = examples.create_report()
        self.assertIsInstance(create_report, as_Activity)
        finder = examples.finder()
        report = examples.gen_report()

        # does it have the right fields?
        self.assertIsInstance(create_report, as_Create)
        self.assertEqual(create_report.type_, "Create")
        self.assertEqual(create_report.actor, finder.id_)
        self.assertEqual(create_report.object_, report)

    def test_submit_report(self):
        # is it an activity?
        submit_report = examples.submit_report()
        self.assertIsInstance(submit_report, as_Activity)
        finder = examples.finder()
        report = examples.gen_report()

        # does it have the right fields?
        self.assertIsInstance(submit_report, as_Offer)
        self.assertEqual(submit_report.type_, "Offer")
        self.assertEqual(submit_report.actor, finder.id_)
        self.assertEqual(submit_report.object_, report)

    def test_read_report(self):
        # is it an activity?
        read_report = examples.read_report()
        self.assertIsInstance(read_report, as_Activity)
        vendor = examples.vendor()
        report = examples.gen_report()

        # does it have the right fields?
        self.assertIsInstance(read_report, as_Read)
        self.assertEqual(read_report.type_, "Read")
        self.assertEqual(read_report.actor, vendor.id_)
        self.assertEqual(read_report.object_, report)

    def test_validate_report(self):
        # is it an activity?
        activity = examples.validate_report(verbose=True)
        self.assertIsInstance(activity, as_Activity)
        vendor = examples.vendor()
        report = examples.gen_report()
        finder = examples.finder()

        # does it have the right fields?
        self.assertIsInstance(activity, as_Accept)
        self.assertEqual(activity.type_, "Accept")
        self.assertEqual(activity.actor, vendor)

        # the object should be an offer
        offer = cast(as_Offer, activity.object_)
        # and the offer should contain the report
        self.assertEqual(offer.type_, "Offer")
        self.assertEqual(offer.actor, finder)

        report_ = cast(VulnerabilityReport, offer.object_)
        self.assertEqual(report, report_)

    def test_invalidate_report(self):
        # is it an activity?
        activity = examples.invalidate_report(verbose=True)
        self.assertIsInstance(activity, as_Activity)
        vendor = examples.vendor()
        report = examples.gen_report()
        finder = examples.finder()

        # does it have the right fields?
        self.assertIsInstance(activity, as_TentativeReject)
        self.assertEqual(activity.type_, "TentativeReject")
        self.assertEqual(activity.actor, vendor)

        # the object should be an offer
        offer = cast(as_Offer, activity.object_)
        # and the offer should contain the report
        self.assertEqual(offer.type_, "Offer")
        self.assertEqual(offer.actor, finder)

        report_ = cast(VulnerabilityReport, offer.object_)
        self.assertEqual(report, report_)

    def test_close_report(self):
        # is it an activity?
        activity = examples.close_report(verbose=True)
        self.assertIsInstance(activity, as_Activity)
        vendor = examples.vendor()
        report = examples.gen_report()
        finder = examples.finder()

        # does it have the right fields?
        self.assertIsInstance(activity, as_Reject)
        self.assertEqual(activity.type_, "Reject")
        self.assertEqual(vendor, activity.actor)
        # the object should be an offer
        offer = cast(as_Offer, activity.object_)
        # and the offer should contain the report
        self.assertEqual(offer.type_, "Offer")
        self.assertEqual(offer.actor, finder)

        report_ = cast(VulnerabilityReport, offer.object_)
        self.assertEqual(report, report_)

    def test_case(self):
        case = examples.case()
        self.assertIsInstance(case, as_Object)
        self.assertIsInstance(case, VulnerabilityCase)

        self.assertTrue(hasattr(case, "to_json"))
        json = case.to_json()
        self.assertIsInstance(json, str)

    def test_create_case(self):
        # is it an activity?
        create_case = examples.create_case()
        self.assertIsInstance(create_case, as_Activity)
        vendor = examples.vendor()
        case = examples.case()
        report = examples.gen_report()

        # does it have the right fields?
        self.assertIsInstance(create_case, as_Create)
        self.assertEqual(create_case.type_, "Create")
        self.assertEqual(create_case.actor, vendor.id_)

        case_from_activity = cast(VulnerabilityCase, create_case.object_)
        # the case should be the object, but it will have the report and participant embedded
        self.assertEqual(case_from_activity.id_, case.id_)
        # report should be the report id
        self.assertEqual(
            case_from_activity.vulnerability_reports[0], report.id_
        )
        # attributed_to should be a pointer to the vendor
        participant = cast(
            CaseParticipant, case_from_activity.case_participants[0]
        )
        self.assertEqual(participant.attributed_to, vendor.id_)

    def test_add_report_to_case(self):
        # is it an activity?
        add_report_to_case = examples.add_report_to_case()
        self.assertIsInstance(add_report_to_case, as_Activity)
        vendor = examples.vendor()
        case = examples.case()
        report = examples.gen_report()

        # does it have the right fields?
        self.assertIsInstance(add_report_to_case, as_Add)
        self.assertEqual(add_report_to_case.type_, "Add")
        self.assertEqual(add_report_to_case.actor, vendor.id_)
        self.assertEqual(add_report_to_case.object_, report)
        self.assertEqual(add_report_to_case.target, case.id_)

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
        # inside the activity is a deferral activity
        inner_activity = cast(as_Ignore, activity.object_)
        self.assertEqual(inner_activity.type_, "Ignore")
        self.assertEqual(inner_activity.actor, vendor.id_)
        self.assertEqual(inner_activity.object_, case)

        self.assertEqual(activity.context, case.id_)

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

    def test_coordinator(self):
        coordinator = examples.coordinator()
        self.assertIsInstance(coordinator, as_Actor)

        self.assertTrue(hasattr(coordinator, "to_json"))
        self.assertIsInstance(coordinator, as_Organization)
        assert coordinator.name is not None
        self.assertIn("coordinator", coordinator.name.lower())

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
            # skip list fields because they aren't always identical
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

    def test_update_case(self):
        activity = examples.update_case()
        self.assertIsInstance(activity, as_Activity)
        vendor = examples.vendor()
        case = examples.case()

        self.assertIsInstance(activity, as_Update)
        self.assertEqual(activity.type_, "Update")

        self.assertEqual(activity.actor, vendor.id_)
        self.assertEqual(activity.object_, case)

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

        # object_ is now the _RecommendActorActivity offer, not the coordinator ID
        from vultron.wire.as2.vocab.activities.actor import (
            _RecommendActorActivity,
        )

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

        # object_ is now the _RecommendActorActivity offer, not the coordinator ID
        from vultron.wire.as2.vocab.activities.actor import (
            _RecommendActorActivity,
        )

        self.assertIsInstance(activity.object_, _RecommendActorActivity)
        self.assertEqual(activity.target, case.id_)
        self.assertEqual(activity.to, finder.id_)

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

    def test_case_status(self):
        obj = examples.case_status()
        self.assertIsInstance(obj, as_Object)
        self.assertIsInstance(obj, CaseStatus)
        self.assertIn(obj.em_state, EM)
        self.assertIn(obj.pxa_state, CS_pxa)

    def test_participant_status(self):
        obj = examples.participant_status()
        self.assertIsInstance(obj, as_Object)
        self.assertIsInstance(obj, ParticipantStatus)

        # attributed_to and context are required
        self.assertIsNotNone(obj.attributed_to)
        self.assertIsNotNone(obj.context)

        self.assertIn(obj.rm_state, RM)
        self.assertIn(obj.vfd_state, CS_vfd)

        if obj.case_status is not None:
            self.assertIsInstance(obj.case_status, CaseStatus)
            self.assertIn(obj.case_status.em_state, EM)
            self.assertIn(obj.case_status.pxa_state, CS_pxa)

    def test_case_participant(self):
        obj = examples.case_participant()
        self.assertIsInstance(obj, as_Object)
        self.assertIsInstance(obj, CaseParticipant)

        # attributed_to and context are required
        self.assertIsNotNone(obj.id_)
        self.assertIsNotNone(obj.name)
        self.assertIsNotNone(obj.attributed_to)
        self.assertIsNotNone(obj.context)

        # status should be a list of ParticipantStatus objects
        # and there should be at least one
        self.assertIsInstance(obj.participant_statuses, Sequence)
        self.assertGreaterEqual(len(obj.participant_statuses), 1)
        for status in obj.participant_statuses:
            self.assertIsInstance(status, ParticipantStatus)

    def test_embargo_event(self):
        obj = examples.embargo_event()
        self.assertIsInstance(obj, as_Object)
        self.assertIsInstance(obj, as_Event)

        # id, name, and context are required
        self.assertIsNotNone(obj.id_)
        self.assertIsNotNone(obj.name)
        self.assertIsNotNone(obj.context)

        # end time is required
        # end time should be a TZ-aware datetime
        self.assertIsNotNone(obj.end_time)
        self.assertIsInstance(obj.end_time, datetime.datetime)
        self.assertIsNotNone(obj.end_time.tzinfo)

        if obj.start_time is not None:
            # start time should be a TZ-aware datetime
            self.assertIsNotNone(obj.start_time)
            self.assertIsInstance(obj.start_time, datetime.datetime)
            self.assertIsNotNone(obj.start_time.tzinfo)
            # start time should be at or before end time
            self.assertLessEqual(obj.start_time, obj.end_time)

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

        # is it a question?
        self.assertIsInstance(activity, as_Question)

        self.assertEqual(activity.actor, coordinator.id_)
        assert activity.context is not None
        self.assertIn(case.id_, activity.context)

        # one_of is a list, is non-empty, and contains embargo events
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


if __name__ == "__main__":
    unittest.main()
