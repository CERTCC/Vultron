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
This module defines the CVD Case State Machine as a Behavior Tree.
"""


from functools import partial

from vultron.bt.base.composites import SequenceNode
from vultron.bt.case_state.conditions import (
    CSinStateVendorAware,
    CSinStateVendorAwareAndFixReady,
)
from vultron.bt.common import make_flag_state_change
from vultron.case_states.states import CS

# wrap the make_flag_state_change function to make it easier
# to create transitions for the q_cs state
make_cs_state_change = partial(make_flag_state_change, key="q_cs")

# create the transitions

q_cs_to_V = make_cs_state_change(end_state=CS.V)

# We will need to wrap this in a sequence node to enforce that
# the vendor is aware of the vulnerability before allowing the transition to Fix Ready
_q_cs_to_F = make_cs_state_change(end_state=CS.F)


class q_cs_to_F(SequenceNode):
    """
    Sequence node for transitioning from V to F.
    Enforces that the vendor is aware of the vulnerability before allowing the transition to Fix Ready
    """

    _children = (CSinStateVendorAware, _q_cs_to_F)


# Similarly, we will need to wrap this in a sequence node to enforce that
# the vendor is aware of the vulnerability and has a fix ready before allowing the transition to Fix Deployed
_q_cs_to_D = make_cs_state_change(end_state=CS.D)


class q_cs_to_D(SequenceNode):
    """
    Sequence node for transitioning from F to D.
    Enforces that the vendor is aware of the vulnerability and has a fix ready before allowing the transition to Fix Deployed.
    """

    _children = (CSinStateVendorAwareAndFixReady, _q_cs_to_D)


# The remaining transitions are simple and do not need to be wrapped
# in a sequence node because they do not have any conditions that need to be enforced
q_cs_to_P = make_cs_state_change(end_state=CS.P)
q_cs_to_X = make_cs_state_change(end_state=CS.X)
q_cs_to_A = make_cs_state_change(end_state=CS.A)

q_cs_to_V.__doc__ = "Transition to Vendor Aware"
q_cs_to_F.__doc__ = "Transition to Fix Ready"
q_cs_to_D.__doc__ = "Transition to Fix Deployed"
q_cs_to_P.__doc__ = "Transition to Public Aware"
q_cs_to_X.__doc__ = "Transition to Exploit Public"
q_cs_to_A.__doc__ = "Transition to Attacks Observed"
