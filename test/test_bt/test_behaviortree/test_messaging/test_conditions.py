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

import vultron.bt.messaging.conditions as vmc
from vultron.bt.base.node_status import NodeStatus
from vultron.bt.messaging.states import MessageTypes


class MockMsg:
    msg_type = None

class MockState:
    current_message = MockMsg()


_TO_TEST = {
    # RS, RI, RV, RD, RA, RC, RK, RE
    MessageTypes.RS: vmc.IsMsgTypeRS,
    MessageTypes.RI: vmc.IsMsgTypeRI,
    MessageTypes.RV: vmc.IsMsgTypeRV,
    MessageTypes.RD: vmc.IsMsgTypeRD,
    MessageTypes.RA: vmc.IsMsgTypeRA,
    MessageTypes.RC: vmc.IsMsgTypeRC,
    MessageTypes.RK: vmc.IsMsgTypeRK,
    MessageTypes.RE: vmc.IsMsgTypeRE,

    # EP ER EA EV EJ EC ET EK EE
    MessageTypes.EP: vmc.IsMsgTypeEP,
    MessageTypes.ER: vmc.IsMsgTypeER,
    MessageTypes.EA: vmc.IsMsgTypeEA,
    MessageTypes.EV: vmc.IsMsgTypeEV,
    MessageTypes.EJ: vmc.IsMsgTypeEJ,
    MessageTypes.EC: vmc.IsMsgTypeEC,
    MessageTypes.ET: vmc.IsMsgTypeET,
    MessageTypes.EK: vmc.IsMsgTypeEK,
    MessageTypes.EE: vmc.IsMsgTypeEE,

    # CV CF CD CP CX CA CK CE
    MessageTypes.CV: vmc.IsMsgTypeCV,
    MessageTypes.CF: vmc.IsMsgTypeCF,
    MessageTypes.CD: vmc.IsMsgTypeCD,
    MessageTypes.CP: vmc.IsMsgTypeCP,
    MessageTypes.CX: vmc.IsMsgTypeCX,
    MessageTypes.CA: vmc.IsMsgTypeCA,
    MessageTypes.CK: vmc.IsMsgTypeCK,
    MessageTypes.CE: vmc.IsMsgTypeCE,

    # GI GK GE
    MessageTypes.GI: vmc.IsMsgTypeGI,
    MessageTypes.GK: vmc.IsMsgTypeGK,
    MessageTypes.GE: vmc.IsMsgTypeGE,
}




class MyTestCase(unittest.TestCase):


    def _test_is_msg_type_generic(self,cls,msg_type):
        node = cls()
        node.bb = MockState()
        node.msg_type = msg_type

        for mtype in MessageTypes:
            node.bb.current_message.msg_type = mtype
            if mtype == msg_type:
                with self.subTest(msg_type=mtype):
                    self.assertEqual(node.tick(), NodeStatus.SUCCESS)
            else:
                with self.subTest(msg_type=mtype):
                    self.assertEqual(node.tick(), NodeStatus.FAILURE)

    def test_is_msg_type(self):
        self.assertEqual(len(_TO_TEST),len(MessageTypes),msg="Not all message types are tested")

        for (msg_type,cls) in _TO_TEST.items():
            self._test_is_msg_type_generic(cls,msg_type)

    def _test_msg_type_compound(self,cls,pfx):
        # loop through all message types
        for msg_type in MessageTypes:
            node = cls()
            node.bb = MockState()
            node.bb.current_message.msg_type = msg_type

            if msg_type.value.startswith(pfx):
                # if the message type starts with the prefix, it should succeed
                self.assertEqual(NodeStatus.SUCCESS,node.tick())
            else:
                # if the message type does not start with the prefix, it should fail
                self.assertEqual(NodeStatus.FAILURE,node.tick())

    def test_is_rm_msg(self):
        self._test_msg_type_compound(vmc.IsRMMessage, "R")

    def test_is_em_msg(self):
        self._test_msg_type_compound(vmc.IsEMMessage, "E")

    def test_is_cs_msg(self):
        self._test_msg_type_compound(vmc.IsCSMessage, "C")

    def test_is_gm_msg(self):
        self._test_msg_type_compound(vmc.IsGMMessage, "G")



if __name__ == '__main__':
    unittest.main()
