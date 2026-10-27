"""Shared helpers for tests that read ``.github/workflows/*.yml``.

The docs-gate ratchets (DOCBW-03) all ask the same questions of a workflow:
which steps does it run, in what order, and which workflows build the site at
all. Parsing lives here so each ratchet states only its assertion.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS_DIR = REPO_ROOT / ".github" / "workflows"

MKDOCS_BUILD = "mkdocs build"
# The one composite action every site-building workflow builds through
# (DOCBW-06-004).
BUILD_SITE_ACTION = "./.github/actions/build-site"


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


def local_action_steps(uses: str) -> list[dict[str, Any]]:
    """Return the steps of the local composite action a ``uses:`` names."""
    action_dir = REPO_ROOT / uses.removeprefix("./")
    action_file = next(
        (
            action_dir / name
            for name in ("action.yml", "action.yaml")
            if (action_dir / name).is_file()
        ),
        None,
    )
    assert action_file is not None, f"Local action {uses} has no action.yml."
    runs = load_workflow(action_file).get("runs", {})
    return [s for s in runs.get("steps", []) if isinstance(s, dict)]


def expanded_steps(step_list: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return *step_list* in run order, each local action replaced by its steps.

    Expansion recurses, so a step a local action reaches through another local
    action is returned too.
    """
    flat: list[dict[str, Any]] = []
    for step in step_list:
        uses = str(step.get("uses", ""))
        if uses.startswith("./"):
            flat.extend(expanded_steps(local_action_steps(uses)))
        else:
            flat.append(step)
    return flat


def site_building_workflows() -> list[Path]:
    """Return every workflow that builds the site.

    A workflow builds the site when it calls the shared build action or names
    ``mkdocs build`` itself; the second is what DOCBW-06-004 forbids, and it
    still counts here so every gate on a site build sees it.
    """
    return sorted(
        path
        for path in WORKFLOWS_DIR.glob("*.yml")
        if any(
            needle in path.read_text(encoding="utf-8")
            for needle in (BUILD_SITE_ACTION, MKDOCS_BUILD)
        )
    )
