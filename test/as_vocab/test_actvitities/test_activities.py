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

import vultron.as_vocab.activities as activities  # noqa: F401
from vultron.as_vocab.activities.case_participant import CreateParticipant
from vultron.as_vocab.objects.case_participant import VendorParticipant


class MyTestCase(unittest.TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_something(self):
        pass


class TestCreateParticipantName(unittest.TestCase):
    """CreateParticipant activity name should clearly identify CaseParticipant creation."""

    def setUp(self):
        self.actor_id = "https://vultron.example/organizations/vendorco"
        self.case_id = "https://vultron.example/cases/1"
        self.attributed_to = "https://vultron.example/users/finndervul"

        self.participant = VendorParticipant(
            attributed_to=self.attributed_to,
            context=self.case_id,
        )
        self.activity = CreateParticipant(
            actor=self.actor_id,
            as_object=self.participant,
            context=self.case_id,
        )

    def test_name_contains_case_participant_type(self):
        """Name must include 'CaseParticipant' to distinguish from creating an actor."""
        assert self.activity.name is not None
        assert "CaseParticipant" in self.activity.name

    def test_name_contains_participant_id(self):
        """Name must include the participant's ID."""
        assert self.participant.as_id in self.activity.name

    def test_name_contains_attributed_to(self):
        """Name must include the actor the participant is attributed to."""
        assert self.attributed_to in self.activity.name

    def test_name_contains_actor(self):
        """Name must include the creating actor."""
        assert self.actor_id in self.activity.name

    def test_name_not_misleading(self):
        """Name must not look like creating an actor (old buggy format was '{actor} Create {actor_uri}')."""
        # The old broken name was e.g. "vendorco Create finndervul" — two actor URIs with no "CaseParticipant"
        old_format = f"{self.actor_id} Create {self.attributed_to}"
        assert self.activity.name != old_format


if __name__ == "__main__":
    unittest.main()
