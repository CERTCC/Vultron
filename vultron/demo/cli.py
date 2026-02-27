#!/usr/bin/env python

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

"""
Unified Vultron demo CLI (DC-01-001 through DC-01-005).

Each sub-command maps to one demo script in ``vultron/demo/``.
The ``all`` sub-command runs every demo in sequence and prints a
pass/fail summary.

A ``vultrabot`` sub-group provides access to the three standalone
behaviour-tree demos (pacman, robot, cvd).
"""

import logging
import sys
from types import SimpleNamespace

import click

import vultron.demo.acknowledge_demo as acknowledge_demo
import vultron.demo.establish_embargo_demo as establish_embargo_demo
import vultron.demo.initialize_case_demo as initialize_case_demo
import vultron.demo.initialize_participant_demo as initialize_participant_demo
import vultron.demo.invite_actor_demo as invite_actor_demo
import vultron.demo.manage_case_demo as manage_case_demo
import vultron.demo.manage_embargo_demo as manage_embargo_demo
import vultron.demo.manage_participants_demo as manage_participants_demo
import vultron.demo.receive_report_demo as receive_report_demo
import vultron.demo.status_updates_demo as status_updates_demo
import vultron.demo.suggest_actor_demo as suggest_actor_demo
import vultron.demo.transfer_ownership_demo as transfer_ownership_demo
import vultron.bt.base.demo.pacman as pacman_demo
import vultron.bt.base.demo.robot as robot_demo
import vultron.demo.vultrabot as cvd_vultrabot_demo

# Ordered list of (sub-command name, demo module) pairs.
# Order defines execution sequence for the `all` sub-command (DC-01-003).
DEMOS = [
    ("receive-report", receive_report_demo),
    ("initialize-case", initialize_case_demo),
    ("initialize-participant", initialize_participant_demo),
    ("invite-actor", invite_actor_demo),
    ("establish-embargo", establish_embargo_demo),
    ("acknowledge", acknowledge_demo),
    ("status-updates", status_updates_demo),
    ("suggest-actor", suggest_actor_demo),
    ("transfer-ownership", transfer_ownership_demo),
    ("manage-case", manage_case_demo),
    ("manage-embargo", manage_embargo_demo),
    ("manage-participants", manage_participants_demo),
]


@click.group()
@click.option(
    "--debug",
    is_flag=True,
    default=False,
    help="Enable DEBUG-level logging to the console (default: INFO).",
)
@click.option(
    "--log-file",
    default=None,
    metavar="PATH",
    help="Also write log output to FILE.",
)
@click.pass_context
def main(ctx: click.Context, debug: bool, log_file: str | None) -> None:
    """Vultron demo CLI — run individual demos or all demos in sequence."""
    level = logging.DEBUG if debug else logging.INFO
    handlers: list[logging.Handler] = [logging.StreamHandler()]
    if log_file:
        handlers.append(logging.FileHandler(log_file))
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
        handlers=handlers,
        force=True,
    )
    ctx.ensure_object(dict)
    ctx.obj["debug"] = debug


def _make_sub_command(name: str, module) -> click.Command:
    """Return a click Command that calls ``module.main()``."""

    @click.command(name=name, help=module.__doc__ or f"Run {name} demo.")
    @click.option(
        "--skip-health-check",
        is_flag=True,
        default=False,
        help="Skip server availability check.",
    )
    def _cmd(skip_health_check: bool) -> None:
        """Invoke ``module.main()`` with the given options."""
        module.main(skip_health_check=skip_health_check)

    return _cmd


for _name, _module in DEMOS:
    main.add_command(_make_sub_command(_name, _module))


@main.command(name="all")
@click.option(
    "--skip-health-check",
    is_flag=True,
    default=False,
    help="Skip server availability check for every demo.",
)
def run_all(skip_health_check: bool) -> None:
    """Run every demo in sequence and print a pass/fail summary (DC-01-003, DC-01-004)."""
    results: list[tuple[str, bool, str]] = []

    for name, module in DEMOS:
        try:
            module.main(skip_health_check=skip_health_check)
            results.append((name, True, ""))
        except Exception as exc:  # noqa: BLE001
            results.append((name, False, str(exc)))
            click.echo(f"\n❌  Demo '{name}' FAILED: {exc}", err=True)
            _print_summary(results)
            sys.exit(1)

    _print_summary(results)


def _print_summary(results: list[tuple[str, bool, str]]) -> None:
    """Print a human-readable pass/fail summary (DC-01-004)."""
    click.echo("\n" + "=" * 50)
    click.echo("Demo Summary")
    click.echo("=" * 50)
    for name, passed, error in results:
        status = "✅ PASS" if passed else f"❌ FAIL ({error})"
        click.echo(f"  {name:35s}  {status}")
    total = len(results)
    passed_count = sum(1 for _, ok, _ in results if ok)
    click.echo("=" * 50)
    click.echo(f"  {passed_count}/{total} demos passed")
    click.echo("=" * 50)


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
