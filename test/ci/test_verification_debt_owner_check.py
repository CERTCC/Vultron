"""CI verification test — the ``verification_debt`` owner checks run as built.

MS-10-006 checks owners against GitHub at two points, split by who can cause a
closed owner (ARCH-18-004):

- a pull request that closes an owner still in use fails — closing it is that
  PR's own act, so failing it races no other PR;
- an owner closed by hand is reported, never failed, on a schedule and on each
  push to ``main``, through one tracking issue.

Both need the GitHub API, so neither can live in the unit suite or the offline
pre-commit hook; this test pins the workflow that runs them.
"""

from __future__ import annotations

from typing import Any

import pytest

from test.ci._workflows import WORKFLOWS_DIR, load_workflow, triggers

_WORKFLOW = WORKFLOWS_DIR / "verification-debt-owners.yml"
_CLOSING = "spec-lint specs/ --check-closing-pr"
_OWNERS = "spec-lint specs/ --check-debt-owners"


def _job_running(command: str) -> tuple[dict[str, Any], dict[str, Any]]:
    """The one ``(job, step)`` whose ``run:`` contains *command*."""
    found = [
        (job, step)
        for job in load_workflow(_WORKFLOW).get("jobs", {}).values()
        for step in job.get("steps", [])
        if command in step.get("run", "")
    ]
    assert len(found) == 1, f"{_WORKFLOW.name} must run `{command}` once"
    return found[0]


@pytest.mark.spec("MS-10-006")
def test_closing_pr_check_fails_the_pr_on_every_pull_request():
    job, step = _job_running(_CLOSING)
    assert job["if"] == "github.event_name == 'pull_request'"
    assert "if" not in step
    assert not step.get("continue-on-error", False)
    assert "GH_TOKEN" in step["env"]
    assert "github.event.pull_request.number" in step["env"]["PR_NUMBER"]


def test_closing_pr_check_reruns_when_the_body_is_edited():
    """`Closes #N` lives in the PR body, which can change with no push."""
    pull_request = triggers(load_workflow(_WORKFLOW))["pull_request"]
    assert "edited" in pull_request["types"]
    assert "paths" not in pull_request  # any PR body can close an owner


@pytest.mark.spec("ARCH-18-004")
def test_open_owner_check_reports_and_never_fails_the_build():
    job, step = _job_running(_OWNERS)
    assert job["if"] == "github.event_name != 'pull_request'"
    assert step["continue-on-error"] is True
    assert "GH_TOKEN" in step["env"]
    modes = {
        s["with"]["mode"]: s["if"]
        for s in job["steps"]
        if s.get("uses") == "./.github/actions/notify-failure"
    }
    assert modes == {
        "notify": f"steps.{step['id']}.outcome == 'failure'",
        "close": f"steps.{step['id']}.outcome == 'success'",
    }


@pytest.mark.spec("ARCH-18-004")
def test_open_owner_check_runs_at_least_hourly():
    """Hundreds of PRs a week: a closed owner must surface within the hour."""
    (entry,) = triggers(load_workflow(_WORKFLOW))["schedule"]
    minute, hour, *_ = entry["cron"].split()
    assert minute.isdigit()
    assert hour == "*"
