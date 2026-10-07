"""CI verification test — the Epic ``needs-planning`` label reconcile.

An Epic carries ``needs-planning`` exactly while it has an open Concern or Idea
sub-issue.
The decision is a pure function in ``.github/scripts``; the workflow that runs
it is pinned here so it keeps its triggers and its failure notification.
"""

from __future__ import annotations

import importlib.util
from types import ModuleType

import pytest

from test.ci._workflows import (
    REPO_ROOT,
    WORKFLOWS_DIR,
    load_workflow,
    triggers,
)

_SCRIPT = REPO_ROOT / ".github" / "scripts" / "reconcile_needs_planning.py"
_WORKFLOW = WORKFLOWS_DIR / "epic-needs-planning.yml"


def _load_script() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "reconcile_needs_planning", _SCRIPT
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_change = _load_script().wanted_label_change


@pytest.mark.parametrize(
    ("has_label", "children", "expected"),
    [
        (False, [("open", "Concern")], "add"),
        (False, [("open", "Idea")], "add"),
        (False, [("closed", "Task"), ("open", "Idea")], "add"),
        (True, [("open", "Concern")], None),
        (True, [("closed", "Concern"), ("closed", "Idea")], "remove"),
        (True, [("open", "Task"), ("open", "Bug"), ("open", "")], "remove"),
        (True, [], None),
        (False, [], "add"),
        (True, [("closed", "Task")], "remove"),
        (False, [("closed", "Idea"), ("open", "Feature")], None),
    ],
)
def test_wanted_label_change(
    has_label: bool, children: list[tuple[str, str]], expected: str | None
) -> None:
    assert _change(has_label, children) == expected


def test_workflow_triggers_and_permissions() -> None:
    wf = load_workflow(_WORKFLOW)
    on = triggers(wf)
    assert {"issues", "schedule", "workflow_dispatch"} <= set(on)
    assert {"closed", "reopened"} <= set(on["issues"]["types"])
    assert wf["permissions"]["issues"] == "write"


def test_workflow_runs_the_reconcile_script() -> None:
    runs = [
        step.get("run", "")
        for job in load_workflow(_WORKFLOW)["jobs"].values()
        for step in job["steps"]
    ]
    assert any(
        ".github/scripts/reconcile_needs_planning.py" in r for r in runs
    )
