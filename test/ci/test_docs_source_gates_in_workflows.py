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
fires on that file must run the hook's command in a step that can fail the
run.
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
    RUN_EVEN_AFTER_FAILURE,
    WORKFLOWS_DIR,
    index_of,
    load_workflow,
    triggers,
)

PRE_COMMIT_CONFIG = REPO_ROOT / ".pre-commit-config.yaml"
DOCS_DIR = REPO_ROOT / "docs"
REVIEW_WORKFLOW = WORKFLOWS_DIR / "docs-build-check.yml"

# A hook whose own command no workflow runs, and the command that checks the
# same thing in CI. ``validate-adr-frontmatter`` only loads the ADR registry,
# which ``index_gen --check`` also does, and fails on the same bad frontmatter.
# ``markdownlint-cli2`` runs locally with ``--fix``; CI runs the read-only
# action with the same config.
COVERED_BY = {
    "validate-adr-frontmatter": "vultron.metadata.adr.index_gen --check",
    "markdownlint-cli2": "DavidAnson/markdownlint-cli2-action",
}

# A job-level ``if:`` that holds on every pull request.
ON_PULL_REQUEST = frozenset(
    {
        "github.event_name == 'pull_request'",
        "${{ github.event_name == 'pull_request' }}",
    }
)


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


def _commands(hook: dict[str, Any]) -> tuple[str, ...]:
    """Return every spelling of the hook's command that a workflow may run.

    ``uv run python -m vultron.metadata.docs.page_frontmatter`` and
    ``uv run docs-frontmatter`` run the same code, so both count. The hook's
    ``args:``, if any, are part of the command.
    """
    if hook["id"] in COVERED_BY:
        return (COVERED_BY[hook["id"]],)
    command = str(hook.get("entry", "")).removeprefix("uv run ").strip()
    command = " ".join([command, *map(str, hook.get("args", []))])
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
            if hook.get("pass_filenames", True):
                continue
            exclude = hook.get("exclude")
            hooks.append(
                Hook(
                    id=hook["id"],
                    # pre-commit's default `files:` matches every file.
                    files=re.compile(hook.get("files", "")),
                    exclude=re.compile(exclude) if exclude else None,
                    commands=_commands(hook),
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


def _last_match_wins(patterns: list[Any], rel_path: str) -> bool:
    """Apply a GitHub path list in order: the last pattern that matches decides.

    A ``!`` pattern excludes what it matches, so ``["docs/**", "!docs/adr/**"]``
    does not include ``docs/adr/0001.md``.
    """
    matched = False
    for raw in patterns:
        pattern = str(raw)
        negated = pattern.startswith("!")
        if _glob_regex(pattern.removeprefix("!")).fullmatch(rel_path):
            matched = not negated
    return matched


def _fires_on(event: Any, rel_path: str) -> bool:
    """Return whether a ``pull_request`` trigger block fires on *rel_path*."""
    if not isinstance(event, dict):
        return True  # A bare `pull_request:` has no path filter.
    if "paths" in event:
        return _last_match_wins(list(event["paths"]), rel_path)
    if "paths-ignore" in event:
        return not _last_match_wins(list(event["paths-ignore"]), rel_path)
    return True


def _live_text(step: dict[str, Any]) -> str:
    """Return the step's ``run`` and ``uses`` text, with shell comments dropped."""
    lines = [
        line
        for line in str(step.get("run", "")).splitlines()
        if not line.lstrip().startswith("#")
    ]
    return "\n".join([*lines, str(step.get("uses", ""))])


def _can_fail_the_run(job: dict[str, Any], step: dict[str, Any]) -> bool:
    """Return whether a failure of *step* fails a pull-request run."""
    if job.get("continue-on-error") or step.get("continue-on-error"):
        return False
    if "if" in job and job["if"] not in ON_PULL_REQUEST:
        return False
    return "if" not in step or step["if"] in RUN_EVEN_AFTER_FAILURE


def _runs_hook(wf_data: dict[str, Any], hook: Hook) -> bool:
    """Return whether some job runs *hook* in a step that can fail the run."""
    for job in wf_data.get("jobs", {}).values():
        if not isinstance(job, dict):
            continue
        for step in job.get("steps", []):
            if not isinstance(step, dict) or not _can_fail_the_run(job, step):
                continue
            if any(command in _live_text(step) for command in hook.commands):
                return True
    return False


@cache
def _pull_request_workflows() -> tuple[tuple[str, Any, dict[str, Any]], ...]:
    """Return (name, pull_request block, parsed workflow) for each PR workflow."""
    found = []
    for path in sorted(WORKFLOWS_DIR.glob("*.yml")):
        data = load_workflow(path)
        on = triggers(data)
        if "pull_request" in on:
            found.append((path.name, on["pull_request"], data))
    return tuple(found)


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
            _fires_on(event, rel_path) and _runs_hook(data, hook)
            for _, event, data in _pull_request_workflows()
        )
    ]
    assert not uncovered, (
        f"No workflow runs the '{hook.id}' pre-commit hook "
        f"({' or '.join(hook.commands)!r}) in a step that can fail a pull "
        f"request changing {len(uncovered)} docs file(s) it checks, e.g. "
        f"{uncovered[:3]}. No workflow runs pre-commit, so such a pull "
        "request merges green whatever the hook would say (DOCBW-03-013, #5084)."
    )


