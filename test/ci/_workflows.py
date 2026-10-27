"""Shared helpers for tests that read ``.github/workflows/*.yml``.

The docs-gate ratchets (DOCBW-03) all ask the same questions of a workflow:
which steps does it run, in what order, and which workflows build the site at
all. Parsing lives here so each ratchet states only its assertion.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS_DIR = REPO_ROOT / ".github" / "workflows"

MKDOCS_BUILD = "mkdocs build"

# An ``if:`` that still runs the step after an earlier step failed. It widens
# when the step runs rather than narrowing it, so it cannot skip a gate.
RUN_EVEN_AFTER_FAILURE = frozenset({"${{ !cancelled() }}", "!cancelled()"})

# A shell suffix that makes a failed command exit 0, so the step passes.
_IGNORED_EXIT = re.compile(
    r"\|\|\s*(?:true|:|exit\s+0)(?=\s|;|\)|$)", re.MULTILINE
)


# Parsed workflow YAML is untyped by nature; ``Any`` here is the YAML boundary.
def load_workflow(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def triggers(wf_data: dict[Any, Any]) -> dict[str, Any]:
    """Return the workflow's ``on:`` block.

    PyYAML reads a bare ``on:`` key as the boolean ``True``, so look there too.
    """
    block = wf_data.get("on", wf_data.get(True, {}))
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


def index_of(
    wf_steps: list[dict[str, Any]], needle: str, key: str
) -> int | None:
    """Return the index of the first step whose ``key`` field contains ``needle``."""
    for i, step in enumerate(wf_steps):
        if needle in str(step.get(key, "")):
            return i
    return None


def site_building_workflows() -> list[Path]:
    """Return every workflow that runs ``mkdocs build``."""
    return sorted(
        path
        for path in WORKFLOWS_DIR.glob("*.yml")
        if MKDOCS_BUILD in path.read_text(encoding="utf-8")
    )


def live_text(step: dict[str, Any]) -> str:
    """Return the step's ``run`` and ``uses`` text, with shell comments dropped.

    A whole-line comment and a trailing `` # …`` comment both run nothing.
    """
    lines = [
        re.sub(r"\s+#.*$", "", line)
        for line in str(step.get("run", "")).splitlines()
        if not line.lstrip().startswith("#")
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
