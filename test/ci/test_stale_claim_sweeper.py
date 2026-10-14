"""CI verification test — the stale-claim sweeper (PAD-10, PAD-19-005).

The decisions are pure functions in ``.github/scripts``; the workflow that runs
them is pinned here so it keeps its triggers and its failure notification.
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

_SCRIPT = REPO_ROOT / ".github" / "scripts" / "stale_claim_sweeper.py"
_WORKFLOW = WORKFLOWS_DIR / "stale_claim_sweeper.yml"

CUTOFF = "2026-10-11T00:00:00Z"
OLD = "2026-10-01T00:00:00Z"
NEW = "2026-10-12T00:00:00Z"


def _load_script() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "stale_claim_sweeper", _SCRIPT
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_sweeper = _load_script()


@pytest.mark.spec("PAD-10-001")
@pytest.mark.parametrize(
    ("branch", "expected"),
    [
        ("task/4617-epic-claim", 4617),
        ("bug/12-fix", 12),
        ("plan/3-idea", 3),
        ("learn/77-notes", 77),
        ("main", None),
        ("task/no-number", None),
        ("dependabot/pip/foo-1.2", None),
        ("task/4617", None),
    ],
)
def test_every_claim_prefix_names_its_issue(
    branch: str, expected: int | None
) -> None:
    """PAD-10-001: any prefix, not only ``task/``."""
    assert _sweeper.claim_issue_number(branch) == expected


@pytest.mark.spec("PAD-10-001")
@pytest.mark.parametrize(
    ("last_commit", "claimed_at", "has_open_pr", "expected"),
    [
        (OLD, OLD, False, True),
        (NEW, OLD, False, False),
        # A claim branch starts at an old main tip; the claim is the activity.
        (OLD, NEW, False, False),
        (OLD, None, False, True),
        (OLD, OLD, True, False),
        (None, None, False, False),
    ],
)
def test_issue_claim_staleness(
    last_commit: str | None,
    claimed_at: str | None,
    has_open_pr: bool,
    expected: bool,
) -> None:
    assert (
        _sweeper.is_stale_issue_claim(
            activity=_sweeper.claim_activity(last_commit, claimed_at),
            has_open_pr=has_open_pr,
            cutoff=CUTOFF,
        )
        is expected
    )


@pytest.mark.spec("PAD-19-005")
@pytest.mark.parametrize(
    ("claimed_at", "child_activity", "child_has_open_pr", "expected"),
    [
        (OLD, [], False, True),
        (OLD, [OLD, None], False, True),
        (OLD, [OLD, NEW], False, False),
        (OLD, [OLD], True, False),
        (NEW, [], False, False),
        (None, [], False, False),
    ],
)
def test_epic_claim_staleness(
    claimed_at: str | None,
    child_activity: list[str | None],
    child_has_open_pr: bool,
    expected: bool,
) -> None:
    """PAD-19-005: an epic run with no live child is orphaned."""
    assert (
        _sweeper.is_stale_epic_claim(
            claimed_at=claimed_at,
            child_activity=child_activity,
            child_has_open_pr=child_has_open_pr,
            cutoff=CUTOFF,
        )
        is expected
    )


@pytest.mark.spec("PAD-19-005")
def test_an_epic_run_owns_descendants_down_to_a_nested_epic(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The sweeper holds what epic-hold.sh holds: nearest-Epic descendants."""
    tree = {
        1: [
            {"number": 2, "type": {"name": "Task"}},
            {"number": 5, "type": {"name": "Epic"}},
        ],
        2: [{"number": 3, "type": {"name": "Task"}}],
        3: [],
        5: [{"number": 6, "type": {"name": "Task"}}],
    }

    def paginated(endpoint: str) -> list[dict[str, object]]:
        return tree[
            int(endpoint.split("/issues/")[1].split("/", maxsplit=1)[0])
        ]

    monkeypatch.setattr(_sweeper, "_paginated", paginated)
    sweeper = object.__new__(_sweeper.Sweeper)
    sweeper.repo = "o/r"
    assert sweeper._owned_by_run(1) == {2, 3}


def test_workflow_triggers_and_permissions() -> None:
    wf = load_workflow(_WORKFLOW)
    on = triggers(wf)
    assert {"schedule", "workflow_dispatch"} <= set(on)
    assert wf["permissions"]["issues"] == "write"


def test_workflow_runs_the_sweeper_script() -> None:
    runs = [
        step.get("run", "")
        for job in load_workflow(_WORKFLOW)["jobs"].values()
        for step in job["steps"]
    ]
    assert any(".github/scripts/stale_claim_sweeper.py" in r for r in runs)
