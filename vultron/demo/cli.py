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

The multi-container **scenario** sub-commands are not declared here at all:
they are generated, one per registered scenario, by :func:`_make_scenario_command`
from the scenario registry (DEMOCI-11-011, ADR-0098).  The registry is the sole
declaration point for which scenarios exist, so this module cannot be a place a
scenario is omitted from or added to independently of it — which it was while it
hand-wired one ``@main.command`` block each.  Each scenario module supplies the
two things the registry deliberately does not carry: its ``ROLES`` list (the
container-URL and actor-id options, whose env bindings key to physical container
slots rather than roles) and its ``CLI_HELP`` text.

A ``vultrabot`` sub-group provides access to the three standalone
behaviour-tree demos (pacman, robot, cvd).

The ``seed`` sub-command bootstraps actor records in the DataLayer on
container startup, supporting multi-actor demo scenarios (D5-1-G2).
"""

import importlib
import logging
import sys
from collections.abc import Callable, Sequence
from types import ModuleType, SimpleNamespace
from typing import Any, cast

import click

import vultron.demo.exchange.acknowledge_demo as acknowledge_demo
import vultron.demo.exchange.establish_embargo_demo as establish_embargo_demo
import vultron.demo.exchange.initialize_case_demo as initialize_case_demo
import vultron.demo.exchange.initialize_participant_demo as initialize_participant_demo
import vultron.demo.exchange.invite_actor_demo as invite_actor_demo
import vultron.demo.exchange.manage_case_demo as manage_case_demo
import vultron.demo.exchange.manage_embargo_demo as manage_embargo_demo
import vultron.demo.exchange.manage_participants_demo as manage_participants_demo
import vultron.demo.exchange.receive_report_demo as receive_report_demo
import vultron.demo.exchange.status_updates_demo as status_updates_demo
import vultron.demo.exchange.suggest_actor_demo as suggest_actor_demo
import vultron.demo.exchange.transfer_ownership_demo as transfer_ownership_demo
import vultron.demo.exchange.trigger_demo as trigger_demo
from vultron.demo.helpers.actor_roles import ActorRole, role_kwarg_names
from vultron.demo.scenario.registry import ScenarioSpec, discover_scenarios
from vultron.demo.seed_config import SeedConfig
from vultron.demo.utils import DataLayerClient, BASE_URL, seed_actor, seed_peer
from vultron.errors import DemoScenarioRegistryError
from vultron.logging_setup import suppress_third_party_info_noise
import vultron.bt.base.demo.pacman as pacman_demo
import vultron.bt.base.demo.robot as robot_demo
import vultron.bt.base.demo.cvd as cvd_vultrabot_demo

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
    suppress_third_party_info_noise(level)
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


# ---------------------------------------------------------------------------
# Scenario sub-commands — generated from the registry (DEMOCI-11-011)
# ---------------------------------------------------------------------------


#: Type of a built ``click.option`` decorator, which is what the factory
#: assembles per role before applying them in ``role_kwarg_names()`` order.
_OptionDecorator = Callable[[Callable[..., None]], Callable[..., None]]


def _require_module_attr(
    module: ModuleType, attr: str, spec: ScenarioSpec
) -> object:
    """Return *module*'s *attr*, raising if the scenario module omits it.

    Fails closed for the same reason ``discover_scenarios()`` does: a scenario
    that quietly lost its ``ROLES`` list would produce a sub-command with no
    container options, which runs against localhost defaults and *looks* like a
    working demo.
    """
    value = getattr(module, attr, None)
    if value is None:
        raise DemoScenarioRegistryError(
            f"scenario {spec.name!r} module {spec.module_name!r} defines no "
            f"{attr}; the demo CLI generates its sub-command from the registry "
            f"and reads {attr} from the module (DEMOCI-11-011)."
        )
    return value


def _scenario_roles(
    module: ModuleType, spec: ScenarioSpec
) -> Sequence[ActorRole]:
    """The scenario module's declared role list."""
    return cast(
        "Sequence[ActorRole]", _require_module_attr(module, "ROLES", spec)
    )


