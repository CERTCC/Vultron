"""CI verification test — the built-site gates run wherever the site builds.

Implements DOCBW-03-005, DOCBW-03-006 and DOCBW-03-007 from
``specs/docs-build-workflow.yaml``. Two gates read the built ``site/``:
``docs-withheld`` (the publication axis — a withheld artifact produced no files)
and ``docs-links`` (the reference axis — every internal reference resolves). A
workflow that builds ``site/`` MUST run both against it, unconditionally, and in
``deploy_site.yml`` each MUST sit between the build and the Pages upload.

Ordering is the whole point, and it is why this is a test rather than a review
habit. Both gates read the built tree, so a step placed before the build fails
on an absent ``site/``; a step placed after the upload cannot stop a bad build
from reaching Pages. The withheld gate first shipped in the pull-request
workflow only, which left the publishing path — the one act #3549 exists to
prevent — ungated.
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

# Each built-site gate's command, and the requirement it implements.
GATES = {"docs-withheld": "DOCBW-03-005", "docs-links": "DOCBW-03-007"}
UPLOAD_PAGES_ACTION = "actions/upload-pages-artifact"

WORKFLOW_GATE_PAIRS = [
    pytest.param(workflow, gate, id=f"{workflow.name}-{gate}")
    for workflow in site_building_workflows()
    for gate in GATES
]


def test_some_workflow_builds_the_site():
    """Guard the discovery step: an empty target set must fail (DF-09-009)."""
    assert site_building_workflows(), (
        "No workflow runs 'mkdocs build'. Either the build moved, or this "
        "test's discovery is broken — both make the checks below vacuous."
    )


@pytest.mark.spec("DOCBW-03-006")
@pytest.mark.spec("DOCBW-03-007")
@pytest.mark.parametrize("workflow, gate", WORKFLOW_GATE_PAIRS)
def test_site_building_workflow_runs_the_gate(workflow: Path, gate: str):
    """Every workflow that builds the site runs every built-site gate."""
    wf_steps = steps(load_workflow(workflow))
    assert index_of(wf_steps, gate, "run") is not None, (
        f"{workflow.name} runs 'mkdocs build' but never runs '{gate}'. A "
        f"build that is not checked can publish what it catches ({GATES[gate]})."
    )


@pytest.mark.spec("DOCBW-03-006")
@pytest.mark.spec("DOCBW-03-007")
@pytest.mark.parametrize("workflow, gate", WORKFLOW_GATE_PAIRS)
def test_gate_runs_after_the_build(workflow: Path, gate: str):
    """The check reads ``site/``, so it is meaningless before the build."""
    wf_steps = steps(load_workflow(workflow))
    build = index_of(wf_steps, MKDOCS_BUILD, "run")
    step = index_of(wf_steps, gate, "run")
    assert build is not None and step is not None
    assert step > build, (
        f"In {workflow.name} the '{gate}' step precedes 'mkdocs build', so it "
        "would fail on an absent site/ rather than checking the build's output."
    )


@pytest.mark.spec("DOCBW-03-005")
@pytest.mark.spec("DOCBW-03-007")
@pytest.mark.parametrize("workflow, gate", WORKFLOW_GATE_PAIRS)
def test_gate_is_not_neutered(workflow: Path, gate: str):
    """The step must run on every trigger and be able to fail the workflow.

    A correctly ordered step that is skipped by an ``if:`` or whose failure is
    swallowed by ``continue-on-error`` satisfies every ordering check above
    while gating nothing.
    """
    wf_steps = steps(load_workflow(workflow))
    index = index_of(wf_steps, gate, "run")
    assert index is not None
    step = wf_steps[index]
    assert "if" not in step, (
        f"The '{gate}' step in {workflow.name} is conditional "
        f"(if: {step['if']!r}), so it can be skipped ({GATES[gate]})."
    )
    assert not step.get("continue-on-error", False), (
        f"The '{gate}' step in {workflow.name} sets continue-on-error, so what "
        f"it catches would not fail the workflow ({GATES[gate]})."
    )


@pytest.mark.spec("DOCBW-03-006")
@pytest.mark.spec("DOCBW-03-007")
@pytest.mark.parametrize("gate", GATES)
def test_gate_precedes_the_pages_upload(gate: str):
    """In the publishing workflow each gate blocks the upload.

    Placed after the upload, the check would report the violation only once the
    bad build was already on Pages.
    """
    deploy = WORKFLOWS_DIR / "deploy_site.yml"
    assert (
        deploy.is_file()
    ), f"{deploy} is missing — the publishing path moved."
    wf_steps = steps(load_workflow(deploy))
    step = index_of(wf_steps, gate, "run")
    upload = index_of(wf_steps, UPLOAD_PAGES_ACTION, "uses")
    assert step is not None, f"deploy_site.yml does not run '{gate}'."
    assert (
        upload is not None
    ), "deploy_site.yml no longer uploads a Pages artifact."
    assert step < upload, (
        f"'{gate}' must run before '{UPLOAD_PAGES_ACTION}' so what it catches "
        f"cannot reach Pages ({GATES[gate]})."
    )
