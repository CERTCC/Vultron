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

from vultron.bt.base.bt_node import ActionNode
from vultron.bt.base.composites import SequenceNode
from vultron.bt.case_state.conditions import (
    CSinStateVendorAware,
    CSinStateVendorAwareAndFixReady,
)
from vultron.case_states.states import CS


class _CsStateChange(ActionNode):
    """
    Base class for transitioning the q_cs state

    This class is not intended to be used directly outside of this module.
    """

    to_state = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if self.to_state is None:
            raise ValueError("to_state must be set")

    def func(self):
        # get the current state name
        current_state_name = self.bb.q_cs.name

        # force the V in the state name to upper case
        # if "v" is not in the state name, this will do nothing
        # which means this is a no-op for the "V" states
        to_state = self.to_state
        from_state = to_state.lower()

        new_state_name = current_state_name.replace(from_state, to_state)

        # set the state to the one with the new name
        try:
            new_state = CS[new_state_name]
        except KeyError:
            # just don't change the state if the new state name is invalid
            return True

        self.bb.q_cs = new_state

        # action node functions return True for success
        return True


class q_cs_to_V(_CsStateChange):
    """
    Transition to Vendor Aware
    """

    to_state = "V"


class _q_cs_to_F(_CsStateChange):
    """
    Transition to Fix Ready.

    This class is not intended to be used directly outside of this module.
    Instead, use the q_cs_to_F class defined below.
    """

    # We will need to wrap this in a sequence node to enforce that
    # the vendor is aware of the vulnerability before allowing the transition to Fix Ready

    to_state = "F"


class q_cs_to_F(SequenceNode):
    """
    Sequence node for transitioning from V to F.
    Enforces that the vendor is aware of the vulnerability before allowing the transition to Fix Ready
    """

    _children = (CSinStateVendorAware, _q_cs_to_F)


class _q_cs_to_D(_CsStateChange):
    """
    Transition to Fix Deployed

    This class is not intended to be used directly outside of this module.
    Instead, use the q_cs_to_D class defined below.
    """

    to_state = "D"


class q_cs_to_D(SequenceNode):
    """
    Sequence node for transitioning from F to D.
    Enforces that the vendor is aware of the vulnerability and has a fix ready before allowing the transition to Fix Deployed.
    """

    _children = (CSinStateVendorAwareAndFixReady, _q_cs_to_D)


# # The remaining transitions are simple and do not need to be wrapped
# # in a sequence node because they do not have any conditions that need to be enforced
class q_cs_to_P(_CsStateChange):
    """
    Transition to Public Aware
    """

    to_state = "P"


class q_cs_to_X(_CsStateChange):
    """
    Transition to Exploit Public
    """

    to_state = "X"


class q_cs_to_A(_CsStateChange):
    """
    Transition to Attacks Observed
    """

    to_state = "A"
