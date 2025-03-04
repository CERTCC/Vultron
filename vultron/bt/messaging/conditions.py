#!/usr/bin/env python
"""
Provides messaging conditions for use in Vultron BTs.
"""
#  Copyright (c) 2023-2025 Carnegie Mellon University and Contributors.
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
from typing import Type

from vultron.bt.base.bt_node import BtNode, ConditionCheck
from vultron.bt.base.composites import FallbackNode
from vultron.bt.base.decorators import Invert
from vultron.bt.base.factory import condition_check, invert
from vultron.bt.common import show_graph
from vultron.bt.messaging.states import MessageTypes

logger = logging.getLogger(__name__)


def msg_queue_not_empty(obj: BtNode) -> bool:
    """True if the message queue is not empty"""
    return bool(obj.bb.incoming_messages)


MsgQueueNotEmpty = condition_check("MsgQueueNotEmpty", msg_queue_not_empty)

MsgQueueEmpty = invert(
    "MsgQueueEmpty", "True if the message queue is empty", MsgQueueNotEmpty
)


def check_msg_type(msg_t: MessageTypes) -> Type[ConditionCheck]:
    """Given a message type, return a condition check class for that message type"""

    if msg_t not in MessageTypes:
        raise ValueError(f"Invalid message type: {msg_t}")

    def func(obj: BtNode) -> bool:
        """True if the current message type is {msg_t}""" ""
        return obj.bb.current_message.msg_type == msg_t

    node_cls = condition_check(f"IsMsgType_{msg_t}", func)

    return node_cls


IsMsgTypeRS = check_msg_type(MessageTypes.RS)
IsMsgTypeRI = check_msg_type(MessageTypes.RI)
IsMsgTypeRV = check_msg_type(MessageTypes.RV)
IsMsgTypeRD = check_msg_type(MessageTypes.RD)
IsMsgTypeRA = check_msg_type(MessageTypes.RA)
IsMsgTypeRC = check_msg_type(MessageTypes.RC)
IsMsgTypeRK = check_msg_type(MessageTypes.RK)
IsMsgTypeRE = check_msg_type(MessageTypes.RE)

IsMsgTypeEP = check_msg_type(MessageTypes.EP)
IsMsgTypeER = check_msg_type(MessageTypes.ER)
IsMsgTypeEA = check_msg_type(MessageTypes.EA)
IsMsgTypeEV = check_msg_type(MessageTypes.EV)
IsMsgTypeEJ = check_msg_type(MessageTypes.EJ)
IsMsgTypeEC = check_msg_type(MessageTypes.EC)
IsMsgTypeET = check_msg_type(MessageTypes.ET)
IsMsgTypeEK = check_msg_type(MessageTypes.EK)
IsMsgTypeEE = check_msg_type(MessageTypes.EE)

IsMsgTypeCV = check_msg_type(MessageTypes.CV)
IsMsgTypeCF = check_msg_type(MessageTypes.CF)
IsMsgTypeCD = check_msg_type(MessageTypes.CD)
IsMsgTypeCP = check_msg_type(MessageTypes.CP)
IsMsgTypeCX = check_msg_type(MessageTypes.CX)
IsMsgTypeCA = check_msg_type(MessageTypes.CA)
IsMsgTypeCK = check_msg_type(MessageTypes.CK)
IsMsgTypeCE = check_msg_type(MessageTypes.CE)

IsMsgTypeGI = check_msg_type(MessageTypes.GI)
IsMsgTypeGK = check_msg_type(MessageTypes.GK)
IsMsgTypeGE = check_msg_type(MessageTypes.GE)


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
    for cls in [IsRMMessage, IsEMMessage, IsCSMessage, IsGMMessage]:
        show_graph(cls)


if __name__ == "__main__":
    main()
