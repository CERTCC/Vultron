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

from vultron.bt.base.factory import fallback_node, sequence_node
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


_HandleGeMessage = sequence_node(
    "_HandleGeMessage",
    """Handle general error (GE) messages.""",
    IsMsgTypeGE,
    FollowUpOnErrorMessage,
)


_HandleGmMessageTypes = fallback_node(
    "_HandleGmMessageTypes",
    """Handle GI messages.""",
    IsMsgTypeGI,
    _HandleGeMessage,
)


_HandleAckableGmMessages = sequence_node(
    "_HandleAckableGmMessages",
    """Handle ackable GI messages.""",
    _HandleGmMessageTypes,
    EmitGK,
)


_HandleGmMessage = fallback_node(
    "_HandleGmMessage",
    """Handle GM messages.""",
    IsMsgTypeGK,
    _HandleAckableGmMessages,
)


ProcessMessagesOtherBt = sequence_node(
    "ProcessMessagesOtherBt",
    """Process GI messages""",
    IsGMMessage,
    _HandleGmMessage,
)


def main():
    show_graph(ProcessMessagesOtherBt)


if __name__ == "__main__":
    main()
