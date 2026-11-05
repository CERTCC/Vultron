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
"""The ``test`` job's parts together collect every test exactly once.

``python-app.yml`` runs the suite as parallel matrix parts, so a round ends
with the slowest part rather than the sum (#5943). Splitting it that way adds
two failure modes a green run cannot show, and both are silent:

- a test directory no part selects never runs, and every part is green;
- a directory two parts select runs twice, paying for a part's worth of runner
  time twice over.

The workflow closes both by construction: each named part lists the paths it
claims, and one catch-all part selects ``test`` while ignoring exactly those
paths. This module checks that construction holds — the ignores match the
claims, no claim nests inside another, and the catch-all still selects the
whole tree, which is what makes a directory added tomorrow run without a
workflow edit (TB-11-002).

It asserts nothing about how many tests are collected. A pinned count is right
on the pull request that sets it and wrong on every other one in flight
([notes/testing-pitfalls.md](../../notes/testing-pitfalls.md) § "A Two-Sided
Count Pin Races Every Concurrent PR", #3984); the partition is a property of
the selections, so read it off them.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from test.ci._workflows import REPO_ROOT, WORKFLOWS_DIR, load_workflow

WORKFLOW = WORKFLOWS_DIR / "python-app.yml"

#: The job whose matrix fans the suite out. ``build`` and ``notify`` reach
#: every part through ``needs:`` on this one job id.
TEST_JOB = "test"

#: The jobs that must wait for every part (TB-11-003).
DOWNSTREAM_JOBS = ("build", "notify")

IGNORE_PREFIX = "--ignore="

#: What the catch-all part selects: the whole test tree, minus its ignores.
WHOLE_TREE = "test"


@dataclass(frozen=True)
class Part:
    """One matrix leg: its name and the two halves of its pytest selection."""

    name: str
    claims: tuple[str, ...]
    ignores: tuple[str, ...]

    @property
    def is_catch_all(self) -> bool:
        return bool(self.ignores)


def _job(job_id: str) -> dict[str, Any]:
    jobs = load_workflow(WORKFLOW).get("jobs", {})
    assert isinstance(jobs, dict), f"{WORKFLOW.name} has no `jobs:` mapping"
    job = jobs.get(job_id)
    assert isinstance(job, dict), f"{WORKFLOW.name} has no `{job_id}` job"
    return job


def _matrix_include() -> list[dict[str, Any]]:
    strategy = _job(TEST_JOB).get("strategy", {})
    assert isinstance(strategy, dict), (
        f"the `{TEST_JOB}` job has no `strategy:`, so it runs as one job"
    )
    matrix = strategy.get("matrix", {})
    assert isinstance(matrix, dict), f"the `{TEST_JOB}` job has no `matrix:`"
    include = matrix.get("include")
    # An empty matrix expands to no jobs at all, and a workflow that ran no
    # tests reports green (DEMOCI-06 § vacuous success).
    assert isinstance(include, list) and include, (
        f"the `{TEST_JOB}` matrix has no non-empty `include:`, so it would "
        "expand to no jobs and the workflow would report green having run "
        "no tests"
    )
    return [entry for entry in include if isinstance(entry, dict)]


def _part(entry: dict[str, Any]) -> Part:
    name, select = entry.get("part"), entry.get("select")
    assert isinstance(name, str) and name, (
        f"a matrix entry has no `part`: {entry}"
    )
    assert isinstance(select, str) and select.strip(), (
        f"matrix part {name!r} has no `select` string of pytest arguments"
    )
    tokens = select.split()
    return Part(
        name=name,
        claims=tuple(t for t in tokens if not t.startswith(IGNORE_PREFIX)),
        ignores=tuple(
            t.removeprefix(IGNORE_PREFIX)
            for t in tokens
            if t.startswith(IGNORE_PREFIX)
        ),
    )


def _parts() -> tuple[Part, ...]:
    return tuple(_part(entry) for entry in _matrix_include())


def _catch_all() -> Part:
    found = [part for part in _parts() if part.is_catch_all]
    assert len(found) == 1, (
        "exactly one part selects the whole tree minus the others' claims; "
        f"{[p.name for p in found]} carry `{IGNORE_PREFIX}` arguments"
    )
    return found[0]


def _named_claims() -> dict[str, tuple[str, ...]]:
    return {p.name: p.claims for p in _parts() if not p.is_catch_all}


def unpartitioned(
    claims: set[str], ignores: set[str]
) -> tuple[set[str], set[str]]:
    """The paths run twice, and the paths never run, for one part set.

    A path a named part claims that the catch-all does not ignore is collected
    by both, so it runs twice. A path the catch-all ignores that no named part
    claims is collected by neither, so it never runs.
    """
    return claims - ignores, ignores - claims


def nested_claims(claims: dict[str, tuple[str, ...]]) -> set[str]:
    """Each claim that lies inside another part's claim, so it runs twice."""
    owned = sorted(
        (path, name) for name, paths in claims.items() for path in paths
    )
    return {
        f"{inner} ({inner_part}) inside {outer} ({outer_part})"
        for outer, outer_part in owned
        for inner, inner_part in owned
        if inner != outer and inner.startswith(f"{outer}/")
    }


