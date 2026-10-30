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
"""Ratchets over the branch-point table and the scenario tree (DEMOCI-11-013/014).

The branch-point table defines every decision of the demo once; each
registered scenario declares its path through it on ``@scenario``; discovery
merges the paths into one tree. These tests prove the table is well formed,
that every choice is a trigger the routers expose, that a malformed path or a
set of paths that is not one tree fails discovery (each on a mutated fixture
registry), and that the committed registry is one tree in which every
scenario is exactly one ending.

Kept in ``test/demo_unit/`` for the reason ``test_scenario_registry.py``
gives: ``test/demo/`` is auto-marked ``integration`` and deselected by default.
"""

from __future__ import annotations

import inspect
from dataclasses import replace
from typing import Any

import pytest

from test.adapters.driving.fastapi.test_openapi_trigger_snapshot import (
    DEMO_PATH_FRAGMENT,
    TRIGGER_PATH_FRAGMENT,
    build_prototype_app,
)
from vultron.demo.scenario import registry
from vultron.demo.scenario.branch_points import (
    BRANCH_POINTS,
    BranchPoint,
    Choice,
    build_branch_point_table,
    validate_path,
)
from vultron.demo.scenario.registry import (
    ScenarioSpec,
    discover_scenarios,
    scenario,
    scenario_tree,
)
from vultron.demo.scenario.tree import build_scenario_tree
from vultron.enums.roles import CVDRole
from vultron.errors import DemoScenarioRegistryError

_A = Choice(id="a", label="Do A", trigger="notify-fix-ready")
_B = Choice(id="b", label="Do B", trigger="notify-published")


def _specs_by_name() -> dict[str, ScenarioSpec]:
    return {spec.name: spec for spec in discover_scenarios()}


# ---------------------------------------------------------------------------
# The branch-point table (DEMOCI-11-013)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def mounted_trigger_verbs() -> set[str]:
    """Verbs of every POST under ``/trigger/`` or ``/demo/`` on the app.

    Built from the prototype app, which mounts the demo router, so demo-only
    triggers are visible (TRIG-09-001).
    """
    paths: dict[str, Any] = build_prototype_app().openapi()["paths"]
    return {
        path.rsplit("/", 1)[-1]
        for path, item in paths.items()
        if (TRIGGER_PATH_FRAGMENT in path or DEMO_PATH_FRAGMENT in path)
        and "post" in item
    }


@pytest.mark.spec("DEMOCI-11-013")
@pytest.mark.parametrize(
    ("branch_point_id", "choice_id"),
    [
        (bp.id, choice.id)
        for bp in BRANCH_POINTS.values()
        for choice in bp.choices
    ],
)
def test_every_choice_is_a_mounted_trigger(
    branch_point_id: str, choice_id: str, mounted_trigger_verbs: set[str]
) -> None:
    """Each choice names a trigger the trigger or demo routers expose."""
    trigger = BRANCH_POINTS[branch_point_id].choice(choice_id).trigger
    assert trigger in mounted_trigger_verbs, (
        f"{branch_point_id}:{choice_id} names trigger {trigger!r}, which no "
        "/actors/{id}/trigger/ or /actors/{id}/demo/ route exposes"
    )


def test_mounted_trigger_verbs_are_read(
    mounted_trigger_verbs: set[str],
) -> None:
    """The route read is not vacuous: both routers contribute verbs."""
    assert {"submit-report", "notify-fix-ready"} <= mounted_trigger_verbs


@pytest.mark.spec("DEMOCI-11-013")
def test_committed_table_is_well_formed() -> None:
    """Every entry names a role, a prompt and at least two choices."""
    assert BRANCH_POINTS, "the branch-point table is empty"
    for bp_id, bp in BRANCH_POINTS.items():
        assert bp.id == bp_id
        assert isinstance(bp.role, CVDRole)
        assert bp.prompt.strip()
        assert len(bp.choices) >= 2
        assert len({c.id for c in bp.choices}) == len(bp.choices)


