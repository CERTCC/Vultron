#!/usr/bin/env python
"""file: behavior_tree_fuzzer
author: adh
created_at: 4/12/22 1:18 PM

This is a fuzzer for bt trees. It's a bit of a hack, but it's useful for testing.
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


class AlwaysSucceed(BtNode):
    """Always returns NodeStatus.SUCCESS"""

    def _tick(self, depth=0):
        return NodeStatus.SUCCESS


class AlwaysFail(BtNode):
    """Always returns NodeStatus.FAILURE"""

    def _tick(self, depth=0):
        return NodeStatus.FAILURE


class AlwaysRunning(BtNode):
    """Always returns NodeStatus.RUNNING"""

    def _tick(self, depth=0):
        return NodeStatus.RUNNING


class RandomActionNodeWithRunning(BtNode):
    """Returns a random NodeStatus, including NodeStatus.RUNNING"""

    def _tick(self, depth=0):
        return random.choice(list(NodeStatus))


class SuccessOrRunning(BtNode):
    """Returns NodeStatus.SUCCESS or NodeStatus.RUNNING"""

    def _tick(self, depth=0):
        return random.choice((NodeStatus.SUCCESS, NodeStatus.RUNNING))


class WeightedSuccess(BtNode):
    """Returns NodeStatus.SUCCESS with a probability of success_rate.
    Otherwise, returns NodeStatus.FAILURE.
    """

    success_rate = 0.5
    name_pfx = "z"

    # _node_shape = "invtrapezium"

    def _tick(self, depth=0):
        if random.random() < self.success_rate:
            return NodeStatus.SUCCESS
        return NodeStatus.FAILURE


####################
# From here on down, the classes are just different success rates
# for the WeightedSuccess class.
# The names of the success rates are based on the following:
# https://en.wikipedia.org/wiki/Words_of_estimative_probability
# http://www.probabilitysurvey.com/
####################


class OneNinetyNineInTwoHundred(WeightedSuccess):
    """Returns NodeStatus.SUCCESS with a probability of 0.995."""

    success_rate = 199.0 / 200.0


class NinetyNineInOneHundred(WeightedSuccess):
    """Returns NodeStatus.SUCCESS with a probability of 0.99."""

    success_rate = 99.0 / 100.0


class FortyNineInFifty(WeightedSuccess):
    """Returns NodeStatus.SUCCESS with a probability of 0.98."""

    success_rate = 49.0 / 50.0


class TwentyNineInThirty(WeightedSuccess):
    """Returns NodeStatus.SUCCESS with a probability of 0.96667."""

    success_rate = 29.0 / 30.0


class NineteenInTwenty(WeightedSuccess):
    """Returns NodeStatus.SUCCESS with a probability of 0.95."""

    success_rate = 19.0 / 20.0


class AlmostCertainlySucceed(WeightedSuccess):
    """Returns NodeStatus.SUCCESS with a probability of 0.93."""

    success_rate = 93.0 / 100.0


class AlmostAlwaysSucceed(WeightedSuccess):
    """Returns NodeStatus.SUCCESS with a probability of 0.90."""

    success_rate = 9.0 / 10.0


class UsuallySucceed(WeightedSuccess):
    """Returns NodeStatus.SUCCESS with a probability of 0.75."""

    success_rate = 3.0 / 4.0


class OftenSucceed(WeightedSuccess):
    """Returns NodeStatus.SUCCESS with a probability of 0.70."""

    success_rate = 7.0 / 10.0


class ProbablySucceed(WeightedSuccess):
    """Returns NodeStatus.SUCCESS with a probability of 0.6667."""

    success_rate = 2.0 / 3.0


class UniformSucceedFail(WeightedSuccess):
    """Returns NodeStatus.SUCCESS with a probability of 0.50."""

    success_rate = 1.0 / 2.0


class ProbablyFail(WeightedSuccess):
    """Returns NodeStatus.SUCCESS with a probability of 0.3333."""

    success_rate = 1.0 / 3.0


class OftenFail(WeightedSuccess):
    """Returns NodeStatus.SUCCESS with a probability of 0.30."""

    success_rate = 3.0 / 10.0


class UsuallyFail(WeightedSuccess):
    """Returns NodeStatus.SUCCESS with a probability of 0.25."""

    success_rate = 1.0 / 4.0


class AlmostAlwaysFail(WeightedSuccess):
    """Returns NodeStatus.SUCCESS with a probability of 0.10."""

    success_rate = 1.0 / 10.0


class AlmostCertainlyFail(WeightedSuccess):
    """Returns NodeStatus.SUCCESS with a probability of 0.07."""

    success_rate = 7.0 / 100.0


class OneInTwenty(WeightedSuccess):
    """Returns NodeStatus.SUCCESS with a probability of 0.05."""

    success_rate = 1.0 / 20.0


class OneInThirty(WeightedSuccess):
    """Returns NodeStatus.SUCCESS with a probability of 0.033333."""

    success_rate = 1.0 / 30.0


class OneInFifty(WeightedSuccess):
    """Returns NodeStatus.SUCCESS with a probability of 0.02."""

    success_rate = 1.0 / 50.0


class OneInOneHundred(WeightedSuccess):
    """Returns NodeStatus.SUCCESS with a probability of 0.01."""

    success_rate = 1.0 / 100.0


class OneInTwoHundred(WeightedSuccess):
    """Returns NodeStatus.SUCCESS with a probability of 0.005."""

    success_rate = 1.0 / 200.0


# aliases
LikelyFail = OftenFail
RarelySucceed = AlmostAlwaysFail

RandomSucceedFail = UniformSucceedFail
RandomConditionNode = UniformSucceedFail
RandomActionNode = UniformSucceedFail
LikelySucceed = OftenSucceed
