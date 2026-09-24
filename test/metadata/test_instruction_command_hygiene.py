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
"""Ratchet: instruction files never prescribe an exit-code-masking gate command.

A shell pipeline exits with the status of its **last** stage.  So
``uv run pytest ... 2>&1 | tail -5`` reports 0 no matter how pytest exited: when
``pytest-timeout`` kills a test, the run dies non-zero and the pipeline still
says success, showing dump frames where the ``N passed`` summary line would be.
``| tee log | tail``, ``| head``, and ``| wc`` mask identically — the ``tee`` is
incidental, the trailing pipe is the defect.

This went unenforced, which is the whole reason it needed fixing twice.  Root
``AGENTS.md`` carried a "never use ``tee | tail``" rule while prescribing the
masking form 160 lines below it, and ``test/AGENTS.md`` prescribed it under a
heading marked **MUST** — 11 sites across skills, agent instructions, and
developer docs (#3518).  Prose rules that nothing checks decay back into
violations, so the rule lives here as a test.

The correct form redirects, captures ``$?`` immediately, prints it last, and
re-raises it::

    uv run pytest --tb=short > /tmp/x.log 2>&1; rc=$?; tail -5 /tmp/x.log; echo "exit: $rc"; (exit $rc)

``(exit $rc)`` is load-bearing: without it the statement still exits 0, so the
code is visible to a human reader but invisible to ``&&``, to ``set -e``, to a CI
``run:`` step, and to anything consuming a skill's ``commands:`` frontmatter.

Documentation that *quotes* the bad form to name it as the anti-pattern is
legitimate and is listed in :data:`ANTI_PATTERN_CITATIONS`.  Add an entry there
only for prose that forbids the pattern — never to excuse a command an agent is
meant to run.

See ``notes/testing-pitfalls.md`` § "A Killed ``pytest`` Run Reports Exit 0 Under
``tail -5``" and ``.agents/skills/run-tests/SKILL.md`` § Constraints.

Source: #3518 (root cause ISSUE-2232).
"""

import re
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).parents[2]

# Commands whose exit status is a gate: a wrong answer must fail the build.
_GATE_COMMANDS = (
    "pytest",
    "mkdocs build",
    "flake8",
    "mypy",
    "pyright",
    "markdownlint",
)

# A gate command whose output is piped onward, discarding its exit status.
_MASKING_PIPE = re.compile(
    r"uv run (?:[A-Za-z0-9_=-]+ )*(?:" + "|".join(_GATE_COMMANDS) + r")"
    r"[^\n`]*?\|\s*(?:tee|tail|head|wc)\b"
)

# Files that instruct an agent or a developer how to run this repo's gates.
_INSTRUCTION_GLOBS = (
    "AGENTS.md",
    "*/AGENTS.md",
    "*/*/AGENTS.md",
    "*/*/*/AGENTS.md",
    ".agents/skills/**/*.md",
    ".github/copilot-instructions.md",
    "docs/developer/**/*.md",
    "notes/*.md",
)

# Prose that quotes the masking form in order to forbid it.  Key is the repo
# relative path; value is the number of such citations the file is allowed to
# contain.  Lower these freely; raising one means a real command slipped in.
ANTI_PATTERN_CITATIONS: dict[str, int] = {
    "notes/testing-pitfalls.md": 1,
}

# Archived validation records, not instructions: they must keep whatever command
# text they were written with.
_EXCLUDED_PARTS = (".git", "plan", "node_modules", ".venv", "wip_notes")


def _instruction_files() -> list[Path]:
    found: set[Path] = set()
    for glob in _INSTRUCTION_GLOBS:
        for path in _REPO_ROOT.glob(glob):
            if not path.is_file():
                continue
            parts = path.relative_to(_REPO_ROOT).parts
            if any(part in _EXCLUDED_PARTS for part in parts):
                continue
            found.add(path)
    return sorted(found)


def _masking_lines(path: Path) -> list[tuple[int, str]]:
    text = path.read_text(encoding="utf-8")
    return [
        (lineno, line.strip())
        for lineno, line in enumerate(text.splitlines(), start=1)
        if _MASKING_PIPE.search(line)
    ]


