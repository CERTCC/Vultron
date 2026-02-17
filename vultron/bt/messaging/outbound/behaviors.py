#!/usr/bin/env python
"""
Provides outbound messaging behaviors for Vultron.
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
from typing import Callable

from vultron.bt.base.bt_node import ActionNode
from vultron.bt.base.factory import action_node
from vultron.bt.common import show_graph
from vultron.bt.messaging.behaviors import incoming_message
from vultron.bt.messaging.states import MessageTypes, MessageTypes as MT
from vultron.sim.messages import Message

logger = logging.getLogger(__name__)

# keep track of all emitters
_emitters = set()


def _emitter_func(
    msg_type: MessageTypes, body: str = "msg_body"
) -> Callable[[ActionNode], bool]:
    def func(obj: ActionNode) -> bool:
        f"""Emit a message of type {msg_type}."""

        msg = Message(sender=obj.bb.name, msg_type=msg_type, body=body)
        emit = obj.bb.emit_func
        if emit is not None:
            emit(msg)
        else:
            logger.debug("Emitter not set")

        # append history
        obj.bb.msg_history.append(msg)
        obj.bb.msgs_emitted_this_tick.append(msg.msg_type)
        incoming_message(obj.bb, msg)

        return True

    return func


def emitter(msg_type, body="msg_body"):
    node_cls = action_node(f"Emit_{msg_type}", _emitter_func(msg_type, body))
    node_cls.name_pfx = "!"
    node_cls.msg_type = msg_type

    _emitters.add(node_cls)

    return node_cls


EmitCV = emitter(MT.CV)
EmitCF = emitter(MT.CF)
EmitCD = emitter(MT.CD)
EmitCP = emitter(MT.CP)
EmitCX = emitter(MT.CX)
EmitCA = emitter(MT.CA)
EmitCE = emitter(MT.CE)
EmitCK = emitter(MT.CK)
EmitRS = emitter(MT.RS)
EmitRI = emitter(MT.RI)
EmitRV = emitter(MT.RV)
EmitRA = emitter(MT.RA)
EmitRD = emitter(MT.RD)
EmitRC = emitter(MT.RC)
EmitRE = emitter(MT.RE)
EmitRK = emitter(MT.RK)
EmitEP = emitter(MT.EP)
EmitER = emitter(MT.ER)
EmitEA = emitter(MT.EA)
EmitEV = emitter(MT.EV)
EmitEJ = emitter(MT.EJ)
EmitEC = emitter(MT.EC)
EmitET = emitter(MT.ET)
EmitEK = emitter(MT.EK)
EmitEE = emitter(MT.EE)
EmitGI = emitter(MT.GI)
EmitGE = emitter(MT.GE)
EmitGK = emitter(MT.GK)


def main():
    for emitter in _emitters:
        show_graph(emitter)


if __name__ == "__main__":
    main()
