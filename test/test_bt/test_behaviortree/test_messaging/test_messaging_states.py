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

import unittest

from vultron.bt.messaging.states import (
    CS_MESSAGE_TYPES,
    EM_MESSAGE_TYPES,
    GM_MESSAGE_TYPES,
    MessageTypes,
    RM_MESSAGE_TYPES,
)


class MyTestCase(unittest.TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_messaging_states(self):
        """Test that the MessageTypes enum is set up correctly including the aliases

        Returns:

        """
        self.assertIs(MessageTypes.RS, MessageTypes.ReportSubmission)
        self.assertIs(MessageTypes.RI, MessageTypes.ReportInvalid)
        self.assertIs(MessageTypes.RV, MessageTypes.ReportValid)
        self.assertIs(MessageTypes.RD, MessageTypes.ReportDeferred)
        self.assertIs(MessageTypes.RA, MessageTypes.ReportAccepted)
        self.assertIs(MessageTypes.RC, MessageTypes.ReportClosed)
        self.assertIs(MessageTypes.RK, MessageTypes.ReportManagementAck)
        self.assertIs(MessageTypes.RE, MessageTypes.ReportManagementError)

        self.assertIs(MessageTypes.EP, MessageTypes.EmbargoProposal)
        self.assertIs(MessageTypes.ER, MessageTypes.EmbargoRejected)
        self.assertIs(MessageTypes.EA, MessageTypes.EmbargoAccepted)
        self.assertIs(MessageTypes.EV, MessageTypes.EmbargoRevisionProposal)
        self.assertIs(MessageTypes.EJ, MessageTypes.EmbargoRevisionRejected)
        self.assertIs(MessageTypes.EC, MessageTypes.EmbargoRevisionAccepted)
        self.assertIs(MessageTypes.ET, MessageTypes.EmbargoTerminated)
        self.assertIs(MessageTypes.EK, MessageTypes.EmbargoManagementAck)
        self.assertIs(MessageTypes.EE, MessageTypes.EmbargoManagementError)

        self.assertIs(MessageTypes.CV, MessageTypes.CaseStateVendorAware)
        self.assertIs(MessageTypes.CF, MessageTypes.CaseStateFixReady)
        self.assertIs(MessageTypes.CD, MessageTypes.CaseStateFixDeployed)
        self.assertIs(MessageTypes.CP, MessageTypes.CaseStatePublicAware)
        self.assertIs(MessageTypes.CX, MessageTypes.CaseStateExploitPublished)
        self.assertIs(MessageTypes.CA, MessageTypes.CaseStateAttacksObserved)
        self.assertIs(MessageTypes.CK, MessageTypes.CaseStateAck)
        self.assertIs(MessageTypes.CE, MessageTypes.CaseStateError)

        self.assertIs(MessageTypes.GI, MessageTypes.GeneralInformationRequest)
        self.assertIs(MessageTypes.GK, MessageTypes.GeneralInformationAck)
        self.assertIs(MessageTypes.GE, MessageTypes.GeneralInformationError)

    def _check_expected_in_list(self, expected, actual) -> None:
        """Check that all expected items are in the actual list

        Args:
            expected: list of expected items
            actual: list of actual items

        Returns:
            None
        """
        for e in expected:
            self.assertIn(e, actual)

    def test_report_management_message_types(self):
        """Check that all expected report management message types are in the list of report management message types

        Returns:

        """
        rm_types = [
            MessageTypes.RS,
            MessageTypes.RI,
            MessageTypes.RV,
            MessageTypes.RD,
            MessageTypes.RA,
            MessageTypes.RC,
            MessageTypes.RK,
            MessageTypes.RE,
        ]

        self._check_expected_in_list(rm_types, RM_MESSAGE_TYPES)

    def test_embargo_management_message_types(self):
        """Check that all expected embargo management message types are in the list of embargo management message types

        Returns:

        """
        em_types = [
            MessageTypes.EP,
            MessageTypes.ER,
            MessageTypes.EA,
            MessageTypes.EV,
            MessageTypes.EJ,
            MessageTypes.EC,
            MessageTypes.ET,
            MessageTypes.EK,
            MessageTypes.EE,
        ]

        self._check_expected_in_list(em_types, EM_MESSAGE_TYPES)

    def test_case_state_message_types(self):
        """Check that all expected case state message types are in the list of case state message types

        Returns:

        """
        cs_types = [
            MessageTypes.CV,
            MessageTypes.CF,
            MessageTypes.CD,
            MessageTypes.CP,
            MessageTypes.CX,
            MessageTypes.CA,
            MessageTypes.CK,
            MessageTypes.CE,
        ]

        self._check_expected_in_list(cs_types, CS_MESSAGE_TYPES)

    def test_general_information_message_types(self):
        """Check that all expected general information message types are in the list of general information message types

        Returns:

        """
        gi_types = [MessageTypes.GI, MessageTypes.GK, MessageTypes.GE]

        self._check_expected_in_list(gi_types, GM_MESSAGE_TYPES)


if __name__ == "__main__":
    unittest.main()
