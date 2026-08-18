#!/usr/bin/env python

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

"""Typed-Ports isolation tests for case domain nodes (AC-4, issue #1883).

Covers BTND-03-011 (NoDataAvailable on missing required port) and happy-path
execution via BTTestScenario for one representative node per case sub-module.
"""

import pytest
from py_trees.ports import NoDataAvailable

from vultron.core.behaviors.case.nodes.conditions import (
    CheckCaseAlreadyExists,
)
from vultron.core.behaviors.case.nodes.suggest_actor.conditions import (
    ActorAlreadyParticipantNode,
)
from vultron.core.behaviors.case.nodes.update import (
    CheckCaseUpdateOwnerNode,
)
from vultron.core.behaviors.case.nodes.vfd_role_guards import (
    CheckVendorRoleNode,
)
from vultron.core.models.case import VulnerabilityCase
from test.core.behaviors.bt_harness import BTTestScenario

SENDER_ID = "https://example.org/actors/update-sender"
ACTOR_ID = "https://example.org/actors/vendor"
CASE_ID = "https://example.org/cases/case-001"
PARTICIPANT_ID = "https://example.org/participants/p-001"


# ---------------------------------------------------------------------------
# conditions.py — CheckCaseAlreadyExists
# ---------------------------------------------------------------------------


class TestCheckCaseAlreadyExistsPorts:
    def test_missing_datalayer_raises_no_data_available(self) -> None:
        node = CheckCaseAlreadyExists(case_id=CASE_ID)
        node.setup_ports()
        with pytest.raises(NoDataAvailable):
            node.get_input("datalayer")

    def test_failure_when_case_not_present(
        self, bt_scenario: BTTestScenario
    ) -> None:
        result = bt_scenario.run(
            CheckCaseAlreadyExists(case_id=CASE_ID), actor_id=ACTOR_ID
        )
        bt_scenario.assert_failure(result)

    def test_success_when_case_has_participants(
        self, bt_scenario: BTTestScenario
    ) -> None:
        from vultron.core.models.case_participant import CaseParticipant

        participant = CaseParticipant(
            id_=PARTICIPANT_ID,
            attributed_to=ACTOR_ID,
        )
        case = VulnerabilityCase(
            id_=CASE_ID,
            name="Test Case",
            attributed_to=ACTOR_ID,
        )
        case.case_participants.append(participant)
        bt_scenario.seed(case, participant)
        result = bt_scenario.run(
            CheckCaseAlreadyExists(case_id=CASE_ID), actor_id=ACTOR_ID
        )
        bt_scenario.assert_success(result)


# ---------------------------------------------------------------------------
# vfd_role_guards.py — CheckVendorRoleNode
# ---------------------------------------------------------------------------


class TestCheckVendorRoleNodePorts:
    def test_missing_datalayer_raises_no_data_available(self) -> None:
        node = CheckVendorRoleNode(case_id=CASE_ID, actor_id=ACTOR_ID)
        node.setup_ports()
        with pytest.raises(NoDataAvailable):
            node.get_input("datalayer")

    def test_failure_when_case_not_found(
        self, bt_scenario: BTTestScenario
    ) -> None:
        result = bt_scenario.run(
            CheckVendorRoleNode(case_id=CASE_ID, actor_id=ACTOR_ID),
            actor_id=ACTOR_ID,
        )
        bt_scenario.assert_failure(result)


# ---------------------------------------------------------------------------
# suggest_actor/conditions.py — ActorAlreadyParticipantNode
# ---------------------------------------------------------------------------


class TestActorAlreadyParticipantNodePorts:
    def test_missing_datalayer_raises_no_data_available(self) -> None:
        node = ActorAlreadyParticipantNode(
            recommended_id=ACTOR_ID, case_id=CASE_ID
        )
        node.setup_ports()
        with pytest.raises(NoDataAvailable):
            node.get_input("datalayer")

    def test_failure_when_actor_not_participant(
        self, bt_scenario: BTTestScenario
    ) -> None:
        case = VulnerabilityCase(
            id_=CASE_ID,
            name="Test Case",
            attributed_to=ACTOR_ID,
        )
        bt_scenario.seed(case)
        result = bt_scenario.run(
            ActorAlreadyParticipantNode(
                recommended_id=ACTOR_ID, case_id=CASE_ID
            ),
            actor_id=ACTOR_ID,
        )
        bt_scenario.assert_failure(result)


# ---------------------------------------------------------------------------
# update.py — CheckCaseUpdateOwnerNode
# ---------------------------------------------------------------------------


class TestCheckCaseUpdateOwnerNodePorts:
    def test_missing_datalayer_raises_no_data_available(self) -> None:
        node = CheckCaseUpdateOwnerNode(case_id=CASE_ID)
        node.setup_ports()
        with pytest.raises(NoDataAvailable):
            node.get_input("datalayer")

    def test_failure_when_case_not_found(
        self, bt_scenario: BTTestScenario
    ) -> None:
        result = bt_scenario.run(
            CheckCaseUpdateOwnerNode(case_id=CASE_ID), actor_id=ACTOR_ID
        )
        bt_scenario.assert_failure(result)

    def test_success_when_sender_owns_case(
        self, bt_scenario: BTTestScenario
    ) -> None:
        """The gate authorizes the *sender*, not the executing actor.

        The executing actor here is the receiver applying the update to its own
        replica; whether it happens to own the case is irrelevant.
        """
        case = VulnerabilityCase(
            id_=CASE_ID,
            name="Test Case",
            attributed_to=SENDER_ID,
        )
        bt_scenario.seed(case)
        result = bt_scenario.run(
            CheckCaseUpdateOwnerNode(
                case_id=CASE_ID, sender_actor_id=SENDER_ID
            ),
            actor_id=ACTOR_ID,
        )
        bt_scenario.assert_success(result)

    def test_failure_when_sender_is_not_owner(
        self, bt_scenario: BTTestScenario
    ) -> None:
        case = VulnerabilityCase(
            id_=CASE_ID,
            name="Test Case",
            attributed_to="https://example.org/actors/other",
        )
        bt_scenario.seed(case)
        result = bt_scenario.run(
            CheckCaseUpdateOwnerNode(
                case_id=CASE_ID, sender_actor_id=SENDER_ID
            ),
            actor_id=ACTOR_ID,
        )
        bt_scenario.assert_failure(result)

    def test_failure_when_receiver_owns_case_but_sender_does_not(
        self, bt_scenario: BTTestScenario
    ) -> None:
        """Owning the case does not authorize applying someone else's update.

        This is the case the pre-fix gate got backwards: it compared the
        executing actor, so a receiver that owned the case accepted an update
        from *any* sender.
        """
        case = VulnerabilityCase(
            id_=CASE_ID,
            name="Test Case",
            attributed_to=ACTOR_ID,
        )
        bt_scenario.seed(case)
        result = bt_scenario.run(
            CheckCaseUpdateOwnerNode(
                case_id=CASE_ID, sender_actor_id=SENDER_ID
            ),
            actor_id=ACTOR_ID,
        )
        bt_scenario.assert_failure(result)
