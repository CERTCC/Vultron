#!/usr/bin/env python
"""
Implements a command line interface behavior tree demo for the Vultron package.
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

import argparse
import logging

from vultron.bt.base.demo.pacman import main as run_pacman
from vultron.bt.base.demo.robot import main as run_robot
from vultron.demo.vultrabot import main as run_cvd


def main():
    """
    Implements a command line interface behavior tree demo for the Vultron package.
    """
    parser = argparse.ArgumentParser(
        description="Vultrabot Command Line Interface"
    )
    # debug
    parser.add_argument(
        "-d",
        "--debug",
        dest="log_level",
        action="store_const",
        const=logging.DEBUG,
        default=logging.WARNING,
        help="Enable debug output",
    )
    # verbose
    parser.add_argument(
        "-v",
        "--verbose",
        dest="log_level",
        action="store_const",
        const=logging.INFO,
        default=logging.WARNING,
        help="Enable verbose output",
    )
    # quiet
    parser.add_argument(
        "-q",
        "--quiet",
        dest="log_level",
        action="store_const",
        const=logging.ERROR,
        default=logging.WARNING,
        help="Enable quiet output",
    )
    # pacman
    parser.add_argument(
        "--pacman",
        dest="select_demo",
        action="store_const",
        const="pacman",
        default="cvd",
        help="Run the Pacman demo",
    )
    # robot
    parser.add_argument(
        "--robot",
        dest="select_demo",
        action="store_const",
        const="robot",
        default="cvd",
        help="Run the Robot demo",
    )
    # cvd (default if neither pacman nor robot)
    parser.add_argument(
        "--cvd",
        dest="select_demo",
        action="store_const",
        const="cvd",
        default="cvd",
        help="Run the CVD demo",
    )

    # if print-tree just print the tree and exit
    parser.add_argument(
        "-t",
        "--print-tree",
        dest="print_tree",
        action="store_true",
        default=False,
        help="print the tree and exit",
    )

    args = parser.parse_args()

    # select the demo
    selector = {
        "pacman": run_pacman,
        "robot": run_robot,
        "cvd": run_cvd,
    }

    selector[args.select_demo](args)


if __name__ == "__main__":
    main()
