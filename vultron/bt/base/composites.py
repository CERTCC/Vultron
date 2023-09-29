#!/usr/bin/env python
"""file: composites
author: adh
created_at: 5/20/22 1:10 PM
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

from vultron.bt.base.bt_node import BtNode
from vultron.bt.base.node_status import NodeStatus


class SequenceNode(BtNode):
    """SequenceNode is a composite node that ticks its children in order.
    If a child returns SUCCESS, the SequenceNode ticks the next child.
    If a child returns RUNNING, the SequenceNode returns RUNNING.
    If a child returns FAILURE, the SequenceNode returns FAILURE.
    If all children return SUCCESS, the SequenceNode returns SUCCESS.
    """

    name_pfx = ">"

    # _node_shape = "rarrow"

    def _tick(self, depth=0):
        for child in self.children:
            child_status = child.tick(depth + 1)
            if child_status == NodeStatus.RUNNING:
                return NodeStatus.RUNNING
            elif child_status == NodeStatus.FAILURE:
                return NodeStatus.FAILURE
        return NodeStatus.SUCCESS


class FallbackNode(BtNode):
    """FallbackNode is a composite node that ticks its children in order.
    If a child returns SUCCESS, the FallbackNode returns SUCCESS.
    If a child returns RUNNING, the FallbackNode returns RUNNING.
    If a child returns FAILURE, the FallbackNode ticks the next child.
    If all children return FAILURE, the FallbackNode returns FAILURE.
    """

    name_pfx = "?"

    # _node_shape = "diamond"

    def _tick(self, depth=0):
        for child in self.children:
            child_status = child.tick(depth + 1)

            if child_status == NodeStatus.RUNNING:
                return NodeStatus.RUNNING
            elif child_status == NodeStatus.SUCCESS:
                return NodeStatus.SUCCESS
        return NodeStatus.FAILURE


SelectorNode = FallbackNode


class ParallelNode(BtNode):
    """
    ParallelNode is a composite node that ticks its children in parallel.
    If a child returns SUCCESS, the ParallelNode increments a success counter.
    If a child returns RUNNING, the ParallelNode increments a running counter.
    If a child returns FAILURE, the ParallelNode increments a failure counter.
    If the success counter reaches the minimum number of successes, the ParallelNode returns SUCCESS.
    If the failure counter reaches the minimum number of failures, the ParallelNode returns FAILURE.
    If the running counter reaches the minimum number of running, the ParallelNode returns RUNNING.
    """

    # todo this needs to have a policy for how to handle failures/successes in the children
    # e.g., a Sequence-like policy where all children must succeed, or a Selector-like policy where only one child needs to succeed
    # or just actually implement the parallelism as described in the docstring

    name_pfx = "="
    m = 1

    # _node_shape = "parallelogram"

    @property
    def N(self):
        return len(self.children)

    def set_min_successes(self, m):
        self.m = m

    def _tick(self, depth=0):
        successes = 0
        failures = 0

        # todo: this is a kludge because I'm too lazy to do real parallelism yet
        # randomize order so we don't get stuck
        children = list(self.children)
        random.shuffle(children)

        for child in children:
            child_status = child.tick(depth + 1)
            if child_status == NodeStatus.SUCCESS:
                successes += 1
            elif child_status == NodeStatus.FAILURE:
                failures += 1

            if successes >= self.m:
                return NodeStatus.SUCCESS
            elif failures > (self.N - self.m):
                return NodeStatus.FAILURE
        return NodeStatus.RUNNING