@pytest.mark.spec("DEMOCI-11-013")
def test_two_branch_points_may_not_share_an_id() -> None:
    first = BranchPoint(
        id="x", role=CVDRole.VENDOR, prompt="Pick.", choices=(_A, _B)
    )
    second = replace(first, prompt="Pick again.")
    with pytest.raises(DemoScenarioRegistryError, match="defined twice"):
        build_branch_point_table((first, second))


@pytest.mark.spec("DEMOCI-11-013")
@pytest.mark.parametrize(
    ("kwargs", "match"),
    [
        ({"choices": (_A,)}, "fewer than two choices"),
        ({"choices": (_A, _A)}, "twice"),
        ({"choices": (_A, "b")}, "not a Choice"),
        ({"prompt": ""}, "empty prompt"),
        ({"prompt": "Pick.\n"}, "line break"),
        ({"role": "vendor"}, "not a CVDRole"),
        ({"id": "Not An Id"}, "not a valid identifier"),
    ],
)
def test_malformed_branch_point_is_refused(
    kwargs: dict[str, Any], match: str
) -> None:
    fields: dict[str, Any] = {
        "id": "x",
        "role": CVDRole.VENDOR,
        "prompt": "Pick.",
        "choices": (_A, _B),
    }
    fields.update(kwargs)
    with pytest.raises(DemoScenarioRegistryError, match=match):
        BranchPoint(**fields)


@pytest.mark.spec("DEMOCI-11-013")
@pytest.mark.parametrize(
    ("kwargs", "match"),
    [
        ({"label": ""}, "empty label"),
        ({"trigger": ""}, "not a trigger verb"),
        ({"trigger": "trigger/submit-report"}, "not a trigger verb"),
        ({"id": "A"}, "not a valid identifier"),
    ],
)
def test_malformed_choice_is_refused(
    kwargs: dict[str, Any], match: str
) -> None:
    fields: dict[str, Any] = {"id": "a", "label": "Do A", "trigger": "x"}
    fields.update(kwargs)
    with pytest.raises(DemoScenarioRegistryError, match=match):
        Choice(**fields)


@pytest.mark.spec("DEMOCI-11-013")
def test_scenario_decorator_takes_no_prompt_or_choice_label() -> None:
    """Prompts and choice labels live only in the table, never on ``@scenario``.

    ``label`` is the scenario's own display casing, not a choice label.
    """
    assert set(inspect.signature(scenario).parameters) == {
        "name",
        "label",
        "participants",
        "feature",
        "in_pr_set",
        "path",
    }


def test_every_choice_is_taken_by_a_registered_scenario() -> None:
    """A choice no scenario takes would offer the presenter a dead end."""
    taken = {step for spec in discover_scenarios() for step in spec.path}
    offered = {
        (bp.id, choice.id)
        for bp in BRANCH_POINTS.values()
        for choice in bp.choices
    }
    assert offered - taken == set()


# ---------------------------------------------------------------------------
# Path declarations (DEMOCI-11-014)
# ---------------------------------------------------------------------------


@pytest.mark.spec("DEMOCI-11-014", "DEMOCI-11-023")
@pytest.mark.parametrize(
    ("path", "match"),
    [
        ((("no-such-branch-point", "vendor"),), "unknown branch point"),
        ((("reporter-whom-to-tell", "no-such-choice"),), "no choice"),
        ((), "path is empty"),
        ((("reporter-whom-to-tell",),), "not a .branch point, choice. pair"),
        ("reporter-whom-to-tell", "not a sequence"),
    ],
)
def test_a_malformed_path_is_refused(path: Any, match: str) -> None:
    with pytest.raises(DemoScenarioRegistryError, match=match):
        validate_path(path)


