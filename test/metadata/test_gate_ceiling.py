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
"""The rules over the commands written for agents, and over the CI test job.

A per-test ``signal`` timeout cannot reach a C call that holds the GIL or a
stuck xdist controller, so the outer ceiling is the only thing that ends such
a run (TB-14-005, #4809).  The printed ``targeted-tests --pytest`` command is
pinned in ``test_targeted_tests.py``; this module pins the written commands
an agent copies and the CI test job, and the ``timeout-minutes`` cap on every
job in every workflow (TB-14-006).  A heavy command queues on the per-host
lock (#5947).  No command runs a test on a merge in a checkout the agent does
not commit, which is where a scratch merge has to live (PAD-18-024), and the
conflict check that replaced one asks git for a trial merge (PAD-18-025).

Loose readings here, with the direction each is loose in, because a docstring
that claims one-sidedness for all of them stops anyone looking
(``notes/architecture-ratchet-corpus.md``):

- ``_BUILDS_A_CHECKOUT`` matches ``worktree add``, the way such a checkout is
  built, rather than the test run that is the act itself.  It **misses** one
  built another way -- a clone, or ``git worktree`` split over a backslash
  continuation -- and one in a shell script outside
  :func:`_scratch_checkout_corpus` (``.github/scripts``, the repository root,
  ``.devcontainer``) or in a module outside :func:`_tooling_modules`.
  Markdown prose and inline code are missed on purpose: reading them would
  **invent** a violation out of a sentence forbidding one.  It can still
  invent from a Python docstring, or from a shell line that only prints the
  command, both of which read as runnable here.
- ``_RUNS_A_TEST`` and ``_REWRITES_THE_WORKTREE`` match command names, so they
  miss a test run or a merge reached through a wrapper this module does not
  name.  No agent-facing file holds such a wrapper today.

It also pins which tools those commands may run: a heavy one queues on the
per-host lock (#5947), and pyright does not run locally at all, because CI
owns it (PAD-18-026, PAD-18-027).

Human developer how-to pages under ``docs/developer/`` are out of scope: stock
macOS has no ``timeout`` binary.
"""

import ast
import re
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import pytest

from test.ci._workflows import WORKFLOWS_DIR, load_workflow, workflow_files
from vultron.metadata.planning.heavy_lock import HEAVY_LOCK_SCRIPT
from vultron.metadata.planning.targeted_tests import GATE_CEILING

_REPO_ROOT = Path(__file__).parents[2]

_CEILING = " ".join(GATE_CEILING)

