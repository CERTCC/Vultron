#  Copyright (c) 2026 Carnegie Mellon University and Contributors.
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
"""The demo CLI's scenario sub-commands are generated, not written (DEMOCI-11-011).

Three different things need checking and they fail for different reasons, so
they are separate tests rather than one "the CLI is right" assertion:

* **No hand-wiring.** A factory-built command and a hand-declared one are
  indistinguishable at click runtime — ``main.commands["fv"]`` is a
  ``click.Command`` either way — so the absence of hand-wiring can only be
  checked at the source level, over the AST.
* **Faithful generation.** Every generated option must be exactly what the
  scenario's ``ROLES`` list declares.  Asserted *against ``ROLES``* rather than
  against a literal table, because a literal table of nine scenarios' options
  would be a fresh hand-maintained copy of the inventory this consolidation
  deleted.
* **The declared divergences.** ``ROLES`` being self-consistent does not make it
  *right*: the checks above pass just as happily if a careless edit gives every
  scenario the same options.  The asymmetries the scenarios actually have are
  pinned by name in ``TestDeclaredDivergences``, because smoothing one of them
  over is the likely mistake and nothing else would notice.

These read the CLI and the filesystem, never a running container, so they belong
in the unit suite — see this package's docstring for why that means not
``test/demo/``.
"""

from __future__ import annotations

import ast
import importlib
import inspect
from collections.abc import Sequence
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from typing import cast
from unittest.mock import MagicMock, patch

import click
import pytest
from click.testing import CliRunner

from vultron.demo import cli
from vultron.demo.helpers.actor_roles import ActorRole
from vultron.demo.scenario.registry import ScenarioSpec, discover_scenarios
from vultron.errors import DemoActorRoleError, DemoScenarioRegistryError

_CLI_SOURCE = Path(inspect.getfile(cli))

#: One generated click option, compared positionally: first flag, parameter
#: name, envvar, default, help, ``is_flag``, ``show_default``.
_OptionTuple = tuple[
    str, str | None, str | None, object, str | None, bool, bool
]

#: A well-formed role, used to build the malformed module declarations in
#: ``TestFactoryRejectsABadModule`` by changing one field at a time.
_ROLE = ActorRole(
    name="finder",
    url_env="VULTRON_FINDER_BASE_URL",
    default_url="http://localhost:7901/api/v2",
    url_help="Base URL of the Finder container API.",
)

#: Sub-commands on ``vultron-demo`` that are deliberately not scenarios: the
#: exchange demos (``cli.DEMOS``) plus the three standing commands. Needed
#: because an exchange-demo name is indistinguishable from a scenario name by
#: spelling alone.
_NON_SCENARIO_COMMANDS = frozenset(
    {name for name, _ in cli.DEMOS} | {"all", "seed", "vultrabot"}
)

#: A role whose ``url_env`` does not name its own role — the asymmetry that makes
#: the bindings undeclarable from the registry. ``fccv-handoff`` puts C1 in the
#: Vendor container slot and the Vendor in the Vendor2 slot, because compose
#: service names are routing labels (DEMOMA, ISSUE-1786).
_SLOT_NOT_ROLE_BINDINGS = {
    ("fccv-handoff", "c1"): "VULTRON_VENDOR_BASE_URL",
    ("fccv-handoff", "c2"): "VULTRON_COORDINATOR_BASE_URL",
    ("fccv-handoff", "vendor"): "VULTRON_VENDOR2_BASE_URL",
    ("fccv-extension", "c1"): "VULTRON_COORDINATOR_BASE_URL",
    ("fccv-extension", "c2"): "VULTRON_VENDOR2_BASE_URL",
    ("fcvcv", "c1"): "VULTRON_COORDINATOR_BASE_URL",
    ("fcvcv", "c2"): "VULTRON_VENDOR2_BASE_URL",
    ("fcvcv", "v1"): "VULTRON_VENDOR_BASE_URL",
    ("fcvcv", "v2"): "VULTRON_VENDOR_DEPLOYER_BASE_URL",
}

#: Scenarios that hand a deterministic ``--case-actor-id`` to the CaseActor.
#: Only the two ownership-handoff scenarios do: they assert on the CaseActor's
#: own replica after the transfer, so its id has to be predictable.
_CASE_ACTOR_ID_SCENARIOS = frozenset({"fvcv-handoff", "fccv-handoff"})

