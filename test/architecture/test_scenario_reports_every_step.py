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

Each scenario reports reaching each ``(branch point, choice)`` of its
``@scenario(path=...)`` to its harness, with ``reach_step`` or a
``step_reporter`` hook, and the harness marks the ledger tail there for the
shared-prefix check (DEMOCI-11-017).  The recorder refuses a run with a
missing mark, but it runs daily on ``main``, not on a pull request, and the
committed marks stay valid until the next recording.  So a dropped call
would pass every PR check.  This reads each scenario module's source and
requires one report per declared step, so a dropped or misspelled call fails
here instead.
"""

import ast
import importlib
from collections import Counter

import pytest

from vultron.demo.scenario.registry import ScenarioSpec, discover_scenarios

#: The calls that report a step: the harness method, the module-level function
#: and the hook factory, each taking the branch point and the choice.
_REPORTERS = frozenset({"reach_step", "step_reporter"})


def _reported_steps(module_name: str) -> Counter[tuple[str, str]]:
    """Every literal ``(branch point, choice)`` the module reports."""
    module = importlib.import_module(module_name)
    source = module.__file__
    assert source is not None
    with open(source, encoding="utf-8") as fh:
        tree = ast.parse(fh.read())
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


@pytest.mark.parametrize(
    "spec", discover_scenarios(), ids=lambda spec: spec.name
)
def test_each_declared_step_is_reported_once(spec: ScenarioSpec) -> None:
    reported = _reported_steps(spec.module_name)
    declared = Counter(spec.path)
    assert reported == declared, (
        f"{spec.demo_path} reports {dict(reported)}, but its path declares "
        f"{dict(declared)}. Call harness.reach_step(branch_point, choice) "
        "once per declared step, where the scenario makes the decision "
        "(notes/demo-scenario-tree.md § Shared-prefix check)."
    )
