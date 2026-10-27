"""CI verification test — every docs source gate runs in CI on a docs-only PR.

Implements DOCBW-03-013 from ``specs/docs-build-workflow.yaml`` (#5084).

The docs source gates (``docs-frontmatter``, ``docs-normative-banner`` and the
rest) are pre-commit hooks, and no workflow runs pre-commit. Their
committed-tree tests run in ``python-app.yml``, whose path filter does not
cover ``docs/**``, so a pull request that changed only ``docs/`` and broke a
page's frontmatter merged green.

The hook set is derived from ``.pre-commit-config.yaml`` rather than listed
here, so a new docs gate added to pre-commit fails this test until a workflow
runs it too. A hook qualifies when it checks the whole tree
(``pass_filenames: false``) and its ``files:`` pattern matches a file under
``docs/``. For every such file, some workflow whose ``pull_request`` trigger
fires on that file must run the hook's command.
"""

from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass
from functools import cache
from typing import Any

import pytest
import yaml

from test.ci._workflows import (
    MKDOCS_BUILD,
    REPO_ROOT,
    WORKFLOWS_DIR,
    load_workflow,
    steps,
    triggers,
)

PRE_COMMIT_CONFIG = REPO_ROOT / ".pre-commit-config.yaml"
DOCS_DIR = REPO_ROOT / "docs"
REVIEW_WORKFLOW = WORKFLOWS_DIR / "docs-build-check.yml"

# A hook whose own command no workflow runs, and the command that checks the
# same thing in CI. ``validate-adr-frontmatter`` only loads the ADR registry,
# which ``index_gen --check`` also does, and fails on the same bad frontmatter.
COVERED_BY = {
    "validate-adr-frontmatter": "vultron.metadata.adr.index_gen --check",
}

# An ``if:`` that still runs the step after an earlier step failed.
RUN_EVEN_AFTER_FAILURE = frozenset({"${{ !cancelled() }}", "!cancelled()"})


@dataclass(frozen=True)
class Hook:
    """A tree-wide pre-commit hook, and the commands that count as running it."""

    id: str
    files: re.Pattern[str]
    exclude: re.Pattern[str] | None
    commands: tuple[str, ...]

    def matches(self, rel_path: str) -> bool:
        if not self.files.search(rel_path):
            return False
        return self.exclude is None or not self.exclude.search(rel_path)


@cache
def _console_scripts() -> dict[str, str]:
    """Map each ``module:main`` target in pyproject.toml to its script name."""
    data = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text("utf-8"))
    scripts = data.get("project", {}).get("scripts", {})
    return {
        target.removesuffix(":main"): name
        for name, target in scripts.items()
        if target.endswith(":main")
    }


def _commands(hook_id: str, entry: str) -> tuple[str, ...]:
    """Return every spelling of the hook's command that a workflow may run.

    ``uv run python -m vultron.metadata.docs.page_frontmatter`` and
    ``uv run docs-frontmatter`` run the same code, so both count.
    """
    if hook_id in COVERED_BY:
        return (COVERED_BY[hook_id],)
    command = entry.removeprefix("uv run ").strip()
    found = [command]
    match = re.fullmatch(r"python -m (\S+)(.*)", command)
    if match and match.group(1) in _console_scripts():
        found.append(_console_scripts()[match.group(1)] + match.group(2))
    return tuple(found)


@cache
def _tree_wide_hooks() -> tuple[Hook, ...]:
    config = yaml.safe_load(PRE_COMMIT_CONFIG.read_text(encoding="utf-8"))
    hooks: list[Hook] = []
    for repo in config.get("repos", []):
        for hook in repo.get("hooks", []):
            if hook.get("pass_filenames", True) or "files" not in hook:
                continue
            exclude = hook.get("exclude")
            hooks.append(
                Hook(
                    id=hook["id"],
                    files=re.compile(hook["files"]),
                    exclude=re.compile(exclude) if exclude else None,
                    commands=_commands(hook["id"], str(hook.get("entry", ""))),
                )
            )
    return tuple(hooks)


@cache
def _docs_files() -> tuple[str, ...]:
    return tuple(
        sorted(
            p.relative_to(REPO_ROOT).as_posix()
            for p in DOCS_DIR.rglob("*")
            if p.is_file()
        )
    )


def _docs_hooks() -> list[Hook]:
    """Return every tree-wide hook whose pattern matches a ``docs/`` file."""
    return [
        hook
        for hook in _tree_wide_hooks()
        if any(hook.matches(f) for f in _docs_files())
    ]


def _glob_regex(pattern: str) -> re.Pattern[str]:
    """Translate a GitHub Actions path glob to a regex.

    ``*`` and ``?`` stop at ``/``; ``**`` crosses it, and ``**/`` also matches
    no directory at all, as GitHub's filter does.
    """
    out = ""
    i = 0
    while i < len(pattern):
        if pattern.startswith("**/", i):
            out += "(?:.*/)?"
            i += 3
        elif pattern.startswith("**", i):
            out += ".*"
            i += 2
        elif pattern[i] == "*":
            out += "[^/]*"
            i += 1
        elif pattern[i] == "?":
            out += "[^/]"
            i += 1
        else:
            out += re.escape(pattern[i])
            i += 1
    return re.compile(out)


