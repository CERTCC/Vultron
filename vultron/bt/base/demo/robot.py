#!/usr/bin/env python
"""file: robot_demo
author: adh
created_at: 4/1/22 10:08 AM

This module demonstrates a simple robot bt tree. The robot has a number of tasks it must perform in order to
complete its mission. The robot must find a ball, approach the ball, grasp the ball, approach the bin, and place
the ball in the bin. If any of these tasks fail, the robot must ask for help.

The implementation also shows how to use the included bt tree fuzzer to exercise the bt tree.

The robot's bt tree is as follows:

Root (FallbackNode)
|-- BallPlaced (UsuallyFail) -- checks if the ball is already placed in the bin
|-- MainSequence (SequenceNode) -- otherwise, the robot must perform the following tasks
|   |-- EnsureBallFound (FallbackNode) -- the robot must find the ball
|   |   |-- BallFound (UsuallyFail)
|   |   |-- FindBall (UsuallySucceed)
|   |-- EnsureBallClose (FallbackNode) -- the robot must approach the ball
|   |   |-- BallClose (UsuallyFail)
|   |   |-- ApproachBall (UsuallySucceed)
|   |-- EnsureBallGrasped (FallbackNode) -- the robot must grasp the ball
|   |   |-- BallGrasped (UsuallyFail)
|   |   |-- GraspBall (UsuallySucceed)
|   |-- EnsureBinClose (FallbackNode) -- the robot must approach the bin
|   |   |-- BinClose (UsuallyFail)
|   |   |-- ApproachBin (UsuallySucceed)
|   |-- EnsureBallPlaced (FallbackNode) -- the robot must place the ball in the bin
|   |   |-- BallPlaced (UsuallyFail)
|   |   |-- PlaceBall (UsuallySucceed)
|-- AskForHelp (AlwaysSucceed)
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

import vultron.bt.base.fuzzer as btz
from vultron.bt.base.composites import FallbackNode, SequenceNode

logger = logging.getLogger(__name__)


class BallPlaced(btz.UsuallyFail):
    """
    This is a stub for a task that checks if the ball is already placed in the bin. In our stub implementation, we just
    stochastically return Success or Failure to simulate whether the ball is placed.
    """


class PlaceBall(btz.UsuallySucceed):
    """This is a stub for a task that places the ball in the bin. In our stub implementation, we just stochastically return
    Success or Failure to simulate placing the ball in the bin.
    """


class EnsureBallPlaced(FallbackNode):
    """This is a fallback node that ensures the ball is placed in the bin. If the ball is placed, the task succeeds. If the ball
    is not placed, and the robot cannot place the ball, the task fails.
    """

    _children = (BallPlaced, PlaceBall)


class BinClose(btz.UsuallyFail):
    """This is a stub for a task that checks if the bin is close. In our stub implementation, we just stochastically
    return Success or Failure to simulate whether the bin is close.
    """


class ApproachBin(btz.UsuallySucceed):
    """This is a stub for a task that approaches the bin. In our stub implementation, we just stochastically return
    Success or Failure to simulate approaching the bin.
    """


class EnsureBinClose(FallbackNode):
    """This is a fallback node that ensures the bin is close. If the bin is close, the task succeeds. If the bin
    is not close, and the robot cannot approach the bin, the task fails.
    """

    _children = (BinClose, ApproachBin)


class BallGrasped(btz.UsuallyFail):
    """This is a stub for a task that checks if the ball is already grasped. In our stub implementation, we just stochastically
    return Success or Failure to simulate whether the ball is grasped.
    """


class GraspBall(btz.UsuallySucceed):
    """This is a stub for a task that grasps the ball. In our stub implementation, we just stochastically return"""


class EnsureBallGrasped(FallbackNode):
    """This is a fallback node that ensures the ball is grasped. If the ball is grasped, the task succeeds. If the ball
    is not already grasped, and the robot cannot grasp the ball, the task fails.
    """

    _children = (BallGrasped, GraspBall)


class BallClose(btz.UsuallyFail):
    """This is a stub for a task that checks if the ball is close. In our stub implementation, we just stochastically
    return Success or Failure to simulate whether the ball is close.
    """


class ApproachBall(btz.UsuallySucceed):
    """This is a stub for a task that approaches the ball. In our stub implementation, we just stochastically return
    Success or Failure to simulate approaching the ball.
    """


class EnsureBallClose(FallbackNode):
    """This is a fallback node that ensures the ball is close. If the ball is close, the task succeeds. If the ball
    is not close, and the robot cannot approach the ball, the task fails.
    """

    _children = (BallClose, ApproachBall)


class FindBall(btz.UsuallySucceed):
    """This is a stub for a task that finds the ball. In our stub implementation, we just stochastically return
    Success or Failure to simulate finding the ball.
    """


class BallFound(btz.UsuallyFail):
    """This is a stub for a task that checks if the ball is found. In our stub implementation, we just stochastically
    return Success or Failure to simulate whether the ball has already been found.
    """


class EnsureBallFound(FallbackNode):
    """This is a fallback node that ensures the ball is found. If the ball is found, the task succeeds. If the ball
    is not already found, and the robot cannot find the ball, the task fails.
    """

    _children = (BallFound, FindBall)


class AskForHelp(btz.AlwaysSucceed):
    """This is a stub for a task that asks for help. In our stub implementation, we just always return Success to simulate
    asking for help.
    """


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
    _children = (BallPlaced, MainSequence, AskForHelp)


def main():
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)
    hdlr = logging.StreamHandler()
    logger.addHandler(hdlr)

    for trial in range(10):
        print(f"Trial {trial}")
        root = Robot()
        root.setup()
        root.tick()


if __name__ == "__main__":
    main()
