"""CI verification test — the built-site gates run wherever the site builds.

Implements DOCBW-03-005, DOCBW-03-006, DOCBW-03-007, DOCBW-03-008 and
DOCBW-03-012 from ``specs/docs-build-workflow.yaml``. A
workflow that builds ``site/`` MUST run ``docs-withheld`` (the publication
axis), ``docs-links`` (the reference axis), ``docs-legacy-urls`` (the continuity
axis) and ``docs-legacy-urls --require-recorded`` (every built page recorded)
against it, unconditionally, and in ``deploy_site.yml`` each MUST sit between
the build and the Pages upload.

Ordering is the whole point, and it is why this is a test rather than a review
habit. Both checks read the built tree, so a step placed before the build fails
on an absent ``site/``; a step placed after the upload cannot stop the bad build
from reaching Pages. The withheld gate first shipped in the pull-request
workflow only, which left the publishing path — the one act #3549 exists to
prevent — ungated.

The workflows run the checks through the local composite action
``.github/actions/check-site-publication`` (#3556), so the test expands a
``uses: ./…`` step into the action's own steps before looking for a command. A
step found inside an action inherits its caller's ``if:`` and
``continue-on-error``: a conditional ``uses:`` step skips every check it runs.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from test.ci._workflows import (
    MKDOCS_BUILD,
    RUN_EVEN_AFTER_FAILURE,
    WORKFLOWS_DIR,
    expanded_steps,
    live_text,
    load_workflow,
    local_action_steps,
    neutering,
    site_building_workflows,
)

# Each built-site gate's command, and the requirement it implements. Two share
# a tool, so a step runs a gate only when a live line of its ``run:`` is the
# whole command (:func:`_runs_gate`): matching a substring would let the
# ``--require-recorded`` step stand in for a missing continuity step.
GATES = {
    "docs-withheld": "DOCBW-03-005",
    "docs-links": "DOCBW-03-007",
    "docs-legacy-urls": "DOCBW-03-008",
    "docs-legacy-urls --require-recorded": "DOCBW-03-012",
}
GATE_COMMANDS = tuple(GATES)
UPLOAD_PAGES_ACTION = "actions/upload-pages-artifact"
PUBLICATION_ACTION = "./.github/actions/check-site-publication"


@dataclass(frozen=True)
class Step:
    """A step in run order, with the workflow step that caused it to run.

    ``caller`` is the step itself for an ordinary workflow step, and the
    ``uses: ./…`` step for a step expanded from a local composite action.
    """

    # Parsed workflow YAML is untyped by nature; ``Any`` here is the YAML boundary.
    body: dict[str, Any]
    caller: dict[str, Any]


def _steps(wf_data: dict[str, Any]) -> list[Step]:
    """Return every step across every job, in run order, actions expanded."""
    flat: list[Step] = []
    for job in wf_data.get("jobs", {}).values():
        if not isinstance(job, dict):
            continue
        for step in job.get("steps", []):
            if not isinstance(step, dict):
                continue
            flat.extend(Step(s, step) for s in expanded_steps([step]))
    return flat


def _neutering(step: Step) -> list[str]:
    """Return every way *step*, or the step that called it, cannot fail the run."""
    return [p for part in (step.body, step.caller) for p in neutering(part)]


def _index_of(steps: list[Step], needle: str, key: str) -> int | None:
    """Return the index of the first step whose ``key`` field contains ``needle``."""
    for i, step in enumerate(steps):
        if needle in str(step.body.get(key, "")):
            return i
    return None


# A line that runs a gate: optional environment assignments, then the command.
# Anything else on the line (``echo``, ``true ||``) means the gate may not run.
_GATE_LINE = re.compile(
    r"(?:[A-Za-z_][A-Za-z0-9_]*=\S*\s+)*uv run (?P<command>.+)"
)


def _runs_gate(step: Step, command: str) -> bool:
    """Return whether a live line of *step*'s ``run:`` is exactly *command*.

    Shell comments are dropped first, so a commented-out gate runs nothing.
    """
    for line in live_text(step.body).splitlines():
        match = _GATE_LINE.fullmatch(line.strip())
        if match and match["command"].strip() == command:
            return True
    return False


def _gate_index(steps: list[Step], command: str) -> int | None:
    """Return the index of the first step that runs gate *command*."""
    for i, step in enumerate(steps):
        if _runs_gate(step, command):
            return i
    return None


def test_gate_lookup_tells_the_two_legacy_url_gates_apart():
    continuity = {"run": "PYTHONPATH='' uv run docs-legacy-urls"}
    recorded = {
        "run": "PYTHONPATH='' uv run docs-legacy-urls --require-recorded"
    }
    steps = [Step(recorded, recorded)]
    assert _gate_index(steps, "docs-legacy-urls") is None
    assert _gate_index(steps, "docs-legacy-urls --require-recorded") == 0
    steps.append(Step(continuity, continuity))
    assert _gate_index(steps, "docs-legacy-urls") == 1


@pytest.mark.parametrize(
    "run",
    [
        "# PYTHONPATH='' uv run docs-links",
        "echo PYTHONPATH='' uv run docs-links",
        "true || uv run docs-links",
        "uv run docs-links-other",
    ],
    ids=["commented-out", "echoed", "short-circuited", "other-command"],
)
def test_gate_lookup_rejects_a_line_that_does_not_run_the_gate(run: str):
    step = {"run": run}
    assert not _runs_gate(Step(step, step), "docs-links")


def test_gate_lookup_accepts_a_trailing_comment():
    step = {"run": "PYTHONPATH='' uv run docs-links  # DOCBW-03-007"}
    assert _runs_gate(Step(step, step), "docs-links")


def test_some_workflow_builds_the_site():
    """Guard the discovery step: an empty target set must fail (DF-09-009)."""
    assert site_building_workflows(), (
        "No workflow runs 'mkdocs build'. Either the build moved, or this "
        "test's discovery is broken — both make the checks below vacuous."
    )


_CASES = [
    pytest.param(workflow, command, id=f"{workflow.name}-{command}")
    for workflow in site_building_workflows()
    for command in GATE_COMMANDS
]


@pytest.mark.spec("DOCBW-03-006")
@pytest.mark.spec("DOCBW-03-007")
@pytest.mark.spec("DOCBW-03-008")
@pytest.mark.spec("DOCBW-03-012")
@pytest.mark.parametrize("workflow,command", _CASES)
def test_site_building_workflow_runs_the_gate(workflow: Path, command: str):
    """Every workflow that builds the site runs every built-site gate."""
    steps = _steps(load_workflow(workflow))
    assert _gate_index(steps, command) is not None, (
        f"{workflow.name} runs 'mkdocs build' but never runs '{command}', "
        "directly or through a local action. A build that is not checked can "
        f"ship what the gate exists to stop ({GATES[command]})."
    )


@pytest.mark.spec("DOCBW-03-006")
@pytest.mark.spec("DOCBW-03-007")
@pytest.mark.spec("DOCBW-03-008")
@pytest.mark.spec("DOCBW-03-012")
@pytest.mark.parametrize("workflow,command", _CASES)
def test_gate_runs_after_the_build(workflow: Path, command: str):
    """The checks read ``site/``, so they are meaningless before the build."""
    steps = _steps(load_workflow(workflow))
    build = _index_of(steps, MKDOCS_BUILD, "run")
    gate = _gate_index(steps, command)
    assert build is not None and gate is not None
    assert gate > build, (
        f"In {workflow.name} the '{command}' step precedes 'mkdocs build', so "
        "it would fail on an absent site/ rather than checking the build's "
        "output."
    )


@pytest.mark.spec("DOCBW-03-005")
@pytest.mark.spec("DOCBW-03-007")
@pytest.mark.spec("DOCBW-03-008")
@pytest.mark.spec("DOCBW-03-012")
@pytest.mark.parametrize("workflow,command", _CASES)
def test_gate_is_not_neutered(workflow: Path, command: str):
    """The step must run on every trigger and be able to fail the workflow.

    A correctly ordered step that is skipped by an ``if:`` or whose failure is
    swallowed by ``continue-on-error`` satisfies every ordering check above
    while gating nothing — and so does one whose calling ``uses:`` step is.
    """
    steps = _steps(load_workflow(workflow))
    gate = _gate_index(steps, command)
    assert gate is not None
    assert not _neutering(steps[gate]), (
        f"The '{command}' step in {workflow.name} cannot fail the workflow: "
        + "; ".join(_neutering(steps[gate]))
    )


@pytest.mark.spec("DOCBW-03-006")
@pytest.mark.spec("DOCBW-03-007")
@pytest.mark.spec("DOCBW-03-008")
@pytest.mark.spec("DOCBW-03-012")
@pytest.mark.parametrize("command", GATE_COMMANDS)
def test_gate_precedes_the_pages_upload(command: str):
    """In the publishing workflow each gate blocks the upload.

    Placed after the upload, a check would report the problem only once the
    bad build was already on Pages.
    """
    deploy = WORKFLOWS_DIR / "deploy_site.yml"
    assert deploy.is_file(), (
        f"{deploy} is missing — the publishing path moved."
    )
    steps = _steps(load_workflow(deploy))
    gate = _gate_index(steps, command)
    upload = _index_of(steps, UPLOAD_PAGES_ACTION, "uses")
    assert gate is not None, f"deploy_site.yml does not run '{command}'."
    assert upload is not None, (
        "deploy_site.yml no longer uploads a Pages artifact."
    )
    assert gate < upload, (
        f"'{command}' must run before '{UPLOAD_PAGES_ACTION}' so a bad build "
        f"cannot reach Pages (DOCBW-03-006, {GATES[command]})."
    )


def test_a_conditional_action_step_neuters_the_checks_it_runs():
    """The expansion carries the caller's ``if:``, so the neuter check sees it.

    Without this, gating the ``uses:`` step on ``docs_changed`` would skip both
    checks while every step inside the action still looked unconditional.
    """
    wf = {
        "jobs": {
            "j": {
                "steps": [
                    {
                        "if": "false",
                        "uses": PUBLICATION_ACTION,
                    }
                ]
            }
        }
    }
    steps = _steps(wf)
    gate = _gate_index(steps, "docs-legacy-urls")
    assert gate is not None
    assert steps[gate].body.get("if") in RUN_EVEN_AFTER_FAILURE
    assert _neutering(steps[gate]) == ["it is conditional (if: 'false')"]


def test_every_publication_check_runs_even_if_an_earlier_one_failed():
    """A failing ``docs-withheld`` must not hide what ``docs-legacy-urls`` finds.

    Composite-action steps stop at the first failure, so without a
    run-after-failure condition a PR sees only the first check's errors and
    learns of the second only after fixing them (EH-07-001).
    """
    steps = local_action_steps(PUBLICATION_ACTION)
    later = [
        step
        for step in steps
        if any(
            _runs_gate(Step(step, step), command) for command in GATE_COMMANDS
        )
    ][1:]
    assert later, "the action runs fewer than two publication checks"
    for step in later:
        assert step.get("if") in RUN_EVEN_AFTER_FAILURE, (
            f"'{step.get('name')}' is skipped when an earlier check fails; "
            "give it 'if: ${{ !cancelled() }}'."
        )


def test_a_run_after_failure_condition_does_not_neuter_a_gate():
    step = {"if": "${{ !cancelled() }}", "run": "uv run docs-legacy-urls"}
    assert _neutering(Step(step, step)) == []