def _step_run(job_id: str, needle: str) -> str:
    runs = [
        str(step.get("run", ""))
        for step in _job(job_id).get("steps", [])
        if isinstance(step, dict) and needle in str(step.get("run", ""))
    ]
    assert len(runs) == 1, (
        f"the `{job_id}` job runs {len(runs)} steps containing {needle!r}; "
        "one step runs the part"
    )
    return runs[0]


@pytest.mark.spec("TB-11-002")
def test_the_suite_fans_out_into_more_than_one_part() -> None:
    """A single-leg matrix is the old one-runner job under a new name."""
    names = [part.name for part in _parts()]
    assert len(names) > 1, f"the `{TEST_JOB}` job runs as one part: {names}"
    assert len(set(names)) == len(names), f"two parts share a name: {names}"


@pytest.mark.spec("TB-11-002")
def test_the_catch_all_part_selects_the_whole_test_tree() -> None:
    """Whatever no named part claims — a new directory included — runs here."""
    catch_all = _catch_all()
    assert catch_all.claims == (WHOLE_TREE,), (
        f"part {catch_all.name!r} selects {catch_all.claims}, not "
        f"({WHOLE_TREE!r},); a catch-all that names directories stops "
        "catching the next one added"
    )


@pytest.mark.spec("TB-11-002")
def test_the_catch_all_ignores_exactly_what_the_other_parts_claim() -> None:
    """The partition: nothing is run twice, and nothing is left unrun."""
    claimed = {path for claims in _named_claims().values() for path in claims}
    twice, never = unpartitioned(claimed, set(_catch_all().ignores))
    assert not twice and not never, (
        "the catch-all part's ignores and the named parts' claims disagree. "
        f"Claimed but not ignored (would run twice): {sorted(twice)}. "
        f"Ignored but not claimed (would never run): {sorted(never)}."
    )


def test_a_claim_without_its_ignore_reads_as_running_twice() -> None:
    """The comparison bites in the direction that costs runner time."""
    twice, never = unpartitioned({"test/core", "test/wire"}, {"test/core"})
    assert (twice, never) == ({"test/wire"}, set())


def test_an_ignore_without_its_claim_reads_as_never_running() -> None:
    """And in the direction that silently drops tests from CI."""
    twice, never = unpartitioned({"test/core"}, {"test/core", "test/wire"})
    assert (twice, never) == (set(), {"test/wire"})


@pytest.mark.spec("TB-11-002")
def test_every_claimed_path_is_a_real_path_under_test() -> None:
    """A claim that no longer exists silently shrinks what the parts run."""
    bad = {
        f"{name}:{path}"
        for name, claims in _named_claims().items()
        for path in claims
        if not (REPO_ROOT / path).exists()
        or not path.startswith(f"{WHOLE_TREE}/")
    }
    assert not bad, (
        f"these claims name no existing path under `{WHOLE_TREE}/`: "
        f"{sorted(bad)}"
    )


@pytest.mark.spec("TB-11-002")
def test_no_claim_is_nested_inside_another() -> None:
    """``test/core`` beside ``test/core/models`` runs the inner one twice."""
    nested = nested_claims(_named_claims())
    assert not nested, f"overlapping claims run tests twice: {sorted(nested)}"


def test_a_claim_inside_another_part_s_claim_is_reported() -> None:
    """The nesting check bites: an ignore pair cannot show this overlap."""
    nested = nested_claims(
        {"core": ("test/core",), "models": ("test/core/models",)}
    )
    assert nested == {"test/core/models (models) inside test/core (core)"}


@pytest.mark.spec("TB-11-002")
def test_each_part_runs_its_selection_with_every_marker_enabled() -> None:
    """``-m ""``: the parts together are the full suite, integration included."""
    run = _step_run(TEST_JOB, "pytest")
    assert '-m ""' in run, (
        f"the part's pytest command deselects markers, so the parts together "
        f"are less than the full suite: {run!r}"
    )
    assert "${{ matrix.select }}" in run, (
        f"the part's pytest command ignores `matrix.select`, so every part "
        f"runs the same tests: {run!r}"
    )


@pytest.mark.spec("TB-11-003")
@pytest.mark.parametrize("job_id", DOWNSTREAM_JOBS)
def test_the_downstream_jobs_wait_for_every_part(job_id: str) -> None:
    """One red part fails the run, and notifies on a push to main."""
    needs = _job(job_id).get("needs", [])
    assert TEST_JOB in needs, (
        f"the `{job_id}` job does not need `{TEST_JOB}`, so a red part "
        f"neither fails the run nor reaches its `needs.*.result` aggregate: "
        f"{needs}"
    )


@pytest.mark.spec("TB-11-003")
def test_a_red_part_does_not_cancel_its_siblings() -> None:
    """``fail-fast`` would report one failing part and cancel the rest."""
    strategy = _job(TEST_JOB).get("strategy", {})
    assert strategy.get("fail-fast") is False, (
        "the `test` matrix needs `fail-fast: false`; otherwise the first red "
        "part cancels the others and one round reports one failure at a time"
    )
