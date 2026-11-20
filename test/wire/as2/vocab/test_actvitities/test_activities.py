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

from test.support.objects import make
from vultron.enums.roles import CVDRole
from vultron.wire.as2.vocab.activities.case_participant import (
    _AddParticipantToCaseActivity,
)
from vultron.wire.as2.vocab.objects.case_participant import as_CaseParticipant


class MyTestCase(unittest.TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_something(self):
        pass


class TestAddParticipantToCaseName(unittest.TestCase):
    """_AddParticipantToCaseActivity's name should identify the record added to the case."""

    def setUp(self):
        self.actor_id = "https://vultron.example/organizations/vendorco"
        self.case_id = "https://vultron.example/cases/1"
        self.attributed_to = "https://vultron.example/users/finndervul"

        self.participant = make(
            as_CaseParticipant,
            attributed_to=self.attributed_to,
            context=self.case_id,
            case_roles=[CVDRole.VENDOR],
        )
        self.activity = make(
            _AddParticipantToCaseActivity,
            actor=self.actor_id,
            object_=self.participant,
            target=self.case_id,
            context=self.case_id,
        )

    def test_name_contains_case_participant_type(self):
        """Name must include 'as_CaseParticipant' to distinguish from creating an actor."""
        assert self.activity.name is not None
        assert "CaseParticipant" in self.activity.name

    def test_name_contains_participant_id(self):
        """Name must include the participant's ID."""
        assert self.activity.name is not None
        assert self.participant.id_ in self.activity.name

    def test_name_contains_attributed_to(self):
        """Name must include the actor the participant is attributed to."""
        assert self.activity.name is not None
        assert self.attributed_to in self.activity.name

    def test_name_contains_actor(self):
        """Name must include the adding actor."""
        assert self.activity.name is not None
        assert self.actor_id in self.activity.name

    def test_name_names_the_case(self):
        """Name must name the case whose participant list the record joins."""
        assert self.activity.name is not None
        assert self.activity.name.endswith(f"to {self.case_id}")


if __name__ == "__main__":
    unittest.main()
