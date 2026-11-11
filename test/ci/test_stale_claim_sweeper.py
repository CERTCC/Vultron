"""CI verification test — the stale-claim sweeper (PAD-10, PAD-19-005).

The decisions are pure functions in ``.github/scripts``; the workflow that runs
them is pinned here so it keeps its triggers and its failure notification.
"""

from __future__ import annotations

import importlib.util
import json
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


def _issue(
    number: int,
    issue_type: str = "Task",
    *,
    assigned: bool = True,
    labels: tuple[str, ...] = (),
) -> dict:
    return {
        "number": number,
        "type": {"name": issue_type},
        "assignees": [{"login": "me"}] if assigned else [],
        "labels": [{"name": n} for n in labels],
    }


class _FakeGitHub:
    """Routes the sweeper's ``_paginated`` and ``_gh`` calls; records writes."""

    def __init__(
        self,
        issues: list[dict],
        branches: dict[str, str],
        *,
        open_pr_heads: tuple[str, ...] = (),
        open_pr_bodies: dict[str, str | None] | None = None,
        sub_issues: dict[int, list[dict]] | None = None,
        assigned_at: str = OLD,
    ) -> None:
        self.issues = issues
        self.branches = branches  # branch name -> last commit date
        self.open_pr_heads = open_pr_heads
        self.open_pr_bodies = open_pr_bodies or {}  # head -> body
        self.sub_issues = sub_issues or {}
        self.assigned_at = assigned_at
        self.writes: list[tuple[str, ...]] = []
        self.unretried: list[tuple[str, ...]] = []

    def paginated(self, endpoint: str) -> list[dict]:
        if endpoint.startswith("repos/o/r/issues?"):
            return self.issues
        if "matching-refs" in endpoint:
            return [
                {"ref": f"refs/heads/{b}", "object": {"sha": f"sha{i}"}}
                for i, b in enumerate(self.branches)
            ]
        if endpoint.endswith("/events?per_page=100"):
            return [{"event": "assigned", "created_at": self.assigned_at}]
        number = int(endpoint.split("/issues/")[1].split("/", maxsplit=1)[0])
        return self.sub_issues.get(number, [])

    def gh(self, *args: str, retry: bool = True) -> str:
        if not retry:
            self.unretried.append(args[:2])
        if args[:2] == ("pr", "list"):
            heads: dict[str, str | None] = {h: "" for h in self.open_pr_heads}
            heads |= self.open_pr_bodies
            return json.dumps(
                [
                    {
                        "headRefName": h,
                        "closingIssuesReferences": [],
                        "body": b,
                    }
                    for h, b in heads.items()
                ]
            )
        if args[0] == "api":
            index = int(args[1].rsplit("/sha", 1)[1])
            return list(self.branches.values())[index]
        self.writes.append(args[:3])
        return ""


def _sweep(monkeypatch: pytest.MonkeyPatch, fake: _FakeGitHub) -> _FakeGitHub:
    monkeypatch.setattr(_sweeper, "_paginated", fake.paginated)
    monkeypatch.setattr(_sweeper, "_gh", fake.gh)
    sweeper = _sweeper.Sweeper("o/r", CUTOFF, dry_run=False)
    sweeper.sweep_issue_claims()
    sweeper.sweep_epic_claims()
    return fake


