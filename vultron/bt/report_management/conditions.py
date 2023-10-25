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

from vultron.bt.base.factory import fallback, invert
from vultron.bt.common import state_in
from vultron.bt.report_management.states import RM

RMinStateStart = state_in("q_rm", RM.START)
RMinStateReceived = state_in("q_rm", RM.RECEIVED)
RMinStateInvalid = state_in("q_rm", RM.INVALID)
RMinStateValid = state_in("q_rm", RM.VALID)
RMinStateDeferred = state_in("q_rm", RM.DEFERRED)
RMinStateAccepted = state_in("q_rm", RM.ACCEPTED)
RMinStateClosed = state_in("q_rm", RM.CLOSED)


RMnotInStateStart = invert(
    "RMnotInStateStart", "True when RM not in START", RMinStateStart
)
RMnotInStateClosed = invert(
    "RMnotInStateClosed", "True when RM not in CLOSED", RMinStateClosed
)

RMinStateDeferredOrAccepted = fallback(
    "RMinStateDeferredOrAccepted",
    "SUCCESS when the report management state is in the DEFERRED or ACCEPTED state. FAILURE otherwise.",
    RMinStateDeferred,
    RMinStateAccepted,
)

RMinStateReceivedOrInvalid = fallback(
    "RMinStateReceivedOrInvalid",
    "SUCCESS when the report management state is in the RECEIVED or INVALID state. FAILURE otherwise.",
    RMinStateReceived,
    RMinStateInvalid,
)

RMinStateStartOrClosed = fallback(
    "RMinStateStartOrClosed",
    "SUCCESS when the report management state is in the START or CLOSED state. FAILURE otherwise.",
    RMinStateStart,
    RMinStateClosed,
)


RMinStateValidOrDeferredOrAccepted = fallback(
    "RMinStateValidOrDeferredOrAccepted",
    "SUCCESS when the report management state is in the VALID, DEFERRED, or ACCEPTED state. FAILURE otherwise.",
    RMinStateValid,
    RMinStateDeferred,
    RMinStateAccepted,
)
