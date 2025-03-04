#!/usr/bin/env python
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
"""
Provides condition nodes for report management states.
"""
from typing import Type

from vultron.bt.base.bt_node import ConditionCheck
from vultron.bt.base.factory import fallback_node, invert
from vultron.bt.common import state_in
from vultron.bt.report_management.states import RM


def rm_state_in(state: RM) -> Type[ConditionCheck]:
    """
    Convenience function to create a ConditionCheck for a Report Management state.

    Args:
        state: a Report Management state

    Returns:
        A ConditionCheck class for the given state
    """
    if state not in RM:
        raise ValueError(f"Invalid Report Management state: {state}")

    return state_in("q_rm", state)


RMinStateStart = rm_state_in(RM.START)
RMinStateReceived = rm_state_in(RM.RECEIVED)
RMinStateInvalid = rm_state_in(RM.INVALID)
RMinStateValid = rm_state_in(RM.VALID)
RMinStateDeferred = rm_state_in(RM.DEFERRED)
RMinStateAccepted = rm_state_in(RM.ACCEPTED)
RMinStateClosed = rm_state_in(RM.CLOSED)


RMnotInStateStart = invert(
    "RMnotInStateStart", "True when RM not in START", RMinStateStart
)
RMnotInStateClosed = invert(
    "RMnotInStateClosed", "True when RM not in CLOSED", RMinStateClosed
)

RMinStateDeferredOrAccepted = fallback_node(
    "RMinStateDeferredOrAccepted",
    "SUCCESS when the report management state is in the DEFERRED or ACCEPTED state. FAILURE otherwise.",
    RMinStateDeferred,
    RMinStateAccepted,
)

RMinStateReceivedOrInvalid = fallback_node(
    "RMinStateReceivedOrInvalid",
    "SUCCESS when the report management state is in the RECEIVED or INVALID state. FAILURE otherwise.",
    RMinStateReceived,
    RMinStateInvalid,
)

RMinStateStartOrClosed = fallback_node(
    "RMinStateStartOrClosed",
    "SUCCESS when the report management state is in the START or CLOSED state. FAILURE otherwise.",
    RMinStateStart,
    RMinStateClosed,
)


RMinStateValidOrDeferredOrAccepted = fallback_node(
    "RMinStateValidOrDeferredOrAccepted",
    "SUCCESS when the report management state is in the VALID, DEFERRED, or ACCEPTED state. FAILURE otherwise.",
    RMinStateValid,
    RMinStateDeferred,
    RMinStateAccepted,
)
