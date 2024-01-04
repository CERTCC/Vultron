#  Copyright (c) 2023-2024 Carnegie Mellon University and Contributors.
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

from vultron.bt.base.bt_node import ActionNode, BtNode
from vultron.bt.base.factory import action_node, sequence_node
from vultron.bt.case_state.conditions import (
    CSinStateVendorAware,
    CSinStateVendorAwareAndFixReady,
)
from vultron.case_states.states import CS


def cs_state_change(
    name: str,
    target_state: str = None,
) -> Type[ActionNode]:
    """
    Factory function to create a class for transitioning to a new CS state.

    Args:
        name: the name of the class
        target_state: the target state shorthand for the transition (V,F,D,P,X,A)

    Returns:
        A class for transitioning to the given state

    """

    def _func(obj: BtNode) -> bool:
        f"""Transition to the target state {target_state}"""
        # get the current state name
        current_state_name = obj.bb.q_cs.name

        # note: we are operating on the node name string because the values
        # are more complex to work with (e.g. "Vendor Aware" vs "V")

        # force the corresponding letter in the state name to upper case
        # if the lower case is not in the state name, this will do nothing
        # which means this is a no-op for the upper-cased states
        new_state_name = current_state_name.replace(
            target_state.lower(), target_state
        )

        # set the state to the one with the new name
        try:
            new_state = CS[new_state_name]
        except KeyError:
            # just don't change the state if the new state name is invalid
            return True

        obj.bb.q_cs = new_state
        obj.bb.q_cs_history.append(new_state)

        # action node functions return True for success
        return True

    node_cls = action_node(name, _func)
    # add the target state as a class attribute (for testing)
    node_cls.target_state = target_state
    return node_cls


q_cs_to_V = cs_state_change("q_cs_to_V", "V")

# We will need to wrap this in a sequence node to enforce that
# the vendor is aware of the vulnerability before allowing the transition to Fix Ready
_q_cs_to_F = cs_state_change(
    "_q_cs_to_F",
    "F",
)

q_cs_to_F = sequence_node(
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
    "D",
)

q_cs_to_D = sequence_node(
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
q_cs_to_P = cs_state_change("q_cs_to_P", "P")
q_cs_to_X = cs_state_change("q_cs_to_X", "X")
q_cs_to_A = cs_state_change("q_cs_to_A", "A")
