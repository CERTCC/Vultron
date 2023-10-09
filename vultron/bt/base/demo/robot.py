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

import vultron.bt.base.bt_node as btn
import vultron.bt.base.fuzzer as btz
from vultron.bt.base.blackboard import Blackboard
from vultron.bt.base.bt import BehaviorTree
from vultron.bt.base.composites import FallbackNode, SequenceNode

logger = logging.getLogger(__name__)


class BallPlaced(btn.ConditionCheck):
    """
    Reports SUCCESS if the ball is placed in the bin, FAILURE otherwise.
    """

    def func(self) -> bool:
        return self.bb["ball_placed"]


class SetBallPlaced(btn.ActionNode):
    """
    Records that the ball has been placed in the bin.
    """

    def func(self) -> bool:
        self.bb["ball_placed"] = True
        return True


class PlaceBall(SequenceNode):
    """
    This is a stub for a task that places the ball in the bin. In our stub implementation, we just stochastically
    return Success or Failure to simulate placing the ball.
    """

    _children = (btz.UsuallySucceed, SetBallPlaced)


class EnsureBallPlaced(FallbackNode):
    """This is a fallback node that ensures the ball is placed in the bin. If the ball is placed, the task succeeds. If the ball
    is not placed, and the robot cannot place the ball, the task fails.
    """

    _children = (BallPlaced, PlaceBall)


class BinClose(btn.ConditionCheck):
    """
    Checks if the bin is close.

    Returns:
        SUCCESS if the bin is close, FAILURE otherwise.
    """

    def func(self) -> bool:
        return self.bb["bin_close"]


class SetBinClose(btn.ActionNode):
    """
    Reports that the bin is close.

    Returns:
        SUCCESS
    """

    def func(self) -> bool:
        self.bb["bin_close"] = True
        return True


class ApproachBin(SequenceNode):
    """This is a stub for a task that approaches the bin. In our stub implementation, we just stochastically return
    Success or Failure to simulate approaching the bin.
    """

    _children = (btz.UsuallySucceed, SetBinClose)


class EnsureBinClose(FallbackNode):
    """This is a fallback node that ensures the bin is close. If the bin is close, the task succeeds. If the bin
    is not close, and the robot cannot approach the bin, the task fails.
    """

    _children = (BinClose, ApproachBin)


class BallGrasped(btn.ConditionCheck):
    """
    Checks if the ball is grasped.

    Returns:
        SUCCESS if the ball is grasped, FAILURE otherwise.
    """

    def func(self) -> bool:
        return self.bb["ball_grasped"]


class SetBallGrasped(btn.ActionNode):
    """
    Records that the ball has been grasped.

    Returns:
        SUCCESS
    """

    def func(self) -> bool:
        self.bb["ball_grasped"] = True
        return True


class GraspBall(SequenceNode):
    """
    This is a stub for a task that grasps the ball. In our stub implementation, we just stochastically return SUCCESS.

    Returns:
        SUCCESS if the ball is grasped, FAILURE otherwise.
    """

    _children = (btz.OftenFail, SetBallGrasped)


class EnsureBallGrasped(FallbackNode):
    """This is a fallback node that ensures the ball is grasped. If the ball is grasped, the task succeeds. If the ball
    is not already grasped, and the robot cannot grasp the ball, the task fails.
    """

    _children = (BallGrasped, GraspBall)


class BallClose(btn.ConditionCheck):
    """
    Checks if the ball is close.
    """

    def func(self) -> bool:
        return self.bb["ball_close"]


class SetBallClose(btn.ActionNode):
    """
    Records that the ball is close.

    Returns:
        SUCCESS
    """

    def func(self) -> bool:
        self.bb["ball_close"] = True
        return True


class ApproachBall(SequenceNode):
    """This is a stub for a task that approaches the ball. In our stub implementation, we just stochastically return
    Success or Failure to simulate approaching the ball.
    """

    _children = (btz.UsuallySucceed, SetBallClose)


class EnsureBallClose(FallbackNode):
    """This is a fallback node that ensures the ball is close. If the ball is close, the task succeeds. If the ball
    is not close, and the robot cannot approach the ball, the task fails.
    """

    _children = (BallClose, ApproachBall)


class SetBallFound(btn.ActionNode):
    """
    Records that the ball has been found.
    """

    def func(self) -> bool:
        self.bb["ball_found"] = True
        return True


class FindBall(SequenceNode):
    """This is a stub for a task that finds the ball. In our stub implementation, we just stochastically return
    Success or Failure to simulate finding the ball.
    """

    _children = (btz.UsuallySucceed, SetBallFound)


class BallFound(btn.ConditionCheck):
    """This is a stub for a task that checks if the ball is found. In our stub implementation, we just stochastically
    return Success or Failure to simulate whether the ball has already been found.
    """

    def func(self) -> bool:
        return self.bb["ball_found"]


class EnsureBallFound(FallbackNode):
    """This is a fallback node that ensures the ball is found. If the ball is found, the task succeeds. If the ball
    is not already found, and the robot cannot find the ball, the task fails.
    """

    _children = (BallFound, FindBall)


class TimeToAskForHelp(btn.ConditionCheck):
    """
    Checks if it is time to ask for help.

    Returns:
        SUCCESS if it is time to ask for help, FAILURE otherwise.
    """

    def func(self) -> bool:
        return self.bb["ticks"] > 10


class AskForHelp(btn.ActionNode):
    """
    Records that the robot has asked for help.

    Returns:
        SUCCESS
    """

    def func(self) -> bool:
        logger.info("I need help!")
        self.bb["asked_for_help"] = True
        return True


class MaybeAskForHelp(SequenceNode):
    """
    Decide whether we need to ask for help.
    """

    _children = (TimeToAskForHelp, AskForHelp)


class MainSequence(SequenceNode):
    """This is the main sequence of tasks the robot must perform in order to complete its mission."""

    _children = (
        EnsureBallFound,
        EnsureBallClose,
        EnsureBallGrasped,
        EnsureBinClose,
        EnsureBallPlaced,
    )


class Robot(FallbackNode):
    _children = (BallPlaced, MainSequence, MaybeAskForHelp)


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

    bot = BehaviorTree(root=Robot(), bbclass=Blackboard)

    bot.bb.update(
        {
            "ball_found": False,
            "ball_close": False,
            "ball_grasped": False,
            "bin_close": False,
            "ball_placed": False,
            "asked_for_help": False,
            "ticks": 0,
        }
    )

    bot.setup()

    if args.print_tree:
        print(bot.root.to_mermaid(topdown=False))
        exit()

    knockout = True
    while not bot.bb["ball_placed"]:
        # maybe knock the ball out of the robot's grasp
        if knockout and bot.bb["ball_grasped"]:
            bot.bb["ball_grasped"] = False
            logger.info("The ball was knocked out of the robot's grasp!")
            knockout = False

        bot.tick()
        bot.bb["ticks"] += 1

        if bot.bb["asked_for_help"]:
            logger.info("The robot asked for help!")
            break

    if bot.bb["asked_for_help"]:
        logger.info(
            f"Robot failed to complete its mission after {bot.bb['ticks']} ticks."
        )
    elif bot.bb["ball_placed"]:
        logger.info(f"Robot completed its mission in {bot.bb['ticks']} ticks.")
    else:
        logger.info(f"Not sure what happened. {bot.bb}")


if __name__ == "__main__":
    main()
