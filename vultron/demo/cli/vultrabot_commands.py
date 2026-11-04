"""The ``vultrabot`` sub-group of standalone behaviour-tree demos (DC-01-001)."""

#  Copyright (c) 2025-2026 Carnegie Mellon University and Contributors.
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

import logging
from types import SimpleNamespace

import click

import vultron.bt.base.demo.cvd as cvd_vultrabot_demo
import vultron.bt.base.demo.pacman as pacman_demo
import vultron.bt.base.demo.robot as robot_demo
from vultron.demo.cli.group import main

# ---------------------------------------------------------------------------
# Vultrabot sub-group — behaviour-tree demos (pacman, robot, cvd)
# ---------------------------------------------------------------------------


@main.group(name="vultrabot")
def vultrabot_group() -> None:
    """Standalone behaviour-tree demos (pacman, robot, cvd)."""


def _bt_args(print_tree: bool, verbose: bool, debug: bool) -> SimpleNamespace:
    """Build an argparse-compatible Namespace for bt demo mains."""
    if debug:
        log_level = logging.DEBUG
    elif verbose:
        log_level = logging.INFO
    else:
        log_level = logging.WARNING
    return SimpleNamespace(print_tree=print_tree, log_level=log_level)


def _bt_options(fn):
    """Decorator that adds ``--print-tree``, ``-v``/``--verbose``, and ``-d``/``--debug`` options."""
    fn = click.option(
        "--print-tree",
        is_flag=True,
        default=False,
        help="Print the behaviour tree and exit.",
    )(fn)
    fn = click.option("-v", "--verbose", is_flag=True, default=False)(fn)
    fn = click.option("-d", "--debug", is_flag=True, default=False)(fn)
    return fn


@vultrabot_group.command(name="pacman")
@_bt_options
def vultrabot_pacman(print_tree: bool, verbose: bool, debug: bool) -> None:
    """Run the Pacman behaviour-tree demo."""
    pacman_demo.main(_bt_args(print_tree, verbose, debug))


@vultrabot_group.command(name="robot")
@_bt_options
def vultrabot_robot(print_tree: bool, verbose: bool, debug: bool) -> None:
    """Run the Robot behaviour-tree demo."""
    robot_demo.main(_bt_args(print_tree, verbose, debug))


@vultrabot_group.command(name="cvd")
@_bt_options
def vultrabot_cvd(print_tree: bool, verbose: bool, debug: bool) -> None:
    """Run the CVD Vultron behaviour-tree demo."""
    cvd_vultrabot_demo.main(_bt_args(print_tree, verbose, debug))


if __name__ == "__main__":
    main()