def _scenario_cli_help(module: ModuleType, spec: ScenarioSpec) -> str:
    """The scenario module's declared ``--help`` body."""
    return cast(str, _require_module_attr(module, "CLI_HELP", spec))


def _role_option_decorators(
    roles: Sequence[ActorRole],
) -> dict[str, _OptionDecorator]:
    """Map each role-contributed ``main()`` keyword to its click option.

    Keyed by parameter name rather than returned as a list so the caller can
    apply them in whatever order :func:`role_kwarg_names` states, instead of
    reproducing that order here.
    """
    options: dict[str, _OptionDecorator] = {}
    for role in roles:
        options[role.url_param] = click.option(
            role.url_option,
            envvar=role.url_env,
            default=role.url,
            show_default=True,
            help=role.url_help,
        )
        if role.has_id:
            id_kwargs: dict[str, Any] = {}
            if role.id_env is not None:
                id_kwargs["envvar"] = role.id_env
            options[role.id_param] = click.option(
                role.id_option, default=None, help=role.id_help, **id_kwargs
            )
    return options


def _make_scenario_command(spec: ScenarioSpec) -> click.Command:
    """Return the click Command for one registered scenario.

    The option order is not chosen here: it is read off
    :func:`~vultron.demo.helpers.actor_roles.role_kwarg_names`, the single
    statement of it, which
    ``test/architecture/test_scenario_roles_match_main_kwargs.py`` also pins the
    scenario's ``main()`` signature to. Re-deriving the order in this function
    would give that ratchet a second copy of the rule to agree with instead of
    the rule itself. ``--skip-health-check`` goes last because it is the one
    keyword no role contributes.

    Args:
        spec: The registered scenario to build a sub-command for.

    Returns:
        A click Command named ``spec.name``.

    Raises:
        DemoScenarioRegistryError: If the scenario module defines no ``ROLES``
            or no ``CLI_HELP``.
    """
    module = importlib.import_module(spec.module_name)
    roles = _scenario_roles(module, spec)
    help_text = _scenario_cli_help(module, spec)

    def _cmd(**kwargs: Any) -> None:
        """Invoke the scenario module's ``main()`` with the parsed options."""
        # Looked up on the module at call time, not captured at build time, so
        # `patch.object(module, "main", ...)` in the CLI unit tests still
        # intercepts the call — the same late binding the hand-wired blocks had.
        run = cast("Callable[..., None]", module.main)
        run(**kwargs)

    _cmd.__name__ = spec.module_stem

    built: Callable[..., None] = click.option(
        "--skip-health-check",
        is_flag=True,
        default=False,
        help="Skip container availability checks.",
    )(_cmd)
    # click decorators apply bottom-up, so walk the declared order backwards.
    role_options = _role_option_decorators(roles)
    for param in reversed(role_kwarg_names(roles)):
        built = role_options[param](built)

    return click.command(name=spec.name, help=help_text)(built)


#: The registered scenarios this module built a sub-command for — the scenario
#: half of what :data:`DEMOS` is for the exchange demos. Discovery walks the
#: package (DEMOCI-11-002); `registered_scenarios()` would see only the modules
#: something else happened to import.
SCENARIOS: tuple[ScenarioSpec, ...] = discover_scenarios()

for _spec in SCENARIOS:
    main.add_command(_make_scenario_command(_spec))


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
    help="Path to a YAML seed config file. Overrides individual options.",
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
    1. A YAML config file (``--config`` / ``VULTRON_SEED_CONFIG``).
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

    # Register peer actors as address-book entries in the local actor's store.
    for peer in cfg.peers:
        click.echo(f"🌱 Registering peer: {peer.name!r} ({peer.actor_type})")
        peer_actor = seed_peer(
            client=client,
            local_actor_id=actor.id_,
            peer_id=peer.id_,
            name=peer.name,
            actor_type=peer.actor_type,
        )
        click.echo(f"   → {peer_actor.id_}")
        logger.info("Peer registered: %s", peer_actor.id_)

    click.echo("✅ Seed complete.")


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
