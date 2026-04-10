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

The ``seed`` sub-command bootstraps actor records in the DataLayer on
container startup, supporting multi-actor demo scenarios (D5-1-G2).
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
import vultron.demo.multi_vendor_demo as multi_vendor_demo
import vultron.demo.three_actor_demo as three_actor_demo
import vultron.demo.transfer_ownership_demo as transfer_ownership_demo
import vultron.demo.trigger_demo as trigger_demo
import vultron.demo.two_actor_demo as two_actor_demo
from vultron.demo.seed_config import SeedConfig
from vultron.demo.utils import DataLayerClient, BASE_URL, seed_actor
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
    ("trigger", trigger_demo),
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
# Seed sub-command — bootstrap actor records (D5-1-G2)
# ---------------------------------------------------------------------------


@main.command(name="seed")
@click.option(
    "--config",
    "config_path",
    envvar="VULTRON_SEED_CONFIG",
    default=None,
    metavar="PATH",
    help="Path to a JSON seed config file. Overrides individual options.",
)
@click.option(
    "--actor-name",
    envvar="VULTRON_ACTOR_NAME",
    default=None,
    help="Display name for the local actor (env: VULTRON_ACTOR_NAME).",
)
@click.option(
    "--actor-type",
    envvar="VULTRON_ACTOR_TYPE",
    default=None,
    help="ActivityStreams type for the local actor (env: VULTRON_ACTOR_TYPE).",
)
@click.option(
    "--actor-id",
    envvar="VULTRON_ACTOR_ID",
    default=None,
    help="Full URI for the local actor (env: VULTRON_ACTOR_ID).",
)
@click.option(
    "--api-url",
    envvar="VULTRON_API_BASE_URL",
    default=BASE_URL,
    show_default=True,
    help="Base URL of the Vultron API server (env: VULTRON_API_BASE_URL).",
)
def seed(
    config_path: str | None,
    actor_name: str | None,
    actor_type: str | None,
    actor_id: str | None,
    api_url: str,
) -> None:
    """Bootstrap actor records in the local DataLayer (D5-1-G2).

    Creates the local actor and any configured peer actors in the DataLayer
    via ``POST /actors/``.  Safe to re-run: existing records are returned
    unchanged (idempotent).

    Configuration is loaded from (in decreasing priority):

    \b
    1. A JSON config file (``--config`` / ``VULTRON_SEED_CONFIG``).
    2. Individual CLI options / environment variables.
    """
    logger = logging.getLogger(__name__)

    cfg = SeedConfig.load(
        config_path=config_path,
        actor_name=actor_name,
        actor_type=actor_type,
        actor_id=actor_id,
    )

    client = DataLayerClient(base_url=api_url)

    # Create local actor.
    local = cfg.local_actor
    click.echo(f"🌱 Seeding local actor: {local.name!r} ({local.actor_type})")
    actor = seed_actor(
        client=client,
        name=local.name,
        actor_type=local.actor_type,
        actor_id=local.id_,
    )
    click.echo(f"   → {actor.id_}")
    logger.info("Local actor seeded: %s", actor.id_)

    # Register peer actors.
    for peer in cfg.peers:
        click.echo(f"🌱 Seeding peer actor: {peer.name!r} ({peer.actor_type})")
        peer_actor = seed_actor(
            client=client,
            name=peer.name,
            actor_type=peer.actor_type,
            actor_id=peer.id_,
        )
        click.echo(f"   → {peer_actor.id_}")
        logger.info("Peer actor seeded: %s", peer_actor.id_)

    click.echo("✅ Seed complete.")


# ---------------------------------------------------------------------------
# Two-actor sub-command — multi-container Finder + Vendor demo (D5-1-G5)
# ---------------------------------------------------------------------------


