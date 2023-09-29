#!/usr/bin/env python
"""file: pacman_demo
author: adh
created_at: 4/1/22 11:13 AM

This is a demo of the bt tree library. It is a stub implementation of a bot that plays Pacman.

The tree structure is as follows:

Root(FallbackNode)
|-- MainSeq(SequenceNode) -- if a ghost is close, chase or avoid it depending on whether it is scared
|   |-- GhostClose(OftenSucceed) -- checks ghoste proximity
|   |-- ChaseOrAvoidGhost(FallbackNode) -- if a ghost is scared, chase it, otherwise avoid it
|   |   |-- ChaseIfScared(SequenceNode) -- if a ghost is scared, chase it
|   |   |   |-- GhostScared(RarelySucceed) -- checks if a ghost is scared
|   |   |   |-- ChaseGhost(UsuallySucceed) -- chases a ghost
|   |   |-- AvoidGhost(AlmostAlwaysSucceed) -- if a ghost is not scared, avoid it
|-- EatPills(AlwaysSucceed) -- eat pills if no ghosts are close

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


import logging

import vultron.bt.base.composites as bt
import vultron.bt.base.fuzzer as btz

logger = logging.getLogger(__name__)


class GhostClose(btz.OftenSucceed):
    """
    This is a stub for determining if a ghost is close. In our stub implementation, we just stochastically
    succeed 70% of the time.
    """


class GhostScared(btz.RarelySucceed):
    """This is a stub for determining if a ghost is scared. In our stub implementation, we just stochastically
    succeed 10% of the time.
    """


class ChaseGhost(btz.UsuallySucceed):
    """This is a stub for chasing a ghost. In our stub implementation, we just stochastically succeed 75% of the time."""


class ChaseIfScared(bt.SequenceNode):
    """This node implements chasing a ghost if it is scared."""

    _children = (GhostScared, ChaseGhost)


class AvoidGhost(btz.AlmostAlwaysSucceed):
    """This is a stub for avoiding a ghost. In our stub implementation, we just stochastically succeed 90% of the time."""


class ChaseOrAvoidGhost(bt.FallbackNode):
    """This node implements chasing a ghost if it is scared, otherwise it avoids the ghost."""

    _children = (ChaseIfScared, AvoidGhost)


class MainSeq(bt.SequenceNode):
    """This node implements the main sequence of the pacman bt tree."""

    _children = (GhostClose, ChaseOrAvoidGhost)


class EatPills(btz.AlwaysSucceed):
    """This is a stub for eating pills. In our stub implementation, we just succeed 100% of the time."""


class Root(bt.FallbackNode):
    """This node implements the root of the pacman bt tree."""

    _children = (MainSeq, EatPills)


def main():
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)
    handler = logging.StreamHandler()
    logger.addHandler(handler)

    for trial in range(10):
        print(f"Trial {trial}")
        root = Root()
        root.setup()
        root.tick()


if __name__ == "__main__":
    main()
