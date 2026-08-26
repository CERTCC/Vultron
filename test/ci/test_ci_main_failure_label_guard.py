"""CI verification test — confirm the ci:main-failure label guard workflow.

Implements CISEC-05-005 from specs/ci-security.yaml: a workflow triggered on
``issues: labeled`` SHOULD enforce that the ``ci:main-failure`` label is
bot-managed.  If ``github.actor`` is not ``github-actions[bot]``, the label
MUST be removed immediately.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS_DIR = REPO_ROOT / ".github" / "workflows"
GUARD_WORKFLOW = WORKFLOWS_DIR / "ci-main-failure-label-guard.yml"

_EXPECTED_LABEL = "ci:main-failure"
_EXPECTED_ACTOR = "github-actions[bot]"


def _load() -> dict[str, Any]:
    return yaml.safe_load(GUARD_WORKFLOW.read_text())  # type: ignore[no-any-return]


def test_guard_workflow_exists() -> None:
    """CISEC-05-005: the label guard workflow file must exist."""
    assert GUARD_WORKFLOW.exists(), (
        f"{GUARD_WORKFLOW.name} not found. "
        "Create .github/workflows/ci-main-failure-label-guard.yml "
        "per CISEC-05-005."
    )


def test_guard_workflow_triggers_on_issues_labeled() -> None:
    """CISEC-05-005: workflow must trigger on issues: labeled."""
    data = _load()
    on = data.get(True, data.get("on", {}))  # type: ignore[call-overload]
    assert isinstance(on, dict), "workflow has no 'on:' block"
    issues_trigger = on.get("issues", {})
    types = (
        issues_trigger.get("types", [])
        if isinstance(issues_trigger, dict)
        else []
    )
    assert (
        "labeled" in types
    ), "Workflow must trigger on 'issues: labeled' (CISEC-05-005)."


def test_guard_workflow_has_issues_write_permission() -> None:
    """CISEC-05-005: workflow must have issues: write and no broader permissions."""
    data = _load()
    # permissions may be at workflow level or job level
    workflow_perms = data.get("permissions", {})
    if isinstance(workflow_perms, dict):
        assert (
            workflow_perms.get("issues") == "write"
        ), "Workflow-level permissions must include 'issues: write' (CISEC-05-005)."
        extra = {k: v for k, v in workflow_perms.items() if k != "issues"}
        assert not extra, (
            f"Workflow should have minimal permissions (issues: write only). "
            f"Extra permissions found: {extra}"
        )


def test_guard_workflow_filters_to_ci_main_failure_label() -> None:
    """CISEC-05-005: workflow must filter to the ci:main-failure label."""
    text = GUARD_WORKFLOW.read_text()
    assert (
        _EXPECTED_LABEL in text
    ), f"Workflow must reference '{_EXPECTED_LABEL}' label (CISEC-05-005)."


def test_guard_workflow_checks_actor() -> None:
    """CISEC-05-005: workflow must guard against non-bot actors."""
    text = GUARD_WORKFLOW.read_text()
    assert _EXPECTED_ACTOR in text, (
        f"Workflow must check github.actor against '{_EXPECTED_ACTOR}' "
        "(CISEC-05-005)."
    )


def test_guard_workflow_removes_label() -> None:
    """CISEC-05-005: workflow must remove the label when actor is not bot."""
    text = GUARD_WORKFLOW.read_text()
    assert "--remove-label" in text, (
        "Workflow must use --remove-label to strip the ci:main-failure label "
        "(CISEC-05-005)."
    )