def _fires_on(event: Any, rel_path: str) -> bool:
    """Return whether a ``pull_request`` trigger block fires on *rel_path*."""
    if not isinstance(event, dict):
        return True  # A bare `pull_request:` has no path filter.
    if "paths" in event:
        return any(
            _glob_regex(str(p)).fullmatch(rel_path)
            for p in event["paths"]
            if not str(p).startswith("!")
        )
    if "paths-ignore" in event:
        return not any(
            _glob_regex(str(p)).fullmatch(rel_path)
            for p in event["paths-ignore"]
        )
    return True


@cache
def _pull_request_workflows() -> tuple[tuple[str, Any, str], ...]:
    """Return (name, pull_request block, step text) for each PR workflow."""
    found = []
    for path in sorted(WORKFLOWS_DIR.glob("*.yml")):
        data = load_workflow(path)
        on = triggers(data)
        if "pull_request" not in on:
            continue
        text = "\n".join(
            f"{s.get('run', '')}\n{s.get('uses', '')}" for s in steps(data)
        )
        found.append((path.name, on["pull_request"], text))
    return tuple(found)


def _runs(text: str, hook: Hook) -> bool:
    return any(command in text for command in hook.commands)


def test_the_hook_set_is_not_empty():
    """Guard the derivation: an empty target set must fail (DF-09-009)."""
    ids = {hook.id for hook in _docs_hooks()}
    assert {
        "validate-docs-page-frontmatter",
        "docs-normative-banner",
    } <= ids, (
        "The docs hooks derived from .pre-commit-config.yaml do not include "
        f"the two this test exists for; found {sorted(ids)}. The derivation "
        "is broken, so every check below is vacuous."
    )


@pytest.mark.spec("DOCBW-03-013")
@pytest.mark.parametrize("hook", _docs_hooks(), ids=lambda h: h.id)
def test_a_docs_only_pull_request_runs_the_hook(hook: Hook):
    """Every ``docs/`` file the hook judges triggers a workflow that runs it."""
    uncovered = [
        rel_path
        for rel_path in _docs_files()
        if hook.matches(rel_path)
        and not any(
            _fires_on(event, rel_path) and _runs(text, hook)
            for _, event, text in _pull_request_workflows()
        )
    ]
    assert not uncovered, (
        f"No workflow runs the '{hook.id}' pre-commit hook "
        f"({' or '.join(hook.commands)!r}) on a pull request that changes "
        f"{len(uncovered)} docs file(s) it checks, e.g. {uncovered[:3]}. "
        "No workflow runs pre-commit, so such a pull request merges green "
        "whatever the hook would say (DOCBW-03-013, #5084)."
    )


def _review_gate_indexes() -> list[int]:
    wf_steps = steps(load_workflow(REVIEW_WORKFLOW))
    return [
        i
        for i, step in enumerate(wf_steps)
        if any(_runs(str(step.get("run", "")), h) for h in _docs_hooks())
    ]


@pytest.mark.spec("DOCBW-03-013")
def test_review_workflow_gates_precede_the_build_and_do_not_stop_it():
    """A failed gate fails the job, but still lets the build report."""
    wf_steps = steps(load_workflow(REVIEW_WORKFLOW))
    build = next(
        i
        for i, s in enumerate(wf_steps)
        if MKDOCS_BUILD in str(s.get("run", ""))
    )
    gates = _review_gate_indexes()
    assert gates, (
        f"{REVIEW_WORKFLOW.name} runs no docs source gate (DF-09-009)."
    )
    problems = [
        f"'{wf_steps[i].get('name')}' runs after the build"
        for i in gates
        if i > build
    ]
    problems += [
        f"'{wf_steps[i].get('name')}' sets continue-on-error"
        for i in gates
        if wf_steps[i].get("continue-on-error", False)
    ]
    problems += [
        f"'{wf_steps[i].get('name')}' does not run after an earlier gate fails "
        f"(if: {wf_steps[i].get('if')!r})"
        for i in [*gates[1:], build]
        if wf_steps[i].get("if") not in RUN_EVEN_AFTER_FAILURE
    ]
    assert not problems, (
        f"In {REVIEW_WORKFLOW.name}: "
        + "; ".join(problems)
        + " (DOCBW-03-013)."
    )


@pytest.mark.parametrize(
    "pattern,path,expected",
    [
        ("docs/**", "docs/reference/specs/protocol.md", True),
        ("**/*.md", "README.md", True),
        ("**/*.md", "docs/a/b.md", True),
        ("docs/*.md", "docs/a/b.md", False),
        ("specs/**", "docs/adr/0001.md", False),
    ],
)
def test_glob_translation(pattern: str, path: str, expected: bool):
    """The trigger check is only as right as its reading of a path glob."""
    assert bool(_glob_regex(pattern).fullmatch(path)) is expected