def test_discovery_finds_the_known_instruction_files() -> None:
    """Discovery MUST be non-empty and include the files that regressed.

    ``_instruction_files()`` feeds the parametrize list below.  An empty or
    truncated list turns every per-file assertion into a *skip* rather than a
    failure, which would silently delete this ratchet while leaving CI green —
    the same class of quiet failure the ratchet itself exists to catch.
    """
    found = {str(p.relative_to(_REPO_ROOT)) for p in _instruction_files()}
    assert found, (
        "No instruction files discovered — this ratchet would collapse to a "
        "skip. Check _INSTRUCTION_GLOBS, _EXCLUDED_PARTS, and the repo layout."
    )
    expected = {
        "AGENTS.md",
        "test/AGENTS.md",
        ".agents/skills/run-tests/SKILL.md",
        ".agents/skills/build/SKILL.md",
        ".agents/skills/create-pr/SKILL.md",
        ".agents/skills/pr-execute/SKILL.md",
        ".github/copilot-instructions.md",
        "docs/developer/how-to/run-tests.md",
        "notes/testing-pitfalls.md",
    }
    assert (
        expected <= found
    ), f"Discovery missed known files: {expected - found}"


def test_masking_pipe_regex_matches_the_forms_that_regressed() -> None:
    """The detector MUST catch every masking form found in #3518.

    A ratchet whose pattern does not match is indistinguishable from a clean
    tree.  These are the exact strings that were live in the repo, plus the
    correct form, which must not be flagged.
    """
    should_match = (
        "uv run pytest --tb=short 2>&1 | tail -5",
        'uv run pytest -m "" --tb=short 2>&1 | tail -5',
        "uv run pytest --tb=short 2>&1 | tee /tmp/pytest-unit.log | tail -20",
        "uv run pytest integration_tests/ -v 2>&1 | tee /tmp/x.log",
        "UV_NO_SYNC=1 uv run mkdocs build --strict 2>&1 | tee /tmp/b.log | tail -20",
        "uv run pytest -m integration --tb=short 2>&1 | head -30",
    )
    for command in should_match:
        assert _MASKING_PIPE.search(command), f"detector missed: {command}"

    should_not_match = (
        'uv run pytest --tb=short > /tmp/x.log 2>&1; rc=$?; tail -5 /tmp/x.log; echo "exit: $rc"; (exit $rc)',
        "uv run flake8 vultron/ test/ && uv run mypy && uv run pyright",
        "uv run black vultron/ test/",
        # grep's own status is the intended signal here, not a masked gate.
        'git merge-tree $(git merge-base HEAD main) HEAD main | grep -i "^CONFLICT" || true',
    )
    for command in should_not_match:
        assert not _MASKING_PIPE.search(
            command
        ), f"detector false-positived: {command}"


@pytest.mark.parametrize(
    "rel_path",
    [
        pytest.param(
            str(p.relative_to(_REPO_ROOT)), id=str(p.relative_to(_REPO_ROOT))
        )
        for p in _instruction_files()
    ],
)
def test_instruction_file_has_no_masking_gate_command(rel_path: str) -> None:
    """An instruction file MUST NOT prescribe a gate command ending in a pipe."""
    path = _REPO_ROOT / rel_path
    hits = _masking_lines(path)
    allowed = ANTI_PATTERN_CITATIONS.get(rel_path, 0)

    assert len(hits) <= allowed, (
        f"{rel_path} contains {len(hits)} exit-code-masking gate command(s), "
        f"{allowed} allowed as anti-pattern citations:\n"
        + "\n".join(f"  line {lineno}: {text}" for lineno, text in hits)
        + "\n\nA pipeline exits with its last stage's status, so a killed run "
        "reads as success. Use:\n"
        '  <gate> > /tmp/x.log 2>&1; rc=$?; tail -5 /tmp/x.log; echo "exit: $rc"; (exit $rc)\n'
        "See .agents/skills/run-tests/SKILL.md § Constraints."
    )


def test_anti_pattern_citation_allowances_are_tight() -> None:
    """Each allowance MUST match the file's actual citation count.

    An allowance above the real count is slack a future edit could quietly grow
    a live masking command into — the same failure mode this ratchet exists to
    prevent, one level up.
    """
    for rel_path, allowed in ANTI_PATTERN_CITATIONS.items():
        path = _REPO_ROOT / rel_path
        assert (
            path.exists()
        ), f"ANTI_PATTERN_CITATIONS names a missing file: {rel_path}"
        actual = len(_masking_lines(path))
        assert actual == allowed, (
            f"{rel_path} is allowed {allowed} anti-pattern citation(s) but has "
            f"{actual}. Lower the ANTI_PATTERN_CITATIONS entry to {actual}."
        )