@pytest.mark.spec("PAD-10-002", "PAD-10-003")
def test_an_orphaned_issue_claim_is_labelled_and_commented(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = _sweep(monkeypatch, _FakeGitHub([_issue(7)], {"bug/7-x": OLD}))
    assert fake.writes == [
        ("issue", "edit", "7"),
        ("issue", "comment", "7"),
    ]
    # A retried comment would post twice; a deleted branch's 404 is no flake.
    assert fake.unretried == [
        ("api", "repos/o/r/commits/sha0"),
        ("issue", "comment"),
    ]


@pytest.mark.spec("PAD-10-001", "PAD-04-008")
@pytest.mark.parametrize(
    ("issue", "kw"),
    [
        (_issue(7, assigned=False), {}),
        (_issue(7, labels=("stale-claim",)), {}),
        (_issue(7), {"open_pr_heads": ("bug/7-x",)}),
        # A split's part, open from its unlinked sibling branch (PAD-04-008).
        (_issue(7), {"open_pr_bodies": {"bug/7a-x": "- Part of #7\n"}}),
        (_issue(8), {}),  # the branch names an issue that is not open
    ],
)
def test_live_or_ineligible_issue_claims_are_left_alone(
    monkeypatch: pytest.MonkeyPatch, issue: dict, kw: dict
) -> None:
    issues = [issue] if issue["number"] == 7 else []
    fake = _sweep(monkeypatch, _FakeGitHub(issues, {"bug/7-x": OLD}, **kw))
    assert fake.writes == []


@pytest.mark.spec("PAD-19-005")
def test_an_abandoned_epic_run_is_flagged_and_a_live_one_is_not(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    epic, child = _issue(1, "Epic"), _issue(2, assigned=False)
    subs = {1: [{"number": 2, "type": {"name": "Task"}}]}
    stale = _sweep(
        monkeypatch,
        _FakeGitHub([epic, child], {"task/2-x": OLD}, sub_issues=subs),
    )
    assert stale.writes == [("issue", "edit", "1"), ("issue", "comment", "1")]

    live = _sweep(
        monkeypatch,
        _FakeGitHub([epic, child], {"task/2-x": NEW}, sub_issues=subs),
    )
    assert live.writes == []


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


def test_a_hung_gh_call_ends_well_before_the_job_cap() -> None:
    """A hung call fails the job red; the cap would cancel it unreported."""
    (job,) = load_workflow(_WORKFLOW)["jobs"].values()
    timeout = float(job["env"]["GH_CALL_TIMEOUT_SECONDS"])
    assert 2 * timeout <= 60 * job["timeout-minutes"]


@pytest.mark.spec("PAD-10-001", "PAD-04-008")
@pytest.mark.parametrize(
    ("body", "expected"),
    [
        ("- Part of #7", {7}),
        ("- part of #7\n- Part of #12", {7, 12}),
        ("- Closes #7", set()),
        ("Part of #7a", set()),
        ("Depart of #7", set()),
        ("", set()),
        # Quoted, not claimed: a code span or a fenced block keeps nothing live.
        ("Like `Part of #7`.", set()),
        ("```text\n- Part of #7\n```\n- Part of #9", {9}),
        ("~~~~\n```\nPart of #7\n~~~~", set()),
    ],
)
def test_part_of_issues(body: str, expected: set[int]) -> None:
    assert _sweeper.part_of_issues(body) == expected


@pytest.mark.spec("PAD-10-001", "PAD-04-008")
def test_another_issues_part_pr_does_not_keep_a_claim_live(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = _sweep(
        monkeypatch,
        _FakeGitHub(
            [_issue(7)],
            {"bug/7-x": OLD},
            open_pr_bodies={"task/8a-x": "- Part of #8\n"},
        ),
    )
    assert fake.writes == [("issue", "edit", "7"), ("issue", "comment", "7")]


@pytest.mark.spec("PAD-19-005", "PAD-04-008")
def test_an_open_split_part_keeps_an_epic_run_live(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    epic, child = _issue(1, "Epic"), _issue(2, assigned=False)
    subs = {1: [{"number": 2, "type": {"name": "Task"}}]}
    fake = _sweep(
        monkeypatch,
        _FakeGitHub(
            [epic, child],
            {"task/2-x": OLD},
            open_pr_bodies={"task/2a-x": "- Part of #2\n"},
            sub_issues=subs,
        ),
    )
    assert fake.writes == []


@pytest.mark.spec("PAD-19-005", "PAD-04-008")
def test_a_part_pr_for_an_issue_the_run_does_not_hold_leaves_it_stale(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    epic, child = _issue(1, "Epic"), _issue(2, assigned=False)
    subs = {1: [{"number": 2, "type": {"name": "Task"}}]}
    fake = _sweep(
        monkeypatch,
        _FakeGitHub(
            [epic, child],
            {"task/2-x": OLD},
            open_pr_bodies={"task/9a-x": "- Part of #9\n"},
            sub_issues=subs,
        ),
    )
    assert fake.writes == [("issue", "edit", "1"), ("issue", "comment", "1")]


@pytest.mark.spec("PAD-10-001")
def test_a_pr_with_a_null_body_keeps_nothing_live(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = _sweep(
        monkeypatch,
        _FakeGitHub(
            [_issue(7)], {"bug/7-x": OLD}, open_pr_bodies={"x/1": None}
        ),
    )
    assert fake.writes == [("issue", "edit", "7"), ("issue", "comment", "7")]
