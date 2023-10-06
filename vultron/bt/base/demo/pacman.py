#!/usr/bin/env python
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
"""
This is a demo of the bt tree library. It is a stub implementation of a bot that plays Pacman.

"""


import logging
import random

import vultron.bt.base.bt_node as btn
import vultron.bt.base.composites as bt
import vultron.bt.base.decorators as btd
import vultron.bt.base.fuzzer as btz
from vultron.bt.base.bt import BehaviorTree

logger = logging.getLogger(__name__)

SCORE = 0

DOTS = 240
PER_DOT = 10
PER_GHOST = 200
GHOST_INC = 2
GHOSTS_SCARED = False
GHOST_NAMES = ["Blinky", "Pinky", "Inky", "Clyde"]


### Action Nodes


class EatPill(btn.ActionNode):
    """increments score for eating pills"""

    def func(self):
        bb = self.bb

        dots = bb.get("dots", 0)
        if dots == 0:
            return False

        bb["dots"] -= 1
        bb["score"] += PER_DOT
        return True


class IncrGhostScore(btn.ActionNode):
    """increments the score for the next ghost."""

    def func(self):
        bb = self.bb
        bb["per_ghost"] *= GHOST_INC
        logger.info(f"Ghost score is now {self.bb['per_ghost']}")
        return True


class ScoreGhost(btn.ActionNode):
    """increments score for catching ghosts"""

    def func(self):
        bb = self.bb
        bb["score"] += bb["per_ghost"]
        return True


class DecrGhostCount(btn.ActionNode):
    """decrements the ghost count"""

    def func(self):
        ghost = self.bb["ghosts_remaining"].pop()
        logger.info(f"{ghost} was caught!")
        return True


### Condition Check Nodes


class GhostsRemain(btn.ConditionCheck):
    """
    checks if there are any ghosts remaining.

    Returns:
        SUCCESS if there are ghosts remaining, FAILURE otherwise
    """

    def func(self):
        bb = self.bb
        return len(bb["ghosts_remaining"]) > 0


class GhostsScared(btn.ConditionCheck):
    """
    determines if a ghost is scared.

    Returns:
        SUCCESS if a ghost is scared, FAILURE otherwise
    """

    def func(self):
        return self.bb["ghosts_scared"]


### Fuzzer Nodes


class GhostClose(btz.OftenSucceed):
    """
    determines if a ghost is close.

    Returns:
        SUCCESS if a ghost is close, FAILURE otherwise
    """


class ChaseGhost(btz.OftenSucceed):
    """
    chases a ghost.

    Returns:
        SUCCESS if a ghost is caught, FAILURE otherwise
    """


class AvoidGhost(btz.OftenSucceed):
    """
    implements avoiding a ghost.

    Returns:
        SUCCESS if no ghosts remain, or if a ghost is avoided, FAILURE otherwise
    """


### Composite Nodes


class NoMoreGhosts(btd.Invert):
    """
    inverts the result of GhostsRemain.

    Returns:
        SUCCESS if there are no ghosts remaining, FAILURE otherwise
    """

    _children = (GhostsRemain,)


class NoGhostClose(btd.Invert):
    """
    inverts the result of GhostClose.

    Returns:
        SUCCESS if a ghost is not close, FAILURE otherwise
    """

    _children = (GhostClose,)


class CaughtGhost(bt.SequenceNode):
    """
    handles actions after catching a ghost.
    """

    _children = (DecrGhostCount, ScoreGhost, IncrGhostScore)


class GhostsNotScared(btd.Invert):
    """
    inverts the result of GhostsScared.

    Returns:
        SUCCESS if a ghost is not scared, FAILURE otherwise
    """

    _children = (GhostsScared,)


class ChaseIfScared(bt.SequenceNode):
    """
    implements chasing a ghost if it is scared.

    Returns:
        SUCCESS if a ghost is caught, FAILURE otherwise
    """

    _children = (
        GhostsScared,
        ChaseGhost,
        CaughtGhost,
    )


class ChaseOrAvoidGhost(bt.FallbackNode):
    """
    implements chasing a ghost if it is scared, otherwise it avoids the ghost.

    Returns:
        SUCCESS if no ghosts remain, a ghost is caught or avoided, FAILURE otherwise
    """

    _children = (ChaseIfScared, GhostsScared, AvoidGhost)


class MaybeChaseOrAvoidGhost(bt.FallbackNode):
    """
    implements chasing a ghost if it is scared, otherwise it avoids the ghost.

    Returns:
        SUCCESS if no ghosts remain, a ghost is caught or avoided, FAILURE otherwise
    """

    _children = (NoMoreGhosts, NoGhostClose, ChaseOrAvoidGhost)


class MaybeEatPills(bt.SequenceNode):
    """
    implements eating pills if no ghosts are close.
    """

    _children = (MaybeChaseOrAvoidGhost, EatPill)


def do_tick(bot, ticks):
    bb = bot.bb

    logger.info(f"=== Tick {ticks + 1} ===")

    # maybe make the ghosts scared
    # note this also demonstrates the world changing outside the bot
    if random.random() < 0.5:
        bb["ghosts_scared"] = True
        logger.info("Ghosts are scared!")
    else:
        bb["ghosts_scared"] = False

    bot.tick()
    ticks += 1
    # die on the first failure
    if bot.status == bt.NodeStatus.FAILURE:
        logger.info(
            f"Pacman died! He was eaten by {random.choice(bb['ghosts_remaining'])}!"
        )
    if bb["dots"] <= 0:
        logger.info("Pacman cleared the board!")
    if ticks > 1000:
        logger.info("Pacman got bored and quit!")
    return bot.status


def main():
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)
    handler = logging.StreamHandler()
    logger.addHandler(handler)

    import argparse

    parser = argparse.ArgumentParser()
    parser.description = "Run the Pacman demo."
    parser.add_argument(
        "--print-tree",
        action="store_true",
        help="print the tree and exit",
        default=False,
    )
    args = parser.parse_args()

    bot = BehaviorTree(root=MaybeEatPills())
    bot.setup()

    bb = bot.bb
    bb["dots"] = DOTS
    bb["score"] = SCORE
    bb["per_ghost"] = PER_GHOST
    bb["ghosts_scared"] = GHOSTS_SCARED
    bb["ghosts_remaining"] = GHOST_NAMES[:]

    if args.print_tree:
        print(bot.root.to_mermaid())
        exit()

    ticks = 0
    while bb["dots"] > 0:
        ticks += 1
        result = do_tick(bot, ticks)
        if result == bt.NodeStatus.FAILURE:
            break

    logger.info(f"Final score: {bb['score']}")
    logger.info(f"Ticks: {ticks}")
    logger.info(f"Dots Remaining: {bb['dots']}")
    logger.info(f"Ghosts Remaining: {bb['ghosts_remaining']}")


if __name__ == "__main__":
    main()
