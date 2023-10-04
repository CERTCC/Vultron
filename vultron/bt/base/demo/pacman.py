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

The tree structure is:

(?) ?_Root_1
 | (>) >_MaybeEatPills_2
 |  | (^) ^_NoGhostClose_3
 |  |  | (>) >_GhostClose_4
 |  |  |  | (a) a_GhostsRemain_5
 |  |  |  | (z) z_OftenSucceed_6 p=(0.7)
 |  | (a) a_EatPill_7
 | (?) ?_ChaseOrAvoidGhost_8
 |  | (^) ^_NoMoreGhosts_9
 |  |  | (a) a_GhostsRemain_10
 |  | (>) >_ChaseIfScared_11
 |  |  | (a) a_GhostsRemain_12
 |  |  | (z) z_GhostScared_13 p=(0.25)
 |  |  | (z) z_ChaseGhost_14 p=(0.7)
 |  |  | (a) a_ScoreGhost_15
 |  | (?) ?_AvoidGhost_16
 |  |  | (^) ^_NoMoreGhosts_17
 |  |  |  | (a) a_GhostsRemain_18
 |  |  | (>) >_MaybeAvoidAndEatPill_19
 |  |  |  | (z) z_AlmostAlwaysSucceed_20 p=(0.9)
 |  |  |  | (a) a_EatPill_21

Legend:

- (?) FallbackNode
- (>) SequenceNode
- (^) Invert
- (z) Fuzzer node (randomly succeeds or fails some percentage of the time)
- (a) ActionNode

If no ghosts are nearby, Pacman eats one pill per tick.
But if a ghost is nearby, Pacman will chase it if it is scared, otherwise he will avoid it.
If he successfully avoids a ghost, he will eat a pill.
The game ends when Pacman has eaten all the pills or has been eaten by a ghost.

Scoring is as follows:

- 10 points per pill
- 200 points for the first ghost, 400 for the second, 800 for the third, 1600 for the fourth

