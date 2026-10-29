"""CI verification test — every site build is the same build; one workflow publishes.

Implements DOCBW-06-004 to DOCBW-06-006 and DOCBW-06-001 from
``specs/docs-build-workflow.yaml`` (#4167).

The review workflow (``docs-build-check.yml``) and the publication workflow
(``deploy_site.yml``) once built the site differently: different dependency
groups, tags fetched in one and not the other, different build flags. A green
review then proved nothing about what published. Both now build through
``.github/actions/build-site``, which fixes the checkout, the dependency set
and the ``mkdocs build`` command, and this module keeps it that way: no
workflow, and no other local action, runs a ``mkdocs build`` of its own, and
a workflow's own steps come after the shared build.

DOCBW-06-001 is the other half of the same guarantee. Requirements on the
publication workflow bind every path to Pages only if it is the one workflow
that uploads there.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from test.ci._workflows import (
    BUILD_SITE_ACTION,
    MKDOCS_SITE_BUILD,
    REPO_ROOT,
    RUN_EVEN_AFTER_FAILURE,
    WORKFLOWS_DIR,
    expanded_steps,
    load_workflow,
    local_action_steps,
    site_building_workflows,
    steps,
)

ACTIONS_DIR = REPO_ROOT / ".github" / "actions"
BUILD_SITE_DIR = REPO_ROOT / BUILD_SITE_ACTION.removeprefix("./")
CHECKOUT_ACTION = "actions/checkout@"
SETUP_PYTHON_UV_ACTION = "./.github/actions/setup-python-uv"
# What ships: the project's own dependencies, without the dev group.
SHIPPED_DEPENDENCY_SET = "--no-dev"
PUBLICATION_WORKFLOW = WORKFLOWS_DIR / "deploy_site.yml"
ADR_INDEX_CHECK = "vultron.metadata.adr.index_gen --check"
PAGES_UPLOAD_ACTIONS = (
    "actions/upload-pages-artifact",
    "actions/deploy-pages",
)


# Parsed workflow YAML is untyped by nature; ``Any`` here is the YAML boundary.
def _own_builds(step_list: list[dict[str, Any]]) -> list[str]:
    """Return the name of every step in *step_list* that builds the site.

    Only the steps as written are read, not the actions they call, so a step
    reaching the build through the shared action is not reported.
    """
    return [
        str(step.get("name", step["run"]))
        for step in step_list
        if MKDOCS_SITE_BUILD.search(str(step.get("run", "")))
    ]


def _pages_uploads(wf_data: dict[str, Any]) -> list[str]:
    """Return every Pages upload or deploy a workflow reaches, actions expanded."""
    return [
        str(step["uses"])
        for step in expanded_steps(steps(wf_data))
        if str(step.get("uses", "")).startswith(PAGES_UPLOAD_ACTIONS)
    ]


def _other_local_actions() -> list[Path]:
    return sorted(
        path.parent
        for path in ACTIONS_DIR.glob("*/action.y*ml")
        if path.parent != BUILD_SITE_DIR
    )


def _uses_build_site(wf_data: dict[str, Any]) -> bool:
    return any(
        step.get("uses") == BUILD_SITE_ACTION for step in steps(wf_data)
    )


# --- DOCBW-06-004: the shared action fixes what the build is -----------------


@pytest.mark.spec("DOCBW-06-004")
def test_build_site_action_takes_no_inputs():
    """An input would let one caller build a different site from another."""
    action = load_workflow(BUILD_SITE_DIR / "action.yml")
    assert not action.get("inputs"), (
        f"{BUILD_SITE_ACTION} declares inputs {sorted(action['inputs'])}, so "
        "its callers can build different sites (DOCBW-06-004)."
    )


@pytest.mark.spec("DOCBW-06-004")
def test_build_site_action_checks_out_full_history_and_tags():
    """setuptools_scm reads the version from tags when ``uv sync`` installs."""
    action_steps = local_action_steps(BUILD_SITE_ACTION)
    assert action_steps, f"{BUILD_SITE_ACTION} has no steps."
    first = action_steps[0]
    assert str(first.get("uses", "")).startswith(CHECKOUT_ACTION), (
        f"{BUILD_SITE_ACTION} must check out first, so the history and tags "
        "the build reads do not depend on the caller (DOCBW-06-004)."
    )
    settings = first.get("with", {})
    assert str(settings.get("fetch-depth")) == "0"
    assert settings.get("fetch-tags") is True


@pytest.mark.spec("DOCBW-06-004")
def test_build_site_action_installs_what_ships():
    setups = [
        step
        for step in local_action_steps(BUILD_SITE_ACTION)
        if step.get("uses") == SETUP_PYTHON_UV_ACTION
    ]
    assert len(setups) == 1, (
        f"{BUILD_SITE_ACTION} must set up the environment exactly once."
    )
    sync_args = str(setups[0].get("with", {}).get("uv-sync-args", "")).split()
    assert SHIPPED_DEPENDENCY_SET in sync_args, (
        f"{BUILD_SITE_ACTION} installs {sync_args}, not the set that ships "
        f"({SHIPPED_DEPENDENCY_SET}) (DOCBW-06-004)."
    )


@pytest.mark.spec("DOCBW-06-004")
def test_build_site_action_runs_exactly_one_build():
    builds = _own_builds(local_action_steps(BUILD_SITE_ACTION))
    assert len(builds) == 1, (
        f"{BUILD_SITE_ACTION} runs {len(builds)} mkdocs builds; it must run "
        "exactly one (DOCBW-06-004)."
    )


# --- DOCBW-06-004: no workflow builds the site any other way -----------------


def test_site_building_workflows_found():
    """Guard the discovery step: an empty target set must fail (DF-09-009)."""
    workflows = site_building_workflows()
    assert PUBLICATION_WORKFLOW in workflows, (
        "The publication workflow does not build the site, or discovery is "
        "broken; both make the checks below vacuous."
    )
    assert len(workflows) >= 2, (
        "Only one workflow builds the site, so nothing reviews what publishes."
    )


@pytest.mark.spec("DOCBW-06-006")
@pytest.mark.parametrize(
    "workflow", sorted(WORKFLOWS_DIR.glob("*.yml")), ids=lambda p: p.name
)
def test_no_workflow_runs_its_own_mkdocs_build(workflow: Path):
    builds = _own_builds(steps(load_workflow(workflow)))
    assert not builds, (
        f"{workflow.name} runs 'mkdocs build' itself in {builds}. Build "
        f"through '{BUILD_SITE_ACTION}' instead, so review and publication "
        "build the same site (DOCBW-06-006)."
    )


@pytest.mark.spec("DOCBW-06-004")
@pytest.mark.spec("DOCBW-06-006")
@pytest.mark.parametrize(
    "action", _other_local_actions(), ids=lambda p: p.name
)
def test_no_other_local_action_runs_mkdocs_build(action: Path):
    """A second action with its own build would be a second, divergent build."""
    uses = f"./{action.relative_to(REPO_ROOT)}"
    builds = _own_builds(local_action_steps(uses))
    assert not builds, (
        f"{uses} runs 'mkdocs build' in {builds}; only {BUILD_SITE_ACTION} "
        "may (DOCBW-06-004)."
    )


@pytest.mark.spec("DOCBW-06-004")
@pytest.mark.parametrize(
    "workflow", site_building_workflows(), ids=lambda p: p.name
)
def test_site_building_workflow_uses_the_shared_build(workflow: Path):
    assert _uses_build_site(load_workflow(workflow)), (
        f"{workflow.name} builds the site without '{BUILD_SITE_ACTION}' "
        "(DOCBW-06-004)."
    )


@pytest.mark.spec("DOCBW-06-004")
@pytest.mark.spec("DOCBW-06-005")
@pytest.mark.parametrize(
    "workflow", site_building_workflows(), ids=lambda p: p.name
)
def test_workflow_steps_follow_the_shared_build(workflow: Path):
    """Before the build, a workflow only checks out, to load the action.

    A step placed before it (an extra install, an environment change) could
    alter the site one workflow builds and not the other.
    """
    for job in load_workflow(workflow).get("jobs", {}).values():
        job_steps = [s for s in job.get("steps", []) if isinstance(s, dict)]
        build = next(
            (
                i
                for i, step in enumerate(job_steps)
                if step.get("uses") == BUILD_SITE_ACTION
            ),
            None,
        )
        if build is None:
            continue
        before = [
            str(step.get("name", step.get("uses", step.get("run"))))
            for step in job_steps[:build]
            if not str(step.get("uses", "")).startswith(CHECKOUT_ACTION)
        ]
        assert not before, (
            f"{workflow.name} runs {before} before '{BUILD_SITE_ACTION}'; a "
            "workflow MAY add steps only after the shared build "
            "(DOCBW-06-005)."
        )


@pytest.mark.spec("EH-07-001")
def test_adr_index_check_runs_even_if_the_build_failed():
    """A failed build must not hide ADR-index drift in the same review run."""
    review = load_workflow(WORKFLOWS_DIR / "docs-build-check.yml")
    adr_checks = [
        step
        for step in steps(review)
        if ADR_INDEX_CHECK in str(step.get("run", ""))
    ]
    assert adr_checks, f"docs-build-check.yml never runs '{ADR_INDEX_CHECK}'."
    for step in adr_checks:
        assert step.get("if") in RUN_EVEN_AFTER_FAILURE, (
            f"'{step.get('name')}' is skipped when the build fails; give it "
            "'if: ${{ !cancelled() }}'."
        )


def test_own_builds_finds_a_direct_build_but_not_the_shared_action():
    """The detector the ratchet above rests on catches what it must."""
    step_list = [
        {"uses": BUILD_SITE_ACTION},
        {"name": "Rebuild", "run": "uv run mkdocs build --strict"},
    ]
    assert _own_builds(step_list) == ["Rebuild"]


@pytest.mark.parametrize(
    "command",
    [
        "uv run mkdocs build --strict",
        "uv run mkdocs -v build",
        "python -m mkdocs gh-deploy --force",
        "mkdocs build",
        "uv run mkdocs -f mkdocs.yml build",
        "mkdocs --config-file mkdocs.yml build --strict",
    ],
)
def test_own_builds_finds_every_form_of_a_site_build(command: str):
    assert _own_builds([{"run": command}]) == [command]


@pytest.mark.parametrize(
    "command", ["uv run mkdocs serve", "echo mkdocs-build-strict.sh"]
)
def test_own_builds_ignores_commands_that_build_nothing(command: str):
    assert _own_builds([{"run": command}]) == []


# --- DOCBW-06-001: only the publication workflow uploads to Pages ------------


@pytest.mark.spec("DOCBW-06-001")
def test_publication_workflow_uploads_to_pages():
    """Control: the check below is vacuous if nothing uploads at all."""
    uploads = _pages_uploads(load_workflow(PUBLICATION_WORKFLOW))
    assert any(u.startswith(PAGES_UPLOAD_ACTIONS[0]) for u in uploads), (
        f"{PUBLICATION_WORKFLOW.name} no longer uploads a Pages artifact; "
        "the publishing path moved."
    )


@pytest.mark.spec("DOCBW-06-001")
@pytest.mark.parametrize(
    "workflow",
    [
        path
        for path in sorted(WORKFLOWS_DIR.glob("*.yml"))
        if path != PUBLICATION_WORKFLOW
    ],
    ids=lambda p: p.name,
)
def test_no_other_workflow_uploads_to_pages(workflow: Path):
    uploads = _pages_uploads(load_workflow(workflow))
    assert not uploads, (
        f"{workflow.name} uses {uploads}: a second path to Pages that no "
        f"obligation on {PUBLICATION_WORKFLOW.name} covers (DOCBW-06-001)."
    )


def test_expansion_reaches_through_nested_local_actions():
    """An upload two local actions deep would still be found.

    ``build-site`` calls ``setup-python-uv``, which calls
    ``actions/setup-python``: one level of expansion would stop short of it.
    """
    reached = [
        str(step.get("uses", ""))
        for step in expanded_steps([{"uses": BUILD_SITE_ACTION}])
    ]
    assert any(u.startswith("actions/setup-python@") for u in reached)
