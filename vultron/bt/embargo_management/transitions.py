#!/usr/bin/env python
"""file: em_transitions
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


from dataclasses import dataclass
from typing import List

from vultron.bt.common import EnumStateTransition, show_graph, state_change
from vultron.bt.embargo_management.states import EM


@dataclass
class EmTransition(EnumStateTransition):
    """Represents a transition between two states in the q_em state machine"""

    start_states: List[EM]
    end_state: EM


_to_P = EmTransition(
    start_states=[EM.NO_EMBARGO, EM.PROPOSED], end_state=EM.PROPOSED
)
_to_N = EmTransition(
    start_states=[EM.PROPOSED, EM.NO_EMBARGO], end_state=EM.NO_EMBARGO
)
_to_A = EmTransition(
    start_states=[EM.PROPOSED, EM.REVISE], end_state=EM.ACTIVE
)
_to_R = EmTransition(start_states=[EM.ACTIVE, EM.REVISE], end_state=EM.REVISE)
_R_to_A = EmTransition(start_states=[EM.REVISE], end_state=EM.ACTIVE)
_to_X = EmTransition(start_states=[EM.ACTIVE, EM.REVISE], end_state=EM.EXITED)

# Create the state change functions
q_em_to_P = state_change(key="q_em", transition=_to_P)
q_em_to_N = state_change(key="q_em", transition=_to_N)
q_em_to_A = state_change(key="q_em", transition=_to_A)
q_em_to_R = state_change(key="q_em", transition=_to_R)
q_em_to_X = state_change(key="q_em", transition=_to_X)

q_em_R_to_A = state_change(key="q_em", transition=_R_to_A)


def main():
    for x in [
        q_em_to_P,
        q_em_to_N,
        q_em_to_A,
        q_em_to_R,
        q_em_to_X,
        q_em_R_to_A,
    ]:
        print(x)
        show_graph(x)


if __name__ == "__main__":
    main()
