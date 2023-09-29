#!/usr/bin/env python
"""file: common
author: adh
created_at: 6/27/22 1:36 PM

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

import vultron.bt.base.bt_node
import vultron.bt.base.node_status

logger = logging.getLogger(__name__)


class PopMessage(vultron.bt.base.bt_node.ActionNode):
    """
    Pop the next message off the blackboard's incoming message queue.
    """

    def _tick(self, depth=0):
        indent = "  " * (depth - 1)
        # make sure there's not already a message to be handled
        if self.bb.current_message is not None:
            return vultron.bt.base.node_status.NodeStatus.FAILURE

        if not self.bb.incoming_messages:
            return vultron.bt.base.node_status.NodeStatus.FAILURE

        msg_q = self.bb.incoming_messages
        # take one down
        next_msg = msg_q.popleft()
        # pass it around
        self.bb.current_message = next_msg
        logger.debug(f"**{indent}<-- Recv {next_msg}")
        return vultron.bt.base.node_status.NodeStatus.SUCCESS


class PushMessage(vultron.bt.base.bt_node.ActionNode):
    """Push the current message back onto the blackboard's incoming message queue."""

    def _tick(self, depth=0):
        msg_to_push = self.bb.current_message

        # if there's no message, we're done
        if msg_to_push is not None:
            # there is a message, so see if we can
            # put it back on the queue to be handled next
            msg_q = self.bb.incoming_messages
            try:
                msg_q.appendleft(msg_to_push)
                self.bb.current_message = None
            except IndexError as e:
                logger.warning(f"Caught error: {e}")
                return vultron.bt.base.node_status.NodeStatus.FAILURE

        return vultron.bt.base.node_status.NodeStatus.SUCCESS


class LogMsg(vultron.bt.base.bt_node.ActionNode):
    """Log the current message."""

    def _tick(self, depth=0):
        current_msg = self.bb.current_message
        if current_msg is not None:
            self.bb.msgs_received_this_tick.append(current_msg)
        return vultron.bt.base.node_status.NodeStatus.SUCCESS


class UnsetCurrentMsg(vultron.bt.base.bt_node.ActionNode):
    """Unset the current message in the blackboard."""

    def _tick(self, depth=0):
        self.bb.current_message = None
        return vultron.bt.base.node_status.NodeStatus.SUCCESS
