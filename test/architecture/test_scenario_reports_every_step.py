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

Every scenario is written as composition, so each declares its steps as the
``choose(...)`` items of its story, which is also what the runner emits the
marks from (DEMOCI-11-019): a mark cannot go missing.  What a scenario can
still do is place a ``reach_step`` by hand beside the runner's, which would
mark one step twice, and that is what is forbidden here.
"""

import ast
from collections import Counter

import pytest

from test.architecture import _corpus
from vultron.demo.scenario.registry import ScenarioSpec, discover_scenarios

#: The module that is allowed to report a step: the story runner, which makes
#: the call as it passes each ``choose(...)`` item (DEMOCI-11-019).
_RUNNER_MODULE = "story/runner.py"

#: Every other helper module.  DEMOCI-11-019 forbids a mark placed by any
#: helper, not only by one holding story fragments, so the scan takes the whole
#: package rather than a suffix glob: a `choose`'s trigger is called from
#: ``workflow/`` and the invite halves from ``invite_chain/``, and a mark
#: slipped into either would have been invisible to a ``*_story.py`` glob.
#: Recursive, because a split module is a subpackage whose submodules hold the
#: fragments (``coordinated_story/``, ``story/``, ``invite_chain/``, …;
#: #5592, CS-18-005).
_HELPERS_DIR = _corpus.REPO_ROOT / "vultron" / "demo" / "helpers"
_HELPER_MODULES = sorted(
    path
    for path in _corpus.paths_under(_HELPERS_DIR)
    if path.relative_to(_HELPERS_DIR).as_posix() != _RUNNER_MODULE
)


#: The call that reports a step: the harness method, which
#: :func:`~vultron.demo.helpers.story.run_story` is the only legitimate caller
#: of.  The module-level function and the hook factory that let a helper place
#: one by hand are gone, so this is the whole surface a scenario could reach.
_REPORTERS = frozenset({"reach_step"})


def _reported_steps(module_name: str) -> Counter[tuple[str, str]]:
    """Every literal ``(branch point, choice)`` the module reports."""
    return _steps_in(
        _corpus.tree_of(
            _corpus.REPO_ROOT / (module_name.replace(".", "/") + ".py")
        )
    )


def _reporter_calls(tree: ast.AST) -> int:
    """How many times *tree* calls a step reporter, readable pair or not.

    :func:`_steps_in` deliberately reads only a literal pair, because its job
    is to name *which* steps a module reports.  The rule is stronger than
    that: a helper may place no mark at all, and a call whose pair is computed
    or splatted is as much a hand-placed mark as a literal one
    (DEMOCI-11-019).  The runner's own calls are of exactly that shape — it
    passes ``item.branch_point`` and ``item.choice`` — so a count is the only
    check that can see them.
    """
    return sum(
        1
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and _called_name(node) in _REPORTERS
    )


def _called_name(node: ast.Call) -> str | None:
    """The bare name *node* calls, for an attribute or a plain name."""
    func = node.func
    if isinstance(func, ast.Attribute):
        return func.attr
    if isinstance(func, ast.Name):
        return func.id
    return None


def _steps_in(tree: ast.AST) -> Counter[tuple[str, str]]:
    """Every literal ``(branch point, choice)`` *tree* reports.

    Both argument forms are read.  A reporter takes the pair positionally at
    every call site today, but nothing stops a hand-placed
    ``reach_step(branch_point="x", choice="y", by=...)``, and a scan that
    required two positional arguments would not see it — leaving the
    "a scenario places no reach_step by hand" ratchet below passing
    over the one call it exists to forbid (#5533).
    """
    steps: Counter[tuple[str, str]] = Counter()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if _called_name(node) not in _REPORTERS:
            continue
        step = _step_args(node)
        if step is None:
            continue
        branch_point, choice = step
        if isinstance(branch_point, ast.Constant) and isinstance(
            choice, ast.Constant
        ):
            steps[(str(branch_point.value), str(choice.value))] += 1
    return steps


def _step_args(node: ast.Call) -> tuple[ast.expr, ast.expr] | None:
    """The branch point and choice *node* passes, however it passes them.

    Returns:
        The two argument expressions in declaration order, or ``None`` when
        the call does not supply exactly those two — a ``*args`` splat, or a
        reporter called with something other than the pair.
    """
    by_keyword = {kw.arg: kw.value for kw in node.keywords if kw.arg}
    supplied = list(node.args) + [
        by_keyword[name]
        for name in ("branch_point", "choice")
        if name in by_keyword
    ]
    if len(supplied) != 2:
        return None
    return supplied[0], supplied[1]


_STEP = Counter({("vendor-join", "accept"): 1})


@pytest.mark.parametrize(
    "source",
    [
        'h.reach_step("vendor-join", "accept", by=v)',
        'h.reach_step(branch_point="vendor-join", choice="accept", by=v)',
        'h.reach_step(choice="accept", branch_point="vendor-join", by=v)',
        'h.reach_step("vendor-join", choice="accept", by=v)',
        'reach_step(branch_point="vendor-join", choice="accept", by=v)',
    ],
    ids=["positional", "keyword", "keyword-reversed", "mixed", "bare-name"],
)
def test_a_hand_placed_report_is_seen_in_every_argument_form(
    source: str,
) -> None:
    """The scan reads the pair however the call passes it.

    The two checks below are only as strong as what the scan can see, so a
    form it misses is a hole in the ratchet, not a style question.
    """
    assert _steps_in(_corpus.parse_inline(source)) == _STEP


@pytest.mark.parametrize(
    "source",
    ["h.reach_step(*step, by=v)", 'h.reach_step("vendor-join", by=v)'],
    ids=["splat", "one-argument"],
)
def test_a_call_that_names_no_literal_pair_counts_as_no_step(
    source: str,
) -> None:
    """A call the scan cannot read a pair from reports nothing, not a guess."""
    assert _steps_in(_corpus.parse_inline(source)) == Counter()


def test_at_least_one_scenario_is_registered() -> None:
    """The check below is not a zero-target gate.

    ``discover_scenarios()`` is what parametrizes it, and an empty registry
    collects no cases: pytest then reports a skip, so this module's only
    ratchet would vanish without a red test anywhere
    (``notes/documentation-strategy.md`` § "A gate that resolves zero targets
    must fail").
    """
    assert discover_scenarios(), "no scenario is registered"


def _helper_steps() -> Counter[tuple[str, str]]:
    """Every literal step a helper module other than the runner reports."""
    assert _HELPER_MODULES, "no demo helper module found"
    total: Counter[tuple[str, str]] = Counter()
    for path in _HELPER_MODULES:
        total += _steps_in(_corpus.tree_of(path))
    return total


def _helper_reporter_calls() -> dict[str, int]:
    """Reporter calls per helper module other than the runner, where nonzero."""
    assert _HELPER_MODULES, "no demo helper module found"
    return {
        path.relative_to(_HELPERS_DIR).as_posix(): count
        for path in _HELPER_MODULES
        if (count := _reporter_calls(_corpus.tree_of(path)))
    }


def test_the_runner_is_the_one_module_held_out_of_the_scan() -> None:
    """The exclusion is the runner, and the runner does report steps.

    Both halves matter.  Holding out a module that reports nothing would mean
    the exclusion is aimed at the wrong file and the runner's own calls are
    being counted as hand-placed; holding out more than one would open a place
    to put a second mark (DEMOCI-11-019).

    Counted with :func:`_reporter_calls` rather than :func:`_steps_in`: the
    runner passes ``item.branch_point`` and ``item.choice``, so it names no
    literal pair and the literal scan reads nothing from it.
    """
    runner = _HELPERS_DIR / _RUNNER_MODULE
    assert runner.is_file(), runner
    assert _reporter_calls(_corpus.tree_of(runner)), (
        f"{_RUNNER_MODULE} is held out of the scan as the one module allowed "
        "to report a step, but it calls no reporter; run_story must be what "
        "marks each choose(...) item it passes."
    )
    assert runner not in _HELPER_MODULES
    names = {
        path.relative_to(_HELPERS_DIR).as_posix() for path in _HELPER_MODULES
    }
    assert _RUNNER_MODULE not in names
    assert (
        "invite_chain/chain.py" in names and "workflow/report.py" in names
    ), sorted(names)
    # A subpackage's submodules are scanned too: a flat glob would pass over
    # every fragment a split moved, and the checks above would still pass.
    assert any(path.parent != _HELPERS_DIR for path in _HELPER_MODULES), (
        "no helper subpackage submodule is scanned"
    )


@pytest.mark.parametrize(
    "source",
    ["h.reach_step(*step, by=v)", "reach_step(bp, choice, by=v)"],
    ids=["splat", "computed"],
)
def test_a_reporter_call_with_no_literal_pair_is_still_counted(
    source: str,
) -> None:
    """The count sees a call the literal scan cannot read.

    :func:`_steps_in` returns nothing for these, by design, so a ratchet built
    on it alone would pass over a hand-placed mark whose arguments are
    computed — which is how the runner's own calls are written.
    """
    tree = _corpus.parse_inline(source)
    assert _steps_in(tree) == Counter()
    assert _reporter_calls(tree) == 1


@pytest.mark.spec("DEMOCI-11-019")
@pytest.mark.parametrize(
    "spec", discover_scenarios(), ids=lambda spec: spec.name
)
def test_a_scenario_places_no_reach_step_by_hand(
    spec: ScenarioSpec,
) -> None:
    """The runner is the only source of a scenario's marks.

    Scans every helper module as well as the scenario module, because
    composition empties the scenario module: a hand-placed ``reach_step`` in a
    fragment or in a helper a fragment calls is where the double-mark defect
    would be introduced, and a scan of ``scenario/`` alone would pass over it.
    """
    reported = _reported_steps(spec.module_name) + _helper_steps()
    assert reported == Counter(), (
        f"{spec.demo_path} or a demo helper places {dict(reported)} by hand, "
        "but a story's choose(...) items already declare its steps and "
        "run_story() marks each one as it passes it. Drop the call "
        "(DEMOCI-11-019, notes/demo-scenario-tree.md § Composition)."
    )
    # Asserted as a count too, so a call whose pair is computed or splatted —
    # which the literal scan reads as no step at all — is caught as well.
    scenario_calls = _reporter_calls(
        _corpus.tree_of(
            _corpus.REPO_ROOT / (spec.module_name.replace(".", "/") + ".py")
        )
    )
    offenders = _helper_reporter_calls()
    assert scenario_calls == 0 and not offenders, (
        f"{spec.demo_path} makes {scenario_calls} reporter call(s) and the "
        f"helpers make {offenders}; run_story is the only caller of "
        "ScenarioHarness.reach_step (DEMOCI-11-019)."
    )
