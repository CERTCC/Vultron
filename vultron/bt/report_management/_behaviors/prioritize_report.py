#!/usr/bin/env python
"""
Provides report prioritization behaviors.
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


class _PriorityNotDefer(ConditionCheck):
    def func(self):
        return self.bb.priority != ReportPriority.DEFER


# todo: wire up SSVC lookup here
class _EvaluatePriority(ActionNode):
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


class _GetMorePrioritizationInfo(SequenceNode):
    _children = (GatherPrioritizationInfo, NoNewPrioritizationInfo)


class _EnsureAdequatePrioritizationInfo(FallbackNode):
    _children = (EnoughPrioritizationInfo, _GetMorePrioritizationInfo)


class _ConsiderGatheringMorePrioritizationInfo(SequenceNode):
    _children = (
        RMinStateDeferredOrAccepted,
        _EnsureAdequatePrioritizationInfo,
    )


class _TransitionToRmAccepted(SequenceNode):
    _children = (OnAccept, q_rm_to_A, EmitRA)


class _EnsureRmAccepted(FallbackNode):
    _children = (RMinStateAccepted, _TransitionToRmAccepted)


class _DecideIfFurtherActionNeeded(SequenceNode):
    _children = (
        RMinStateValidOrDeferredOrAccepted,
        _EvaluatePriority,
        _PriorityNotDefer,
        _EnsureRmAccepted,
    )


class _TransitionToRmDeferred(SequenceNode):
    _children = (OnDefer, q_rm_to_D, EmitRD)


class _EnsureRmDeferred(FallbackNode):
    _children = (RMinStateDeferred, _TransitionToRmDeferred)


class RMPrioritizeBt(FallbackNode):
    _children = (
        _ConsiderGatheringMorePrioritizationInfo,
        _DecideIfFurtherActionNeeded,
        _EnsureRmDeferred,
    )


def main():
    pass


if __name__ == "__main__":
    main()