#: The only scenario whose ``--*-id`` options are env-bound. Its five actor ids
#: come from the compose environment rather than being left to the demo.
_ID_ENVVAR_SCENARIO = "fcvcv"

#: ``fv`` colocates the CaseActor on the third container; every other scenario
#: that has one gives it a container of its own on 7905.
_CASE_ACTOR_PORTS = {
    "fv": "http://localhost:7903/api/v2",
    "fcv": "http://localhost:7905/api/v2",
    "fcv-reject": "http://localhost:7905/api/v2",
    "fvcv-handoff": "http://localhost:7905/api/v2",
    "fccv-handoff": "http://localhost:7905/api/v2",
}


def _roles_of(spec: ScenarioSpec) -> Sequence[ActorRole]:
    """The scenario module's declared role list."""
    module = importlib.import_module(spec.module_name)
    return cast("Sequence[ActorRole]", module.ROLES)


def _literal_str(node: ast.expr | None) -> str | None:
    """*node* as a string literal, or ``None`` if it is anything else.

    A computed name (``name=spec.name``) is not a hand-declaration, so it is
    correctly invisible to the caller.
    """
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _explicit_command_name(call: ast.Call | None) -> str | None:
    """The command name spelled out in a decorator call, keyword or positional."""
    if call is None:
        return None
    for keyword in call.keywords:
        if keyword.arg == "name":
            return _literal_str(keyword.value)
    return _literal_str(call.args[0] if call.args else None)


def _command_decorator_names(tree: ast.Module) -> set[str]:
    """Every command name a ``@*.command``/``@*.group`` decorator declares.

    All four spellings click accepts, because the guard below is only as strong
    as this function and three of them name a command without a ``name=``
    keyword anywhere in the source:

    * ``@main.command(name="fv")`` — the keyword form;
    * ``@main.command("fv")`` — the same string, positionally;
    * ``@main.command()`` and bare ``@main.command`` — click derives the name
      from ``__name__``, lowercased with ``_`` → ``-``, so ``def fcv_reject``
      declares ``fcv-reject`` and even a hyphenated scenario name is reachable.

    Missing any of the last three would let a hand-wired block shadow a
    generated command with every other check in this file still green, which is
    the one failure this guard exists for (DEMOCI-11-011).
    """
    names: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for decorator in node.decorator_list:
            # Bare `@main.command` — no Call node, so the name is derived.
            call = decorator if isinstance(decorator, ast.Call) else None
            func = call.func if call is not None else decorator
            if not isinstance(func, ast.Attribute):
                continue
            if func.attr not in ("command", "group"):
                continue

            explicit = _explicit_command_name(call)
            names.add(
                explicit
                if explicit is not None
                else node.name.lower().replace("_", "-")
            )
    return names


def test_no_scenario_subcommand_is_hand_declared() -> None:
    """No ``@main.command`` in ``cli.py`` names a registered scenario.

    This is the half of DEMOCI-11-011 that click cannot answer: a hand-declared
    block alongside the factory would give a scenario *two* declarations, the
    second silently shadowing the generated one in ``main.commands``, and every
    other check here would still pass.

    Asserted over the AST rather than by substring so that naming a scenario in
    a docstring or comment — as ``cli.py``'s own module docstring does — neither
    satisfies nor trips the check.
    """
    tree = ast.parse(_CLI_SOURCE.read_text(encoding="utf-8"))
    declared = _command_decorator_names(tree)
    registered = {spec.name for spec in discover_scenarios()}

    offenders = sorted(declared & registered)
    assert not offenders, (
        f"{_CLI_SOURCE.name} hand-declares sub-command(s) for registered "
        f"scenario(s) {offenders}. Scenario sub-commands are generated from the "
        "registry by _make_scenario_command (DEMOCI-11-011); delete the block "
        "and declare what it carried on the scenario module (ROLES, CLI_HELP)."
    )


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ('@main.command(name="fv")\ndef _x() -> None: ...', "fv"),
        ('@main.command("fv")\ndef _x() -> None: ...', "fv"),
        ("@main.command()\ndef fv() -> None: ...", "fv"),
        ("@main.command\ndef fv() -> None: ...", "fv"),
        ("@main.command()\ndef fcv_reject() -> None: ...", "fcv-reject"),
        ("@main.group\ndef fvcv_extension() -> None: ...", "fvcv-extension"),
    ],
    ids=[
        "name-keyword",
        "name-positional",
        "derived-empty-call",
        "derived-bare",
        "derived-underscores-to-hyphens",
        "derived-group",
    ],
)
def test_command_decorator_names_sees_every_click_spelling(
    source: str, expected: str
) -> None:
    """Guards the guard above: all four ways click names a command are detected.

    ``test_no_scenario_subcommand_is_hand_declared`` is only as strong as
    ``_command_decorator_names``, and three of these spellings put no ``name=``
    keyword in the source at all — click derives the name from ``__name__``,
    lowercased with ``_`` → ``-``, which reaches even the hyphenated scenario
    names. A reader would assume a ``name=``-only scan was sufficient, so the
    shortfall is asserted here rather than left to be rediscovered by the
    shadowed command it would allow.
    """
    assert expected in _command_decorator_names(ast.parse(source))


