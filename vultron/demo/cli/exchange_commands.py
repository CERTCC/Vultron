"""One sub-command per single-exchange demo, plus ``all`` (DC-01-002 to DC-01-004)."""

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

import sys

import click

from vultron.demo.cli.group import main
from vultron.demo.exchange import (
    acknowledge_demo,
    establish_embargo_demo,
    initialize_case_demo,
    initialize_participant_demo,
    invite_actor_demo,
    manage_case_demo,
    manage_embargo_demo,
    manage_participants_demo,
    receive_report_demo,
    report_with_embargo_demo,
    status_updates_demo,
    suggest_actor_demo,
    transfer_ownership_demo,
    trigger_demo,
)
from vultron.errors import DemoFailureError

# Ordered list of (sub-command name, demo module) pairs.
# Order defines execution sequence for the `all` sub-command (DC-01-003).
DEMOS = [
    ("receive-report", receive_report_demo),
    ("initialize-case", initialize_case_demo),
    ("initialize-participant", initialize_participant_demo),
    ("invite-actor", invite_actor_demo),
    ("establish-embargo", establish_embargo_demo),
    ("report-with-embargo", report_with_embargo_demo),
    ("acknowledge", acknowledge_demo),
    ("status-updates", status_updates_demo),
    ("suggest-actor", suggest_actor_demo),
    ("transfer-ownership", transfer_ownership_demo),
    ("manage-case", manage_case_demo),
    ("manage-embargo", manage_embargo_demo),
    ("manage-participants", manage_participants_demo),
    ("trigger", trigger_demo),
]


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
        """Invoke ``module.main()``, reporting FAIL and exiting 1 on failure.

        A ``DemoFailureError`` is the demo's recorded verdict, already logged
        step by step, so it is reported as one FAIL line rather than a
        traceback (DEMOCI-01-001).  Any other exception propagates unchanged.
        """
        try:
            module.main(skip_health_check=skip_health_check)
        except DemoFailureError as exc:
            click.echo(f"\n❌  Demo '{name}' FAILED: {exc}", err=True)
            sys.exit(1)

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
        except Exception as exc:  # noqa: BLE001  # ruff-baseline #3326
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