def _review_problems(
    job_steps: list[dict[str, Any]], hooks: list[Hook]
) -> list[str]:
    """Return every way one job's gates fail DOCBW-03-013's ordering rule."""
    build = index_of(job_steps, MKDOCS_BUILD, "run")
    gates = [
        i
        for i, step in enumerate(job_steps)
        if any(c in _live_text(step) for h in hooks for c in h.commands)
    ]
    if build is None:
        return ["the job that runs the gates does not build the site"]
    if not gates:
        return [
            "the job that builds the site runs no docs source gate (DF-09-009)"
        ]
    problems = [
        f"'{job_steps[i].get('name')}' runs after the build"
        for i in gates
        if i > build
    ]
    problems += [
        f"'{job_steps[i].get('name')}' sets continue-on-error"
        for i in gates
        if job_steps[i].get("continue-on-error", False)
    ]
    problems += [
        f"'{job_steps[i].get('name')}' does not run after an earlier gate fails "
        f"(if: {job_steps[i].get('if')!r})"
        for i in [*gates[1:], build]
        if job_steps[i].get("if") not in RUN_EVEN_AFTER_FAILURE
    ]
    return problems


@pytest.mark.spec("DOCBW-03-013")
def test_review_workflow_gates_precede_the_build_and_do_not_stop_it():
    """In the job that builds the site, a failed gate still lets the rest run."""
    jobs = load_workflow(REVIEW_WORKFLOW).get("jobs", {})
    building = [
        [s for s in job.get("steps", []) if isinstance(s, dict)]
        for job in jobs.values()
        if isinstance(job, dict)
        and any(
            MKDOCS_BUILD in str(s.get("run", "")) for s in job.get("steps", [])
        )
    ]
    assert len(building) == 1, (
        f"{REVIEW_WORKFLOW.name} should build the site in exactly one job "
        f"(DOCBW-03-001); found {len(building)}."
    )
    problems = _review_problems(building[0], _docs_hooks())
    assert not problems, (
        f"In {REVIEW_WORKFLOW.name}: "
        + "; ".join(problems)
        + " (DOCBW-03-013)."
    )


_GATE = Hook("gate", re.compile(""), None, ("docs-gate",))
_BUILD = {"name": "Build", "run": "uv run mkdocs build --strict"}
_KEPT_BUILD = {**_BUILD, "if": "${{ !cancelled() }}"}


