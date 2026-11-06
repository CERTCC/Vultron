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

It also pins which tools those commands may run: a heavy one queues on the
per-host lock (#5947), and pyright does not run locally at all, because CI
owns it (PAD-18-026, PAD-18-027).

Human developer how-to pages under ``docs/developer/`` are out of scope: stock
macOS has no ``timeout`` binary.
"""

import re
from pathlib import Path
from typing import Any

import pytest

from test.ci._workflows import WORKFLOWS_DIR, load_workflow, workflow_files
from vultron.metadata.planning.heavy_lock import HEAVY_LOCK_SCRIPT
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

# The redirected gate form: ``uv run pytest ... > /tmp/x.log ...; (exit $rc)``,
# the log named by path or by a variable (``> "$log"``, ``> "$logs-unit.log"``).
_REDIRECTED_GATE = re.compile(
    r'uv run pytest[^\n`]*>\s*(?:/tmp/|"\$)[^\n`]*\(exit \$rc\)'
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


# --- The per-host heavy-check lock (#5947) ----------------------------------

#: The wrapper as written in a command.
_LOCK = "uv run python " + HEAVY_LOCK_SCRIPT

#: What every parallel gate starts with: the lock, then the ceiling, so time
#: spent waiting for a slot is not charged to the run.
_LOCKED_PREFIX = f"{_LOCK} {_CEILING} "

#: A heavy command on a line of a skill's code: one that starts many processes
#: or uses much memory.
_HEAVY_COMMAND = re.compile(
    r"uv run pyright|mkdocs build|mkdocs-build-strict\.sh|merged-tree-tests"
)


def _unlocked_parallel_gates(text: str) -> list[str]:
    return [
        match.group(0)
        for match in _REDIRECTED_GATE.finditer(text)
        if "-n auto" in match.group(0)
        and not text[: match.start()].endswith(_LOCKED_PREFIX)
    ]


def _code_lines(text: str) -> list[str]:
    """The lines of *text* an agent runs: frontmatter ``commands:`` and fences."""
    lines = text.splitlines()
    code: list[str] = []
    fenced = False
    in_frontmatter = bool(lines) and lines[0] == "---"
    in_commands = False
    for index, line in enumerate(lines):
        if in_frontmatter:
            if index and line == "---":
                in_frontmatter = False
            elif not line.startswith(" "):
                in_commands = line.startswith("commands:")
            elif in_commands:
                code.append(line)
        elif line.lstrip().startswith("```"):
            fenced = not fenced
        elif fenced:
            code.append(line)
    return code


def _unlocked_heavy_lines(text: str) -> list[str]:
    unlocked = []
    for line in _code_lines(text):
        match = _HEAVY_COMMAND.search(line)
        if match and _LOCK not in line[: match.start()]:
            unlocked.append(line.strip())
    return unlocked


def test_detector_tells_a_locked_parallel_gate_from_a_bare_one() -> None:
    gate = 'uv run pytest -n auto > "$log" 2>&1; rc=$?; echo "exit: $rc"; (exit $rc)'
    serial = gate.replace(" -n auto", "")
    assert _unlocked_parallel_gates(f"{_CEILING} {gate}") == [gate]
    assert _unlocked_parallel_gates(f"{_LOCKED_PREFIX}{gate}") == []
    assert _unlocked_parallel_gates(f"{_CEILING} {serial}") == []


def test_the_parallel_gate_scan_sees_the_skill_gates() -> None:
    # The gates log to "$log" and "$logs-*.log"; a scan that matched only a
    # literal /tmp/ path would pass having checked none of them.
    for skill in ("run-tests", "create-pr"):
        text = (_REPO_ROOT / ".agents/skills" / skill / "SKILL.md").read_text()
        assert len(list(_REDIRECTED_GATE.finditer(text))) >= 2, skill


def test_detector_reads_only_the_code_an_agent_runs() -> None:
    text = "\n".join(
        [
            "---",
            'description: "Run mkdocs build with strict validation."',
            'commands:\n  - "uv run mkdocs build --strict"',
            "inputs:\n  - mkdocs build",
            "---",
            "Confirm `uv run mkdocs build --strict` passed.",
            "```bash",
            '"$G" pyright vultron/ -- uv run pyright',
            f'"$G" pyright vultron/ -- {_LOCK} uv run pyright',
            f"{_LOCK} timeout -k 30 1800 uv run merged-tree-tests",
            "```",
            "uv run pyright",
        ]
    )
    assert _unlocked_heavy_lines(text) == [
        '- "uv run mkdocs build --strict"',
        '"$G" pyright vultron/ -- uv run pyright',
    ]


@pytest.mark.parametrize(
    "rel_path",
    [str(p.relative_to(_REPO_ROOT)) for p in _agent_files()],
)
def test_parallel_pytest_gate_queues_on_the_heavy_check_lock(
    rel_path: str,
) -> None:
    text = (_REPO_ROOT / rel_path).read_text(encoding="utf-8")
    unlocked = _unlocked_parallel_gates(text)
    assert not unlocked, (
        f"{rel_path} has `-n auto` pytest gate(s) not starting with "
        f"`{_LOCKED_PREFIX}` (#5947):\n"
        + "\n".join(f"  {cmd}" for cmd in unlocked)
    )


def _skill_files() -> list[Path]:
    return sorted((_REPO_ROOT / ".agents" / "skills").glob("**/*.md"))


def test_discovery_finds_the_skills_with_heavy_commands() -> None:
    found = {str(p.relative_to(_REPO_ROOT)) for p in _skill_files()}
    assert {
        ".agents/skills/build-docs/SKILL.md",
        ".agents/skills/pr-execute/SKILL.md",
    } <= found


# `run-linters` is not here: PAD-18-027 made pyright CI's, and nothing else
# that skill runs is heavy.
@pytest.mark.parametrize("skill", ["build-docs", "pr-execute"])
def test_the_heavy_command_scan_sees_each_skills_heavy_commands(
    skill: str,
) -> None:
    # A code form _code_lines missed would pass the scan having read nothing.
    text = (_REPO_ROOT / ".agents/skills" / skill / "SKILL.md").read_text()
    assert any(_HEAVY_COMMAND.search(line) for line in _code_lines(text))


@pytest.mark.parametrize(
    "rel_path",
    [str(p.relative_to(_REPO_ROOT)) for p in _skill_files()],
)
def test_skill_heavy_command_queues_on_the_heavy_check_lock(
    rel_path: str,
) -> None:
    unlocked = _unlocked_heavy_lines(
        (_REPO_ROOT / rel_path).read_text(encoding="utf-8")
    )
    assert not unlocked, (
        f"{rel_path} runs heavy command(s) outside `{_LOCK}` "
        "(#5947):\n" + "\n".join(f"  {line}" for line in unlocked)
    )


# --- The local linter step: ruff and mypy, never pyright (PAD-18-026/027) ---

#: How a command runs pyright, in any of the forms the skills used before
#: PAD-18-027: bare, inside `run-heavy.py`, or behind the memo wrapper. A
#: mention of `pyrightconfig.json` or of a `# pyright: ignore[...]` pragma is
#: not an invocation and does not match.
_PYRIGHT_INVOCATION = re.compile(r'uv run pyright\b|"\$G" pyright\b')


def test_detector_tells_a_pyright_invocation_from_a_mention() -> None:
    for command in (
        "uv run pyright",
        "uv run python .agents/skills/shared/run-heavy.py uv run pyright",
        '"$G" pyright vultron/ test/ pyrightconfig.json uv.lock -- uv run pyright',
    ):
        assert _PYRIGHT_INVOCATION.search(command), f"missed: {command}"
    for prose in (
        "pyright runs in CI only (PAD-18-027)",
        "a stranded `# pyright: ignore[...]`",
        "pyrightconfig.json is an input of CI's pyright job",
    ):
        assert not _PYRIGHT_INVOCATION.search(prose), f"flagged: {prose}"


@pytest.mark.spec("PAD-18-027")
@pytest.mark.parametrize(
    "rel_path",
    [str(p.relative_to(_REPO_ROOT)) for p in _agent_files()],
)
def test_no_local_gate_runs_pyright(rel_path: str) -> None:
    """CI's `lint-pyright` job owns pyright; no local gate may run it.

    It took a median of two minutes in each local linter step and enough
    memory to starve a parallel test run, and the required `CI gate` refuses
    a merge until CI's job is green (PAD-18-027, #3156).
    """
    text = (_REPO_ROOT / rel_path).read_text(encoding="utf-8")
    found = [
        line.strip()
        for line in text.splitlines()
        if _PYRIGHT_INVOCATION.search(line)
    ]
    assert not found, (
        f"{rel_path} runs pyright locally (PAD-18-027):\n"
        + "\n".join(f"  {line}" for line in found)
    )


@pytest.mark.spec("PAD-18-026")
def test_the_linter_skill_runs_ruff_and_mypy() -> None:
    # The other half of the rule: dropping pyright must not leave the step
    # with nothing, which `test_no_local_gate_runs_pyright` alone would pass.
    code = "\n".join(
        _code_lines(
            (_REPO_ROOT / ".agents/skills/run-linters/SKILL.md").read_text(
                encoding="utf-8"
            )
        )
    )

    assert "uv run ruff check" in code
    assert "uv run ruff format" in code
    assert "uv run mypy" in code


def _python_app_jobs() -> dict[str, object]:
    jobs = load_workflow(WORKFLOWS_DIR / "python-app.yml")["jobs"]
    assert isinstance(jobs, dict)
    return jobs


def test_ci_test_job_has_a_timeout() -> None:
    job = _python_app_jobs()["test"]
    assert isinstance(job, dict)
    minutes = job.get("timeout-minutes")
    assert isinstance(minutes, int) and minutes > 0, (
        "The `test` job that runs pytest needs `timeout-minutes`; the cap is "
        "on the job, so every matrix part carries it (TB-14-005)."
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
            "null": None,
        }
    }
    assert _uncapped_jobs("x.yml", wf_data) == [
        "x.yml:uncapped",
        "x.yml:zero",
        "x.yml:boolean",
        "x.yml:null",
    ]


@pytest.mark.parametrize("wf_data", [{}, {"jobs": {}}, {"jobs": ["a"]}])
def test_detector_refuses_a_workflow_with_no_jobs(
    wf_data: dict[str, Any],
) -> None:
    with pytest.raises(AssertionError, match=r"x\.yml has no non-empty"):
        _uncapped_jobs("x.yml", wf_data)


def test_discovery_finds_every_workflow_file() -> None:
    names = {p.name for p in workflow_files()}
    # python-app.yml has the gate jobs and deploy_site.yml the deploy. A job
    # that only calls a reusable workflow is skipped, not missed: see
    # test_detector_flags_an_uncapped_job_and_skips_a_reusable_call.
    assert {"python-app.yml", "deploy_site.yml"} <= names


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
