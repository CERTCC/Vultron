#!/usr/bin/env python
"""file: prioritize_report
author: adh
created_at: 6/23/22 3:17 PM
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


import random

from vultron.bt.base.bt_node import ActionNode, ConditionCheck
from vultron.bt.base.composites import FallbackNode, SequenceNode
from vultron.bt.base.node_status import NodeStatus
from vultron.bt.messaging.outbound.behaviors import EmitRA, EmitRD
from vultron.bt.report_management.conditions import (
    RMinStateAccepted,
    RMinStateDeferred,
    RMinStateDeferredOrAccepted,
    RMinStateValidOrDeferredOrAccepted,
)
from vultron.bt.report_management.report_priority_states import (
    ReportPriority,
)
from vultron.bt.report_management.transitions import (
    q_rm_to_A,
    q_rm_to_D,
)
from ..fuzzer.prioritize_report import (
    EnoughPrioritizationInfo,
    GatherPrioritizationInfo,
    NoNewPrioritizationInfo,
    OnAccept,
    OnDefer,
)


class PriorityNotDefer(ConditionCheck):
    def func(self):
        return self.bb.priority != ReportPriority.DEFER


# todo: wire up SSVC lookup here
class EvaluatePriority(ActionNode):
    def _tick(self, depth=0):
        current_priority = self.bb.priority
        prioritization_count = self.bb.prioritization_count

        willing_to_reprioritize = (current_priority is None) or (
            random.random() < (0.5**prioritization_count)
        )

        if willing_to_reprioritize:
            new_priority = random.choice(list(ReportPriority))
            if new_priority != current_priority:
                self.bb.priority = new_priority
                self.bb.prioritization_count += 1

        return NodeStatus.SUCCESS


class GetMorePrioritizationInfo(SequenceNode):
    _children = (GatherPrioritizationInfo, NoNewPrioritizationInfo)


class EnsureAdequatePrioritizationInfo(FallbackNode):
    _children = (EnoughPrioritizationInfo, GetMorePrioritizationInfo)


class ConsiderGatheringMorePrioritizationInfo(SequenceNode):
    _children = (RMinStateDeferredOrAccepted, EnsureAdequatePrioritizationInfo)


class TransitionToRmAccepted(SequenceNode):
    _children = (OnAccept, q_rm_to_A, EmitRA)


class EnsureRmAccepted(FallbackNode):
    _children = (RMinStateAccepted, TransitionToRmAccepted)


class DecideIfFurtherActionNeeded(SequenceNode):
    _children = (
        RMinStateValidOrDeferredOrAccepted,
        EvaluatePriority,
        PriorityNotDefer,
        EnsureRmAccepted,
    )


class TransitionToRmDeferred(SequenceNode):
    _children = (OnDefer, q_rm_to_D, EmitRD)


class EnsureRmDeferred(FallbackNode):
    _children = (RMinStateDeferred, TransitionToRmDeferred)


class RMPrioritizeBt(FallbackNode):
    _children = (
        ConsiderGatheringMorePrioritizationInfo,
        DecideIfFurtherActionNeeded,
        EnsureRmDeferred,
    )


def main():
    pass


if __name__ == "__main__":
    main()
