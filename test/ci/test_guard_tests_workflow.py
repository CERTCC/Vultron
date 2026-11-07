"""CI owns the guard tests, on every pull request (PAD-18-023, PAD-18-031).

``prepush-ci-mirror`` ran the guard set before each push until PAD-18-023
moved it to CI. The move only holds if something in CI runs it on the pull
request shapes that have no other check: ``python-app.yml``'s ``pull_request``
filter lists no glob for Markdown, ``specs/``, ``AGENTS.md`` or ``notes/``, and
PAD-18-010 gives a pull request that changes no Python no local suite. So
``guard-tests.yml`` runs on every pull request to ``main``, and the required
``CI gate`` judges it.

These tests pin the three things that would silently empty the job: a path
filter added to its trigger, a path in its command naming no file, and a
shrunken list.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from test.ci._workflows import (
    REPO_ROOT,
    WORKFLOWS_DIR,
    load_workflow,
    triggers,
)
from vultron.metadata.planning.ci_mirror import EXCLUSIONS

_WORKFLOW = WORKFLOWS_DIR / "guard-tests.yml"

#: The exclusion key of the step this job runs, as the mirror's registry
#: spells it. The parity test (PAD-18-022) already fails when no such step
#: runs; this names it so a renamed step fails here too, with the reason.
_EXCLUSION_KEY = "guard-tests.yml::guard-tests::Run the guard tests"

#: How many tests the job runs. A fixed floor, not `len()` of the list below:
#: a floor derived from the thing it guards shrinks with it (#5535).
_GUARD_TEST_COUNT = 14

#: Guards with an input that **no** CI job running pytest reaches, so each is a
#: reason this job exists rather than an incidental member. Derived against two
#: things per workflow, not one: its `pull_request` paths **and** its pytest
#: selector. Named, not counted: a rename must fail here rather than quietly
#: shrink the subject set (#5535).
#:
#: Deliberately absent, because CI does reach them: the two `specs/**` guards
#: (`test_spec_statement_guard.py`, `test_spec_kind_ratchet.py`) are
#: `spec_corpus`-marked and `spec-check.yml` lists `specs/**` and runs
#: `pytest -m spec_corpus`; `test_python_app_test_parts.py` reads
#: `.github/workflows/`, which `python-app.yml` itself lists; the Python half
#: of `test_line_length_ratchet.py` rides `**/*.py` and its spec half is
#: `spec_corpus`-marked; `test_vocab_examples_current.py` reads
#: `docs/reference/examples/**`, which `python-app.yml` lists; and
#: `test_btnd07_structure.py` reads `vultron/**`.
_INPUTS_NO_SUITE_REACHES = (
    # Reads every AGENTS.md. The root one matches no pytest workflow's paths
    # (`vultron/**` and `test/**` happen to catch the nested ones).
    "test/metadata/test_agents_md_size_ratchet.py",
    # Reads `.agents/skills/**/*.md` and `notes/*.md`; the pytest workflows
    # list only `.agents/**/*.py` and `.agents/**/*.sh`.
    "test/metadata/test_gate_ceiling.py",
    # Reads four skills' `SKILL.md` and `REFERENCE.md` and nothing else, so
    # the pull request most likely to break it — one that edits only those
    # files — is exactly the one no pytest workflow starts on (#5948).
    "test/metadata/test_draft_pr_wiring.py",
    # Reads `docs/adr/`, which no pytest workflow lists; `adr-lifecycle.yml`
    # triggers on it and runs no pytest.
    "test/metadata/test_adr_back_edges.py",
    # Scans `notes/` as well as specs/, vultron/ and test/.
    "test/metadata/test_no_decision_record_part_citations.py",
    # Compares the committed `docs/reference/messages/_occasions/` fragments
    # with a fresh generation. `docs-build-check.yml` triggers on `docs/**`
    # and runs no pytest; the pytest workflows list neither path.
    "test/metadata/test_msm_occasions.py",
    # Read `docs/**/*.md`. The pytest workflows list only
    # `docs/reference/examples/**`, `docs/reference/codebase/**` and
    # `docs/reference/user_stories/**`.
    "test/metadata/docs/test_page_frontmatter.py",
    "test/metadata/docs/test_level_order.py",
)


def _workflow() -> dict[str, Any]:
    return load_workflow(_WORKFLOW)


def _guard_step() -> dict[str, Any]:
    job = _workflow()["jobs"]["guard-tests"]
    assert isinstance(job, dict)
    [step] = [
        s
        for s in job["steps"]
        if isinstance(s, dict) and s.get("name") == "Run the guard tests"
    ]
    return step


def _guard_paths() -> list[str]:
    """The test paths the job's pytest command names, in file order."""
    words = str(_guard_step()["run"]).split()
    return [w for w in words if w.startswith("test/")]


@pytest.mark.spec("PAD-18-023")
def test_it_runs_on_every_pull_request_to_main() -> None:
    """No ``paths`` filter: a skip here is a guard that did not run.

    The ``CI gate`` passes on a skipped check, so a path-filtered job would
    leave the guards unrun on exactly the pull requests they police
    (PAD-18-031).
    """
    on = triggers(_workflow())
    pull_request = on["pull_request"]

    assert pull_request["branches"] == ["main"]
    assert "paths" not in pull_request
    assert "paths-ignore" not in pull_request
    # `GITHUB_BASE_REF` is set on `pull_request` alone, and the merge-base
    # growth guards here skip without it — all-skipped is green. The gate
    # judges only the newest run per workflow, so a dispatch on the branch
    # would stand in for the real verdict with nothing checked.
    assert set(on) == {"pull_request"}


@pytest.mark.spec("PAD-18-023")
def test_the_job_runs_both_test_tiers_in_parallel() -> None:
    run = str(_guard_step()["run"])

    assert "uv run pytest" in run
    # -m "": the unit and integration tiers both, as the mirror ran them.
    assert '-m ""' in run
    assert "-n auto" in run


@pytest.mark.spec("PAD-18-023")
def test_the_job_names_every_guard_test() -> None:
    # A command with no paths would run the whole suite, or nothing, and
    # `test_every_guard_test_exists` would pass having collected none.
    assert len(_guard_paths()) == _GUARD_TEST_COUNT


@pytest.mark.spec("PAD-18-023")
@pytest.mark.parametrize("path", _guard_paths())
def test_every_guard_test_exists(path: str) -> None:
    assert (REPO_ROOT / Path(path)).is_file(), (
        f"{path} is in guard-tests.yml but does not exist; a rename left the "
        "job running one test fewer, with nothing red to say so"
    )


@pytest.mark.spec("PAD-18-023")
@pytest.mark.parametrize("path", _INPUTS_NO_SUITE_REACHES)
def test_the_job_keeps_the_guards_no_other_check_reaches(path: str) -> None:
    assert path in _guard_paths(), (
        f"{path} has an input no CI job running pytest reaches, so dropping "
        "it from guard-tests.yml leaves it running on no pull request. Before "
        "removing it, check both halves for every workflow: its "
        "`pull_request` paths and its pytest selector (PAD-18-023)"
    )


@pytest.mark.spec("PAD-18-023")
def test_the_mirror_leaves_the_job_to_ci_with_a_reason() -> None:
    reason = EXCLUSIONS[_EXCLUSION_KEY]

    assert "CI" in reason
    assert "PAD-18-023" in reason