@pytest.mark.parametrize(
    "job_steps,expected",
    [
        (
            [{"name": "A", "run": "docs-gate"}, _KEPT_BUILD],
            [],
        ),
        (
            [{"name": "A", "run": "docs-gate"}],
            ["the job that runs the gates does not build the site"],
        ),
        (
            [_KEPT_BUILD],
            [
                "the job that builds the site runs no docs source gate (DF-09-009)"
            ],
        ),
        (
            [_KEPT_BUILD, {"name": "A", "run": "docs-gate"}],
            ["'A' runs after the build"],
        ),
        (
            [
                {"name": "A", "run": "docs-gate", "continue-on-error": True},
                _KEPT_BUILD,
            ],
            ["'A' sets continue-on-error"],
        ),
        (
            [
                {"name": "A", "run": "docs-gate"},
                {"name": "B", "run": "docs-gate"},
                _BUILD,
            ],
            [
                "'B' does not run after an earlier gate fails (if: None)",
                "'Build' does not run after an earlier gate fails (if: None)",
            ],
        ),
        (
            [{"name": "A", "run": "# docs-gate"}, _KEPT_BUILD],
            [
                "the job that builds the site runs no docs source gate (DF-09-009)"
            ],
        ),
    ],
)
def test_review_problems_reports_each_violation(
    job_steps: list[dict[str, Any]], expected: list[str]
):
    """Each failure branch of the ordering check fires, and only when it should."""
    assert _review_problems(job_steps, [_GATE]) == expected


@pytest.mark.parametrize(
    "job,step,expected",
    [
        ({}, {"run": "x"}, True),
        ({}, {"run": "x", "if": "${{ !cancelled() }}"}, True),
        ({}, {"run": "x", "if": "github.base_ref == 'publish'"}, False),
        ({}, {"run": "x", "continue-on-error": True}, False),
        ({"continue-on-error": True}, {"run": "x"}, False),
        ({"if": "github.event_name == 'pull_request'"}, {"run": "x"}, True),
        ({"if": "github.event_name != 'pull_request'"}, {"run": "x"}, False),
    ],
)
def test_a_neutered_step_does_not_count(
    job: dict[str, Any], step: dict[str, Any], expected: bool
):
    """A step that a condition skips, or whose failure is swallowed, gates nothing."""
    assert _can_fail_the_run(job, step) is expected


def test_a_commented_out_command_does_not_count():
    hook = Hook("gate", re.compile(""), None, ("docs-gate",))
    commented = {
        "jobs": {"j": {"steps": [{"run": "# uv run docs-gate\ntrue"}]}}
    }
    live = {"jobs": {"j": {"steps": [{"run": "uv run docs-gate"}]}}}
    assert not _runs_hook(commented, hook)
    assert _runs_hook(live, hook)


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


@pytest.mark.parametrize(
    "event,path,expected",
    [
        (None, "docs/a.md", True),
        ({"branches": ["main"]}, "docs/a.md", True),
        ({"paths": ["docs/**"]}, "docs/a.md", True),
        ({"paths": ["specs/**"]}, "docs/a.md", False),
        ({"paths": ["docs/**", "!docs/adr/**"]}, "docs/adr/0001.md", False),
        ({"paths": ["docs/**", "!docs/adr/**"]}, "docs/a.md", True),
        ({"paths": ["!docs/adr/**", "docs/**"]}, "docs/adr/0001.md", True),
        ({"paths-ignore": ["docs/**"]}, "docs/a.md", False),
        ({"paths-ignore": ["specs/**"]}, "docs/a.md", True),
        ({"paths-ignore": ["docs/**", "!docs/a.md"]}, "docs/a.md", True),
    ],
)
def test_trigger_reading(event: Any, path: str, expected: bool):
    """Each form of ``pull_request`` filter is read as GitHub reads it."""
    assert _fires_on(event, path) is expected


def test_hook_commands_include_args_and_the_console_script():
    assert _commands(
        {"id": "x", "entry": "uv run docs-site", "args": ["--check"]}
    ) == ("docs-site --check",)
    assert _commands(
        {
            "id": "x",
            "entry": "uv run python -m vultron.metadata.docs.normative_banner",
        }
    ) == (
        "python -m vultron.metadata.docs.normative_banner",
        "docs-normative-banner",
    )
