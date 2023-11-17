#  Copyright (c) 2023 Carnegie Mellon University and Contributors.
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
#
#  See LICENSE for details

import logging
import unittest
from itertools import product

from vultron.cvd_states.states import CS
from vultron.sim.participants import (
    Coordinator,
    Participant,
    ParticipantTypes,
    Vendor,
)

import vultron.bt.report_management._behaviors.report_to_others as rto
import vultron.bt.report_management.fuzzer.report_to_others
from vultron.bt.base.node_status import NodeStatus
from vultron.bt.embargo_management.states import EM
from vultron.bt.messaging.states import MessageTypes
from vultron.bt.states import CapabilityFlag


class MockCase:
    def __init__(self):
        self.potential_participants = []


class MockState:
    capabilities = CapabilityFlag.NoCapability
    reporting_effort_budget = 0
    participant_types = ParticipantTypes
    add_participant_func = None
    q_em = EM.NO_EMBARGO
    q_cs = CS.vfdpxa

    def __init__(self):
        self.case = MockCase()
        self.currently_notifying = None


class MyTestCase(unittest.TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_have_rto_capability(self):
        node = rto.HaveReportToOthersCapability()
        node.bb = MockState()
        node.setup()

        self.assertEqual(CapabilityFlag.NoCapability, node.bb.capabilities)
        r = node._tick()
        self.assertEqual(NodeStatus.FAILURE, r)

        # bestow the ability
        node.bb.capabilities |= CapabilityFlag.ReportToOthers
        self.assertEqual(CapabilityFlag.ReportToOthers, node.bb.capabilities)
        r = node._tick()
        self.assertEqual(NodeStatus.SUCCESS, r)

    def test_reporting_effort_available(self):
        node = rto._ReportingEffortAvailable()
        node.bb = MockState()
        node.setup()

        # fail when 0
        self.assertEqual(0, node.bb.reporting_effort_budget)
        r = node._tick()
        self.assertEqual(NodeStatus.FAILURE, r)

        # succeed when > 0
        node.bb.reporting_effort_budget = 1
        self.assertEqual(1, node.bb.reporting_effort_budget)
        r = node._tick()
        self.assertEqual(NodeStatus.SUCCESS, r)

    def test_total_effort_limit_met(self):
        node = rto._TotalEffortLimitMet()
        node.bb = MockState()
        node.setup()

        # succeed when 0
        self.assertEqual(0, node.bb.reporting_effort_budget)
        r = node._tick()
        self.assertEqual(NodeStatus.SUCCESS, r)

        # fail when > 0
        node.bb.reporting_effort_budget = 1
        self.assertEqual(1, node.bb.reporting_effort_budget)
        r = node._tick()
        self.assertEqual(NodeStatus.FAILURE, r)

    def test_choose_recipient(self):
        # take a recipient from potential_participants
        # put them in currently_notifying
        node = rto.ChooseRecipient()
        node.bb = MockState()
        node.setup()

        # fail if potential_participants is empty
        self.assertFalse(node.bb.case.potential_participants)
        r = node._tick()
        self.assertEqual(NodeStatus.FAILURE, r)

        # succeed if there's something to do
        potential = node.bb.case.potential_participants
        p = Participant()
        potential.append(p)
        self.assertTrue(node.bb.case.potential_participants)
        r = node._tick()
        self.assertEqual(NodeStatus.SUCCESS, r)
        self.assertIs(node.bb.currently_notifying, p)

    def test_add_vendor(self):
        node = (
            vultron.bt.report_management.fuzzer.report_to_others.InjectVendor()
        )
        node.bb = MockState()
        node.setup()

        self.assertEqual(len(node.bb.case.potential_participants), 0)

        for i in range(10):
            node._tick()
            self.assertEqual(len(node.bb.case.potential_participants), i + 1)

        for p in node.bb.case.potential_participants:
            self.assertIsInstance(p, Vendor)

    def test_add_coordinator(self):
        node = (
            vultron.bt.report_management.fuzzer.report_to_others.InjectCoordinator()
        )
        node.bb = MockState()
        node.setup()

        self.assertEqual(len(node.bb.case.potential_participants), 0)

        for i in range(10):
            node._tick()
            self.assertEqual(len(node.bb.case.potential_participants), i + 1)

        for p in node.bb.case.potential_participants:
            self.assertIsInstance(p, Coordinator)

    def test_add_other(self):
        node = (
            vultron.bt.report_management.fuzzer.report_to_others.InjectOther()
        )
        node.bb = MockState()
        node.setup()

        self.assertEqual(len(node.bb.case.potential_participants), 0)

        for i in range(10):
            node._tick()
            self.assertEqual(len(node.bb.case.potential_participants), i + 1)

        for p in node.bb.case.potential_participants:
            self.assertIsInstance(p, Participant)

    def test_remove_recipient(self):
        node = rto._RemoveRecipient()
        node.bb = MockState()
        node.setup()

        # succeed when it's already none, just a no-op
        self.assertIsNone(node.bb.currently_notifying)
        r = node._tick()
        self.assertEqual(NodeStatus.SUCCESS, r)

        # succeed when p not in list
        p = Participant()
        node.bb.currently_notifying = p
        self.assertNotIn(p, node.bb.case.potential_participants)
        # not sure how you'd get here in the real world, so it logs a warning
        with self.assertLogs(rto.logger, logging.WARNING) as lc:
            r = node._tick()
        self.assertEqual(NodeStatus.SUCCESS, r)

        p = Participant()
        node.bb.case.potential_participants.append(p)
        node.bb.currently_notifying = p
        self.assertIsNotNone(node.bb.currently_notifying)
        self.assertIn(p, node.bb.case.potential_participants)
        r = node._tick()
        self.assertEqual(NodeStatus.SUCCESS, r)
        self.assertIsNone(node.bb.currently_notifying)
        self.assertNotIn(p, node.bb.case.potential_participants)

    def test_report_to_new_participant(self):
        node = rto._ReportToNewParticipant()
        node.bb = MockState()
        node.setup()

        msg = []
        rcpt = []

        def mock_dm(message, recipient):
            msg.append(message)
            rcpt.append(recipient)

        node.bb.dm_func = mock_dm

        # fail if currently notifying is empty
        with self.assertLogs(level=logging.WARNING):
            self.assertIsNone(node.bb.currently_notifying)
            r = node._tick()
            self.assertEqual(NodeStatus.FAILURE, r)

        # success otherwise
        p = Participant()
        node.bb.currently_notifying = p
        self.assertIsNotNone(node.bb.currently_notifying)
        r = node._tick()
        self.assertEqual(NodeStatus.SUCCESS, r)
        # check that dm got called
        self.assertIn(p, rcpt)
        self.assertEqual(msg[0].msg_type, MessageTypes.RS)

    def test_connect_new_participant_to_case(self):
        node = rto._ConnectNewParticipantToCase()
        node.bb = MockState()
        node.setup()

        # fail if currently notifying is empty
        with self.assertLogs(level=logging.WARNING):
            self.assertIsNone(node.bb.currently_notifying)
            r = node._tick()
            self.assertEqual(NodeStatus.FAILURE, r)

        p = Participant()
        # fail if add_func is none
        with self.assertLogs(level=logging.WARNING):
            node.bb.currently_notifying = p
            self.assertIsNone(node.bb.add_participant_func)
            r = node._tick()
            self.assertEqual(NodeStatus.FAILURE, r)

        participants = []

        def mock_add_func(participant):
            participants.append(participant)

        node.bb.add_participant_func = mock_add_func

        r = node._tick()
        self.assertEqual(NodeStatus.SUCCESS, r)
        self.assertIn(p, participants)

    def test_bring_new_participant_up_to_speed(self):
        node = rto._BringNewParticipantUpToSpeed()
        node.bb = MockState()
        node.setup()

        # fail if currently notifying is empty
        with self.assertLogs(level=logging.WARNING):
            self.assertIsNone(node.bb.currently_notifying)
            r = node._tick()
            self.assertEqual(NodeStatus.FAILURE, r)

        # succeed otherwise

        for qem, qcs in product(EM, CS):
            p = Participant()
            node.bb.currently_notifying = p
            node.bb.q_em = qem
            node.bb.q_cs = qcs

            r = node._tick()
            self.assertEqual(NodeStatus.SUCCESS, r)
            self.assertEqual(node.bb.currently_notifying.bt.bb.q_em, qem)

            qcs_pxa = CS.PXA & qcs
            self.assertEqual(node.bb.currently_notifying.bt.bb.q_cs, qcs_pxa)


if __name__ == "__main__":
    unittest.main()
