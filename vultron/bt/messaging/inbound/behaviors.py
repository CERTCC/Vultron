#!/usr/bin/env python
"""
Provides behavior for inbound messaging.
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

from vultron.bt.base.composites import FallbackNode, SequenceNode
from vultron.bt.base.decorators import RepeatUntilFail
from vultron.bt.common import show_graph
from vultron.bt.messaging.conditions import MsgQueueNotEmpty
from vultron.bt.messaging.inbound._behaviors.common import (
    LogMsg,
    PopMessage,
    PushMessage,
    UnsetCurrentMsg,
)
from vultron.bt.messaging.inbound._behaviors.cs_messages import (
    ProcessCSMessagesBt,
)
from vultron.bt.messaging.inbound._behaviors.em_messages import (
    ProcessEMMessagesBt,
)
from vultron.bt.messaging.inbound._behaviors.general_messages import (
    ProcessMessagesOtherBt,
)
from vultron.bt.messaging.inbound._behaviors.rm_messages import (
    ProcessRMMessagesBt,
)
from vultron.bt.report_management.conditions import RMnotInStateClosed

logger = logging.getLogger(__name__)


class _HandleMessage(FallbackNode):
    """
    Handle the current message.
    Message handling is broken down into separate behaviors for each category of message type.
    E.g., RM messages, EM messages, CS messages, etc.
    """

    _children = (
        ProcessRMMessagesBt,
        ProcessEMMessagesBt,
        ProcessCSMessagesBt,
        ProcessMessagesOtherBt,
    )


class _ProcessNextMessage(SequenceNode):
    """Process the next message in the queue.
    Steps:
    1. Check that the queue is not empty.
    2. Pop the next message off the queue.
    3. Log the message.
    4. Handle the message.
    5. Unset the current message.
    """

    _children = (
        MsgQueueNotEmpty,
        PopMessage,
        LogMsg,
        _HandleMessage,
        UnsetCurrentMsg,
    )


class _ProcessMessage(FallbackNode):
    """Process the current message. If that fails, then put the message back in the queue."""

    _children = (_ProcessNextMessage, PushMessage)


class _ReceiveNextMessage(SequenceNode):
    """Within the context of an active case, this bt tree will receive and process
    the next message in the queue.
    """

    _children = (RMnotInStateClosed, MsgQueueNotEmpty, _ProcessMessage)


class ReceiveMessagesBt(RepeatUntilFail):
    """This is the top-level bt tree for the incoming messaging subsystem."""

    _children = (_ReceiveNextMessage,)


def main():
    show_graph(ReceiveMessagesBt)


if __name__ == "__main__":
    main()
