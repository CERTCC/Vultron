#!/usr/bin/env python
"""file: rm_transitions
author: adh
created_at: 4/7/22 11:28 AM
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

from dataclasses import dataclass
from typing import List

from vultron.bt.common import EnumStateTransition, make_state_change
from vultron.bt.report_management.states import RM


@dataclass
class RmTransition(EnumStateTransition):
    """Represents a transition between two states in the q_rm state machine"""

    start_states = List[RM]
    end_state = RM


# Create the allowed transitions
_to_R = RmTransition(start_states=[RM.START], end_state=RM.RECEIVED)
_to_I = RmTransition(start_states=[RM.RECEIVED], end_state=RM.INVALID)
_to_V = RmTransition(
    start_states=[RM.RECEIVED, RM.INVALID], end_state=RM.VALID
)
_to_D = RmTransition(
    start_states=[RM.VALID, RM.ACCEPTED], end_state=RM.DEFERRED
)
_to_A = RmTransition(
    start_states=[RM.VALID, RM.DEFERRED], end_state=RM.ACCEPTED
)
_to_C = RmTransition(
    start_states=[RM.INVALID, RM.DEFERRED, RM.ACCEPTED], end_state=RM.CLOSED
)

# Create the state change functions
q_rm_to_R = make_state_change(key="q_rm", transition=_to_R)
q_rm_to_I = make_state_change(key="q_rm", transition=_to_I)
q_rm_to_V = make_state_change(key="q_rm", transition=_to_V)
q_rm_to_D = make_state_change(key="q_rm", transition=_to_D)
q_rm_to_A = make_state_change(key="q_rm", transition=_to_A)
q_rm_to_C = make_state_change(key="q_rm", transition=_to_C)