# Files an agent reads for the gate command to run. `**/AGENTS.md` rather than
# one glob per path depth: four hand-rolled levels left ten nested AGENTS.md
# files scanned by nothing. The skills' scripts and the Makefile count too —
# each is somewhere a gate command does live.
_AGENT_GLOBS = (
    "**/AGENTS.md",
    ".agents/skills/**/*.md",
    ".agents/skills/**/*.sh",
    ".agents/skills/**/*.py",
    ".github/copilot-instructions.md",
    "docs/reference/codebase/*.md",
    "notes/*.md",
    "Makefile",
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
        # Four levels deep: `**/AGENTS.md` reaches it, a per-depth glob list
        # stopped short of it.
        "vultron/core/behaviors/case/nodes/participant/AGENTS.md",
        ".agents/skills/run-tests/SKILL.md",
        # A gate command lives in a skill's scripts as much as in its prose.
        ".agents/skills/shared/run-if-changed.sh",
        ".agents/skills/shared/run-heavy.py",
        ".github/copilot-instructions.md",
        "docs/reference/codebase/TESTING.md",
        "notes/testing-pitfalls.md",
        "Makefile",
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
    r"uv run pyright|mkdocs build|mkdocs-build-strict\.sh"
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
            f"{_LOCKED_PREFIX}.github/scripts/mkdocs-build-strict.sh",
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


#: The skills that still write a heavy command, so the scan below has a
#: subject. `run-linters` left when PAD-18-027 made pyright CI's, and
#: `pr-execute` when PAD-18-024 dropped the scratch-merge test run: between
#: them those two removals took every heavy command that skill had. Only
#: `build-docs` is left, and a scan over an empty set would pass having read
#: nothing (#5535), which is what the arm below exists to refuse.
_SKILLS_WITH_HEAVY_COMMANDS = (".agents/skills/build-docs/SKILL.md",)


def test_discovery_finds_the_skills_with_heavy_commands() -> None:
    found = {str(p.relative_to(_REPO_ROOT)) for p in _skill_files()}

    assert _SKILLS_WITH_HEAVY_COMMANDS, (
        "No skill writes a heavy command, so the scan below has no subject. "
        "Delete it and `_HEAVY_COMMAND` with it, or restore the entry."
    )
    assert set(_SKILLS_WITH_HEAVY_COMMANDS) <= found


@pytest.mark.parametrize("rel_path", _SKILLS_WITH_HEAVY_COMMANDS)
def test_the_heavy_command_scan_sees_each_skills_heavy_commands(
    rel_path: str,
) -> None:
    # A code form _code_lines missed would pass the scan having read nothing.
    text = (_REPO_ROOT / rel_path).read_text(encoding="utf-8")
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

#: The tool named in a command, however it is launched. Keyed on the tool, not
#: on one launcher: a pattern matching only `uv run pyright` would miss
#: `uvx pyright`, `-m pyright`, a `make` recipe's bare `pyright`, and the
#: escaped `\"$G\" pyright` a skill's YAML `commands:` key has to write (#5535).
#: `pyrightconfig.json` and a `# pyright: ignore[...]` pragma are not calls.
_PYRIGHT_TOOL = re.compile(r"(?<![\w./-])pyright(?![\w:])")

#: The copy-pasteable form, wherever it is written: prose that spells a command
#: out is prose an agent copies from, fence or no fence.
_PYRIGHT_LAUNCHED = re.compile(
    r"(?:uv run|uvx|uv tool run)\s+(?:[-\w./]+\s+)*?pyright(?![\w:])"
)


def _uncommented(line: str) -> str:
    """*line* up to its `#`: a comment inside a fence names the tool, never runs it."""
    return line.split("#", 1)[0]


def _python_code_lines(text: str) -> list[str]:
    """*text*'s lines, less its docstrings.

    A module that names the tool in its own prose does not run it, the same
    allowance Markdown prose gets. A ``["pyright"]`` argv is *not* excluded:
    only a docstring is, never every string literal.
    """
    lines = text.splitlines()
    try:
        tree = ast.parse(text)
    except SyntaxError:  # pragma: no cover - the corpus parses
        return lines
    prose: set[int] = set()
    holders = (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
    for node in ast.walk(tree):
        if not isinstance(node, holders) or not node.body:
            continue
        first = node.body[0]
        if (
            isinstance(first, ast.Expr)
            and isinstance(first.value, ast.Constant)
            and isinstance(first.value.value, str)
            and first.end_lineno is not None
        ):
            prose.update(range(first.lineno, first.end_lineno + 1))
    return [line for n, line in enumerate(lines, 1) if n not in prose]


def _executable_lines(text: str, suffix: str) -> list[str]:
    """The lines of *text* an agent runs, by what kind of file it is.

    A Markdown file's code is its fences and its frontmatter ``commands:``
    key. A file that is *not* Markdown — a skill's ``.sh`` or ``.py``, the
    ``Makefile`` — is code throughout, bar a Python docstring. Asking
    ``_code_lines`` for those returned nothing, which left the
    launcher-agnostic half of the pyright detector dead on all 32 of them,
    including the ``make`` recipe its own comment names (#3156, #5535).
    """
    if suffix == ".md":
        return _code_lines(text)
    if suffix == ".py":
        return _python_code_lines(text)
    return text.splitlines()


def _pyright_calls(text: str, *, suffix: str = ".md") -> list[str]:
    """Lines of *text* that call pyright: any launcher in code, spelled out anywhere."""
    code = set(_executable_lines(text, suffix))
    return [
        line.strip()
        for line in text.splitlines()
        if _PYRIGHT_LAUNCHED.search(_uncommented(line))
        or (line in code and _PYRIGHT_TOOL.search(_uncommented(line)))
    ]


def test_detector_tells_a_pyright_call_from_a_mention() -> None:
    fenced = "\n".join(["```bash", "%s", "```"])
    for command in (
        "uv run pyright",
        "uv run python .agents/skills/shared/run-heavy.py uv run pyright",
        '"$G" pyright vultron/ test/ pyrightconfig.json uv.lock -- uv run pyright',
        "uvx pyright",
        "uv tool run pyright",
    ):
        assert _pyright_calls(command), f"missed outside a fence: {command}"
    # Launchers that need the code-line scan: no `uv run` to key on.
    for command in (
        "pyright vultron/ test/",
        "\tpyright",
        "python -m pyright",
    ):
        assert _pyright_calls(fenced % command), (
            f"missed in a fence: {command}"
        )
    # The YAML `commands:` key a skill's harness runs, escaped quotes and all.
    frontmatter = '---\ncommands:\n  - "\\"$G\\" pyright vultron/ -- uv run pyright"\n---\n'
    assert _pyright_calls(frontmatter), "missed the commands: key"
    for prose in (
        "pyright runs in CI only (PAD-18-027)",
        "read its findings off CI's `Lint (pyright)` job",
        "a stranded `# pyright: ignore[...]`",
        "pyrightconfig.json is an input of CI's pyright job",
        "CI's `lint-pyright` job owns it",
        # A comment inside a fence names the tool; it does not run it.
        fenced % "# pyright is the second pass, and runs in CI",
        fenced % "uv run mypy  # not pyright: that is CI's",
    ):
        assert not _pyright_calls(prose), f"flagged prose: {prose}"


def test_detector_reads_a_non_markdown_file_as_code_throughout() -> None:
    """A `.sh`, a `.py` and the `Makefile` have no fence to look inside.

    32 of the corpus's 260 files are one of those three, and asking
    ``_code_lines`` for their code returned nothing — so every launcher but
    ``uv run``/``uvx``/``uv tool run`` went unseen there, including the
    ``make`` recipe ``_PYRIGHT_TOOL``'s own comment names (#3156).
    """
    for suffix, script in (
        ("", "pyright:\n\tpyright vultron/ test/\n"),  # a Makefile recipe
        (".sh", "#!/bin/bash\npyright vultron/\n"),
        (".sh", "#!/bin/bash\nnpx pyright\n"),
        (".sh", "python -m pyright\n"),
        (".py", 'subprocess.run(["pyright", "vultron/"], check=True)\n'),
    ):
        assert _pyright_calls(script, suffix=suffix), (
            f"missed in a {suffix or 'Makefile'}: {script!r}"
        )
    # The same text read as Markdown is prose, and must not be flagged there.
    assert not _pyright_calls("pyright:\n\tpyright vultron/ test/\n")
    # A comment names the tool, and so does a module's own docstring; neither
    # runs it. A docstring is the only string a `.py` read excludes.
    for suffix, benign in (
        ("", "# No pyright target: CI's Lint (pyright) job owns pyright.\n"),
        (".sh", "#!/bin/bash\nuv run mypy  # pyright is CI's\n"),
        (".py", '"""Sizes a pyright run or a site build."""\nx = 1\n'),
        (".py", 'def f():\n    """pyright is CI\'s."""\n    return 1\n'),
    ):
        assert not _pyright_calls(benign, suffix=suffix), (
            f"flagged a mention in a {suffix or 'Makefile'}: {benign!r}"
        )


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

    The bar is the written command, not the word: an agent-instruction file
    that spells a pyright call out is a file an agent copies from, whatever the
    surrounding prose says, and inside a code line any launcher counts. Prose
    that names CI as pyright's owner is the wording this project wants, so it
    passes. A developer how-to under ``docs/developer/`` may spell the command
    for a by-hand run, and is out of this module's scope.
    """
    path = _REPO_ROOT / rel_path
    found = _pyright_calls(
        path.read_text(encoding="utf-8"), suffix=path.suffix
    )
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


# --- No test run on a scratch merge (PAD-18-024) ----------------------------

#: A pinned exemption set, not a ratchet: every throwaway checkout an agent is
#: told to make, with why it is allowed, so an entry is not read as open debt
#: (ARCH-18-005). `work-epic-tasks` step 4 reads a pushed PR's head when the
#: PR's own worktree is gone. What it may not do there is run a test on a
#: merge, which :func:`test_a_declared_scratch_checkout_runs_no_test` checks
#: rather than take on trust (PAD-18-009, PAD-18-024).
# permanent: PAD-18-009 — the merger has to read the head it is about to
# merge, so this checkout never retires.
_SCRATCH_CHECKOUT_EXEMPTIONS = {
    ".agents/skills/work-epic-tasks/SKILL.md": [
        "git fetch origin <head_ref> && git worktree add --detach "
        "/tmp/wt-<issue> FETCH_HEAD",
    ],
}

#: A line that runs tests. `targeted-tests` is absent on purpose: it selects
#: and prints, and PAD-18-025's own verification rests on it running none.
_RUNS_A_TEST = re.compile(r"\bpytest\b|\beval \"\$gate\"")

#: A merge that writes a worktree, as `git merge-tree` does not (PAD-18-025).
_REWRITES_THE_WORKTREE = re.compile(r"\bgit merge\b(?!-tree)")

#: ``worktree add``, however it is spelled: a shell command, or the argv items
#: of a :mod:`subprocess` call, where the two words are separate strings. The
#: deleted runner used the second form (``merged_tree.py`` on the base), so a
#: matcher that read only the first would not see it come back.
_BUILDS_A_CHECKOUT = re.compile(r"\bworktree\b[\s,\"']+add\b")


def _scratch_checkout_corpus() -> list[Path]:
    """Where the command arms look: the agent docs, plus the scripts they call.

    ``sync-decision.sh`` holds one of the two conflict checks PAD-18-025
    constrains, so a shell script is as much a place an agent builds a
    checkout as a skill's fenced command is. A checkout built by the tooling
    rather than by a written command is asked about separately, by
    :func:`test_no_tooling_module_builds_a_checkout`.
    """
    return _agent_files() + sorted(
        (_REPO_ROOT / ".agents" / "skills").glob("**/*.sh")
    )


def _tooling_modules() -> list[Path]:
    """Every module behind a console script an agent runs.

    ``vultron/metadata/`` is where they all live
    (``vultron/metadata/AGENTS.md``), which is where the runner this arm
    replaced kept its scratch worktree.
    """
    return sorted((_REPO_ROOT / "vultron" / "metadata").glob("**/*.py"))


def _runnable_lines(path: Path) -> list[str]:
    """The lines of *path* an agent runs: a script's or module's statements,
    or a Markdown file's frontmatter ``commands:`` and fenced blocks."""
    text = path.read_text(encoding="utf-8")
    if path.suffix in {".sh", ".py"}:
        return [
            line
            for line in text.splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        ]
    return _code_lines(text)


def _command_blocks(path: Path) -> list[list[str]]:
    """The runnable lines of *path*, grouped as an agent meets them.

    One group per fenced block in Markdown, so a line can be read against the
    others it runs beside; a script or module is one group.
    """
    text = path.read_text(encoding="utf-8")
    if path.suffix in {".sh", ".py"}:
        return [_runnable_lines(path)]
    blocks: list[list[str]] = []
    fenced = False
    for line in text.splitlines():
        if line.lstrip().startswith("```"):
            fenced = not fenced
            if fenced:
                blocks.append([])
        elif fenced:
            blocks[-1].append(line)
    return [block for block in blocks if block]


def _scratch_checkouts(lines: Iterable[str]) -> list[str]:
    """The given lines that build a checkout nothing commits to.

    Keyed on ``worktree add``, the way one is built, rather than on the name
    of any runner, so a runner re-added under a new name is still caught. See
    this module's docstring for what the reading misses and where it can
    invent.
    """
    return [line.strip() for line in lines if _BUILDS_A_CHECKOUT.search(line)]


def test_detector_reads_a_scratch_checkout_only_from_runnable_code(
    tmp_path: Path,
) -> None:
    line = "git worktree add --detach /tmp/x HEAD"
    doc = tmp_path / "SKILL.md"
    doc.write_text(f"Never run `{line}`.\n\n```bash\n{line}\n```\n")
    script = tmp_path / "s.sh"
    script.write_text(f"# never: {line}\n{line}\n")

    assert _scratch_checkouts(_runnable_lines(doc)) == [line]
    assert _scratch_checkouts(_runnable_lines(script)) == [line]


def test_detector_reads_a_test_run_beside_the_checkout_that_holds_it(
    tmp_path: Path,
) -> None:
    doc = tmp_path / "SKILL.md"
    doc.write_text(
        "```bash\ngit worktree add --detach /tmp/x HEAD\n```\n\n"
        "```bash\nuv run pytest -n auto\n```\n"
    )

    blocks = [b for b in _command_blocks(doc) if _scratch_checkouts(b)]

    # One block per fence, so a test run in a *different* block is not read
    # as running in the checkout.
    assert blocks == [["git worktree add --detach /tmp/x HEAD"]]
    assert not [ln for ln in blocks[0] if _RUNS_A_TEST.search(ln)]
    assert _RUNS_A_TEST.search("uv run pytest -n auto")
    assert not _RUNS_A_TEST.search("uv run targeted-tests --overlap")
    assert _REWRITES_THE_WORKTREE.search("git merge origin/main --no-commit")
    assert not _REWRITES_THE_WORKTREE.search("git merge-tree --write-tree")


def test_the_scratch_checkout_corpus_holds_every_shape() -> None:
    found = {
        str(p.relative_to(_REPO_ROOT)) for p in _scratch_checkout_corpus()
    }
    tooling = {str(p.relative_to(_REPO_ROOT)) for p in _tooling_modules()}

    assert {
        ".agents/skills/work-epic-tasks/SKILL.md",
        ".agents/skills/shared/sync-decision.sh",
    } <= found
    assert {
        "vultron/metadata/planning/ci_mirror/_run.py",
        "vultron/metadata/planning/targeted_tests/selection.py",
    } <= tooling


def test_detector_reads_a_checkout_from_either_spelling() -> None:
    # The deleted runner passed argv items, so the two words were separate
    # strings on separate lines; a written command has them adjacent.
    assert _BUILDS_A_CHECKOUT.search("git worktree add --detach /tmp/x HEAD")
    assert _BUILDS_A_CHECKOUT.search("git worktree  add --detach /tmp/x HEAD")
    assert _BUILDS_A_CHECKOUT.search('"worktree",\n            "add",')
    assert not _BUILDS_A_CHECKOUT.search("git worktree remove --force /tmp/x")
    assert not _BUILDS_A_CHECKOUT.search("adds a detached scratch worktree")


@pytest.mark.spec("PAD-18-024")
def test_no_tooling_module_builds_a_checkout() -> None:
    """No console script an agent runs builds a checkout of its own.

    The deleted runner built one here rather than in a written command, so a
    guard that read only the skills would not see it come back. Read over the
    whole module, because the argv items can sit on separate lines.
    """
    offenders = {}
    for path in _tooling_modules():
        joined = "\n".join(_runnable_lines(path))
        if hits := _BUILDS_A_CHECKOUT.findall(joined):
            offenders[str(path.relative_to(_REPO_ROOT))] = len(hits)

    assert offenders == {}, (
        "A module behind a console script builds a checkout the agent does "
        "not commit. Running tests on a merge in one is what PAD-18-024 "
        "forbids, and CI tests that merge on every push. Use "
        "`git merge-tree` for a conflict check (PAD-18-025).\n"
        f"  found: {offenders}"
    )


@pytest.mark.spec("PAD-18-024")
def test_only_a_declared_agent_command_builds_a_scratch_checkout() -> None:
    found = {
        str(path.relative_to(_REPO_ROOT)): lines
        for path in _scratch_checkout_corpus()
        if (lines := _scratch_checkouts(_runnable_lines(path)))
    }

    assert found == _SCRATCH_CHECKOUT_EXEMPTIONS, (
        "An agent is told to build a checkout it does not commit. A test run "
        "in one is a scratch-merge run, which PAD-18-024 forbids: CI tests "
        "the merge on every push. Add the command to "
        "`_SCRATCH_CHECKOUT_EXEMPTIONS` with why it merges and tests nothing, "
        f"or remove it.\n  found: {found}"
    )


@pytest.mark.spec("PAD-18-024")
def test_a_declared_scratch_checkout_runs_no_test() -> None:
    """Being declared exempt buys the checkout, never a test run in it.

    The act PAD-18-024 forbids is the test run, so the exemption above is
    conditional: each block that builds such a checkout is read for a test
    run and for a merge that writes the worktree it was built in.
    """
    examined: list[str] = []
    offenders: dict[str, list[str]] = {}
    for path in _scratch_checkout_corpus():
        rel = str(path.relative_to(_REPO_ROOT))
        for block in _command_blocks(path):
            if not _scratch_checkouts(block):
                continue
            examined.append(rel)
            offenders.setdefault(rel, []).extend(
                line.strip()
                for line in block
                if _RUNS_A_TEST.search(line)
                or _REWRITES_THE_WORKTREE.search(line)
            )

    assert examined, (
        "No block builds a checkout the agent does not commit, so this arm "
        "has no subject. Either the declared exemption left "
        "`_SCRATCH_CHECKOUT_EXEMPTIONS` — delete this arm with it — or the "
        "detector stopped reading it."
    )
    assert not any(offenders.values()), (
        "A checkout the agent does not commit runs a test, or takes a merge "
        "that writes it. That is the scratch-merge run PAD-18-024 forbids: "
        "CI tests the merge of the branch with its base on every push. Use "
        "`git merge-tree` for a conflict check (PAD-18-025) and leave the "
        f"testing to CI.\n  found: { {k: v for k, v in offenders.items() if v} }"
    )


@pytest.mark.spec("PAD-18-025")
@pytest.mark.parametrize(
    "rel_path",
    [
        ".agents/skills/shared/sync-decision.sh",
        ".agents/skills/work-epic-tasks/SKILL.md",
    ],
)
def test_the_conflict_check_is_a_trial_merge(rel_path: str) -> None:
    # The compliant form that replaced the scratch merge, so this arm stays
    # non-empty: both conflict checks ask git for a merge that writes no
    # worktree and moves no branch. Read from the runnable lines, so a
    # mention in a comment or in prose cannot stand in for the call.
    lines = _runnable_lines(_REPO_ROOT / rel_path)

    assert [line for line in lines if "git merge-tree" in line], (
        f"{rel_path} runs no `git merge-tree`. A conflict check must use a "
        "trial merge that moves no branch and writes no worktree "
        "(PAD-18-025)."
    )
    assert not [
        line.strip() for line in lines if _REWRITES_THE_WORKTREE.search(line)
    ], (
        f"{rel_path} checks for a conflict with a merge that writes the worktree."
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
