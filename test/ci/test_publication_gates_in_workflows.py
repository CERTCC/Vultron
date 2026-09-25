"""CI verification test — the publication gates run wherever the site builds.

Implements DOCBW-03-005, DOCBW-03-006 and DOCBW-03-008 from
``specs/docs-build-workflow.yaml``. A workflow that builds ``site/`` MUST run
``docs-withheld`` and ``docs-legacy-urls`` against it, and in
``deploy_site.yml`` both MUST sit between the build and the Pages upload.

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

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS_DIR = REPO_ROOT / ".github" / "workflows"

GATE_COMMANDS = ("docs-withheld", "docs-legacy-urls")
MKDOCS_BUILD = "mkdocs build"
UPLOAD_PAGES_ACTION = "actions/upload-pages-artifact"


@dataclass(frozen=True)
class Step:
    """A step in run order, with the workflow step that caused it to run.

    ``caller`` is the step itself for an ordinary workflow step, and the
    ``uses: ./…`` step for a step expanded from a local composite action.
    """

    # Parsed workflow YAML is untyped by nature; ``Any`` here is the YAML boundary.
    body: dict[str, Any]
    caller: dict[str, Any]


def _load_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def _local_action_steps(uses: str) -> list[dict[str, Any]]:
    """Return the steps of the local composite action a ``uses:`` names."""
    action_dir = REPO_ROOT / uses.removeprefix("./")
    action_file = next(
        (
            action_dir / name
            for name in ("action.yml", "action.yaml")
            if (action_dir / name).is_file()
        ),
        None,
    )
    assert action_file is not None, f"Local action {uses} has no action.yml."
    runs = _load_yaml(action_file).get("runs", {})
    return [s for s in runs.get("steps", []) if isinstance(s, dict)]


def _steps(wf_data: dict[str, Any]) -> list[Step]:
    """Return every step across every job, in run order, actions expanded."""
    flat: list[Step] = []
    for job in wf_data.get("jobs", {}).values():
        if not isinstance(job, dict):
            continue
        for step in job.get("steps", []):
            if not isinstance(step, dict):
                continue
            uses = str(step.get("uses", ""))
            if uses.startswith("./"):
                flat.extend(Step(s, step) for s in _local_action_steps(uses))
            else:
                flat.append(Step(step, step))
    return flat


def _index_of(steps: list[Step], needle: str, key: str) -> int | None:
    """Return the index of the first step whose ``key`` field contains ``needle``."""
    for i, step in enumerate(steps):
        if needle in str(step.body.get(key, "")):
            return i
    return None


def _site_building_workflows() -> list[Path]:
    """Return every workflow that runs ``mkdocs build``."""
    return sorted(
        path
        for path in WORKFLOWS_DIR.glob("*.yml")
        if MKDOCS_BUILD in path.read_text(encoding="utf-8")
    )


def test_some_workflow_builds_the_site():
    """Guard the discovery step: an empty target set must fail (DF-09-009)."""
    assert _site_building_workflows(), (
        "No workflow runs 'mkdocs build'. Either the build moved, or this "
        "test's discovery is broken — both make the checks below vacuous."
    )


_CASES = [
    pytest.param(workflow, command, id=f"{workflow.name}-{command}")
    for workflow in _site_building_workflows()
    for command in GATE_COMMANDS
]


@pytest.mark.parametrize("workflow,command", _CASES)
def test_site_building_workflow_runs_the_gate(workflow: Path, command: str):
    """DOCBW-03-006, DOCBW-03-008: every workflow that builds the site runs it."""
    steps = _steps(_load_yaml(workflow))
    assert _index_of(steps, command, "run") is not None, (
        f"{workflow.name} runs 'mkdocs build' but never runs '{command}', "
        "directly or through a local action. A build that is not checked can "
        "ship what the gate exists to stop (DOCBW-03-006, DOCBW-03-008)."
    )


@pytest.mark.parametrize("workflow,command", _CASES)
def test_gate_runs_after_the_build(workflow: Path, command: str):
    """The checks read ``site/``, so they are meaningless before the build."""
    steps = _steps(_load_yaml(workflow))
    build = _index_of(steps, MKDOCS_BUILD, "run")
    gate = _index_of(steps, command, "run")
    assert build is not None and gate is not None
    assert gate > build, (
        f"In {workflow.name} the '{command}' step precedes 'mkdocs build', so "
        "it would fail on an absent site/ rather than checking the build's "
        "output."
    )


@pytest.mark.parametrize("workflow,command", _CASES)
def test_gate_is_not_neutered(workflow: Path, command: str):
    """DOCBW-03-005, DOCBW-03-008: the step must be able to fail the workflow.

    A correctly ordered step that is skipped by an ``if:`` or whose failure is
    swallowed by ``continue-on-error`` satisfies every ordering check above
    while gating nothing — and so does one whose calling ``uses:`` step is.
    """
    steps = _steps(_load_yaml(workflow))
    gate = _index_of(steps, command, "run")
    assert gate is not None
    for step in (steps[gate].body, steps[gate].caller):
        assert "if" not in step, (
            f"The '{command}' step in {workflow.name} is conditional "
            f"(if: {step['if']!r}), so it can be skipped."
        )
        assert not step.get("continue-on-error", False), (
            f"The '{command}' step in {workflow.name} sets continue-on-error, "
            "so a failing check would not fail the workflow."
        )


@pytest.mark.parametrize("command", GATE_COMMANDS)
def test_gate_precedes_the_pages_upload(command: str):
    """DOCBW-03-006, DOCBW-03-008: in the publishing workflow the gate blocks the upload.

    Placed after the upload, a check would report the problem only once the
    bad build was already on Pages.
    """
    deploy = WORKFLOWS_DIR / "deploy_site.yml"
    assert (
        deploy.is_file()
    ), f"{deploy} is missing — the publishing path moved."
    steps = _steps(_load_yaml(deploy))
    gate = _index_of(steps, command, "run")
    upload = _index_of(steps, UPLOAD_PAGES_ACTION, "uses")
    assert gate is not None, f"deploy_site.yml does not run '{command}'."
    assert (
        upload is not None
    ), "deploy_site.yml no longer uploads a Pages artifact."
    assert gate < upload, (
        f"'{command}' must run before '{UPLOAD_PAGES_ACTION}' so a bad build "
        "cannot reach Pages (DOCBW-03-006, DOCBW-03-008)."
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
                        "uses": "./.github/actions/check-site-publication",
                    }
                ]
            }
        }
    }
    steps = _steps(wf)
    gate = _index_of(steps, "docs-legacy-urls", "run")
    assert gate is not None
    assert "if" not in steps[gate].body
    assert steps[gate].caller.get("if") == "false"
