#!/usr/bin/env python
"""
Provides report prioritization behaviors.
"""

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


import random

from vultron.bt.base.bt_node import BtNode
from vultron.bt.base.factory import (
    action_node,
    condition_check,
    fallback_node,
    sequence_node,
)
from vultron.bt.common import show_graph
from vultron.bt.messaging.outbound.behaviors import EmitRA, EmitRD
from vultron.bt.report_management.conditions import (
    RMinStateAccepted,
    RMinStateDeferred,
    RMinStateDeferredOrAccepted,
    RMinStateValidOrDeferredOrAccepted,
)
from vultron.bt.report_management.fuzzer.prioritize_report import (
    EnoughPrioritizationInfo,
    GatherPrioritizationInfo,
    NoNewPrioritizationInfo,
    OnAccept,
    OnDefer,
)
from vultron.bt.report_management.report_priority_states import (
    ReportPriority,
)
from vultron.bt.report_management.transitions import (
    q_rm_to_A,
    q_rm_to_D,
)


def priority_not_defer(obj: BtNode) -> bool:
    return bool(obj.bb.priority != ReportPriority.DEFER)


_PriorityNotDefer = condition_check("PriorityNotDefer", priority_not_defer)


# todo: wire up SSVC lookup here
def evaluate_priority(obj: BtNode) -> bool:
    """Dummy function that simulates a prioritization decision.
    This implementation randomly chooses a new priority.
    A real implementation could use something like SSVC to determine the priority.
    """
    current_priority = obj.bb.priority
    prioritization_count = obj.bb.prioritization_count

    willing_to_reprioritize = (current_priority is None) or (
        random.random() < (0.5**prioritization_count)
    )

    if willing_to_reprioritize:
        new_priority = random.choice(list(ReportPriority))
        if new_priority != current_priority:
            obj.bb.priority = new_priority
            obj.bb.prioritization_count += 1

    return True


_EvaluatePriority = action_node("EvaluatePriority", evaluate_priority)


_GetMorePrioritizationInfo = sequence_node(
    "_GetMorePrioritizationInfo",
    """This node represents the process of gathering more prioritization information.""",
    GatherPrioritizationInfo,
    NoNewPrioritizationInfo,
)


_EnsureAdequatePrioritizationInfo = fallback_node(
    "_EnsureAdequatePrioritizationInfo",
    """This node represents the process of ensuring that there is adequate prioritization information.
    If there is adequate prioritization information, then this node succeeds.
    If there is not adequate prioritization information, then this node attempts to gather more prioritization
    information.
    """,
    EnoughPrioritizationInfo,
    _GetMorePrioritizationInfo,
)


_ConsiderGatheringMorePrioritizationInfo = sequence_node(
    "_ConsiderGatheringMorePrioritizationInfo",
    """This node represents the process of considering whether to gather more prioritization information.
    If the RM state is in DEFERRED or ACCEPTED, then we might want to gather more prioritization information.
    """,
    RMinStateDeferredOrAccepted,
    _EnsureAdequatePrioritizationInfo,
)


_TransitionToRmAccepted = sequence_node(
    "_TransitionToRmAccepted",
    """This node represents the process of transitioning the RM state to the ACCEPTED state.
    Steps:
    1. Run the OnAccept behavior.
    2. Transition the RM state to the ACCEPTED state.
    3. Emit a RA message indicating that the RM state has been updated.
    """,
    OnAccept,
    q_rm_to_A,
    EmitRA,
)

_EnsureRmAccepted = fallback_node(
    "_EnsureRmAccepted",
    """This node represents the process of ensuring that the RM state is in the ACCEPTED state.
    If the RM state is in the ACCEPTED state, then this node succeeds.
    If the RM state is not in the ACCEPTED state, then this node attempts to transition the RM state to the
    ACCEPTED state.
    """,
    RMinStateAccepted,
    _TransitionToRmAccepted,
)


_DecideIfFurtherActionNeeded = sequence_node(
    "_DecideIfFurtherActionNeeded",
    """This node represents the process of deciding whether prioritization action is needed.
    If the RM state is in VALID or DEFERRED or ACCEPTED, then further action is needed.
    """,
    RMinStateValidOrDeferredOrAccepted,
    _EvaluatePriority,
    _PriorityNotDefer,
    _EnsureRmAccepted,
)


_TransitionToRmDeferred = sequence_node(
    "_TransitionToRmDeferred",
    """This node represents the process of transitioning the RM state to the DEFERRED state.
    Steps:
    1. Run the OnDefer behavior.
    2. Transition the RM state to the DEFERRED state.
    3. Emit a RD message indicating that the RM state has been updated.
    """,
    OnDefer,
    q_rm_to_D,
    EmitRD,
)


_EnsureRmDeferred = fallback_node(
    "_EnsureRmDeferred",
    """This node ensures that the RM state is in the DEFERRED state.
    If the RM state is already in the DEFERRED state, then this node succeeds.
    If the RM state is not in the DEFERRED state, then this node attempts to transition the RM state to the
    DEFERRED state.
    """,
    RMinStateDeferred,
    _TransitionToRmDeferred,
)


RMPrioritizeBt = fallback_node(
    "RMPrioritizeBt",
    """This node represents the process of prioritizing a report.
    Steps:
    1. Consider whether to gather more prioritization information.
    2. Decide whether prioritization action is needed. If so, possibly transition to the ACCEPTED state.
    3. If the previous steps fail, ensure that the RM state is in the DEFERRED state.
    """,
    _ConsiderGatheringMorePrioritizationInfo,
    _DecideIfFurtherActionNeeded,
    _EnsureRmDeferred,
)


def main():
    show_graph(RMPrioritizeBt)


if __name__ == "__main__":
    main()
