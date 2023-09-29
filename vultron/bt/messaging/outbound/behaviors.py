#!/usr/bin/env python
"""file: behaviors
author: adh
created_at: 4/26/22 11:59 AM
"""
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


import logging

from vultron.sim.communications import Message

from vultron.bt.base.bt_node import ActionNode
from vultron.bt.base.node_status import NodeStatus
from vultron.bt.messaging.behaviors import incoming_message
from vultron.bt.messaging.states import MessageTypes as MT

logger = logging.getLogger(__name__)


class EmitMsg(ActionNode):
    name_pfx = "!"
    msg_type = None

    def __init__(self):
        super().__init__()
        self.name = f"{self.name}_{self.msg_type}"

    def _tick(self, depth=0):
        indent = "  " * (depth)
        logger.info(f"->{indent}{self.msg_type}")

        msg = Message(sender=self.bb.name, type=self.msg_type, body="msg_body")
        emit = self.bb.emit_func
        if emit is not None:
            emit(msg)
        else:
            logger.debug("Emitter not set")

        # append history
        self.bb.msg_history.append(msg)
        self.bb.msgs_emitted_this_tick.append(msg.type)
        incoming_message(self.bb, msg)

        return NodeStatus.SUCCESS


class EmitCV(EmitMsg):
    msg_type = MT.CV


class EmitCF(EmitMsg):
    msg_type = MT.CF


class EmitCD(EmitMsg):
    msg_type = MT.CD


class EmitCP(EmitMsg):
    msg_type = MT.CP


class EmitCX(EmitMsg):
    msg_type = MT.CX


class EmitCA(EmitMsg):
    msg_type = MT.CA


class EmitCE(EmitMsg):
    msg_type = MT.CE


class EmitCK(EmitMsg):
    msg_type = MT.CK


class EmitRS(EmitMsg):
    msg_type = MT.RS


class EmitRI(EmitMsg):
    msg_type = MT.RI


class EmitRV(EmitMsg):
    msg_type = MT.RV


class EmitRA(EmitMsg):
    msg_type = MT.RA


class EmitRD(EmitMsg):
    msg_type = MT.RD


class EmitRC(EmitMsg):
    msg_type = MT.RC


class EmitRE(EmitMsg):
    msg_type = MT.RE


class EmitRK(EmitMsg):
    msg_type = MT.RK


class EmitEP(EmitMsg):
    msg_type = MT.EP


class EmitER(EmitMsg):
    msg_type = MT.ER


class EmitEA(EmitMsg):
    msg_type = MT.EA


class EmitEV(EmitMsg):
    msg_type = MT.EV


class EmitEJ(EmitMsg):
    msg_type = MT.EJ


class EmitEC(EmitMsg):
    msg_type = MT.EC


class EmitET(EmitMsg):
    msg_type = MT.ET


class EmitEK(EmitMsg):
    msg_type = MT.EK


class EmitEE(EmitMsg):
    msg_type = MT.EE


class EmitGI(EmitMsg):
    msg_type = MT.GI


class EmitGE(EmitMsg):
    msg_type = MT.GE


class EmitGK(EmitMsg):
    msg_type = MT.GK


Emitters = EmitMsg.__subclasses__()


def main():
    pass


if __name__ == "__main__":
    main()