def test_scenario_subcommands_are_exactly_the_registered_set() -> None:
    """The scenario-shaped sub-commands are exactly the registered scenarios.

    The forward direction (every registered scenario has a sub-command) lives in
    ``test_scenario_registry.py``. This is the reverse: a sub-command whose name
    is a scenario name but which no registered scenario produced. That is what
    ``main.commands`` *can* answer and a per-scenario membership check cannot —
    the dict has no way to report an extra key nobody asked about.

    ``_NON_SCENARIO_COMMANDS`` is subtracted explicitly rather than filtered by a
    name pattern: every exchange-demo name is also a valid scenario-name spelling
    (`is_scenario_name("receive-report")` is True), so a pattern filter would
    classify all thirteen of them as scenarios.
    """
    registered = {spec.name for spec in discover_scenarios()}
    exposed = set(cli.main.commands) - _NON_SCENARIO_COMMANDS

    unregistered = sorted(exposed - registered)
    unexposed = sorted(registered - exposed)
    assert not unregistered and not unexposed, (
        "vultron/demo/cli.py's scenario sub-commands disagree with the "
        "registry:\n"
        f"  exposed but not registered: {unregistered}\n"
        f"  registered but not exposed: {unexposed}\n"
        "The CLI builds one sub-command per registered scenario and must not be "
        "a place a scenario can be added independently (DEMOCI-11-011). If a "
        "genuinely non-scenario command was added, list it in "
        "_NON_SCENARIO_COMMANDS."
    )


def test_registry_is_the_only_source_of_scenario_subcommands() -> None:
    """``cli.py`` imports no scenario demo module by name.

    A named import list would let the CLI's scenario set drift from the
    registry's — the silent-omission hazard DEMOCI-11-002 removes from
    discovery, reintroduced one layer up.
    """
    tree = ast.parse(_CLI_SOURCE.read_text(encoding="utf-8"))

    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.append(node.module)

    offenders = sorted(
        name
        for name in imported
        if name.startswith("vultron.demo.scenario.") and name.endswith("_demo")
    )
    assert not offenders, (
        f"{_CLI_SOURCE.name} imports scenario demo module(s) by name: "
        f"{offenders}. The scenario set comes from discover_scenarios(); a "
        "named import here can omit a scenario without failing anything "
        "(DEMOCI-11-011)."
    )


@pytest.mark.parametrize(
    "spec", discover_scenarios(), ids=lambda spec: spec.name
)
def test_generated_options_match_the_declared_roles(
    spec: ScenarioSpec,
) -> None:
    """Each scenario's options are exactly what its ``ROLES`` list declares.

    Covers flag spelling, env binding, default, help text, ``show_default`` and
    declaration order in one comparison, because they are produced by one loop
    and a regression in the factory would usually break several at once.

    ``show_default`` is in the tuple because it is otherwise unpinned and
    invisible: dropping it from the URL options would strip the
    ``[default: http://localhost:79xx/api/v2]`` line from every scenario's
    ``--help`` — a change to rendered output that no other assertion here or in
    ``test/demo/test_cli.py`` would notice.
    """
    roles = _roles_of(spec)
    command = cli.main.commands[spec.name]

    expected: list[_OptionTuple] = [
        (
            role.url_option,
            role.url_param,
            role.url_env,
            role.url,
            role.url_help,
            False,
            True,
        )
        for role in roles
    ]
    expected += [
        (
            role.id_option,
            role.id_param,
            role.id_env,
            None,
            role.id_help,
            False,
            False,
        )
        for role in roles
        if role.has_id
    ]
    expected.append(
        (
            "--skip-health-check",
            "skip_health_check",
            None,
            False,
            "Skip container availability checks.",
            True,
            False,
        )
    )

    actual: list[_OptionTuple] = [
        (
            param.opts[0],
            param.name,
            cast("str | None", param.envvar),
            param.default,
            cast(click.Option, param).help,
            cast(click.Option, param).is_flag,
            bool(cast(click.Option, param).show_default),
        )
        for param in command.params
    ]

    assert actual == expected, (
        f"the generated options for {spec.name!r} do not match its ROLES "
        f"declaration.\n  expected: {expected}\n  actual:   {actual}"
    )


