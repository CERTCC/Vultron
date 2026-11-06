"""Shared helpers for tests that read ``.github/workflows/*.yml`` and ``*.yaml``.

The docs-gate ratchets (DOCBW-03) all ask the same questions of a workflow:
which steps does it run, in what order, and which workflows build the site at
all. Parsing lives here so each ratchet states only its assertion.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from vultron.metadata.planning.ci_mirror._workflows import (
    composite_steps,
    expand_steps,
    load_mapping,
    on_block,
    workflow_files as _workflow_files,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS_DIR = REPO_ROOT / ".github" / "workflows"

MKDOCS_BUILD = "mkdocs build"
# A mkdocs command that builds the site: ``build`` or ``gh-deploy`` (which
# builds and pushes), with any global options (and their values) before the
# subcommand, so ``mkdocs -v build``, ``mkdocs -f mkdocs.yml build`` and
# ``python -m mkdocs gh-deploy`` count too.
MKDOCS_SITE_BUILD = re.compile(
    r"\bmkdocs(?:\s+-\S+(?:\s+[^-\s]\S*)?)*\s+(?:build|gh-deploy)\b"
)
# The one composite action every site-building workflow builds through
# (DOCBW-06-004).
BUILD_SITE_ACTION = "./.github/actions/build-site"

# An ``if:`` that still runs the step after an earlier step failed. It widens
# when the step runs rather than narrowing it, so it cannot skip a gate.
RUN_EVEN_AFTER_FAILURE = frozenset({"${{ !cancelled() }}", "!cancelled()"})

# A shell suffix that makes a failed command exit 0, so the step passes.
_IGNORED_EXIT = re.compile(
    r"\|\|\s*(?:true|:|exit\s+0)(?=\s|;|\)|$)", re.MULTILINE
)


def workflow_files() -> list[Path]:
    """Return every workflow file, ``*.yml`` and ``*.yaml``, sorted by path."""
    return _workflow_files(REPO_ROOT)


# Parsed workflow YAML is untyped by nature; ``Any`` here is the YAML boundary.
def load_workflow(path: Path) -> dict[str, Any]:
    return load_mapping(path)


def triggers(wf_data: dict[Any, Any]) -> dict[str, Any]:
    """Return the workflow's ``on:`` block.

    PyYAML reads a bare ``on:`` key as the boolean ``True``, so look there too.
    """
    block = on_block(wf_data)
    return block if isinstance(block, dict) else {}


def steps(wf_data: dict[str, Any]) -> list[dict[str, Any]]:
    """Return every step across every job, in file order."""
    return [
        step
        for job in wf_data.get("jobs", {}).values()
        if isinstance(job, dict)
        for step in job.get("steps", [])
        if isinstance(step, dict)
    ]


def job_needs(job: dict[str, Any]) -> set[str]:
    """Return the job ids *job* waits for, from the list or the scalar form.

    ``needs: build`` is as valid as ``needs: [build]``, and a membership test
    against the scalar form is a substring test instead of a set test:
    ``"test" in "test-docs"`` is true. Normalizing here keeps every reader of
    a ``needs:`` list out of that trap.
    """
    needs = job.get("needs", [])
    return {needs} if isinstance(needs, str) else {str(n) for n in needs}


def index_of(
    wf_steps: list[dict[str, Any]], needle: str, key: str
) -> int | None:
    """Return the index of the first step whose ``key`` field contains ``needle``."""
    for i, step in enumerate(wf_steps):
        if needle in str(step.get(key, "")):
            return i
    return None


def local_action_steps(uses: str) -> list[dict[str, Any]]:
    """Return the steps of the local composite action a ``uses:`` names."""
    return composite_steps(REPO_ROOT, uses)


def expanded_steps(step_list: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return *step_list* in run order, each local action replaced by its steps.

    Expansion recurses, so a step a local action reaches through another local
    action is returned too.
    """
    return [dict(step) for _label, step in expand_steps(REPO_ROOT, step_list)]


def site_building_workflows() -> list[Path]:
    """Return every workflow that builds the site.

    A workflow builds the site when it calls the shared build action or runs
    a site build itself (``MKDOCS_SITE_BUILD``); the second is what
    DOCBW-06-004 forbids, and it still counts here so every gate on a site
    build sees it.
    """
    return sorted(
        path
        for path in workflow_files()
        if BUILD_SITE_ACTION in (text := path.read_text(encoding="utf-8"))
        or MKDOCS_SITE_BUILD.search(text)
    )


def _drop_comment(line: str) -> str:
    """Return *line* up to its shell comment, if any.

    A ``#`` starts a comment only outside quotes and at a word start, so
    ``echo "PR #1"`` and ``a#b`` keep their ``#``. Quotes are tracked per
    line, which is enough for the one-line commands a gate step runs.
    """
    quote = ""
    for i, char in enumerate(line):
        if quote:
            if char == quote:
                quote = ""
        elif char in "'\"":
            quote = char
        elif char == "#" and (i == 0 or line[i - 1].isspace()):
            return line[:i].rstrip()
    return line


def live_text(step: dict[str, Any]) -> str:
    """Return the step's ``run`` and ``uses`` text, with shell comments dropped.

    A whole-line comment and a trailing `` # …`` comment both run nothing.
    """
    lines = [
        _drop_comment(line) for line in str(step.get("run", "")).splitlines()
    ]
    return "\n".join([*lines, str(step.get("uses", ""))])


def swallowed_failure(step: dict[str, Any]) -> list[str]:
    """Return every way *step* reports success when its command fails."""
    problems: list[str] = []
    if step.get("continue-on-error", False):
        problems.append("it sets continue-on-error")
    if _IGNORED_EXIT.search(live_text(step)):
        problems.append("its command ignores its own exit status")
    return problems


def neutering(step: dict[str, Any]) -> list[str]:
    """Return every way *step* cannot fail the run: a skipping ``if:`` or a
    swallowed failure."""
    problems: list[str] = []
    if "if" in step and step["if"] not in RUN_EVEN_AFTER_FAILURE:
        problems.append(f"it is conditional (if: {step['if']!r})")
    return problems + swallowed_failure(step)
