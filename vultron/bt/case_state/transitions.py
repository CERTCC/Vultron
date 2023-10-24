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
from typing import Type

from vultron.bt.base.bt_node import ActionNode
from vultron.bt.base.factory import sequence
from vultron.bt.case_state.conditions import (
    CSinStateVendorAware,
    CSinStateVendorAwareAndFixReady,
)
from vultron.case_states.states import CS


def cs_state_change(
    name: str,
    docstr: str,
    target_state: str = None,
) -> Type[ActionNode]:
    """
    Factory function to create a class for transitioning to a new CS state.

    Args:
        name: the name of the class
        docstr: the docstring for the class
        target_state: the target state shorthand for the transition (V,F,D,P,X,A)

    Returns:
        A class for transitioning to the given state

    """

    class _CsStateChange(ActionNode):
        f"""{docstr}"""

        to_state = target_state

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)

            if self.to_state is None:
                raise ValueError("to_state must be set")

        def func(self):
            # get the current state name
            current_state_name = self.bb.q_cs.name

            # note: we are operating on the node name string because the values
            # are more complex to work with (e.g. "Vendor Aware" vs "V")

            # force the corresponding letter in the state name to upper case
            # if the lower case is not in the state name, this will do nothing
            # which means this is a no-op for the upper-cased states
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

    # explicitly set the name of the class
    # so it doesn't show up as _CsStateChange in the BT
    _CsStateChange.__name__ = name
    return _CsStateChange


q_cs_to_V = cs_state_change("q_cs_to_V", "Transition to Vendor Aware", "V")

# We will need to wrap this in a sequence node to enforce that
# the vendor is aware of the vulnerability before allowing the transition to Fix Ready
_q_cs_to_F = cs_state_change(
    "_q_cs_to_F",
    """
    Transition to Fix Ready.

    This class is not intended to be used directly outside of this module.
    Instead, use the q_cs_to_F class defined below.
    """,
    "F",
)

q_cs_to_F = sequence(
    "q_cs_to_F",
    """
    Sequence node for transitioning from V to F.
    Enforces that the vendor is aware of the vulnerability before allowing the transition to Fix Ready
    """,
    CSinStateVendorAware,
    _q_cs_to_F,
)


# We will need to wrap this in a sequence node to enforce that
# the fix is ready before allowing the transition to Fix Deployed
_q_cs_to_D = cs_state_change(
    "_q_cs_to_D",
    """
    Transition to Fix Deployed

    This class is not intended to be used directly outside of this module.
    Instead, use the q_cs_to_D class defined below.
    """,
    "D",
)

q_cs_to_D = sequence(
    "q_cs_to_D",
    """
    Sequence node for transitioning from F to D.
    Enforces that the vendor is aware of the vulnerability and has a fix ready before allowing the transition to Fix Deployed.
    """,
    CSinStateVendorAwareAndFixReady,
    _q_cs_to_D,
)


# # The remaining transitions are simple and do not need to be wrapped
# # in a sequence node because they do not have any conditions that need to be enforced
q_cs_to_P = cs_state_change("q_cs_to_P", "Transition to Public Aware", "P")
q_cs_to_X = cs_state_change("q_cs_to_X", "Transition to Exploit Public", "X")
q_cs_to_A = cs_state_change("q_cs_to_A", "Transition to Attacks Observed", "A")
