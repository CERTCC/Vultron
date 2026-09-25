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

import pytest

from test.ci._workflows import (
    MKDOCS_BUILD,
    WORKFLOWS_DIR,
    index_of,
    load_workflow,
    site_building_workflows,
    steps,
)

WITHHELD_COMMAND = "docs-withheld"
UPLOAD_PAGES_ACTION = "actions/upload-pages-artifact"


def test_some_workflow_builds_the_site():
    """Guard the discovery step: an empty target set must fail (DF-09-009)."""
    assert site_building_workflows(), (
        "No workflow runs 'mkdocs build'. Either the build moved, or this "
        "test's discovery is broken — both make the checks below vacuous."
    )


@pytest.mark.parametrize(
    "workflow",
    site_building_workflows(),
    ids=lambda p: p.name,
)
def test_site_building_workflow_runs_the_withheld_gate(workflow: Path):
    """DOCBW-03-006: every workflow that builds the site runs the gate."""
    wf_steps = steps(load_workflow(workflow))
    assert index_of(wf_steps, WITHHELD_COMMAND, "run") is not None, (
        f"{workflow.name} runs 'mkdocs build' but never runs "
        f"'{WITHHELD_COMMAND}'. A build that is not checked can publish an "
        "artifact the project declared withheld (DOCBW-03-006)."
    )


@pytest.mark.parametrize(
    "workflow",
    site_building_workflows(),
    ids=lambda p: p.name,
)
def test_withheld_gate_runs_after_the_build(workflow: Path):
    """The check reads ``site/``, so it is meaningless before the build."""
    wf_steps = steps(load_workflow(workflow))
    build = index_of(wf_steps, MKDOCS_BUILD, "run")
    gate = index_of(wf_steps, WITHHELD_COMMAND, "run")
    assert build is not None and gate is not None
    assert gate > build, (
        f"In {workflow.name} the '{WITHHELD_COMMAND}' step precedes "
        "'mkdocs build', so it would fail on an absent site/ rather than "
        "checking the build's output."
    )


@pytest.mark.parametrize(
    "workflow",
    site_building_workflows(),
    ids=lambda p: p.name,
)
def test_withheld_gate_is_not_neutered(workflow: Path):
    """DOCBW-03-005: the step must be able to fail the workflow.

    A correctly ordered step that is skipped by an ``if:`` or whose failure is
    swallowed by ``continue-on-error`` satisfies every ordering check above
    while gating nothing.
    """
    wf_steps = steps(load_workflow(workflow))
    gate = index_of(wf_steps, WITHHELD_COMMAND, "run")
    assert gate is not None
    step = wf_steps[gate]
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
    wf_steps = steps(load_workflow(deploy))
    gate = index_of(wf_steps, WITHHELD_COMMAND, "run")
    upload = index_of(wf_steps, UPLOAD_PAGES_ACTION, "uses")
    assert gate is not None, "deploy_site.yml does not run the withheld gate."
    assert (
        upload is not None
    ), "deploy_site.yml no longer uploads a Pages artifact."
    assert gate < upload, (
        "The withheld gate must run before 'actions/upload-pages-artifact' so a "
        "withheld artifact cannot reach Pages (DOCBW-03-006)."
    )
