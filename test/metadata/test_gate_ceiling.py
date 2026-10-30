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
"""Every agent gate command and the CI test job run under a wall-clock ceiling.

A per-test ``signal`` timeout cannot reach a C call that holds the GIL or a
stuck xdist controller, so the outer ceiling is the only thing that ends such
a run (TB-14-005, #4809).  The printed ``targeted-tests --pytest`` command is
pinned in ``test_targeted_tests.py``; this module pins the written commands
an agent copies and the CI test job, and the ``timeout-minutes`` cap on every
job in every workflow (TB-14-006).

Human developer how-to pages under ``docs/developer/`` are out of scope: stock
macOS has no ``timeout`` binary.
"""

import re
from pathlib import Path
from typing import Any

import pytest

from test.ci._workflows import WORKFLOWS_DIR, load_workflow, workflow_files
from vultron.metadata.planning.targeted_tests import GATE_CEILING

_REPO_ROOT = Path(__file__).parents[2]

_CEILING = " ".join(GATE_CEILING)

# Files an agent reads for the gate command to run.
_AGENT_GLOBS = (
    "AGENTS.md",
    "*/AGENTS.md",
    "*/*/AGENTS.md",
    "*/*/*/AGENTS.md",
    ".agents/skills/**/*.md",
    ".github/copilot-instructions.md",
    "docs/reference/codebase/*.md",
    "notes/*.md",
)

_EXCLUDED_PARTS = (".git", "plan", "node_modules", ".venv", "wip_notes")

# The redirected gate form: ``uv run pytest ... > /tmp/x.log ...; (exit $rc)``.
_REDIRECTED_GATE = re.compile(
    r"uv run pytest[^\n`]*>\s*/tmp/[^\n`]*\(exit \$rc\)"
)


def _agent_files() -> list[Path]:
    found: set[Path] = set()
    for glob in _AGENT_GLOBS:
        for path in _REPO_ROOT.glob(glob):
            parts = path.relative_to(_REPO_ROOT).parts
            if path.is_file() and not any(p in _EXCLUDED_PARTS for p in parts):
                found.add(path)
    return sorted(found)


def _gates_without_ceiling(text: str) -> list[str]:
    return [
        match.group(0)
        for match in _REDIRECTED_GATE.finditer(text)
        if not text[: match.start()].endswith(_CEILING + " ")
    ]


def test_detector_tells_a_bare_gate_from_a_ceiled_one() -> None:
    bare = 'uv run pytest -n auto > /tmp/x.log 2>&1; rc=$?; tail -5 /tmp/x.log; echo "exit: $rc"; (exit $rc)'
    assert _gates_without_ceiling(bare) == [bare]
    assert _gates_without_ceiling(f"{_CEILING} {bare}") == []


def test_discovery_finds_the_gate_bearing_files() -> None:
    found = {str(p.relative_to(_REPO_ROOT)) for p in _agent_files()}
    assert {
        "AGENTS.md",
        "test/AGENTS.md",
        ".agents/skills/run-tests/SKILL.md",
        ".github/copilot-instructions.md",
        "docs/reference/codebase/TESTING.md",
        "notes/testing-pitfalls.md",
    } <= found


@pytest.mark.parametrize(
    "rel_path",
    [str(p.relative_to(_REPO_ROOT)) for p in _agent_files()],
)
def test_agent_gate_command_runs_under_the_ceiling(rel_path: str) -> None:
    text = (_REPO_ROOT / rel_path).read_text(encoding="utf-8")
    bare = _gates_without_ceiling(text)
    assert not bare, (
        f"{rel_path} has redirected pytest gate(s) without `{_CEILING}` "
        f"(TB-14-005):\n" + "\n".join(f"  {cmd}" for cmd in bare)
    )


def _python_app_jobs() -> dict[str, object]:
    jobs = load_workflow(WORKFLOWS_DIR / "python-app.yml")["jobs"]
    assert isinstance(jobs, dict)
    return jobs


def test_ci_test_job_has_a_timeout() -> None:
    job = _python_app_jobs()["test"]
    assert isinstance(job, dict)
    minutes = job.get("timeout-minutes")
    assert isinstance(minutes, int) and minutes > 0, (
        "The `Tests (pytest)` job needs `timeout-minutes` (TB-14-005)."
    )


def _uncapped_jobs(file_name: str, wf_data: dict[str, Any]) -> list[str]:
    """Return ``<file>:<job>`` for each job with no positive ``timeout-minutes``.

    A job that calls a reusable workflow (``uses:``) is skipped: GitHub rejects
    ``timeout-minutes`` there, and the called workflow's jobs carry the cap.
    A ``bool`` is an ``int`` to Python, so ``timeout-minutes: true`` is refused
    explicitly.
    """
    jobs = wf_data.get("jobs")
    # A file with no jobs would pass while checking nothing.
    assert isinstance(jobs, dict) and jobs, (
        f"{file_name} has no non-empty `jobs:` mapping"
    )
    missing = []
    for job_key, job_spec in jobs.items():
        if isinstance(job_spec, dict) and "uses" in job_spec:
            continue
        minutes = (
            job_spec.get("timeout-minutes")
            if isinstance(job_spec, dict)
            else None
        )
        if (
            isinstance(minutes, bool)
            or not isinstance(minutes, int)
            or minutes <= 0
        ):
            missing.append(f"{file_name}:{job_key}")
    return missing


def test_detector_flags_an_uncapped_job_and_skips_a_reusable_call() -> None:
    wf_data: dict[str, Any] = {
        "jobs": {
            "capped": {"runs-on": "ubuntu-latest", "timeout-minutes": 5},
            "uncapped": {"runs-on": "ubuntu-latest"},
            "zero": {"runs-on": "ubuntu-latest", "timeout-minutes": 0},
            "boolean": {"runs-on": "ubuntu-latest", "timeout-minutes": True},
            "call": {"uses": "./.github/workflows/docs-build-check.yml"},
        }
    }
    assert _uncapped_jobs("x.yml", wf_data) == [
        "x.yml:uncapped",
        "x.yml:zero",
        "x.yml:boolean",
    ]


@pytest.mark.parametrize("wf_data", [{}, {"jobs": {}}, {"jobs": ["a"]}])
def test_detector_refuses_a_workflow_with_no_jobs(
    wf_data: dict[str, Any],
) -> None:
    with pytest.raises(AssertionError, match=r"x\.yml has no non-empty"):
        _uncapped_jobs("x.yml", wf_data)


def test_discovery_finds_every_workflow_file() -> None:
    names = {p.name for p in workflow_files()}
    # python-app.yml has the gate jobs; docs-publish-check.yml has only a
    # reusable-workflow call, so it must be read and skipped, not missed.
    assert {"python-app.yml", "docs-publish-check.yml"} <= names


def test_every_workflow_job_has_a_timeout() -> None:
    """Every job in every workflow has a ``timeout-minutes`` cap (TB-14-006).

    A job without a cap runs until GitHub's default limit, so a hung linter
    or build step holds a runner for hours and shows as ``cancelled`` in
    ``gh pr checks`` (#2076). Scheduled and issue-triggered jobs hang the same
    way with nobody watching (#5507).
    """
    missing = [
        entry
        for path in workflow_files()
        for entry in _uncapped_jobs(path.name, load_workflow(path))
    ]
    assert not missing, (
        "These workflow jobs lack a positive integer `timeout-minutes` "
        "(TB-14-006): " + ", ".join(missing)
    )
