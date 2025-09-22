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
This is a demo of the bt tree library. It is a stub implementation of a bot that plays Pacman.
"""


import logging
import random
import sys

import vultron.bt.base.composites as bt
import vultron.bt.base.fuzzer as btz
from vultron.bt.base.blackboard import Blackboard
from vultron.bt.base.bt import BehaviorTree
from vultron.bt.base.bt_node import BtNode
from vultron.bt.base.factory import (
    action_node,
    condition_check,
    fallback_node,
    fuzzer,
    invert,
    sequence_node,
)
from vultron.bt.common import show_graph

# TODO: convert to pydantic idioms

logger = logging.getLogger(__name__)

SCORE = 0

PER_DOT = 10
GHOST_INC = 2
GHOST_NAMES = ["Blinky", "Pinky", "Inky", "Clyde"]


class PacmanBlackboard(Blackboard):
    dots: int = 240
    score: int = 0
    per_ghost: int = 200
    ghosts_scared: bool = False
    ghosts_remaining: list = GHOST_NAMES.copy()
    ticks: int = 0


### Action Nodes


def eat_pill(obj: BtNode) -> bool:
    dots = obj.bb.dots
    if dots == 0:
        return False

    obj.bb.dots -= 1
    obj.bb.score += PER_DOT
    return True


EatPill = action_node("EatPill", eat_pill)


def inc_ghost_score(obj: BtNode) -> bool:
    """increments the score for the next ghost."""
    obj.bb.per_ghost *= GHOST_INC
    logger.info(f"Ghost score is now {obj.bb.per_ghost}")
    return True


IncrGhostScore = action_node(
    "IncrGhostScore",
    inc_ghost_score,
)


def score_ghost(obj: BtNode) -> bool:
    obj.bb.score += obj.bb.per_ghost
    return True


ScoreGhost = action_node("ScoreGhost", score_ghost)


def decr_ghost_count(obj: BtNode) -> bool:
    """decrements the ghost count"""
    ghost = obj.bb.ghosts_remaining.pop()
    logger.info(f"{ghost} was caught!")
    return True


DecrGhostCount = action_node(
    "DecrGhostCount",
    decr_ghost_count,
)


### Condition Check Nodes


def ghosts_remain(obj: BtNode) -> bool:
    """checks if there are any ghosts remaining."""
    return len(obj.bb.ghosts_remaining) > 0


GhostsRemain = condition_check(
    "GhostsRemain",
    ghosts_remain,
)


def ghosts_scared(obj: BtNode) -> bool:
    """checks if a ghost is scared."""
    return obj.bb.ghosts_scared


GhostsScared = condition_check(
    "GhostsScared",
    ghosts_scared,
)


### Fuzzer Nodes


GhostClose = fuzzer(
    btz.OftenSucceed, "GhostClose", "determines if a ghost is close."
)
ChaseGhost = fuzzer(btz.OftenSucceed, "ChaseGhost", "chases a ghost.")
AvoidGhost = fuzzer(btz.OftenSucceed, "AvoidGhost", "avoids a ghost.")


### Composite Nodes

NoMoreGhosts = invert(
    "NoMoreGhosts", "inverts the result of GhostsRemain.", GhostsRemain
)
NoGhostClose = invert(
    "NoGhostClose", "inverts the result of GhostClose.", GhostClose
)
CaughtGhost = sequence_node(
    "CaughtGhost",
    "handles actions after catching a ghost.",
    DecrGhostCount,
    ScoreGhost,
    IncrGhostScore,
)
GhostsNotScared = invert(
    "GhostsNotScared", "inverts the result of GhostsScared.", GhostsScared
)
ChaseIfScared = sequence_node(
    "ChaseIfScared",
    "implements chasing a ghost if it is scared.",
    GhostsScared,
    ChaseGhost,
    CaughtGhost,
)
ChaseOrAvoidGhost = fallback_node(
    "ChaseOrAvoidGhost",
    "implements chasing a ghost if it is scared, otherwise it avoids the ghost.",
    ChaseIfScared,
    GhostsScared,
    AvoidGhost,
)

MaybeChaseOrAvoidGhost = fallback_node(
    "MaybeChaseOrAvoidGhost",
    """
    implements chasing a ghost if it is scared, otherwise it avoids the ghost.

    Returns:
        SUCCESS if no ghosts remain, a ghost is caught or avoided, FAILURE otherwise
    """,
    NoMoreGhosts,
    NoGhostClose,
    ChaseOrAvoidGhost,
)


MaybeEatPills = sequence_node(
    "MaybeEatPills",
    """
    implements eating pills if no ghosts are close.
    """,
    MaybeChaseOrAvoidGhost,
    EatPill,
)


def do_tick(bot, ticks):
    bb = bot.bb

    logger.info(f"=== Tick {ticks} ===")

    # maybe make the ghosts scared
    # note this also demonstrates the world changing outside the bot
    if random.random() < 0.5:
        bb.ghosts_scared = True
        logger.info("Ghosts are scared!")
    else:
        bb.ghosts_scared = False

    bot.tick()
    ticks += 1
    # die on the first failure
    if bot.status == bt.NodeStatus.FAILURE:
        logger.info(
            f"Pacman died! He was eaten by {random.choice(bb.ghosts_remaining)}!"
        )
    if bb.dots <= 0:
        logger.info("Pacman cleared the board!")
    if ticks > 1000:
        logger.info("Pacman got bored and quit!")
    return bot.status


def main(args):
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)
    handler = logging.StreamHandler()
    logger.addHandler(handler)

    bot = BehaviorTree(root=MaybeEatPills(), bbclass=PacmanBlackboard)
    bot.setup()

    if args.print_tree:
        logger.info("Printing tree and exiting")
        show_graph(MaybeEatPills)
        sys.exit()

    ticks = 0
    while bot.bb.dots > 0:
        ticks += 1
        result = do_tick(bot, ticks)
        if result == bt.NodeStatus.FAILURE:
            break

    logger.info(f"Final score: {bot.bb.score}")
    logger.info(f"Ticks: {ticks}")
    logger.info(f"Dots Remaining: {bot.bb.dots}")

    nghosts = len(bot.bb.ghosts_remaining)
    if nghosts > 0:
        ghosts = ", ".join(bot.bb.ghosts_remaining)
        ghosts = f"({ghosts})"
    else:
        ghosts = ""
    logger.info(f"Ghosts Remaining: {nghosts} {ghosts}")

def _parse_args():
    import argparse

    parser = argparse.ArgumentParser(description="Pacman Bot Demo")
    parser.add_argument(
        "--print-tree",
        action="store_true",
        help="Print the behavior tree and exit",
    )
    return parser.parse_args()

if __name__ == "__main__":
    args = _parse_args()

    main(args)
