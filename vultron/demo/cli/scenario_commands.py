"""Scenario sub-commands, generated from the scenario registry (DEMOCI-11-011)."""

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

import importlib
from collections.abc import Callable, Sequence
from types import ModuleType
from typing import Any, cast

import click

from vultron.demo.cli.group import main
from vultron.demo.helpers.actor_roles import (
    ActorRole,
    role_kwarg_names,
    role_map,
)
from vultron.demo.scenario.registry import ScenarioSpec, discover_scenarios
from vultron.errors import DemoScenarioRegistryError

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

    Falsy counts as absent, not just ``None``: ``ROLES = []`` and
    ``CLI_HELP = ""`` reach the factory as "declared" and produce exactly the
    optionless, undocumented sub-command described above.
    """
    value = getattr(module, attr, None)
    if not value:
        raise DemoScenarioRegistryError(
            f"scenario {spec.name!r} module {spec.module_name!r} defines no "
            f"usable {attr} (got {value!r}); the demo CLI generates its "
            f"sub-command from the registry and reads {attr} from the module "
            "(DEMOCI-11-011)."
        )
    return value


def _scenario_roles(
    module: ModuleType, spec: ScenarioSpec
) -> Sequence[ActorRole]:
    """The scenario module's declared role list, validated.

    ``role_map()`` is called for its side effect, not its result: it holds the
    "declared once" guarantees (no duplicate name, no two roles reading one
    container slot), and without this call they would bind only because a
    scenario module happens to call it for some other reason — as each once did
    to derive its own ``*_BASE_URL`` constants, which the composed form has
    none of.  Nothing requires a module to call it, and the failure is quiet — two roles
    sharing a ``name`` yield two identical flags both carrying the *second*
    role's binding, because :func:`_role_option_decorators` keys its map by
    parameter name and the first is silently dropped.
    """
    roles = cast(
        "Sequence[ActorRole]", _require_module_attr(module, "ROLES", spec)
    )
    role_map(roles)
    return roles


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
            options[role.id_param] = click.option(
                role.id_option,
                default=None,
                envvar=role.id_env,
                help=role.id_help,
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
