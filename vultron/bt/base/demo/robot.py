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
This module demonstrates a simple robot behavior tree.
The robot has a number of tasks it must perform in order to complete its mission.
The robot must find a ball, approach the ball, grasp the ball, approach the bin, and place
the ball in the bin. If any of these tasks fail, the robot must ask for help.

Oh, and the first time the robot picks up the ball, we knock it out of the robot's grasp, because
we're mean like that.

The implementation also shows how to use the included bt tree fuzzer to exercise the bt tree.
"""

import logging
from dataclasses import dataclass

import vultron.bt.base.fuzzer as btz
from vultron.bt.base.blackboard import Blackboard
from vultron.bt.base.bt import BehaviorTree
from vultron.bt.base.bt_node import BtNode
from vultron.bt.base.factory import (
    action_node,
    condition_check,
    fallback_node,
    sequence_node,
)

logger = logging.getLogger(__name__)


@dataclass(kw_only=True)
class RobotBlackboard(Blackboard):
    ball_found: bool = False
    ball_close: bool = False
    ball_grasped: bool = False
    bin_close: bool = False
    ball_placed: bool = False
    asked_for_help: bool = False
    ticks: int = 0


def ball_placed(obj: BtNode) -> bool:
    """Checks whether the ball is placed in the bin"""
    return obj.bb.ball_placed


BallPlaced = condition_check(
    "BallPlaced",
    ball_placed,
)


def set_ball_placed(obj: BtNode) -> bool:
    """Records that the ball has been placed in the bin"""
    obj.bb.ball_placed = True
    return True


SetBallPlaced = action_node(
    "SetBallPlaced",
    set_ball_placed,
)

PlaceBall = sequence_node("PlaceBall",
                          "This is a stub for a task that places the ball in the bin. In our stub implementation, we just stochastically "
                          "return Success or Failure to simulate placing the ball.", btz.UsuallySucceed, SetBallPlaced)


EnsureBallPlaced = fallback_node("EnsureBallPlaced",
                                 "This is a fallback node that ensures the ball is placed in the bin. If the ball is placed, the task succeeds. If "
                                 "the ball is not placed, and the robot cannot place the ball, the task fails.",
                                 BallPlaced, PlaceBall)


def bin_close(obj: BtNode) -> bool:
    """Checks whether the bin is close"""
    return obj.bb.bin_close


BinClose = condition_check(
    "BinClose",
    bin_close,
)


def set_bin_close(obj: BtNode) -> bool:
    """Records that the bin is close"""
    obj.bb.bin_close = True
    return True


SetBinClose = action_node(
    "SetBinClose",
    set_bin_close,
)

ApproachBin = sequence_node("ApproachBin",
                            "This is a stub for a task that approaches the bin. In our stub implementation, we just stochastically return "
                            "Success or Failure to simulate approaching the bin.", btz.UsuallySucceed, SetBinClose)

EnsureBinClose = fallback_node("EnsureBinClose",
                               "This is a fallback node that ensures the bin is close. If the bin is close, the task succeeds. If the bin "
                               "is not close, and the robot cannot approach the bin, the task fails.", BinClose,
                               ApproachBin)


def ball_grasped(obj: BtNode) -> bool:
    """Checks whether the ball is grasped"""
    return obj.bb.ball_grasped


BallGrasped = condition_check(
    "BallGrasped",
    ball_grasped,
)


def set_ball_grasped(obj: BtNode) -> bool:
    """Records that the ball has been grasped"""
    obj.bb.ball_grasped = True
    return True


SetBallGrasped = action_node(
    "SetBallGrasped",
    set_ball_grasped,
)

GraspBall = sequence_node("GraspBall",
                          "This is a stub for a task that grasps the ball. In our stub implementation, we just stochastically return "
                          "SUCCESS.", btz.OftenFail, SetBallGrasped)

EnsureBallGrasped = fallback_node("EnsureBallGrasped",
                                  "This is a fallback node that ensures the ball is grasped. If the ball is grasped, the task succeeds. If the ball "
                                  "is not already grasped, and the robot cannot grasp the ball, the task fails.",
                                  BallGrasped, GraspBall)


def ball_close(obj: BtNode) -> bool:
    """Checks whether the ball is close"""
    return obj.bb.ball_close


BallClose = condition_check(
    "BallClose",
    ball_close,
)


def set_ball_close(obj: BtNode) -> bool:
    """Records that the ball is close"""
    obj.bb.ball_close = True
    return True


SetBallClose = action_node(
    "SetBallClose",
    set_ball_close,
)

ApproachBall = sequence_node("ApproachBall",
                             "This is a stub for a task that approaches the ball. In our stub implementation, we just stochastically return "
                             "Success or Failure to simulate approaching the ball.", btz.UsuallySucceed, SetBallClose)


EnsureBallClose = fallback_node("EnsureBallClose",
                                "This is a fallback node that ensures the ball is close. If the ball is close, the task succeeds. If the ball "
                                "is not close, and the robot cannot approach the ball, the task fails.", BallClose,
                                ApproachBall)


def set_ball_found(obj: BtNode) -> bool:
    """Records that the ball has been found"""
    obj.bb.ball_found = True
    return True


SetBallFound = action_node(
    "SetBallFound",
    set_ball_found,
)

FindBall = sequence_node("FindBall",
                         "This is a stub for a task that finds the ball. In our stub implementation, we just stochastically return "
                         "Success or Failure to simulate finding the ball.", btz.UsuallySucceed, SetBallFound)


def ball_found(obj: BtNode) -> bool:
    """Checks whether the ball is found"""
    return obj.bb.ball_found


BallFound = condition_check(
    "BallFound",
    ball_found,
)


EnsureBallFound = fallback_node("EnsureBallFound",
                                "This is a fallback node that ensures the ball is found. If the ball is found, the task succeeds. If the ball "
                                "is not found, and the robot cannot find the ball, the task fails.", BallFound,
                                FindBall)


def time_to_ask_for_help(obj: BtNode) -> bool:
    """Checks if it is time to ask for help"""
    return obj.bb.ticks > 10


TimeToAskForHelp = condition_check(
    "TimeToAskForHelp",
    time_to_ask_for_help,
)


def ask_for_help(obj: BtNode) -> bool:
    """Records that the robot has asked for help"""
    logger.info("I need help!")
    obj.bb.asked_for_help = True
    return True


AskForHelp = action_node(
    "AskForHelp",
    ask_for_help,
)

MaybeAskForHelp = sequence_node("MaybeAskForHelp", "Decide whether we need to ask for help.", TimeToAskForHelp,
                                AskForHelp)

MainSequence = sequence_node("MainSequence",
                             "This is the main sequence of tasks the robot must perform in order to complete its mission.",
                             EnsureBallFound, EnsureBallClose, EnsureBallGrasped, EnsureBinClose, EnsureBallPlaced)

Robot = fallback_node("Robot",
                      "This is the robot's main fallback node. It will try to complete its mission. If it fails, it will ask for help.",
                      BallPlaced, MainSequence, MaybeAskForHelp)


def main():
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)
    hdlr = logging.StreamHandler()
    logger.addHandler(hdlr)

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

    bot = BehaviorTree(root=Robot(), bbclass=RobotBlackboard)

    bot.setup()

    if args.print_tree:
        print(bot.root.to_mermaid(topdown=False))
        exit()

    knockout = True
    while not bot.bb.ball_placed:
        # maybe knock the ball out of the robot's grasp
        if knockout and bot.bb.ball_grasped:
            bot.bb.ball_grasped = False
            logger.info("The ball was knocked out of the robot's grasp!")
            knockout = False

        bot.tick()
        bot.bb.ticks += 1

        if bot.bb.asked_for_help:
            logger.info("The robot asked for help!")
            break

    if bot.bb.asked_for_help:
        logger.info(
            f"Robot failed to complete its mission after {bot.bb.ticks} ticks."
        )
    elif bot.bb.ball_placed:
        logger.info(f"Robot completed its mission in {bot.bb.ticks} ticks.")
    else:
        logger.info(f"Not sure what happened. {bot.bb}")


if __name__ == "__main__":
    main()
