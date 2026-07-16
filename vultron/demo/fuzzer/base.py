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
#  ("Third Party Software"). See LICENSE.md for more details.
#  Carnegie Mellon®, CERT® and CERT Coordination Center® are registered in the
#  U.S. Patent and Trademark Office by Carnegie Mellon University
"""Probabilistic base node types for the demo fuzzer, built on py_trees.

This module provides ``WeightedBehavior`` and a set of named probability
subclasses that return ``SUCCESS`` or ``FAILURE`` stochastically, matching
the Words of Estimative Probability naming convention used throughout the
Vultron demo layer.

Each subclass sets a ``success_rate`` class attribute and overrides
``update()`` to return ``py_trees.common.Status.SUCCESS`` or
``py_trees.common.Status.FAILURE`` (or ``RUNNING`` where noted).

References
----------
- Words of Estimative Probability:
  https://en.wikipedia.org/wiki/Words_of_estimative_probability
- Probability Survey by Mauboussin and Mauboussin:
  https://hbr.org/2018/07/if-you-say-something-is-likely-how-likely-do-people-think-it-is
- Source: ``vultron/bt/base/fuzzer.py``
- Spec: ``specs/behavior-tree-integration.yaml`` BT-16-001, BT-16-002
"""

from __future__ import annotations

import random

import py_trees
from py_trees.common import Status


class WeightedBehavior(py_trees.behaviour.Behaviour):
    """Base class for probabilistic demo fuzzer nodes.

    Returns ``Status.SUCCESS`` with probability ``success_rate`` and
    ``Status.FAILURE`` otherwise.  Subclasses set ``success_rate`` as a
    class attribute.

    Args:
        name: Display name for the node in the behaviour tree.  Defaults
            to the class name.
    """

    success_rate: float = 0.5

    def __init__(self, name: str = "") -> None:
        super().__init__(name=name or self.__class__.__name__)

    def update(self) -> Status:
        """Return SUCCESS or FAILURE based on success_rate probability."""
        if random.random() < self.success_rate:
            return Status.SUCCESS
        return Status.FAILURE


class SuccessOrRunning(py_trees.behaviour.Behaviour):
    """Returns ``Status.SUCCESS`` or ``Status.RUNNING`` with equal probability.

    Never returns ``Status.FAILURE``.  Useful for simulating long-running
    operations that eventually succeed.

    Args:
        name: Display name for the node.  Defaults to the class name.
    """

    def __init__(self, name: str = "") -> None:
        super().__init__(name=name or self.__class__.__name__)

    def update(self) -> Status:
        """Return SUCCESS or RUNNING with equal probability."""
        return random.choice((Status.SUCCESS, Status.RUNNING))


class AlwaysSucceed(WeightedBehavior):
    """Always returns ``Status.SUCCESS`` (success_rate = 1.0)."""

    success_rate = 1.0

    def update(self) -> Status:
        return Status.SUCCESS


class AlwaysFail(WeightedBehavior):
    """Always returns ``Status.FAILURE`` (success_rate = 0.0)."""

    success_rate = 0.0

    def update(self) -> Status:
        return Status.FAILURE


class AlmostCertainlySucceed(WeightedBehavior):
    """Returns ``Status.SUCCESS`` with probability 0.93."""

    success_rate = 93.0 / 100.0


class AlmostAlwaysSucceed(WeightedBehavior):
    """Returns ``Status.SUCCESS`` with probability 0.90."""

    success_rate = 9.0 / 10.0


class UsuallySucceed(WeightedBehavior):
    """Returns ``Status.SUCCESS`` with probability 0.75."""

    success_rate = 3.0 / 4.0


class OftenSucceed(WeightedBehavior):
    """Returns ``Status.SUCCESS`` with probability 0.70."""

    success_rate = 7.0 / 10.0


class ProbablySucceed(WeightedBehavior):
    """Returns ``Status.SUCCESS`` with probability 0.6667."""

    success_rate = 2.0 / 3.0


class UniformSucceedFail(WeightedBehavior):
    """Returns ``Status.SUCCESS`` with probability 0.50."""

    success_rate = 1.0 / 2.0


class ProbablyFail(WeightedBehavior):
    """Returns ``Status.SUCCESS`` with probability 0.3333."""

    success_rate = 1.0 / 3.0


class OftenFail(WeightedBehavior):
    """Returns ``Status.SUCCESS`` with probability 0.30."""

    success_rate = 3.0 / 10.0


class UsuallyFail(WeightedBehavior):
    """Returns ``Status.SUCCESS`` with probability 0.25."""

    success_rate = 1.0 / 4.0


class AlmostAlwaysFail(WeightedBehavior):
    """Returns ``Status.SUCCESS`` with probability 0.10."""

    success_rate = 1.0 / 10.0


class AlmostCertainlyFail(WeightedBehavior):
    """Returns ``Status.SUCCESS`` with probability 0.07."""

    success_rate = 7.0 / 100.0


class OneInTwenty(WeightedBehavior):
    """Returns ``Status.SUCCESS`` with probability 0.05."""

    success_rate = 1.0 / 20.0


class OneInOneHundred(WeightedBehavior):
    """Returns ``Status.SUCCESS`` with probability 0.01."""

    success_rate = 1.0 / 100.0


class OneInTwoHundred(WeightedBehavior):
    """Returns ``Status.SUCCESS`` with probability 0.005."""

    success_rate = 1.0 / 200.0


# Aliases — Words of Estimative Probability convenience names
LikelySucceed = OftenSucceed
RarelySucceed = AlmostAlwaysFail
LikelyFail = OftenFail

# Aliases — semantic role names
RandomSucceedFail = UniformSucceedFail
RandomConditionNode = UniformSucceedFail
RandomActionNode = UniformSucceedFail
