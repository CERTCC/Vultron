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
subclasses that answer *yes* or *no* stochastically, matching the Words of
Estimative Probability naming convention used throughout the Vultron demo
layer.

``WeightedBehavior`` is a
:class:`~vultron.core.behaviors.call_out.backend.CallOutBackend`: each
subclass sets a ``success_rate`` class attribute, and ``answer()`` gives *yes*
with that probability, carrying a type-conformant value for every output
its ``contract`` declares (BT-18-003), and *no* otherwise, with a reason
naming the simulated refusal (ADR-0183).  A simulation never answers *error*.

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

from vultron.core.behaviors.call_out.answer import CallOutAnswer, constant_yes
from vultron.core.behaviors.call_out.backend import CallOutBackend


class WeightedBehavior(CallOutBackend):
    """Base class for probabilistic demo fuzzer nodes.

    Answers *yes* with probability ``success_rate`` and *no* otherwise.
    Subclasses set ``success_rate`` as a class attribute.

    Args:
        name: Display name for the node in the behaviour tree.  Defaults
            to the class name.
    """

    success_rate: float = 0.5

    def answer(self) -> CallOutAnswer:
        """Answer *yes* or *no* based on the ``success_rate`` probability."""
        if random.random() < self.success_rate:
            return self.yes()
        return self.no()

    def yes(self) -> CallOutAnswer:
        """A *yes* with a value for every declared output (BT-18-003).

        The same answer the core DETERMINISTIC ceiling gives
        (:func:`~vultron.core.behaviors.call_out.answer.constant_yes`).
        """
        return constant_yes(self.contract)

    def no(self) -> CallOutAnswer:
        """A *no* whose reason names the simulated refusal."""
        return CallOutAnswer.no(
            f"{self.name}: simulated refusal "
            f"(success rate {self.success_rate:.3g})",
            {key: typ() for key, typ in self.contract.refusal_fields.items()},
        )


class AlwaysSucceed(WeightedBehavior):
    """Always answers *yes* (success_rate = 1.0)."""

    success_rate = 1.0

    def answer(self) -> CallOutAnswer:
        return self.yes()


class AlwaysFail(WeightedBehavior):
    """Always answers *no* (success_rate = 0.0)."""

    success_rate = 0.0

    def answer(self) -> CallOutAnswer:
        return self.no()


class AlmostCertainlySucceed(WeightedBehavior):
    """Answers *yes* with probability 0.93."""

    success_rate = 93.0 / 100.0


class AlmostAlwaysSucceed(WeightedBehavior):
    """Answers *yes* with probability 0.90."""

    success_rate = 9.0 / 10.0


class UsuallySucceed(WeightedBehavior):
    """Answers *yes* with probability 0.75."""

    success_rate = 3.0 / 4.0


class OftenSucceed(WeightedBehavior):
    """Answers *yes* with probability 0.70."""

    success_rate = 7.0 / 10.0


class ProbablySucceed(WeightedBehavior):
    """Answers *yes* with probability 0.6667."""

    success_rate = 2.0 / 3.0


class UniformSucceedFail(WeightedBehavior):
    """Answers *yes* with probability 0.50."""

    success_rate = 1.0 / 2.0


class ProbablyFail(WeightedBehavior):
    """Answers *yes* with probability 0.3333."""

    success_rate = 1.0 / 3.0


class OftenFail(WeightedBehavior):
    """Answers *yes* with probability 0.30."""

    success_rate = 3.0 / 10.0


class UsuallyFail(WeightedBehavior):
    """Answers *yes* with probability 0.25."""

    success_rate = 1.0 / 4.0


class AlmostAlwaysFail(WeightedBehavior):
    """Answers *yes* with probability 0.10."""

    success_rate = 1.0 / 10.0


class AlmostCertainlyFail(WeightedBehavior):
    """Answers *yes* with probability 0.07."""

    success_rate = 7.0 / 100.0


class OneInTwenty(WeightedBehavior):
    """Answers *yes* with probability 0.05."""

    success_rate = 1.0 / 20.0


class OneInOneHundred(WeightedBehavior):
    """Answers *yes* with probability 0.01."""

    success_rate = 1.0 / 100.0


class OneInTwoHundred(WeightedBehavior):
    """Answers *yes* with probability 0.005."""

    success_rate = 1.0 / 200.0


# Aliases — Words of Estimative Probability convenience names
LikelySucceed = OftenSucceed
RarelySucceed = AlmostAlwaysFail
LikelyFail = OftenFail

# Aliases — semantic role names
RandomSucceedFail = UniformSucceedFail
RandomConditionNode = UniformSucceedFail
RandomActionNode = UniformSucceedFail
