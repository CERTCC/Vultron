"""CI verification test — the ratchet-baseline owner report runs as built.

Whether each ``# owner: #N`` issue a ratchet baseline cites is still open needs
the GitHub API, so it cannot live in the unit suite. ARCH-18-004 puts it in a
job outside the merge path that reports a closed owner through one tracking
issue and never fails the build; this test pins that workflow's shape.
"""

from __future__ import annotations

from typing import Any

import pytest

from test.ci._workflows import WORKFLOWS_DIR, load_workflow, triggers

_WORKFLOW = WORKFLOWS_DIR / "ratchet-baseline-owners.yml"
_COMMAND = "uv run ratchet-owners"
_NOTIFY = "./.github/actions/notify-failure"


def _job_and_step() -> tuple[dict[str, Any], dict[str, Any]]:
    """The one ``(job, step)`` whose ``run:`` runs the report."""
    found = [
        (job, step)
        for job in load_workflow(_WORKFLOW).get("jobs", {}).values()
        for step in job.get("steps", [])
        if _COMMAND in step.get("run", "")
    ]
    assert len(found) == 1, f"{_WORKFLOW.name} must run `{_COMMAND}` once"
    return found[0]


def _notify_steps(job: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        s["with"]["mode"]: s for s in job["steps"] if s.get("uses") == _NOTIFY
    }


@pytest.mark.spec("ARCH-18-004")
def test_runs_on_a_schedule_and_on_demand_never_on_pull_requests() -> None:
    on = triggers(load_workflow(_WORKFLOW))
    assert set(on) == {"schedule", "workflow_dispatch"}
    (entry,) = on["schedule"]
    assert len(entry["cron"].split()) == 5


@pytest.mark.spec("ARCH-18-004")
def test_a_closed_owner_never_fails_the_build() -> None:
    job, step = _job_and_step()
    assert step["continue-on-error"] is True
    assert "GH_TOKEN" in step["env"]
    assert "if" not in job


@pytest.mark.spec("ARCH-18-004")
def test_one_tracking_issue_is_filed_or_updated_then_closed() -> None:
    """notify files or updates the one tracker; close retires it on success."""
    job, step = _job_and_step()
    modes = _notify_steps(job)
    assert {mode: s["if"] for mode, s in modes.items()} == {
        "notify": f"failure() || steps.{step['id']}.outcome == 'failure'",
        "close": f"steps.{step['id']}.outcome == 'success'",
    }
    labels = {s["with"]["workflow-label"] for s in modes.values()}
    assert labels == {"ci:workflow-ratchet-baseline-owners"}


@pytest.mark.spec("ARCH-18-004")
def test_the_tracking_issue_lists_the_report_the_script_wrote() -> None:
    job, step = _job_and_step()
    notify = _notify_steps(job)["notify"]
    assert '--report "$RUNNER_TEMP/ratchet-owners.md"' in step["run"]
    assert (
        notify["with"]["details-file"]
        == "${{ runner.temp }}/ratchet-owners.md"
    )


def test_workflow_grants_only_contents_read_and_issues_write() -> None:
    """CISEC-02-002: notify-failure needs issues: write; nothing else is granted."""
    assert load_workflow(_WORKFLOW)["permissions"] == {
        "contents": "read",
        "issues": "write",
    }
