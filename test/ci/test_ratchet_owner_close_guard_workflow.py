"""CI verification test — the ratchet-owner close guard runs as built.

ARCH-18-012 fails a pull request whose body closes an issue a non-empty ratchet
still names as its owner. Closing the owner is that PR's own act, so the check
fails it (unlike the scheduled report, ARCH-18-009). This test pins the
workflow's shape; ``test/metadata/test_ratchet_owner_close_guard.py`` tests the
script it runs.
"""

from __future__ import annotations

from typing import Any

import pytest

from test.ci._workflows import WORKFLOWS_DIR, load_workflow, triggers

_WORKFLOW = WORKFLOWS_DIR / "ratchet-owner-close-guard.yml"
_COMMAND = "uv run ratchet-close-guard --body-file"


def _job_and_step() -> tuple[dict[str, Any], dict[str, Any]]:
    """The one ``(job, step)`` whose ``run:`` runs the guard."""
    found = [
        (job, step)
        for job in load_workflow(_WORKFLOW).get("jobs", {}).values()
        for step in job.get("steps", [])
        if _COMMAND in step.get("run", "")
    ]
    assert len(found) == 1, f"{_WORKFLOW.name} must run `{_COMMAND}` once"
    return found[0]


@pytest.mark.spec("ARCH-18-012")
def test_it_runs_on_every_pull_request_and_every_body_edit() -> None:
    """No ``paths`` filter: any body can close an owner, and an edit can add
    the reference without a commit."""
    on = triggers(load_workflow(_WORKFLOW))
    assert set(on) == {"pull_request"}
    assert on["pull_request"]["branches"] == ["main"]
    assert "paths" not in on["pull_request"]
    assert set(on["pull_request"]["types"]) == {
        "opened",
        "edited",
        "synchronize",
        "reopened",
    }


@pytest.mark.spec("ARCH-18-012")
def test_a_closed_owner_fails_the_pull_request() -> None:
    job, step = _job_and_step()
    assert "if" not in job
    assert "if" not in step
    assert not step.get("continue-on-error", False)
    assert not job.get("continue-on-error", False)


def test_the_body_reaches_the_script_through_env_never_the_script_text() -> (
    None
):
    """An interpolated body would run as shell; the env var is data."""
    _job, step = _job_and_step()
    assert step["env"]["PR_BODY"] == "${{ github.event.pull_request.body }}"
    assert "${{" not in step["run"]


def test_workflow_grants_only_contents_read() -> None:
    """It reads the checkout and the event payload, nothing on GitHub."""
    assert load_workflow(_WORKFLOW)["permissions"] == {"contents": "read"}