@main.command(name="two-actor")
@click.option(
    "--finder-url",
    envvar="VULTRON_FINDER_BASE_URL",
    default=two_actor_demo.FINDER_BASE_URL,
    show_default=True,
    help="Base URL of the Finder container API "
    "(env: VULTRON_FINDER_BASE_URL).",
)
@click.option(
    "--vendor-url",
    envvar="VULTRON_VENDOR_BASE_URL",
    default=two_actor_demo.VENDOR_BASE_URL,
    show_default=True,
    help="Base URL of the Vendor container API "
    "(env: VULTRON_VENDOR_BASE_URL).",
)
@click.option(
    "--finder-id",
    default=None,
    help="Deterministic full URI for the Finder actor (optional).",
)
@click.option(
    "--vendor-id",
    default=None,
    help="Deterministic full URI for the Vendor actor (optional).",
)
@click.option(
    "--case-actor-url",
    envvar="VULTRON_CASE_ACTOR_BASE_URL",
    default=two_actor_demo.CASE_ACTOR_BASE_URL,
    show_default=True,
    help="Base URL of the CaseActor container API "
    "(env: VULTRON_CASE_ACTOR_BASE_URL).",
)
@click.option(
    "--skip-health-check",
    is_flag=True,
    default=False,
    help="Skip container availability checks.",
)
def two_actor(
    finder_url: str,
    vendor_url: str,
    finder_id: str | None,
    vendor_id: str | None,
    case_actor_url: str,
    skip_health_check: bool,
) -> None:
    """Run the two-actor (Finder + Vendor) multi-container CVD demo (D5-1-G5).

    Orchestrates a complete CVD workflow across two separate API server
    containers.  Requires both containers to be running and reachable at
    the configured base URLs.

    Use ``--finder-url`` / ``--vendor-url`` (or env vars
    ``VULTRON_FINDER_BASE_URL`` / ``VULTRON_VENDOR_BASE_URL``) to point
    the demo at running containers.

    \b
    Workflow:
      1. Seed both containers (actor records + peer registration).
      2. Finder submits a vulnerability report to Vendor's inbox.
      3. Vendor validates the report (trigger: validate-report).
      4. Vendor engages the case (trigger: engage-case).
      5. Vendor invites Finder to the case (Finder's inbox).
      6. Finder accepts the invitation (Vendor's inbox).
      7. Verify final state on both containers.
    """
    two_actor_demo.main(
        skip_health_check=skip_health_check,
        finder_url=finder_url,
        vendor_url=vendor_url,
        case_actor_url=case_actor_url,
        finder_id=finder_id,
        vendor_id=vendor_id,
    )


# ---------------------------------------------------------------------------
# Three-actor sub-command — multi-container Finder + Vendor + Coordinator demo
# ---------------------------------------------------------------------------


@main.command(name="three-actor")
@click.option(
    "--finder-url",
    envvar="VULTRON_FINDER_BASE_URL",
    default=three_actor_demo.FINDER_BASE_URL,
    show_default=True,
    help="Base URL of the Finder container API "
    "(env: VULTRON_FINDER_BASE_URL).",
)
@click.option(
    "--vendor-url",
    envvar="VULTRON_VENDOR_BASE_URL",
    default=three_actor_demo.VENDOR_BASE_URL,
    show_default=True,
    help="Base URL of the Vendor container API "
    "(env: VULTRON_VENDOR_BASE_URL).",
)
@click.option(
    "--coordinator-url",
    envvar="VULTRON_COORDINATOR_BASE_URL",
    default=three_actor_demo.COORDINATOR_BASE_URL,
    show_default=True,
    help="Base URL of the Coordinator container API "
    "(env: VULTRON_COORDINATOR_BASE_URL).",
)
@click.option(
    "--case-actor-url",
    envvar="VULTRON_CASE_ACTOR_BASE_URL",
    default=three_actor_demo.CASE_ACTOR_BASE_URL,
    show_default=True,
    help="Base URL of the CaseActor container API "
    "(env: VULTRON_CASE_ACTOR_BASE_URL).",
)
@click.option(
    "--finder-id",
    default=None,
    help="Deterministic full URI for the Finder actor (optional).",
)
@click.option(
    "--vendor-id",
    default=None,
    help="Deterministic full URI for the Vendor actor (optional).",
)
@click.option(
    "--coordinator-id",
    default=None,
    help="Deterministic full URI for the Coordinator actor (optional).",
)
@click.option(
    "--case-actor-id",
    default=None,
    help="Deterministic full URI for the CaseActor actor (optional).",
)
@click.option(
    "--skip-health-check",
    is_flag=True,
    default=False,
    help="Skip container availability checks.",
)
def three_actor(
    finder_url: str,
    vendor_url: str,
    coordinator_url: str,
    case_actor_url: str,
    finder_id: str | None,
    vendor_id: str | None,
    coordinator_id: str | None,
    case_actor_id: str | None,
    skip_health_check: bool,
) -> None:
    """Run the three-actor multi-container CVD demo (D5-3)."""
    three_actor_demo.main(
        skip_health_check=skip_health_check,
        finder_url=finder_url,
        vendor_url=vendor_url,
        coordinator_url=coordinator_url,
        case_actor_url=case_actor_url,
        finder_id=finder_id,
        vendor_id=vendor_id,
        coordinator_id=coordinator_id,
        case_actor_id=case_actor_id,
    )


