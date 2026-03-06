#!/usr/bin/env python

#  Copyright (c) 2023-2025 Carnegie Mellon University and Contributors.
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

"""Tests for CaseParticipant model, focusing on accepted_embargo_ids field (CM-10-003)."""

import unittest

from vultron.api.v2.datalayer.db_record import (
    object_to_record,
    record_to_object,
)
from vultron.as_vocab.objects.case_participant import (
    CaseParticipant,
    CoordinatorParticipant,
    FinderParticipant,
    VendorParticipant,
)


class TestCaseParticipantAcceptedEmbargoIds(unittest.TestCase):
    """Tests for CaseParticipant.accepted_embargo_ids (CM-10-001, CM-10-003)."""

    def setUp(self):
        self.actor_id = "https://example.org/actors/alice"
        self.case_id = "https://example.org/cases/case-001"
        self.embargo_id_1 = "https://example.org/embargoes/emb-001"
        self.embargo_id_2 = "https://example.org/embargoes/emb-002"
        self.participant = CaseParticipant(
            attributed_to=self.actor_id,
            context=self.case_id,
        )

    def test_accepted_embargo_ids_default_empty(self):
        """New CaseParticipant has empty accepted_embargo_ids by default (CM-10-003)."""
        self.assertEqual([], self.participant.accepted_embargo_ids)

    def test_accepted_embargo_ids_can_be_set_at_creation(self):
        """accepted_embargo_ids can be populated at creation time."""
        participant = CaseParticipant(
            attributed_to=self.actor_id,
            context=self.case_id,
            accepted_embargo_ids=[self.embargo_id_1],
        )
        self.assertEqual([self.embargo_id_1], participant.accepted_embargo_ids)

    def test_accepted_embargo_ids_can_be_appended(self):
        """accepted_embargo_ids can be extended after creation."""
        self.participant.accepted_embargo_ids.append(self.embargo_id_1)
        self.assertIn(self.embargo_id_1, self.participant.accepted_embargo_ids)

    def test_accepted_embargo_ids_tracks_multiple_embargoes(self):
        """accepted_embargo_ids tracks multiple accepted embargoes."""
        participant = CaseParticipant(
            attributed_to=self.actor_id,
            context=self.case_id,
            accepted_embargo_ids=[self.embargo_id_1, self.embargo_id_2],
        )
        self.assertIn(self.embargo_id_1, participant.accepted_embargo_ids)
        self.assertIn(self.embargo_id_2, participant.accepted_embargo_ids)
        self.assertEqual(2, len(participant.accepted_embargo_ids))

    def test_accepted_embargo_ids_round_trip_json(self):
        """accepted_embargo_ids survives JSON serialization round-trip."""
        participant = CaseParticipant(
            attributed_to=self.actor_id,
            context=self.case_id,
            accepted_embargo_ids=[self.embargo_id_1, self.embargo_id_2],
        )
        json_str = participant.to_json()
        restored = CaseParticipant.model_validate_json(json_str)
        self.assertEqual(
            participant.accepted_embargo_ids, restored.accepted_embargo_ids
        )

    def test_accepted_embargo_ids_round_trip_object_to_record(self):
        """accepted_embargo_ids survives object_to_record/record_to_object round-trip."""
        participant = CaseParticipant(
            attributed_to=self.actor_id,
            context=self.case_id,
            accepted_embargo_ids=[self.embargo_id_1, self.embargo_id_2],
        )
        record = object_to_record(participant)
        restored = record_to_object(record)
        self.assertEqual(
            participant.accepted_embargo_ids, restored.accepted_embargo_ids
        )

    def test_accepted_embargo_ids_empty_round_trip(self):
        """Empty accepted_embargo_ids survives object_to_record/record_to_object round-trip."""
        record = object_to_record(self.participant)
        restored = record_to_object(record)
        self.assertEqual([], restored.accepted_embargo_ids)

    def test_accepted_embargo_ids_present_in_subclasses(self):
        """accepted_embargo_ids field is inherited by CaseParticipant subclasses."""
        for cls in [
            FinderParticipant,
            VendorParticipant,
            CoordinatorParticipant,
        ]:
            participant = cls(
                attributed_to=self.actor_id,
                context=self.case_id,
                accepted_embargo_ids=[self.embargo_id_1],
            )
            self.assertEqual(
                [self.embargo_id_1],
                participant.accepted_embargo_ids,
                f"{cls.__name__} should inherit accepted_embargo_ids",
            )

    def test_accepted_embargo_ids_subclass_round_trip(self):
        """accepted_embargo_ids survives round-trip for a subclass (VendorParticipant)."""
        vendor = VendorParticipant(
            attributed_to=self.actor_id,
            context=self.case_id,
            accepted_embargo_ids=[self.embargo_id_1],
        )
        record = object_to_record(vendor)
        restored = record_to_object(record)
        self.assertEqual(
            vendor.accepted_embargo_ids, restored.accepted_embargo_ids
        )


if __name__ == "__main__":
    unittest.main()
