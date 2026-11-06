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

#: Guards whose only inputs are files no CI pytest path filter lists, so each
#: is a reason this job exists rather than an incidental member. Named, not
#: counted: a rename must fail here rather than quietly shrink the subject set
#: (#5535).
_INPUTS_NO_SUITE_REACHES = (
    # Reads every AGENTS.md.
    "test/metadata/test_agents_md_size_ratchet.py",
    # Reads the skills' Markdown.
    "test/metadata/test_gate_ceiling.py",
    # Read specs/.
    "test/architecture/test_spec_statement_guard.py",
    "test/architecture/test_spec_kind_ratchet.py",
    # Reads docs/adr/ and the notes and specs that cite a record.
    "test/metadata/test_adr_back_edges.py",
    "test/metadata/test_no_decision_record_part_citations.py",
    # Read docs/ pages.
    "test/metadata/docs/test_page_frontmatter.py",
    "test/metadata/docs/test_level_order.py",
    # Reads .github/workflows/, which names no Python symbol.
    "test/ci/test_python_app_test_parts.py",
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
    pull_request = triggers(_workflow())["pull_request"]

    assert pull_request["branches"] == ["main"]
    assert "paths" not in pull_request
    assert "paths-ignore" not in pull_request


@pytest.mark.spec("PAD-18-023")
def test_the_job_runs_both_test_tiers_in_parallel() -> None:
    run = str(_guard_step()["run"])

    assert "uv run pytest" in run
    # -m "": the unit and integration tiers both, as the mirror ran them.
    assert '-m ""' in run
    assert "-n auto" in run


@pytest.mark.spec("PAD-18-023")
def test_the_job_names_tests_at_all() -> None:
    # A command with no paths would run the whole suite, or nothing, and
    # every per-path test below would pass having checked none.
    assert len(_guard_paths()) >= len(_INPUTS_NO_SUITE_REACHES)


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
        f"{path} reads inputs no CI pytest path filter lists, so dropping it "
        "from guard-tests.yml leaves it running on no pull request "
        "(PAD-18-023)"
    )


@pytest.mark.spec("PAD-18-023")
def test_the_mirror_leaves_the_job_to_ci_with_a_reason() -> None:
    reason = EXCLUSIONS[_EXCLUSION_KEY]

    assert "CI" in reason
    assert "PAD-18-023" in reason
