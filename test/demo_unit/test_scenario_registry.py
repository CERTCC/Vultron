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
"""Ratchets over the self-registering demo scenario registry (DEMOCI-11).

The registry is the sole declaration point for the set of demo scenarios that
exist, and every committed scenario artifact is generated from it.  That makes
an *incomplete* registry the dangerous failure: a short registry renders a
short table that looks complete, which is the defect ADR-0098 exists to remove.
These tests close the three ways it could go quietly short:

* a demo module that omits the decorator (``test_registry_matches_modules_on_disk``);
* discovery that stops walking the package and reads a list instead
  (``test_discovery_walks_the_package``, ``test_no_hand_maintained_import_list``);
* a registered scenario whose derived paths do not resolve
  (``test_derived_paths_resolve``).

These read source and the filesystem, not demo artifacts, so they belong in the
ordinary unit suite.  Kept out of ``test/demo/`` deliberately — see this
package's docstring: everything collected there is auto-marked ``integration``
and so deselected by default, which would leave the registry's only guards
invisible to the ``Tests (pytest)`` tier.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from vultron.demo import cli
from vultron.demo.scenario.registry import (
    MODULE_SUFFIX,
    SCENARIO_DIR,
    SCENARIO_PACKAGE,
    ScenarioSpec,
    discover_scenarios,
    scenario,
    scenario_module_stems,
)
from vultron.errors import DemoScenarioRegistryError

_REPO_ROOT = Path(__file__).parents[2]
_SCENARIO_DIR = _REPO_ROOT / SCENARIO_DIR
_REGISTRY_SOURCE = _SCENARIO_DIR / "registry.py"


def _module_stems_on_disk() -> set[str]:
    """Scenario demo module stems, read straight off the filesystem.

    Deliberately an independent ``glob`` rather than a call into the registry:
    comparing discovery against itself would pass whatever discovery did.
    """
    return {
        path.stem
        for path in _SCENARIO_DIR.glob(f"*{MODULE_SUFFIX}.py")
        if not path.name.startswith("_")
    }


def test_registry_matches_modules_on_disk() -> None:
    """The registered set equals the ``*_demo.py`` modules present on disk.

    A module that omits the ``@scenario`` decorator fails here, which is the
    check that makes the registry trustworthy as the sole declaration point
    (DEMOCI-11-001).  Without it, a forgotten decorator is indistinguishable
    from a scenario having been deleted — both just produce a shorter table.
    """
    registered = {
        f"{spec.module_stem}{MODULE_SUFFIX}" for spec in discover_scenarios()
    }
    on_disk = _module_stems_on_disk()

    missing = sorted(on_disk - registered)
    extra = sorted(registered - on_disk)
    assert not missing and not extra, (
        "the scenario registry disagrees with the modules in "
        f"{SCENARIO_DIR}/:\n"
        f"  on disk but unregistered: {missing}\n"
        f"  registered but absent:    {extra}\n"
        "Decorate the module's main() with @scenario(...) from "
        f"{SCENARIO_PACKAGE}.registry."
    )


def test_discovery_walks_the_package() -> None:
    """``scenario_module_stems()`` sees every ``*_demo.py`` module and nothing else.

    Discovery is checked against the filesystem separately from the registry so
    that a discovery regression and a missing decorator fail as different tests
    rather than as one ambiguous set mismatch.
    """
    assert set(scenario_module_stems()) == _module_stems_on_disk()


def test_no_hand_maintained_import_list() -> None:
    """The discovery module imports no scenario demo module by name.

    Import-time registration only sees what was imported, so a hand-written
    import list here would recreate the silent omission the registry removes: a
    new demo is written, nobody adds it to the list, and every generated table
    is quietly complete-looking and wrong (DEMOCI-11-002).

    Asserted over the AST rather than by substring so that naming a module in a
    docstring or comment — as this module's own prose does — cannot satisfy or
    trip the check.
    """
    tree = ast.parse(_REGISTRY_SOURCE.read_text(encoding="utf-8"))

    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.append(node.module)
            imported.extend(
                f"{node.module}.{alias.name}" for alias in node.names
            )

    offenders = sorted(
        name for name in imported if name.endswith(MODULE_SUFFIX)
    )
    assert not offenders, (
        f"{_REGISTRY_SOURCE.name} imports scenario demo module(s) by name: "
        f"{offenders}. Discovery must enumerate the package with pkgutil "
        "(DEMOCI-11-002); a named import list omits any module nobody "
        "remembers to add."
    )

    calls = {
        f"{getattr(node.func.value, 'id', '')}.{node.func.attr}"
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }
    assert "pkgutil.iter_modules" in calls, (
        f"{_REGISTRY_SOURCE.name} no longer calls pkgutil.iter_modules; "
        "package traversal is what makes discovery independent of anyone "
        "remembering to register a module (DEMOCI-11-002)."
    )


@pytest.mark.parametrize(
    "spec", discover_scenarios(), ids=lambda spec: spec.name
)
def test_derived_paths_resolve(spec: ScenarioSpec) -> None:
    """All three of a scenario's convention-derived paths exist on disk.

    The registry stores no paths, so this is the only thing standing between a
    renamed or missing file and a table that confidently describes it
    (DEMOCI-11-003).  It is the defect class the removed ``vc`` row belonged
    to: a row naming a script that had never existed.
    """
    missing = [
        path for path in spec.derived_paths if not (_REPO_ROOT / path).exists()
    ]
    assert not missing, (
        f"scenario {spec.name!r} derives path(s) that do not exist: {missing}. "
        "Rename the file to match the scenario name, or fix the name in the "
        "@scenario decorator — do not add a path override (DEMOCI-11-003)."
    )


@pytest.mark.parametrize(
    "spec", discover_scenarios(), ids=lambda spec: spec.name
)
def test_every_scenario_has_a_cli_subcommand(spec: ScenarioSpec) -> None:
    """Each registered scenario is reachable from ``vultron-demo``.

    Since ISSUE-3475 ``vultron/demo/cli.py`` generates one sub-command per
    registered scenario rather than hand-wiring a ``@main.command`` block each
    (DEMOCI-11-011), so this can no longer fail by someone forgetting a block —
    it fails if discovery and command registration disagree.

    DEMOCI-11-011's "exactly one" has two further halves, neither of which
    ``main.commands`` can answer, because it is a dict keyed by command name: a
    scenario *cannot* resolve to two entries, and a hand-declared block would
    silently replace the generated one rather than coexist with it. Those are
    ``test_no_scenario_subcommand_is_hand_declared`` (source-level) and
    ``test_scenario_subcommands_are_exactly_the_registered_set`` (the reverse
    direction), both in ``test_scenario_cli_factory.py``.
    """
    assert spec.name in cli.main.commands, (
        f"scenario {spec.name!r} is registered but vultron/demo/cli.py exposes "
        f"no '{spec.name}' sub-command, so nothing can run it. The CLI builds "
        "one per registered scenario; check discover_scenarios() and "
        "_make_scenario_command()."
    )


def test_scenario_rejects_a_name_that_contradicts_its_module() -> None:
    """A copy-pasted decorator that kept the old ``name`` is rejected.

    This is the one drift a path check cannot catch: all three derived paths
    still resolve, because they point at the module the decorator was copied
    *from*.  Comparing the declared name against the declaring module is what
    catches it.
    """
    decorate = scenario(
        name="fv",
        label="FV",
        participants="Finder + Vendor",
        feature="Baseline two-actor CVD",
        in_pr_set=True,
    )

    def impostor() -> None:
        """Stand in for a copy-pasted main() in the wrong module."""

    impostor.__module__ = f"{SCENARIO_PACKAGE}.fvv_demo"

    with pytest.raises(DemoScenarioRegistryError, match="derives the module"):
        decorate(impostor)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("name", "FV"),
        ("name", "fv_demo"),
        ("name", ""),
        # `$` matches before a trailing newline, so an `re.match(r"...$")`
        # would accept this and the failure would surface later, in the
        # module-name comparison, pointing the author at the wrong thing.
        ("name", "xy\n"),
        ("label", "  "),
        ("participants", ""),
        ("feature", ""),
        # A single trailing newline is the likeliest spelling of the
        # split-the-row mistake, and `len(value.splitlines()) > 1` is 1 for it
        # — so a line-count guard passes and --check then blesses a table whose
        # last column has been dropped.
        ("label", "XY\n"),
        ("participants", "Finder + Vendor\n"),
        ("feature", "Something\n"),
        ("feature", " Something"),
        # Genuinely multi-line, the case the line-count guard does catch.
        ("feature", "Something\nelse"),
        # `markdownlint-cli2 --fix` rewrites each of these inside a table cell
        # (MD049 for the underscores, MD034 for the URL), which would leave it
        # and the demo-scenarios-sync hook undoing each other forever.
        ("feature", "Embargo extension per _RFC 9116_"),
        ("feature", "See https://example.org/spec"),
        ("participants", "Finder + <Vendor>"),
    ],
)
def test_scenario_spec_rejects_malformed_fields(
    field: str, value: str
) -> None:
    """A spec that would render a broken path or a broken cell is refused."""
    fields = {
        "name": "xy",
        "label": "XY",
        "participants": "Finder + Vendor",
        "feature": "Something",
        "in_pr_set": True,
    }
    fields[field] = value
    with pytest.raises(DemoScenarioRegistryError):
        ScenarioSpec(**fields)  # type: ignore[arg-type]


def test_scenario_spec_rejects_non_boolean_in_pr_set() -> None:
    """``in_pr_set`` must be a real bool, not merely truthy.

    The CI matrix filter is ``select(.full_suite_only == false)``, an exact
    comparison, so a truthy non-boolean would silently drop the scenario from
    the PR matrix rather than fail anywhere.
    """
    with pytest.raises(DemoScenarioRegistryError, match="non-boolean"):
        ScenarioSpec(
            name="xy",
            label="XY",
            participants="Finder + Vendor",
            feature="Something",
            in_pr_set=1,  # type: ignore[arg-type]
        )


def test_derived_paths_follow_the_documented_conventions() -> None:
    """Hyphens become underscores in module and harness paths, not in the page.

    Spelled out on a hyphenated name because that is where the two conventions
    differ, and a renderer or harness generator that applied one rule to all
    three would still pass a same-shaped check on an unhyphenated scenario.
    """
    spec = ScenarioSpec(
        name="fvcv-handoff",
        label="FVCV-handoff",
        participants="Finder + Vendor1 → Coordinator + Vendor2",
        feature="Case-ownership transfer to coordinator",
        in_pr_set=True,
    )
    assert spec.demo_path == "vultron/demo/scenario/fvcv_handoff_demo.py"
    assert (
        spec.harness_path
        == "test/ci/invariants/test_fvcv_handoff_invariants.py"
    )
    assert spec.narrative_path == "docs/topics/scenarios/fvcv-handoff.md"
    assert spec.full_suite_only is False