# ---------------------------------------------------------------------------
# Multi-vendor sub-command — ownership transfer + second vendor demo (D5-4)
# ---------------------------------------------------------------------------


@main.command(name="multi-vendor")
@click.option(
    "--finder-url",
    envvar="VULTRON_FINDER_BASE_URL",
    default=multi_vendor_demo.FINDER_BASE_URL,
    show_default=True,
    help="Base URL of the Finder container API "
    "(env: VULTRON_FINDER_BASE_URL).",
)
@click.option(
    "--vendor-url",
    envvar="VULTRON_VENDOR_BASE_URL",
    default=multi_vendor_demo.VENDOR_BASE_URL,
    show_default=True,
    help="Base URL of the Vendor container API "
    "(env: VULTRON_VENDOR_BASE_URL).",
)
@click.option(
    "--coordinator-url",
    envvar="VULTRON_COORDINATOR_BASE_URL",
    default=multi_vendor_demo.COORDINATOR_BASE_URL,
    show_default=True,
    help="Base URL of the Coordinator container API "
    "(env: VULTRON_COORDINATOR_BASE_URL).",
)
@click.option(
    "--case-actor-url",
    envvar="VULTRON_CASE_ACTOR_BASE_URL",
    default=multi_vendor_demo.CASE_ACTOR_BASE_URL,
    show_default=True,
    help="Base URL of the CaseActor container API "
    "(env: VULTRON_CASE_ACTOR_BASE_URL).",
)
@click.option(
    "--vendor2-url",
    envvar="VULTRON_VENDOR2_BASE_URL",
    default=multi_vendor_demo.VENDOR2_BASE_URL,
    show_default=True,
    help="Base URL of the Vendor2 container API "
    "(env: VULTRON_VENDOR2_BASE_URL).",
)
@click.option(
    "--finder-id",
    default=None,
    help="Deterministic full URI for the Finder actor (optional).",
)
@click.option(
    "--vendor-id",
    default=None,
    help="Deterministic full URI for the Vendor actor (optional).",
)
@click.option(
    "--coordinator-id",
    default=None,
    help="Deterministic full URI for the Coordinator actor (optional).",
)
@click.option(
    "--case-actor-id",
    default=None,
    help="Deterministic full URI for the CaseActor actor (optional).",
)
@click.option(
    "--vendor2-id",
    default=None,
    help="Deterministic full URI for the Vendor2 actor (optional).",
)
@click.option(
    "--skip-health-check",
    is_flag=True,
    default=False,
    help="Skip container availability checks.",
)
def multi_vendor(
    finder_url: str,
    vendor_url: str,
    coordinator_url: str,
    case_actor_url: str,
    vendor2_url: str,
    finder_id: str | None,
    vendor_id: str | None,
    coordinator_id: str | None,
    case_actor_id: str | None,
    vendor2_id: str | None,
    skip_health_check: bool,
) -> None:
    """Run the multi-vendor ownership-transfer demo (D5-4).

    Demonstrates case ownership transfer from Vendor to Coordinator, followed
    by Coordinator inviting a second Vendor (Vendor2) to join the case.

    Requires five containers to be running and reachable at the configured
    base URLs: finder, vendor, coordinator, case-actor, and vendor2.

    \b
    Workflow:
      1. Seed all five containers (actor records + peer registration).
      2. Finder submits a vulnerability report to Vendor's inbox.
      3. Vendor validates the report.
      4. Vendor creates the authoritative case on the CaseActor container.
      5. Vendor invites Finder; both establish an embargo.
      6. Vendor transfers case ownership to Coordinator.
      7. Coordinator invites Vendor2; Vendor2 joins and accepts the embargo.
      8. Verify final state: Coordinator owns the case, three participants,
         and the embargo is ACTIVE.
    """
    multi_vendor_demo.main(
        skip_health_check=skip_health_check,
        finder_url=finder_url,
        vendor_url=vendor_url,
        coordinator_url=coordinator_url,
        case_actor_url=case_actor_url,
        vendor2_url=vendor2_url,
        finder_id=finder_id,
        vendor_id=vendor_id,
        coordinator_id=coordinator_id,
        case_actor_id=case_actor_id,
        vendor2_id=vendor2_id,
    )


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