If the game exceeds 1000 ticks, Pacman gets bored and quits (but that should never happen).
"""


import logging

import vultron.bt.base.bt_node as btn
import vultron.bt.base.composites as bt
import vultron.bt.base.decorators as btd
import vultron.bt.base.fuzzer as btz
from vultron.bt.base.bt import BehaviorTree

logger = logging.getLogger(__name__)

SCORE = 0

_DOTS_REMAINING = 240
_GHOSTS = 4
_PER_DOT = 10
_PER_GHOST = 200
_GHOST_INC = 2
_GHOST_NAMES = ["Blinky", "Pinky", "Inky", "Clyde"]


def _inc_ghost_score() -> None:
    """
    increments the score for catching a ghost and decreases the score for the next ghost.

    Returns:
        None
    """
    global _PER_GHOST, _GHOSTS
    _PER_GHOST *= _GHOST_INC
    _GHOSTS -= 1
    logger.info(f"Ghost score is now {_PER_GHOST}")


def _score_dot() -> None:
    """
    increments the score for eating a dot.
    Returns:
        None
    """
    global SCORE, _DOTS_REMAINING
    if _DOTS_REMAINING > 0:
        SCORE += _PER_DOT
        _DOTS_REMAINING -= 1


class EatPill(btn.ActionNode):
    """increments score for eating pills"""

    def _tick(self, depth=0):
        _score_dot()
        return bt.NodeStatus.SUCCESS


class ScoreGhost(btn.ActionNode):
    """increments score for catching ghosts"""

    def _tick(self, depth=0):
        global SCORE
        SCORE += _PER_GHOST
        _inc_ghost_score()
        logger.info("Caught a ghost!")
        return bt.NodeStatus.SUCCESS


class GhostsRemain(btn.ActionNode):
    """
    checks if there are any ghosts remaining.

    Returns:
        SUCCESS if there are ghosts remaining, FAILURE otherwise
    """

    def _tick(self, depth=0) -> bt.NodeStatus:
        global _GHOSTS
        if _GHOSTS > 0:
            return bt.NodeStatus.SUCCESS
        else:
            return bt.NodeStatus.FAILURE


class NoMoreGhosts(btd.Invert):
    """
    inverts the result of GhostsRemain.

    Returns:
        SUCCESS if there are no ghosts remaining, FAILURE otherwise
    """

    _children = (GhostsRemain,)


class GhostClose(bt.SequenceNode):
    """
    determines if a ghost is close.

    Returns:
        SUCCESS if a ghost is close, FAILURE otherwise
    """

    _children = (GhostsRemain, btz.OftenSucceed)


class NoGhostClose(btd.Invert):
    """
    inverts the result of GhostClose.

    Returns:
        SUCCESS if a ghost is not close, FAILURE otherwise
    """

    _children = (GhostClose,)


class GhostScared(btz.UsuallyFail):
    """
    determines if a ghost is scared.

    Returns:
        SUCCESS if a ghost is scared, FAILURE otherwise
    """



class ChaseGhost(btz.OftenSucceed):
    """
    chases a ghost.

    Returns:
        SUCCESS if a ghost is caught, FAILURE otherwise
    """


class ChaseIfScared(bt.SequenceNode):
    """
    implements chasing a ghost if it is scared.

    Returns:
        SUCCESS if a ghost is caught, FAILURE otherwise
    """

    _children = (GhostsRemain, GhostScared, ChaseGhost, ScoreGhost)


class MaybeAvoidAndEatPill(bt.SequenceNode):
    """
    implements avoiding a ghost and eating a pill.

    Returns:
        SUCCESS if a ghost is avoided (and a pill is eaten), FAILURE otherwise
    """

    _children = (btz.AlmostAlwaysSucceed, EatPill)

class AvoidGhost(bt.FallbackNode):
    """
    implements avoiding a ghost.

    Returns:
        SUCCESS if no ghosts remain, or if a ghost is avoided, FAILURE otherwise
    """

    _children = (NoMoreGhosts, MaybeAvoidAndEatPill)



class ChaseOrAvoidGhost(bt.FallbackNode):
    """
    implements chasing a ghost if it is scared, otherwise it avoids the ghost.

    Returns:
        SUCCESS if no ghosts remain, a ghost is caught or avoided, FAILURE otherwise
    """

    _children = (NoMoreGhosts, ChaseIfScared, AvoidGhost)


class MaybeEatPills(bt.SequenceNode):
    """
    implements eating pills if no ghosts are close.
    """

    _children = (NoGhostClose, EatPill)


class Root(bt.FallbackNode):
    """
    implements the root of the pacman bt tree.

    Returns:
        SUCCESS if Pacman survived the tick, FAILURE otherwise
    """

    _children = (MaybeEatPills, ChaseOrAvoidGhost)


def main():
    import random
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)
    handler = logging.StreamHandler()
    logger.addHandler(handler)

    import argparse

    parser = argparse.ArgumentParser()
    parser.description = "Run the Pacman demo."
    parser.add_argument("--print-tree", action="store_true", help="print the tree and exit", default=False)
    args = parser.parse_args()


    bot = BehaviorTree(root=Root())
    bot.setup()

    if args.print_tree:
        print(bot.root.to_str())
        exit()


    ticks = 0
    while _DOTS_REMAINING > 0:
        logger.info(f"=== Tick {ticks + 1} ===")
        bot.tick()
        ticks += 1
        # die on the first failure
        if bot.status == bt.NodeStatus.FAILURE:
            logger.info(f"Pacman died! He was eaten by {random.choice(_GHOST_NAMES)}!")
            break
        if _DOTS_REMAINING <= 0:
            logger.info("Pacman cleared the board!")
            break
        if ticks > 1000:
            logger.info("Pacman got bored and quit!")
            break
    score = SCORE

    logger.info(f"Final score: {score}")
    logger.info(f"Ticks: {ticks}")
    logger.info(f"Dots Remaining: {_DOTS_REMAINING}")
    logger.info(f"Ghosts Remaining: {_GHOSTS}")


if __name__ == "__main__":
    main()


