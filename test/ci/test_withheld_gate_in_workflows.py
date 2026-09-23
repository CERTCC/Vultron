"""CI verification test — the withheld-artifact gate runs wherever the site builds.

Implements DOCBW-03-005 and DOCBW-03-006 from ``specs/docs-build-workflow.yaml``.
A workflow that builds ``site/`` MUST run ``docs-withheld`` against it, and in
``deploy_site.yml`` the check MUST sit between the build and the Pages upload.

Ordering is the whole point, and it is why this is a test rather than a review
habit. ``docs-withheld`` reads the built tree, so a step placed before the build
fails on an absent ``site/``; a step placed after the upload cannot stop a
withheld artifact from reaching Pages. The gate first shipped in the
pull-request workflow only, which left the publishing path — the one act #3549
exists to prevent — ungated.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS_DIR = REPO_ROOT / ".github" / "workflows"

WITHHELD_COMMAND = "docs-withheld"
MKDOCS_BUILD = "mkdocs build"
UPLOAD_PAGES_ACTION = "actions/upload-pages-artifact"


# Parsed workflow YAML is untyped by nature; ``Any`` here is the YAML boundary.
def _load_workflow(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def _steps(wf_data: dict[str, Any]) -> list[dict[str, Any]]:
    """Return every step across every job, in file order."""
    return [
        step
        for job in wf_data.get("jobs", {}).values()
        if isinstance(job, dict)
        for step in job.get("steps", [])
        if isinstance(step, dict)
    ]


def _index_of(
    steps: list[dict[str, Any]], needle: str, key: str
) -> int | None:
    """Return the index of the first step whose ``key`` field contains ``needle``."""
    for i, step in enumerate(steps):
        if needle in str(step.get(key, "")):
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


@pytest.mark.parametrize(
    "workflow",
    _site_building_workflows(),
    ids=lambda p: p.name,
)
def test_site_building_workflow_runs_the_withheld_gate(workflow: Path):
    """DOCBW-03-006: every workflow that builds the site runs the gate."""
    steps = _steps(_load_workflow(workflow))
    assert _index_of(steps, WITHHELD_COMMAND, "run") is not None, (
        f"{workflow.name} runs 'mkdocs build' but never runs "
        f"'{WITHHELD_COMMAND}'. A build that is not checked can publish an "
        "artifact the project declared withheld (DOCBW-03-006)."
    )


@pytest.mark.parametrize(
    "workflow",
    _site_building_workflows(),
    ids=lambda p: p.name,
)
def test_withheld_gate_runs_after_the_build(workflow: Path):
    """The check reads ``site/``, so it is meaningless before the build."""
    steps = _steps(_load_workflow(workflow))
    build = _index_of(steps, MKDOCS_BUILD, "run")
    gate = _index_of(steps, WITHHELD_COMMAND, "run")
    assert build is not None and gate is not None
    assert gate > build, (
        f"In {workflow.name} the '{WITHHELD_COMMAND}' step precedes "
        "'mkdocs build', so it would fail on an absent site/ rather than "
        "checking the build's output."
    )


@pytest.mark.parametrize(
    "workflow",
    _site_building_workflows(),
    ids=lambda p: p.name,
)
def test_withheld_gate_is_not_neutered(workflow: Path):
    """DOCBW-03-005: the step must be able to fail the workflow.

    A correctly ordered step that is skipped by an ``if:`` or whose failure is
    swallowed by ``continue-on-error`` satisfies every ordering check above
    while gating nothing.
    """
    steps = _steps(_load_workflow(workflow))
    gate = _index_of(steps, WITHHELD_COMMAND, "run")
    assert gate is not None
    step = steps[gate]
    assert "if" not in step, (
        f"The '{WITHHELD_COMMAND}' step in {workflow.name} is conditional "
        f"(if: {step['if']!r}), so it can be skipped (DOCBW-03-005)."
    )
    assert not step.get("continue-on-error", False), (
        f"The '{WITHHELD_COMMAND}' step in {workflow.name} sets "
        "continue-on-error, so a withheld artifact would not fail the "
        "workflow (DOCBW-03-005)."
    )


def test_withheld_gate_precedes_the_pages_upload():
    """DOCBW-03-006: in the publishing workflow the gate blocks the upload.

    Placed after the upload, the check would report the violation only once the
    withheld artifact was already on Pages.
    """
    deploy = WORKFLOWS_DIR / "deploy_site.yml"
    assert (
        deploy.is_file()
    ), f"{deploy} is missing — the publishing path moved."
    steps = _steps(_load_workflow(deploy))
    gate = _index_of(steps, WITHHELD_COMMAND, "run")
    upload = _index_of(steps, UPLOAD_PAGES_ACTION, "uses")
    assert gate is not None, "deploy_site.yml does not run the withheld gate."
    assert (
        upload is not None
    ), "deploy_site.yml no longer uploads a Pages artifact."
    assert gate < upload, (
        "The withheld gate must run before 'actions/upload-pages-artifact' so a "
        "withheld artifact cannot reach Pages (DOCBW-03-006)."
    )
