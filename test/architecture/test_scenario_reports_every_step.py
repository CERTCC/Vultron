#!/usr/bin/env python

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

"""Architecture invariant: a scenario reports every step it declares (#4727).

Each scenario reports reaching each ``(branch point, choice)`` of its path to
its harness, and the harness marks the ledger tail there for the shared-prefix
check (DEMOCI-11-017).  The recorder refuses a run with a missing mark, but it
runs daily on ``main``, not on a pull request, and the committed marks stay
valid until the next recording.  So a dropped call would pass every PR check.
These tests read each scenario module's source instead, so a dropped or
misspelled report fails here.

The two declaration forms are checked differently, because the defect each can
have is different:

* a scenario still declaring ``@scenario(path=...)`` places one
  ``reach_step`` or ``step_reporter`` call per declared step by hand, and can
  drop one;
* a scenario written as composition declares its steps as the ``choose(...)``
  items of its story, which is also what the runner emits the marks from
  (DEMOCI-11-019), so a mark cannot go missing — what it can do is place a
  ``reach_step`` by hand beside the runner's, which would mark one step twice.
  That is what is forbidden here.
"""

import ast
from collections import Counter

import pytest

from test.architecture import _corpus
from vultron.demo.scenario.registry import ScenarioSpec, discover_scenarios

#: The modules holding the story fragments of a composed family.  Globbed
#: rather than listed, so a family composed later is covered the moment its
#: fragment module lands beside the others.
_FRAGMENT_MODULES = sorted(
    (_corpus.REPO_ROOT / "vultron" / "demo" / "helpers").glob(
        "coordinated_*.py"
    )
)


def _specs(composed: bool) -> list[ScenarioSpec]:
    """Registered scenarios using one declaration form."""
    return [spec for spec in discover_scenarios() if spec.composed is composed]


#: The calls that report a step: the harness method, the module-level function
#: and the hook factory, each taking the branch point and the choice.
_REPORTERS = frozenset({"reach_step", "step_reporter"})


def _reported_steps(module_name: str) -> Counter[tuple[str, str]]:
    """Every literal ``(branch point, choice)`` the module reports."""
    return _steps_in(
        _corpus.tree_of(
            _corpus.REPO_ROOT / (module_name.replace(".", "/") + ".py")
        )
    )


def _steps_in(tree: ast.AST) -> Counter[tuple[str, str]]:
    """Every literal ``(branch point, choice)`` *tree* reports."""
    steps: Counter[tuple[str, str]] = Counter()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        name = (
            func.attr
            if isinstance(func, ast.Attribute)
            else func.id
            if isinstance(func, ast.Name)
            else None
        )
        if name not in _REPORTERS or len(node.args) != 2:
            continue
        branch_point, choice = node.args
        if isinstance(branch_point, ast.Constant) and isinstance(
            choice, ast.Constant
        ):
            steps[(str(branch_point.value), str(choice.value))] += 1
    return steps


def test_both_declaration_forms_are_still_in_use() -> None:
    """Neither check below is a zero-target gate while the migration runs.

    When the last family is composed (#5537) the ``path=`` form goes away with
    it, and this assertion is what says so out loud rather than letting its
    check pass over nothing.
    """
    assert _specs(composed=True), "no scenario is written as composition"
    assert _specs(composed=False), (
        "every scenario is composed: drop the path= form and this test's "
        "interim half with it (#5537)"
    )


def _fragment_steps() -> Counter[tuple[str, str]]:
    """Every literal step a story-fragment module reports."""
    assert _FRAGMENT_MODULES, "no story-fragment module found"
    total: Counter[tuple[str, str]] = Counter()
    for path in _FRAGMENT_MODULES:
        total += _steps_in(_corpus.tree_of(path))
    return total


@pytest.mark.parametrize(
    "spec", _specs(composed=False), ids=lambda spec: spec.name
)
def test_each_declared_step_is_reported_once(spec: ScenarioSpec) -> None:
    reported = _reported_steps(spec.module_name)
    declared = Counter(spec.path)
    assert reported == declared, (
        f"{spec.demo_path} reports {dict(reported)}, but its path declares "
        f"{dict(declared)}. Call harness.reach_step(branch_point, choice, "
        "by=actor_id) once per declared step, where the scenario makes the "
        "decision "
        "(notes/demo-scenario-tree.md § Shared-prefix check)."
    )


@pytest.mark.parametrize(
    "spec", _specs(composed=True), ids=lambda spec: spec.name
)
def test_a_composed_scenario_places_no_reach_step_by_hand(
    spec: ScenarioSpec,
) -> None:
    """The runner is the only source of a composed scenario's marks.

    Scans the story-fragment modules as well as the scenario module, because
    composition empties the scenario module: a hand-placed ``reach_step`` in a
    fragment is where the double-mark defect would be introduced, and a scan
    of ``scenario/`` alone would pass over it.
    """
    reported = _reported_steps(spec.module_name) + _fragment_steps()
    assert reported == Counter(), (
        f"{spec.demo_path} or a story fragment places {dict(reported)} by "
        "hand, but a story's choose(...) items already declare its steps and "
        "run_story() marks each one as it passes it. Drop the call "
        "(DEMOCI-11-019, notes/demo-scenario-tree.md § Composition)."
    )
