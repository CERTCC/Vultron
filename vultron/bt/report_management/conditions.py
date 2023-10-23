#!/usr/bin/env python
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
"""
Provides condition nodes for report management states.
"""


from vultron.bt.base.composites import FallbackNode
from vultron.bt.base.decorators import Invert
from vultron.bt.common import StateIn
from vultron.bt.report_management.errors import (
    ReportManagementConditionError,
)
from vultron.bt.report_management.states import RM


class RMinState(StateIn):
    """Base class for all report management state conditions.
    This class is used to check if the report management state is in a particular state.
    """

    key = "q_rm"
    states = RM
    Exc = ReportManagementConditionError


class RMinStateStart(RMinState):
    """Check if the report management state is in the START state."""

    state = RM.START


class RMinStateClosed(RMinState):
    """Check if the report management state is in the CLOSED state."""

    state = RM.CLOSED


class RMinStateReceived(RMinState):
    """Check if the report management state is in the RECEIVED state."""

    state = RM.RECEIVED


class RMinStateInvalid(RMinState):
    """Check if the report management state is in the INVALID state."""

    state = RM.INVALID


class RMinStateValid(RMinState):
    """Check if the report management state is in the VALID state."""

    state = RM.VALID


class RMinStateDeferred(RMinState):
    """Check if the report management state is in the DEFERRED state."""

    state = RM.DEFERRED


class RMinStateAccepted(RMinState):
    """Check if the report management state is in the ACCEPTED state."""

    state = RM.ACCEPTED


class RMnotInStateStart(Invert):
    """Check if the report management state is not in the START state."""

    _children = (RMinStateStart,)


class RMnotInStateClosed(Invert):
    """Check if the report management state is not in the CLOSED state."""

    _children = (RMinStateClosed,)


class RMinStateDeferredOrAccepted(FallbackNode):
    """Check if the report management state is in the DEFERRED or ACCEPTED state."""

    _children = (RMinStateDeferred, RMinStateAccepted)


class RMinStateReceivedOrInvalid(FallbackNode):
    """Check if the report management state is in the RECEIVED or INVALID state."""

    _children = (RMinStateReceived, RMinStateInvalid)


class RMinStateStartOrClosed(FallbackNode):
    """Check if the report management state is in the START or CLOSED state."""

    _children = (RMinStateStart, RMinStateClosed)


class RMinStateValidOrDeferredOrAccepted(FallbackNode):
    """Check if the report management state is in the VALID, DEFERRED, or ACCEPTED state."""

    _children = (RMinStateValid, RMinStateDeferred, RMinStateAccepted)
