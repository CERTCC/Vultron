"""CI verification test — confirm every qualifying workflow includes notify-failure.

Implements CISEC-05-004 from specs/ci-security.yaml: every qualifying workflow
(triggered by push to ``main`` or by a ``schedule`` event) SHOULD include the
``.github/actions/notify-failure`` composite action step.

A qualifying workflow is one whose ``on:`` trigger includes:
- ``push`` to the ``main`` branch, OR
- a ``schedule`` entry.

For each qualifying workflow the test asserts that at least one step across all
jobs uses ``./.github/actions/notify-failure`` in ``notify`` mode (CISEC-05-001)
and at least one step uses it in ``close`` mode (CISEC-05-002).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS_DIR = REPO_ROOT / ".github" / "workflows"
NOTIFY_FAILURE_USES = "./.github/actions/notify-failure"


def _load_workflow(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text())  # type: ignore[no-any-return]


def _is_qualifying(wf_data: dict[str, Any]) -> bool:
    """Return True when the workflow triggers on push-to-main or schedule."""
    # PyYAML 1.1 parses the bare `on:` key as Python True, not the string "on".
    on = wf_data.get(True, wf_data.get("on", {}))
    if not isinstance(on, dict):
        return False
    if "schedule" in on:
        return True
    push = on.get("push", {})
    if isinstance(push, dict):
        branches = push.get("branches", [])
        if isinstance(branches, list) and "main" in branches:
            return True
    return False


def _notify_failure_steps(
    wf_data: dict[str, Any],
) -> list[dict[str, Any]]:
    """Return all steps that reference the notify-failure composite action."""
    steps = []
    for job in wf_data.get("jobs", {}).values():
        for step in job.get("steps", []):
            if isinstance(step, dict) and step.get("uses", "").startswith(
                NOTIFY_FAILURE_USES
            ):
                steps.append(step)
    return steps


def _qualifying_workflow_files() -> list[Path]:
    files = []
    for wf in sorted(WORKFLOWS_DIR.glob("*.yml")):
        try:
            data = _load_workflow(wf)
        except Exception:  # pragma: no cover
            continue
        if _is_qualifying(data):
            files.append(wf)
    return files


# ---------------------------------------------------------------------------
# Parametrize: one test case per qualifying workflow
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def qualifying_workflows() -> list[Path]:
    found = _qualifying_workflow_files()
    assert found, f"No qualifying workflows found under {WORKFLOWS_DIR}"
    return found


def test_qualifying_workflows_found(qualifying_workflows: list[Path]) -> None:
    """At least one qualifying workflow must exist."""
    assert len(qualifying_workflows) >= 1


@pytest.mark.parametrize(
    "wf", _qualifying_workflow_files(), ids=lambda p: p.name
)
def test_qualifying_workflow_has_notify_step(wf: Path) -> None:
    """CISEC-05-004/CISEC-05-001: qualifying workflow must have a notify step."""
    data = _load_workflow(wf)
    steps = _notify_failure_steps(data)
    notify_steps = [
        s for s in steps if s.get("with", {}).get("mode") == "notify"
    ]
    assert notify_steps, (
        f"{wf.name} is a qualifying workflow (push-to-main or schedule) "
        f"but has no ./.github/actions/notify-failure step with mode: notify. "
        f"Add the step per CISEC-05-001."
    )


@pytest.mark.parametrize(
    "wf", _qualifying_workflow_files(), ids=lambda p: p.name
)
def test_qualifying_workflow_has_close_step(wf: Path) -> None:
    """CISEC-05-004/CISEC-05-002: qualifying workflow must have a close step."""
    data = _load_workflow(wf)
    steps = _notify_failure_steps(data)
    close_steps = [
        s for s in steps if s.get("with", {}).get("mode") == "close"
    ]
    assert close_steps, (
        f"{wf.name} is a qualifying workflow (push-to-main or schedule) "
        f"but has no ./.github/actions/notify-failure step with mode: close. "
        f"Add the step per CISEC-05-002."
    )


@pytest.mark.parametrize(
    "wf", _qualifying_workflow_files(), ids=lambda p: p.name
)
def test_qualifying_workflow_notify_step_has_workflow_label(wf: Path) -> None:
    """CISEC-05-004/CISEC-05-003: each notify step must carry a workflow-label."""
    data = _load_workflow(wf)
    steps = _notify_failure_steps(data)
    for step in steps:
        label = step.get("with", {}).get("workflow-label", "")
        assert label, (
            f"{wf.name}: a ./.github/actions/notify-failure step is missing "
            f"the workflow-label input (CISEC-05-003)."
        )
