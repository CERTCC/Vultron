"""CI verification test — the open-owner check for ``verification_debt`` runs.

MS-10-006 says a CI check fails when a ``verification_debt`` marker, or an
owner-table entry, names a closed issue. The check needs the GitHub API, so it
cannot live in the unit suite or the offline pre-commit hook; this test pins
that ``spec-check.yml`` runs it unconditionally, with a token, and also on a
schedule — an owner issue can close without any ``specs/`` change to trigger a
run.
"""

from __future__ import annotations

from typing import Any

import pytest

from test.ci._workflows import WORKFLOWS_DIR, load_workflow, steps, triggers

_WORKFLOW = WORKFLOWS_DIR / "spec-check.yml"
_COMMAND = "spec-lint specs/ --check-debt-owners"


def _owner_check_step() -> dict[str, Any]:
    found = [
        s
        for s in steps(load_workflow(_WORKFLOW))
        if _COMMAND in s.get("run", "")
    ]
    assert len(found) == 1, f"{_WORKFLOW.name} must run `{_COMMAND}` once"
    return found[0]


@pytest.mark.spec("MS-10-006")
def test_spec_check_runs_the_open_owner_check_unconditionally():
    step = _owner_check_step()
    assert "if" not in step
    assert not step.get("continue-on-error", False)


def test_owner_check_step_has_a_token_for_gh():
    assert "GH_TOKEN" in _owner_check_step().get("env", {})


def test_spec_check_runs_on_a_schedule():
    assert triggers(load_workflow(_WORKFLOW)).get("schedule")
