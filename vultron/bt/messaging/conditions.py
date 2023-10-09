#!/usr/bin/env python
"""file: message_type_conditions
author: adh
created_at: 4/26/22 10:24 AM
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

from vultron.bt.base.bt_node import ConditionCheck
from vultron.bt.base.composites import FallbackNode
from vultron.bt.base.decorators import Invert
from .states import MessageTypes

logger = logging.getLogger(__name__)


class MsgQueueNotEmpty(ConditionCheck):
    def func(self):
        # converts to boolean
        return bool(self.bb.incoming_messages)


class MsgQueueEmpty(Invert):
    _children = (MsgQueueNotEmpty,)


def is_msg_type_factory(msg_t: MessageTypes) -> ConditionCheck:
    """Given a message type, return a condition check class for that message type"""
    assert msg_t in MessageTypes

    class IsMsgType(ConditionCheck):
        msg_type = msg_t

        def __init__(self):
            super().__init__()
            self.name = f"IsMsgType_{self.msg_type}"

        def func(self):
            msg = self.bb.current_message
            return msg.msg_type == self.msg_type

    return IsMsgType


IsMsgTypeRS = is_msg_type_factory(MessageTypes.RS)
IsMsgTypeRI = is_msg_type_factory(MessageTypes.RI)
IsMsgTypeRV = is_msg_type_factory(MessageTypes.RV)
IsMsgTypeRD = is_msg_type_factory(MessageTypes.RD)
IsMsgTypeRA = is_msg_type_factory(MessageTypes.RA)
IsMsgTypeRC = is_msg_type_factory(MessageTypes.RC)
IsMsgTypeRK = is_msg_type_factory(MessageTypes.RK)
IsMsgTypeRE = is_msg_type_factory(MessageTypes.RE)

IsMsgTypeEP = is_msg_type_factory(MessageTypes.EP)
IsMsgTypeER = is_msg_type_factory(MessageTypes.ER)
IsMsgTypeEA = is_msg_type_factory(MessageTypes.EA)
IsMsgTypeEV = is_msg_type_factory(MessageTypes.EV)
IsMsgTypeEJ = is_msg_type_factory(MessageTypes.EJ)
IsMsgTypeEC = is_msg_type_factory(MessageTypes.EC)
IsMsgTypeET = is_msg_type_factory(MessageTypes.ET)
IsMsgTypeEK = is_msg_type_factory(MessageTypes.EK)
IsMsgTypeEE = is_msg_type_factory(MessageTypes.EE)

IsMsgTypeCV = is_msg_type_factory(MessageTypes.CV)
IsMsgTypeCF = is_msg_type_factory(MessageTypes.CF)
IsMsgTypeCD = is_msg_type_factory(MessageTypes.CD)
IsMsgTypeCP = is_msg_type_factory(MessageTypes.CP)
IsMsgTypeCX = is_msg_type_factory(MessageTypes.CX)
IsMsgTypeCA = is_msg_type_factory(MessageTypes.CA)
IsMsgTypeCK = is_msg_type_factory(MessageTypes.CK)
IsMsgTypeCE = is_msg_type_factory(MessageTypes.CE)

IsMsgTypeGI = is_msg_type_factory(MessageTypes.GI)
IsMsgTypeGK = is_msg_type_factory(MessageTypes.GK)
IsMsgTypeGE = is_msg_type_factory(MessageTypes.GE)


class IsRMMessage(FallbackNode):
    _children = (
        IsMsgTypeRK,
        IsMsgTypeRS,
        IsMsgTypeRI,
        IsMsgTypeRV,
        IsMsgTypeRD,
        IsMsgTypeRA,
        IsMsgTypeRC,
        IsMsgTypeRE,
    )


class IsEMMessage(FallbackNode):
    _children = (
        IsMsgTypeEK,
        IsMsgTypeEP,
        IsMsgTypeER,
        IsMsgTypeEA,
        IsMsgTypeEV,
        IsMsgTypeEJ,
        IsMsgTypeEC,
        IsMsgTypeET,
        IsMsgTypeEE,
    )


class IsCSMessage(FallbackNode):
    _children = (
        IsMsgTypeCK,
        IsMsgTypeCV,
        IsMsgTypeCF,
        IsMsgTypeCD,
        IsMsgTypeCP,
        IsMsgTypeCX,
        IsMsgTypeCA,
        IsMsgTypeCE,
    )


class IsGMMessage(FallbackNode):
    _children = (IsMsgTypeGK, IsMsgTypeGI, IsMsgTypeGE)


class NotRMMessage(Invert):
    _children = (IsRMMessage,)


class NotEMMessage(Invert):
    _children = (IsEMMessage,)


class NotCSMessage(Invert):
    _children = (IsCSMessage,)


class NotGMMessage(Invert):
    _children = (IsGMMessage,)


def main():
    pass


if __name__ == "__main__":
    main()
