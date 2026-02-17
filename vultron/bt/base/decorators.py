#!/usr/bin/env python
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
"""
This module defines a number of Behavior Tree Decorator Nodes.
"""

import logging

from vultron.bt.base.bt_node import BtNode
from vultron.bt.base.node_status import NodeStatus

logger = logging.getLogger(__name__)


class BtDecorator(BtNode):
    """
    BtDecorator is the base class for all decorators in the Behavior Tree.
    """

    name_pfx = "d"


class Invert(BtDecorator):
    """Inverts the result of the child node.

    - If the child node returns SUCCESS, the Invert decorator will return FAILURE.
    - If the child node returns FAILURE, the Invert decorator will return SUCCESS.
    - If the child node returns RUNNING, the Invert decorator will return RUNNING.
    """

    name_pfx = "^"

    def _tick(self, depth=0):
        only_child = self.children[0]
        child_status = only_child.tick(depth + 1)

        if child_status == NodeStatus.FAILURE:
            return NodeStatus.SUCCESS
        elif child_status == NodeStatus.SUCCESS:
            return NodeStatus.FAILURE
        return NodeStatus.RUNNING


class RunningIsFailure(BtDecorator):
    """RunningIsFailure decorator returns FAILURE if the child node returns RUNNING.
    Otherwise, it returns the result of the child node.
    """

    def _tick(self, depth=0):
        only_child = self.children[0]
        child_status = only_child.tick(depth + 1)

        if child_status == NodeStatus.SUCCESS:
            return NodeStatus.SUCCESS
        return NodeStatus.FAILURE


class RunningIsSuccess(BtDecorator):
    """RunningIsSuccess decorator returns SUCCESS if the child node returns RUNNING.
    Otherwise, it returns the result of the child node.
    """

    def _tick(self, depth=0):
        only_child = self.children[0]
        child_status = only_child.tick(depth + 1)

        if child_status == NodeStatus.FAILURE:
            return NodeStatus.FAILURE
        return NodeStatus.SUCCESS


class ForceSuccess(BtDecorator):
    """ForceSuccess decorator returns SUCCESS no matter what the child node returns."""

    name_pfx = "S"

    def _tick(self, depth=0):
        only_child = self.children[0]
        child_status = only_child.tick(depth + 1)
        logger.debug(f"Child {only_child.name} returns {child_status}")
        return NodeStatus.SUCCESS


class ForceFailure(BtDecorator):
    """ForceFailure decorator returns FAILURE no matter what the child node returns."""

    name_pfx = "F"

    def _tick(self, depth=0):
        only_child = self.children[0]
        child_status = only_child.tick(depth + 1)
        logger.debug(f"Child {only_child.name} returns {child_status}")
        return NodeStatus.FAILURE


class ForceRunning(BtDecorator):
    """ForceRunning decorator returns RUNNING no matter what the child node returns."""

    name_pfx = "R"

    def _tick(self, depth=0):
        only_child = self.children[0]
        child_status = only_child.tick(depth + 1)
        logger.debug(f"Child {only_child.name} returns {child_status}")
        return NodeStatus.RUNNING


class LoopDecorator(BtDecorator):
    """LoopDecorator is the base class for all decorators that loop."""

    name_pfx = "l"
    reset = False

    def __init__(self):
        super().__init__()
        self.count = 0

    def _pre_tick(self, depth=0):
        if self.reset:
            self.count = 0


class RetryN(LoopDecorator):
    """
    Retry up to n times until the child returns success or running.
    When subclassing RetryN, set the `n` class variable to the number of retries.
    """

    n = 1

    def _tick(self, depth=0):
        only_child = self.children[0]
        for i in range(self.n):
            child_status = only_child.tick(depth + 1)
            self.count += 1
            if child_status == NodeStatus.FAILURE:
                continue
            if child_status == NodeStatus.SUCCESS:
                return NodeStatus.SUCCESS
            if child_status == NodeStatus.RUNNING:
                return NodeStatus.RUNNING
        return NodeStatus.FAILURE


class RepeatN(LoopDecorator):
    """
    Repeat up to n times until the child returns failure or running.
    When subclassing RepeatN, set the `n` class variable to the number of repeats.
    """

    n = 1

    def _tick(self, depth=0):
        only_child = self.children[0]
        for i in range(self.n):
            child_status = only_child.tick(depth + 1)
            self.count += 1
            if child_status == NodeStatus.SUCCESS:
                continue
            if child_status == NodeStatus.FAILURE:
                return NodeStatus.FAILURE
            if child_status == NodeStatus.RUNNING:
                return NodeStatus.RUNNING

        return NodeStatus.SUCCESS


class RepeatUntilFail(LoopDecorator):
    """
    Repeat until the child returns FAILURE, then return SUCCESS.
    """

    def _tick(self, depth=0):
        only_child = self.children[0]
        while True:
            child_status = only_child.tick(depth + 1)
            self.count += 1
            if child_status == NodeStatus.FAILURE:
                return NodeStatus.SUCCESS
