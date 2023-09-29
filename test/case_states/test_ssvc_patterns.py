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


import unittest

from vultron.case_states.enums.ssvc_2 import (
    SSVC_2_Enum,
    SSVC_2_Exploitation,
    SSVC_2_Report_Public,
    SSVC_2_Supplier_Contacted,
)
from vultron.case_states.enums.utils import enum_item_in_list
from vultron.case_states.hypercube import CVDmodel
from vultron.case_states.patterns.ssvc import (
    ssvc,
)


class MyTestCase(unittest.TestCase):
    def setUp(self):
        self.model = CVDmodel()

    def tearDown(self):
        pass

    def test_ssvc(self):
        for state in self.model.states:
            result = ssvc(state)
            # result should always be a list of non-zero length of ssvc enums
            self.assertIsInstance(result, list)
            self.assertGreater(len(result), 0)
            for item in result:
                self.assertIsInstance(item, SSVC_2_Enum)

    def test_ssvc_exploitation_state(self):
        for state in self.model.states:
            result = ssvc(state)
            # if A in state, then Exploitation: Active should be in result
            if "A" in state:
                self.assertTrue(
                    enum_item_in_list(SSVC_2_Exploitation.ACTIVE, result)
                )
            elif "X" in state:
                self.assertTrue(
                    enum_item_in_list(SSVC_2_Exploitation.POC, result)
                )
            else:
                self.assertTrue(
                    enum_item_in_list(SSVC_2_Exploitation.NONE, result)
                )
                self.assertFalse(
                    enum_item_in_list(SSVC_2_Exploitation.POC, result)
                )
                self.assertFalse(
                    enum_item_in_list(SSVC_2_Exploitation.ACTIVE, result)
                )

    def test_ssvc_report_public_state(self):
        for state in self.model.states:
            # if P in state, then Report: Public should be in result
            result = ssvc(state)

            if "P" in state:
                self.assertTrue(
                    enum_item_in_list(SSVC_2_Report_Public.YES, result)
                )
                self.assertFalse(
                    enum_item_in_list(SSVC_2_Report_Public.NO, result)
                )
            else:
                self.assertTrue(
                    enum_item_in_list(SSVC_2_Report_Public.NO, result)
                )
                self.assertFalse(
                    enum_item_in_list(SSVC_2_Report_Public.YES, result)
                )

    def test_ssvc_vendor_aware_state(self):
        for state in self.model.states:
            # if V in state, then Supplier Contacted: Yes should be in result
            result = ssvc(state)
            if "V" in state:
                self.assertTrue(
                    enum_item_in_list(SSVC_2_Supplier_Contacted.YES, result)
                )
                self.assertFalse(
                    enum_item_in_list(SSVC_2_Supplier_Contacted.NO, result)
                )
            else:
                self.assertTrue(
                    enum_item_in_list(SSVC_2_Supplier_Contacted.NO, result)
                )
                self.assertFalse(
                    enum_item_in_list(SSVC_2_Supplier_Contacted.YES, result)
                )


if __name__ == "__main__":
    unittest.main()