@pytest.mark.parametrize(
    "spec", discover_scenarios(), ids=lambda spec: spec.name
)
def test_subcommand_invokes_the_scenario_main(spec: ScenarioSpec) -> None:
    """Invoking the sub-command calls its module's ``main()`` once, by keyword.

    Also pins the late binding the factory depends on: it resolves ``main`` on
    the module at call time, so ``patch.object`` intercepts it.  Capturing the
    function when the command is built would make every scenario's CLI
    untestable without a live container.
    """
    module = importlib.import_module(spec.module_name)
    mock_main = MagicMock()
    runner = CliRunner()

    with patch.object(module, "main", mock_main):
        result = runner.invoke(cli.main, [spec.name, "--skip-health-check"])

    assert result.exit_code == 0, result.output
    mock_main.assert_called_once()
    args, kwargs = mock_main.call_args
    assert args == (), "the factory must pass every option by keyword"
    assert kwargs["skip_health_check"] is True
    for role in _roles_of(spec):
        assert kwargs[role.url_param] == role.url
        if role.has_id:
            assert kwargs[role.id_param] is None


@pytest.mark.parametrize(
    "spec", discover_scenarios(), ids=lambda spec: spec.name
)
def test_subcommand_exits_nonzero_when_the_scenario_raises(
    spec: ScenarioSpec,
) -> None:
    """A failing scenario surfaces as a non-zero exit (DC-05-003).

    Pinned per scenario because the hand-wired blocks each had their own call
    site; the factory has one, and this is what proves the single path still
    propagates.

    The exception identity is asserted, not just the exit code: a click usage
    error — a generated option the scenario's ``main()`` does not accept, say —
    also exits non-zero, so an exit-code-only assertion would pass while the
    scenario never ran.
    """
    module = importlib.import_module(spec.module_name)
    injected = RuntimeError("injected")
    runner = CliRunner()

    with patch.object(module, "main", MagicMock(side_effect=injected)):
        result = runner.invoke(cli.main, [spec.name, "--skip-health-check"])

    assert result.exit_code != 0
    assert result.exception is injected


@pytest.mark.parametrize(
    "spec", discover_scenarios(), ids=lambda spec: spec.name
)
def test_scenario_declares_cli_help(spec: ScenarioSpec) -> None:
    """Each scenario module supplies its own ``--help`` body.

    The registry carries no help text — it holds one-line prose for table cells
    — so a scenario whose module omitted ``CLI_HELP`` would otherwise get a
    sub-command that documents nothing.
    """
    module = importlib.import_module(spec.module_name)
    help_text = getattr(module, "CLI_HELP", None)
    assert isinstance(help_text, str) and help_text.strip(), (
        f"{spec.module_name} defines no usable CLI_HELP; the generated "
        f"'{spec.name}' sub-command would have no --help body."
    )
    assert cli.main.commands[spec.name].help == help_text