@pytest.mark.spec("DEMOCI-11-023")
def test_spec_refuses_an_unknown_branch_point() -> None:
    spec = _specs_by_name()["rv"]
    with pytest.raises(DemoScenarioRegistryError, match="invalid path"):
        replace(spec, path=(("no-such-branch-point", "vendor"),))


@pytest.mark.spec("DEMOCI-11-014")
def test_spec_refuses_a_mutable_path() -> None:
    spec = _specs_by_name()["rv"]
    with pytest.raises(DemoScenarioRegistryError, match="not a tuple"):
        replace(spec, path=list(spec.path))  # type: ignore[arg-type]


@pytest.mark.spec("DEMOCI-11-022")
def test_a_branch_point_may_recur_on_one_path() -> None:
    """A node is keyed by its prefix, so a repeated decision is two nodes."""
    rv = _specs_by_name()["rv"]
    recurring = replace(
        rv,
        name="xx",
        path=(
            ("reporter-whom-to-tell", "coordinator"),
            ("reporter-whom-to-tell", "vendor"),
        ),
    )
    root = build_scenario_tree([recurring])
    inner = root.children["coordinator"]
    assert inner.branch_point == "reporter-whom-to-tell"
    assert inner.children["vendor"].scenario == "xx"


# ---------------------------------------------------------------------------
# Tree well-formedness on mutated fixture registries (DEMOCI-11-023)
# ---------------------------------------------------------------------------


@pytest.mark.spec("DEMOCI-11-023")
def test_two_scenarios_with_the_same_path_fail_discovery(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    specs = _specs_by_name()
    monkeypatch.setitem(
        registry._REGISTRY,
        "rvv",
        replace(specs["rvv"], path=specs["rv"].path),
    )
    with pytest.raises(DemoScenarioRegistryError, match="same path"):
        discover_scenarios()


@pytest.mark.spec("DEMOCI-11-023")
@pytest.mark.parametrize("shorter", ["rvcv-extension", "rvcv-handoff"])
def test_a_path_that_is_a_strict_prefix_of_another_fails_discovery(
    monkeypatch: pytest.MonkeyPatch, shorter: str
) -> None:
    """Either registration order is caught: the prefix seen first or last.

    ``rvcv-extension`` sorts before ``rvcv-handoff``, so truncating it puts
    the ending first and truncating ``rvcv-handoff`` puts it second.
    """
    specs = _specs_by_name()
    monkeypatch.setitem(
        registry._REGISTRY,
        shorter,
        replace(specs[shorter], path=specs[shorter].path[:-1]),
    )
    with pytest.raises(DemoScenarioRegistryError, match="strict prefix"):
        discover_scenarios()


@pytest.mark.spec("DEMOCI-11-023")
def test_two_decisions_at_one_node_fail_discovery(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Paths sharing a prefix must decide the same branch point next."""
    specs = _specs_by_name()
    monkeypatch.setitem(
        registry._REGISTRY,
        "rvv",
        replace(
            specs["rvv"],
            path=(
                ("reporter-whom-to-tell", "vendor"),
                ("vendor-join", "accept"),
            ),
        ),
    )
    with pytest.raises(DemoScenarioRegistryError, match="one node is one"):
        discover_scenarios()


@pytest.mark.spec("DEMOCI-11-014", "DEMOCI-11-023")
def test_committed_registry_is_one_tree_with_every_scenario_one_ending() -> (
    None
):
    specs = discover_scenarios()
    root = scenario_tree()

    endings = [node.scenario for node in root.walk() if node.scenario]
    assert sorted(endings) == sorted(spec.name for spec in specs)
    for node in root.walk():
        # Every node is exactly one of an ending (no children) or an
        # interior node deciding one branch point.
        if node.scenario is not None:
            assert not node.children and node.branch_point is None
        else:
            assert node.children and node.branch_point in BRANCH_POINTS
    by_name = {spec.name: spec for spec in specs}
    for name, node in root.endings().items():
        assert node.prefix == by_name[name].path
