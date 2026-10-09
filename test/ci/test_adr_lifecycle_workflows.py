"""CI verification test — the ADR epoch checks run as built (MS-14-007).

The clock alone never fails a merge-blocking check (ARCH-18-004):

- a pull request that materially edits an ADR fails when it leaves the status
  off its epoch, compared against the merge base, so only its author can
  cause the failure;
- drift on every other ADR is reported on a schedule through one tracking
  issue, and never fails the build.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest
import yaml

from test.ci._workflows import WORKFLOWS_DIR, load_workflow, triggers
from vultron.metadata.base import repo_root

_EDIT = WORKFLOWS_DIR / "adr-lifecycle.yml"
_DRIFT = WORKFLOWS_DIR / "adr-status-drift.yml"
_LIFECYCLE = "vultron.metadata.adr.lifecycle"


def _step_running(path: Path, command: str) -> dict[str, Any]:
    found = [
        step
        for job in load_workflow(path).get("jobs", {}).values()
        for step in job.get("steps", [])
        if command in step.get("run", "")
    ]
    assert len(found) == 1, f"{path.name} must run `{command}` once"
    step: dict[str, Any] = found[0]
    return step


@pytest.mark.spec("MS-14-009")
def test_edit_check_runs_on_pull_requests_against_the_merge_base():
    step = _step_running(_EDIT, _LIFECYCLE)
    assert "git merge-base" in step["run"]
    assert '--base "$base"' in step["run"]
    assert not step.get("continue-on-error", False)
    assert "pull_request" in triggers(load_workflow(_EDIT))


@pytest.mark.spec("MS-14-009")
def test_edit_check_has_the_history_it_needs_and_no_write_scope():
    workflow = load_workflow(_EDIT)
    assert "issues" not in workflow["permissions"]
    checkout = next(
        s
        for job in workflow["jobs"].values()
        for s in job["steps"]
        if s.get("uses", "").startswith("actions/checkout")
    )
    assert checkout["with"]["fetch-depth"] == 0


@pytest.mark.spec("MS-14-007")
def test_drift_report_reports_and_never_fails_the_build():
    step = _step_running(_DRIFT, f"{_LIFECYCLE} --report-drift")
    assert step["continue-on-error"] is True
    job = next(iter(load_workflow(_DRIFT)["jobs"].values()))
    assert job["permissions"]["issues"] == "write"
    modes = {
        s["with"]["mode"]: s["if"]
        for s in job["steps"]
        if s.get("uses") == "./.github/actions/notify-failure"
    }
    assert modes == {
        "notify": f"failure() || steps.{step['id']}.outcome == 'failure'",
        "close": f"steps.{step['id']}.outcome == 'success'",
    }


@pytest.mark.spec("MS-14-007")
def test_drift_report_runs_at_least_hourly():
    """A boundary crossed overnight must surface within the hour."""
    (entry,) = triggers(load_workflow(_DRIFT))["schedule"]
    minute, hour, *_ = entry["cron"].split()
    assert minute.isdigit()
    assert hour == "*"


_ADDED_REFS = "vultron.metadata.adr.added_refs"


@pytest.mark.spec("MS-15-006")
def test_added_reference_check_runs_on_pull_requests_against_the_merge_base():
    step = _step_running(_EDIT, _ADDED_REFS)
    assert "git merge-base" in step["run"]
    assert '--base "$base"' in step["run"]
    assert "docs/adr/*.md" in step["run"]
    assert not step.get("continue-on-error", False)
    # Neither check's failure hides the other's faults.
    assert step["run"].count("|| rc=1") == 2


@pytest.mark.spec("MS-15-006")
def test_added_reference_check_runs_as_a_pre_commit_hook_on_adrs():
    config = yaml.safe_load(
        (repo_root() / ".pre-commit-config.yaml").read_text(encoding="utf-8")
    )
    hooks = {
        hook["id"]: hook
        for repo in config["repos"]
        for hook in repo.get("hooks", [])
    }
    hook = hooks["adr-added-reference-check"]
    assert hook["entry"] == f"uv run python -m {_ADDED_REFS}"
    assert hook.get("pass_filenames", True) is True
    assert re.search(hook["files"], "docs/adr/0127-x.md")
    assert re.search(hook["exclude"], "docs/adr/index.md")
