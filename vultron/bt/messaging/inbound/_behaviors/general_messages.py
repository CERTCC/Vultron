#!/usr/bin/env python
"""
Provides behaviors to handle general messages.
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


from vultron.bt.base.composites import FallbackNode, SequenceNode
from vultron.bt.common import show_graph
from vultron.bt.messaging.conditions import (
    IsGMMessage,
    IsMsgTypeGE,
    IsMsgTypeGI,
    IsMsgTypeGK,
)
from vultron.bt.messaging.inbound._behaviors.fuzzer import (
    FollowUpOnErrorMessage,
)
from vultron.bt.messaging.outbound.behaviors import EmitGK


# GENERAL messages


class _HandleGeMessage(SequenceNode):
    """Handle general error (GE) messages."""

    _children = (IsMsgTypeGE, FollowUpOnErrorMessage)


class _HandleGmMessageTypes(FallbackNode):
    """Handle GI messages."""

    _children = (IsMsgTypeGI, _HandleGeMessage)


class _HandleAckableGmMessages(SequenceNode):
    """Handle ackable GI messages."""

    _children = (_HandleGmMessageTypes, EmitGK)


class _HandleGmMessage(FallbackNode):
    """Handle GM messages."""

    _children = (IsMsgTypeGK, _HandleAckableGmMessages)


class ProcessMessagesOtherBt(SequenceNode):
    """Process GI messages"""

    _children = (IsGMMessage, _HandleGmMessage)


def main():
    show_graph(ProcessMessagesOtherBt)


if __name__ == "__main__":
    main()
