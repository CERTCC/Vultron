#!/usr/bin/env python
"""This module provides condition check behavior tree nodes"""
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

from typing import Type

from vultron.bt.base.bt_node import ConditionCheck
from vultron.bt.base.factory import fallback_node
from vultron.bt.common import show_graph, state_in
from vultron.bt.embargo_management.states import EM


def em_state_in(state: EM) -> Type[ConditionCheck]:
    if state not in EM:
        raise ValueError(f"{state} is not a valid Embargo Management state")

    return state_in("q_em", state)


EMinStateNone = em_state_in(EM.NO_EMBARGO)
EMinStateProposed = em_state_in(EM.PROPOSED)
EMinStateActive = em_state_in(EM.ACTIVE)
EMinStateRevise = em_state_in(EM.REVISE)
EMinStateExited = em_state_in(EM.EXITED)


EMinStateActiveOrRevise = fallback_node(
    "EMinStateActiveOrRevise",
    """Check if the embargo management state is Active or Revise.""",
    EMinStateActive,
    EMinStateRevise,
)


EMinStateNoneOrExited = fallback_node(
    "EMinStateNoneOrExited",
    """Check if the embargo management state is None or Exited.""",
    EMinStateNone,
    EMinStateExited,
)

EMinStateProposeOrRevise = fallback_node(
    "EMinStateProposeOrRevise",
    """Check if the embargo management state is Proposed or Revise.""",
    EMinStateProposed,
    EMinStateRevise,
)


EMinStateNoneOrPropose = fallback_node(
    "EMinStateNoneOrPropose",
    """Check if the embargo management state is None or Proposed.""",
    EMinStateNone,
    EMinStateProposed,
)


EMinStateNoneOrProposeOrRevise = fallback_node(
    "EMinStateNoneOrProposeOrRevise",
    """Check if the embargo management state is None or Proposed or Revise.""",
    EMinStateNone,
    EMinStateProposed,
    EMinStateRevise,
)


def main():
    for cls in [
        EMinStateNone,
        EMinStateProposed,
        EMinStateActive,
        EMinStateRevise,
        EMinStateExited,
        EMinStateActiveOrRevise,
        EMinStateNoneOrExited,
        EMinStateProposeOrRevise,
        EMinStateNoneOrPropose,
        EMinStateNoneOrProposeOrRevise,
    ]:
        print(cls)
        show_graph(cls)


if __name__ == "__main__":
    main()