class TestFactoryRejectsABadModule:
    """The factory's own guards, exercised on the path the factory uses.

    Each of these is currently unreachable through the nine shipped scenarios,
    which is the point: they are what a *tenth* scenario meets, and every one of
    them fails quietly rather than loudly if the guard is absent.
    """

    @staticmethod
    def _spec() -> ScenarioSpec:
        """A registered scenario's spec, used to name the module under test."""
        return discover_scenarios()[0]

    def _build(self, module: object) -> None:
        """Run the factory against *module* standing in for the real one."""
        spec = self._spec()
        with patch.object(importlib, "import_module", lambda _: module):
            cli._make_scenario_command(spec)

    def test_rejects_an_empty_roles_list(self) -> None:
        """``ROLES = []`` is absent, not declared.

        It would otherwise reach the factory as a real declaration and yield a
        sub-command carrying only ``--skip-health-check`` — a scenario that runs
        against localhost defaults and *looks* like a working demo, which is the
        outcome ``_require_module_attr``'s docstring promises to prevent.
        """
        module = SimpleNamespace(ROLES=[], CLI_HELP="Run it.")
        with pytest.raises(DemoScenarioRegistryError, match="no usable ROLES"):
            self._build(module)

    def test_rejects_an_empty_cli_help(self) -> None:
        """``CLI_HELP = ""`` yields a sub-command that documents nothing."""
        module = SimpleNamespace(ROLES=[_ROLE], CLI_HELP="")
        with pytest.raises(
            DemoScenarioRegistryError, match="no usable CLI_HELP"
        ):
            self._build(module)

    def test_rejects_two_roles_sharing_a_name(self) -> None:
        """The factory enforces ``role_map``'s declared-once guarantee itself.

        Without the ``role_map()`` call in ``_scenario_roles`` this would bind
        only because every scenario module happens to call ``role_map`` to derive
        its ``*_BASE_URL`` constants, and nothing requires a module to do that.
        The failure is quiet: ``_role_option_decorators`` keys its map by
        parameter name, so two roles named ``finder`` collapse into one option
        carrying the *second* role's env var and default — the first binding is
        dropped with no error and the scenario runs against the wrong container.
        """
        other = replace(
            _ROLE,
            url_env="VULTRON_VENDOR_BASE_URL",
            default_url="http://localhost:7902/api/v2",
        )
        module = SimpleNamespace(ROLES=[_ROLE, other], CLI_HELP="Run it.")
        with pytest.raises(DemoActorRoleError, match="declared twice"):
            self._build(module)

    def test_rejects_two_roles_sharing_a_container_slot(self) -> None:
        """One ``url_env`` claimed by two roles is a half-edited copy-paste."""
        module = SimpleNamespace(
            ROLES=[_ROLE, replace(_ROLE, name="vendor")], CLI_HELP="Run it."
        )
        with pytest.raises(DemoActorRoleError, match="one of them is reading"):
            self._build(module)


class TestDeclaredDivergences:
    """The asymmetries a uniform ``ROLES`` edit would smooth over."""

    def test_url_env_names_a_container_slot_not_the_role(self) -> None:
        """Roles whose ``url_env`` does not match their own name keep that binding.

        This is the asymmetry the whole `ActorRole` declaration exists for: if
        every role read `VULTRON_<NAME>_BASE_URL` the bindings would derive from
        the role name and belong on the `@scenario` decorator. Pinned so a
        "tidy-up" that regularises these cannot pass — it would point C1 at the
        wrong container and the scenario would still run.
        """
        actual = {
            (spec.name, role.name): role.url_env
            for spec in discover_scenarios()
            for role in _roles_of(spec)
            if role.url_env != f"VULTRON_{role.param_stem.upper()}_BASE_URL"
        }
        assert actual == _SLOT_NOT_ROLE_BINDINGS

    def test_case_actor_id_only_on_the_handoff_scenarios(self) -> None:
        """Only the ownership-handoff scenarios take ``--case-actor-id``."""
        with_id = {
            spec.name
            for spec in discover_scenarios()
            for role in _roles_of(spec)
            if role.name == "case-actor" and role.has_id
        }
        assert with_id == _CASE_ACTOR_ID_SCENARIOS

    def test_id_options_are_env_bound_only_for_fcvcv(self) -> None:
        """Only ``fcvcv`` binds its ``--*-id`` options to env vars."""
        with_env = {
            spec.name
            for spec in discover_scenarios()
            for role in _roles_of(spec)
            if role.id_env is not None
        }
        assert with_env == {_ID_ENVVAR_SCENARIO}

    def test_fv_colocates_the_case_actor_on_a_different_port(self) -> None:
        """``fv``'s CaseActor default is 7903; the others' is 7905."""
        actual = {
            spec.name: role.default_url
            for spec in discover_scenarios()
            for role in _roles_of(spec)
            if role.name == "case-actor"
        }
        assert actual == _CASE_ACTOR_PORTS
