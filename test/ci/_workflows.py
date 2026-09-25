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


# Parsed workflow YAML is untyped by nature; ``Any`` here is the YAML boundary.
def load_workflow(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


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
