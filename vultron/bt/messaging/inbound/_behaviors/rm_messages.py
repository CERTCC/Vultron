#!/usr/bin/env python
"""file: rm_messages
author: adh
created_at: 6/27/22 1:48 PM
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
#
#  See LICENSE for details

from vultron.bt.base.composites import FallbackNode, SequenceNode
from vultron.bt.case_state.conditions import CSinStateVendorAware
from vultron.bt.case_state.transitions import q_cs_to_V
from vultron.bt.messaging.conditions import (
    IsMsgTypeRE,
    IsMsgTypeRK,
    IsMsgTypeRS,
    IsRMMessage,
)
from vultron.bt.messaging.inbound._behaviors.fuzzer import (
    FollowUpOnErrorMessage,
)
from vultron.bt.messaging.outbound.behaviors import EmitCV, EmitRE, EmitRK
from vultron.bt.report_management.conditions import RMnotInStateStart
from vultron.bt.report_management.transitions import q_rm_to_R
from vultron.bt.roles.conditions import RoleIsNotVendor


class HandleRe(SequenceNode):
    """This is a stub for handling an RE message.
    Steps:
    1. Check that the message is an RE message.
    2. Follow up on what the RE message means.
    """

    _children = (IsMsgTypeRE, FollowUpOnErrorMessage)


class LeaveRmStart(FallbackNode):
    """Leave the RM start state by transitioning to the RECEIVED state."""

    _children = (RMnotInStateStart, q_rm_to_R)


class SetVendorAware(SequenceNode):
    """Set the case state to vendor aware.
    Steps:
    1. Check whether we're already in the VENDOR_AWARE state.
    2. If not, transition to the VENDOR_AWARE state.
    3. Emit a CV message to indicate the transition.
    """

    _children = (CSinStateVendorAware, q_cs_to_V, EmitCV)


class RecognizeVendorNotifiedIfNecessary(FallbackNode):
    """If we're a vendor, recognize that we've been notified.
    Short-circuits if we're not a vendor.
    """

    _children = (RoleIsNotVendor, SetVendorAware)


class HandleRs(SequenceNode):
    """Handle an RS message. The RS message type indicates an incoming report.
    Steps:
    1. Check the message type.
    2. If we're in the start state, leave the start state.
    3. If we're a vendor, recognize that we've been notified.
    """

    _children = (
        IsMsgTypeRS,
        LeaveRmStart,
        RecognizeVendorNotifiedIfNecessary,
    )


class ChooseRmMsgReaction(FallbackNode):
    """Choose the appropriate reaction to an RM message.
    In most cases the only reaction is to acknowledge the message, which is handled by this node's parent.
    Steps:
    1. If it's an RS message, handle it.
    2. If it's an RE message, handle it.
    3. If it's anything else, we just need to confirm that we're not in the start state.
    """

    _children = (HandleRs, HandleRe, RMnotInStateStart)


class HandleAckableRmMessage(SequenceNode):
    """Handle an RM message that expects an ACK.
    Steps:
    1. Handle the message.
    2. Emit an RK message in acknowledgement.
    If all succeed, the node will succeed.
    If any fail, the node will fail.
    """

    _children = (ChooseRmMsgReaction, EmitRK)


class HandleRmMessage(FallbackNode):
    """Handle an RM message.
    Steps:
    1. If it's an RK message, no need to do anything.
    2. If it's a message that expects an ACK, handle it.
    3. If it wasn't one of the above, emit an RE message indicating an error.
    If any these succeed, the node will succeed.
    If all fail, the node will fail.
    """

    _children = (IsMsgTypeRK, HandleAckableRmMessage, EmitRE)


class ProcessRMMessagesBt(SequenceNode):
    """Behavior tree for processing RM messages."""

    _children = (IsRMMessage, HandleRmMessage)
