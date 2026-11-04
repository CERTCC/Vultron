"""``scripts/velocity.py`` net-issue computation and the create-script guards.

Net issues are closed minus opened-by-reason (completeness-doctrine.md
"Net Issues: Close More Than You Open"); these pin what each side counts.
"""

from __future__ import annotations

import subprocess
import sys
from datetime import date
from pathlib import Path

from scripts.velocity_metrics import issues as issue_metrics, periods

_ROOT = Path(__file__).parents[2]
_VELOCITY = _ROOT / "scripts" / "velocity.py"
_MANAGE = _ROOT / ".agents/skills/manage-github-issue/manage_github_issue.sh"


def _issue(
    created: str,
    closed: str | None = None,
    reason: str | None = None,
    state_reason: str | None = "COMPLETED",
    issue_type: str = "Task",
) -> dict:
    labels = [{"name": f"opened:{reason}"}] if reason else []
    return {
        "createdAt": f"{created}T00:00:00Z",
        "closedAt": f"{closed}T00:00:00Z" if closed else None,
        "stateReason": state_reason if closed else None,
        "issueType": {"name": issue_type},
        "labels": {"nodes": labels},
    }


def _row(rows: list[dict], period: str) -> dict:
    return next(r for r in rows if r["period"] == period)


def test_opened_reason_reads_only_known_reasons():
    assert (
        issue_metrics.opened_reason(_issue("2026-09-01", reason="debt"))
        == "debt"
    )
    assert issue_metrics.opened_reason(_issue("2026-09-01")) is None
    bogus = _issue("2026-09-01")
    bogus["labels"] = {"nodes": [{"name": "opened:nonsense"}]}
    assert issue_metrics.opened_reason(bogus) is None


def test_net_counts_completed_closes_minus_net_opened():
    issues = [
        _issue("2026-08-01", "2026-09-10"),  # closed, counts
        _issue("2026-08-01", "2026-09-11", issue_type="Epic"),  # epic: skipped
        _issue("2026-08-01", "2026-09-12", state_reason="NOT_PLANNED"),
        _issue("2026-09-05", "2026-09-06", reason="excursion"),  # nets to zero
        _issue("2026-09-07", reason="debt"),
        _issue("2026-09-08", reason="deferred"),
    ]
    rows = issue_metrics._net_issues(issues, ["2026-09"], periods.month_key)
    row = _row(rows, "2026-09")
    assert row["closed"] == 1
    assert row["closed_other"] == 1
    assert row["opened_excursion"] == 1
    assert row["opened_debt"] == 1
    assert row["opened_deferred"] == 1
    assert row["net"] == 1 - 2


def test_current_month_is_a_period_early_in_the_month():
    # Thu 2026-10-01: the week's Monday (09-28) falls in September.
    _, months = periods._period_keys(date(2026, 9, 14), date(2026, 10, 1))
    assert "2026-10" in months


def test_manage_script_rejects_reason_flags_on_update():
    result = subprocess.run(
        [str(_MANAGE), "--issue-number", "1", "--opened-as", "debt"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 1
    assert "only when creating" in result.stderr


def test_velocity_script_runs_by_path():
    # velocity-report runs ``python scripts/velocity.py``; the script finds
    # its helper package beside it, so it must load when run that way.
    result = subprocess.run(
        [sys.executable, str(_VELOCITY), "--help"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "--no-pipeline-cost" in result.stdout


def test_manage_script_create_does_not_require_milestone():
    # Every required create field except --milestone, and no --title, so the
    # run stops at the title check before any network call.
    result = subprocess.run(
        [str(_MANAGE), "--issue-type-id", "X", "--parent", "1", "--planned"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 1
    assert "missing required field" not in result.stderr
    assert "--title is required" in result.stderr


def test_manage_script_create_still_accepts_explicit_milestone():
    # An explicit --milestone (e.g. a release milestone) is still a known
    # option: the run passes argument parsing and the guard, and stops at the
    # title check before any network call.
    result = subprocess.run(
        [
            str(_MANAGE),
            "--issue-type-id",
            "X",
            "--parent",
            "1",
            "--planned",
            "--milestone",
            "5",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 1
    assert "Unknown" not in result.stderr
    assert "missing required field" not in result.stderr
    assert "--title is required" in result.stderr


def test_manage_script_create_guard_does_not_list_milestone():
    result = subprocess.run(
        [str(_MANAGE), "--title", "t"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 1
    assert "missing required field" in result.stderr
    assert "--milestone" not in result.stderr
