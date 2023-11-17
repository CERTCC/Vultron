#!/usr/bin/env python
"""
This module contains common behaviors that are used by the inbound message handler.
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

from vultron.bt.base.bt_node import BtNode
from vultron.bt.base.factory import action_node

logger = logging.getLogger(__name__)


def pop_message(obj: BtNode) -> bool:
    """Pop the next message off the blackboard's incoming message queue."""

    # make sure there's not already a message to be handled
    if obj.bb.current_message is not None:
        return False

    if not obj.bb.incoming_messages:
        return False

    # take one down
    # pass it around
    obj.bb.current_message = obj.bb.incoming_messages.popleft()
    logger.debug(f"** <-- Recv {obj.bb.current_message.msg_type}")
    return True


PopMessage = action_node("PopMessage", pop_message)


def push_message(obj: BtNode) -> bool:
    """Push the current message back onto the blackboard's incoming message queue."""
    # if there's no message, we're done
    if obj.bb.current_message is not None:
        # there is a message, so see if we can
        # put it back on the queue to be handled next
        try:
            obj.bb.incoming_messages.appendleft(obj.bb.current_message)
            obj.bb.current_message = None
        except IndexError as e:
            logger.warning(f"Caught error: {e}")
            return False

    return True


PushMessage = action_node(
    "PushMessage",
    push_message,
)


def log_message(obj: BtNode) -> bool:
    """Log the current message."""

    if obj.bb.current_message is not None:
        msg_type = obj.bb.current_message.msg_type
        obj.bb.msgs_received_this_tick.append(msg_type)

    return True


LogMsg = action_node(
    "LogMsg",
    log_message,
)


def unset_current_message(obj: BtNode) -> bool:
    """Unset the current message in the blackboard."""

    obj.bb.current_message = None
    return True


UnsetCurrentMsg = action_node(
    "UnsetCurrentMsg",
    unset_current_message,
)
