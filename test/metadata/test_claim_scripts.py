"""The claim scripts in ``.agents/skills/shared/`` (PAD-04, PAD-15-009, PAD-19).

Each script runs against a stand-in ``gh`` (``_fake_gh.py``) and a local bare
repository playing GitHub. The fake creates linked branches the way GitHub does
— an existing name answers ``linkedBranch: null`` rather than failing, the
behaviour ISSUE-4617's AC-1 found — so these tests pin that the scripts read
that ``null`` as "already claimed".
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SHARED = REPO_ROOT / ".agents/skills/shared"
FAKE_GH = Path(__file__).with_name("_fake_gh.py")

EPIC = 900
TASK = 101
BUG = 202
OTHER = 303

pytestmark = pytest.mark.skipif(
    shutil.which("jq") is None, reason="the claim scripts need jq"
)


def _git(*args: str, cwd: Path) -> str:
    return subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    ).stdout


# Board writes and issue writes succeed unless a test says otherwise; they come
# after every per-test rule, so `Sandbox.fail` can still override them.
_DEFAULT_RULES: list[dict] = [
    {
        "match": ["addProjectV2ItemById"],
        "stdout": json.dumps(
            {"data": {"addProjectV2ItemById": {"item": {"id": "PVTI_fake"}}}}
        ),
    },
    {"match": ["updateProjectV2ItemFieldValue"], "stdout": "{}"},
    {"match": ["issue edit"]},
    {"match": ["issue comment"]},
]


def _graphql(issue: dict) -> str:
    return json.dumps({"data": {"repository": {"issue": issue}}})


def _parent(number: int, issue_type: str, assignees: list[str]) -> dict:
    return {
        "number": number,
        "issueType": {"name": issue_type},
        "assignees": {"nodes": [{"login": a} for a in assignees]},
        "parent": None,
    }


@dataclass
class Sandbox:
    """A work clone, its bare origin, a copy of the scripts, and the fake gh."""

    root: Path
    work: Path
    origin: Path
    shared: Path
    log: Path
    rules: list[dict]

    def issue(
        self,
        number: int,
        issue_type: str = "Task",
        *,
        epic_assignees: list[str] | None = None,
    ) -> None:
        """Register an issue under Epic #900, assigned to ``epic_assignees``."""
        parent = _parent(EPIC, "Epic", epic_assignees or [])
        self.rules += [
            {
                "match": ["issue view", str(number), "--json number"],
                "stdout": json.dumps({"number": number}),
            },
            {
                "match": [f"issue(number: {number})", "parent {"],
                "stdout": _graphql(
                    {"issueType": {"name": issue_type}, "parent": parent}
                ),
            },
            {
                "match": [f"issue(number: {number})", "subIssues(first: 1)"],
                "stdout": _graphql(
                    {
                        "issueType": {"name": issue_type},
                        "subIssues": {"totalCount": 0},
                        "labels": {"nodes": []},
                    }
                ),
            },
            {
                "match": [f"issue(number: {number})", "{ id }"],
                "stdout": _graphql({"id": f"I_{number}"}),
            },
        ]

    def fail(self, *match: str) -> None:
        """Make the first call matching ``match`` fail."""
        self.rules.insert(0, {"match": list(match), "exit": 1})

    def run(self, script: str, *args: str) -> subprocess.CompletedProcess[str]:
        rules = self.root / "rules.json"
        rules.write_text(json.dumps([*self.rules, *_DEFAULT_RULES]))
        env = {
            **os.environ,
            "PATH": f"{self.root / 'bin'}{os.pathsep}{os.environ['PATH']}",
            "HOME": str(self.root / "home"),
            "FAKE_GH_LOG": str(self.log),
            "FAKE_GH_RULES": str(rules),
            "FAKE_GH_ORIGIN": str(self.origin),
        }
        return subprocess.run(
            ["bash", str(self.shared / script), *args],
            cwd=self.work,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )

    def calls(self) -> list[str]:
        if not self.log.exists():
            return []
        return [
            " ".join(json.loads(line))
            for line in self.log.read_text().splitlines()
        ]

    def remote_branches(self) -> list[str]:
        out = _git(
            "for-each-ref",
            "--format=%(refname:short)",
            "refs/heads/",
            cwd=self.origin,
        )
        return [b for b in out.split() if b != "main"]


@pytest.fixture()
def box(tmp_path: Path) -> Sandbox:
    origin = tmp_path / "origin.git"
    work = tmp_path / "work"
    _git("init", "-q", "--bare", "-b", "main", str(origin), cwd=tmp_path)
    _git("init", "-q", "-b", "main", str(work), cwd=tmp_path)
    (work / "README").write_text("x")
    _git("add", "-A", cwd=work)
    _git("commit", "-qm", "base", cwd=work)
    _git("remote", "add", "origin", str(origin), cwd=work)
    _git("push", "-q", "origin", "main", cwd=work)
    _git("fetch", "-q", "origin", cwd=work)

    shared = tmp_path / "shared"
    shared.mkdir()
    for script in SHARED.glob("*.sh"):
        shutil.copy(script, shared)
    (shared / "board-ids.json").write_text(
        json.dumps(
            {
                "fetched_at_epoch": int(time.time()),
                "repo": "R_fake",
                "project": "PVT_fake",
                "schedule-field": "F_schedule",
                "schedule": {"Now": "S_now"},
                "status-field": "F_status",
                "status": {"In progress": "S_in_progress"},
                "issue-type": {"Task": "IT_task"},
            }
        )
    )

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    gh = bin_dir / "gh"
    gh.write_text(f'#!/bin/sh\nexec python3 "{FAKE_GH}" "$@"\n')
    gh.chmod(0o755)
    (tmp_path / "home").mkdir()
    return Sandbox(tmp_path, work, origin, shared, tmp_path / "gh.log", [])


def _status_set(calls: list[str]) -> bool:
    return any(
        "updateProjectV2ItemFieldValue" in c and "F_status" in c for c in calls
    )


@pytest.mark.spec(
    "PAD-04-001", "PAD-04-002", "PAD-15-009", "PAD-19-002", "PAD-19-003"
)
class TestClaimIssue:
    def test_github_creates_the_branch_and_the_issue_is_announced(
        self, box: Sandbox
    ):
        box.issue(TASK)
        result = box.run("claim-issue.sh", str(TASK), "task", "slug")
        assert result.returncode == 0, result.stderr
        assert result.stdout.strip().endswith(f"task/{TASK}-slug")
        assert box.remote_branches() == [f"task/{TASK}-slug"]
        head = _git("branch", "--show-current", cwd=box.work).strip()
        assert head == f"task/{TASK}-slug"
        calls = box.calls()
        assert any(f"issue edit {TASK} --add-assignee @me" in c for c in calls)
        assert any(
            f"issue comment {TASK}" in c and f"task/{TASK}-slug" in c
            for c in calls
        )
        assert _status_set(calls), "PAD-04-002: Status = In Progress"

    def test_a_branch_already_on_github_means_already_claimed(
        self, box: Sandbox
    ):
        box.issue(TASK)
        _git(
            "push",
            "-q",
            "origin",
            f"main:refs/heads/task/{TASK}-slug",
            cwd=box.work,
        )
        result = box.run("claim-issue.sh", str(TASK), "task", "slug")
        assert result.returncode == 1
        assert "already claimed" in result.stderr
        assert not any("issue edit" in c for c in box.calls())
        assert _git("branch", "--show-current", cwd=box.work).strip() == "main"

    def test_bundle_members_are_claimed_onto_the_first_members_branch(
        self, box: Sandbox
    ):
        box.issue(TASK)
        box.issue(OTHER)
        result = box.run("claim-issue.sh", str(TASK), "task", "s", str(OTHER))
        assert result.returncode == 0, result.stderr
        assert box.remote_branches() == [f"task/{TASK}-s"]
        assert any(
            f"issue comment {OTHER}" in c and f"Bundled with #{TASK}" in c
            for c in box.calls()
        )

    def test_a_mid_bundle_failure_drops_the_branch_and_names_the_claimed(
        self, box: Sandbox
    ):
        box.issue(TASK)
        box.issue(OTHER)
        box.fail("issue edit", str(OTHER))
        result = box.run("claim-issue.sh", str(TASK), "task", "s", str(OTHER))
        assert result.returncode != 0
        assert f"#{TASK}" in result.stderr
        assert box.remote_branches() == []
        assert _git("branch", "--list", f"task/{TASK}-s", cwd=box.work) == ""

    def test_a_task_under_a_claimed_epic_is_held(self, box: Sandbox):
        box.issue(TASK, epic_assignees=["me"])
        result = box.run("claim-issue.sh", str(TASK), "task", "slug")
        assert result.returncode == 3
        assert f"Epic #{EPIC}" in result.stderr
        assert box.remote_branches() == []

    def test_the_epic_run_may_claim_its_own_task(self, box: Sandbox):
        box.issue(TASK, epic_assignees=["me"])
        result = box.run(
            "claim-issue.sh", "--epic-run", str(EPIC), str(TASK), "task", "s"
        )
        assert result.returncode == 0, result.stderr

    def test_a_run_for_another_epic_is_still_held(self, box: Sandbox):
        box.issue(TASK, epic_assignees=["me"])
        result = box.run(
            "claim-issue.sh", "--epic-run", "999", str(TASK), "task", "s"
        )
        assert result.returncode == 3

    def test_planning_an_epic_does_not_assign_it(self, box: Sandbox):
        """An Epic's assignee means an epic run (PAD-19-001), so a planning
        claim locks with the branch and comments, but never assigns."""
        box.issue(EPIC, "Epic")
        result = box.run("claim-issue.sh", str(EPIC), "plan", "slug")
        assert result.returncode == 0, result.stderr
        assert box.remote_branches() == [f"plan/{EPIC}-slug"]
        calls = box.calls()
        assert any(f"issue comment {EPIC}" in c for c in calls)
        assert not any("--add-assignee" in c for c in calls)
        assert not _status_set(calls)

    def test_a_bug_under_a_claimed_epic_is_not_held(self, box: Sandbox):
        box.issue(BUG, "Bug", epic_assignees=["me"])
        result = box.run("claim-issue.sh", str(BUG), "bug", "slug")
        assert result.returncode == 0, result.stderr


@pytest.mark.spec("PAD-19-001", "PAD-19-004")
class TestEpicClaim:
    def _epic(self, box: Sandbox, assignees: list[str], state="OPEN") -> None:
        box.issue(EPIC, "Epic")
        box.rules.insert(
            0,
            {
                "match": ["issue view", str(EPIC), "--json state,assignees"],
                "stdout": json.dumps(
                    {
                        "state": state,
                        "assignees": [{"login": a} for a in assignees],
                    }
                ),
            },
        )

    def test_claim_assigns_and_comments_without_a_status(self, box: Sandbox):
        self._epic(box, [])
        result = box.run("claim-epic.sh", str(EPIC))
        assert result.returncode == 0, result.stderr
        calls = box.calls()
        assert any(f"issue edit {EPIC} --add-assignee @me" in c for c in calls)
        assert any(f"issue comment {EPIC}" in c for c in calls)
        assert not _status_set(calls), "PAD-16-012: an Epic has no Status"
        assert box.remote_branches() == []

    def test_an_assigned_epic_is_refused(self, box: Sandbox):
        self._epic(box, ["someone"])
        result = box.run("claim-epic.sh", str(EPIC))
        assert result.returncode == 1
        assert "already claimed" in result.stderr
        assert not any("issue edit" in c for c in box.calls())

    def test_a_non_epic_is_refused(self, box: Sandbox):
        box.issue(TASK)
        box.rules.insert(
            0,
            {
                "match": ["issue view", str(TASK), "--json state,assignees"],
                "stdout": json.dumps({"state": "OPEN", "assignees": []}),
            },
        )
        result = box.run("claim-epic.sh", str(TASK))
        assert result.returncode == 1
        assert "not an Epic" in result.stderr

    def test_a_closed_epic_is_refused(self, box: Sandbox):
        self._epic(box, [], state="CLOSED")
        assert box.run("claim-epic.sh", str(EPIC)).returncode == 1

    @pytest.mark.parametrize("assignees", [["me"], []])
    def test_release_unassigns_and_posts_the_summary(
        self, box: Sandbox, assignees: list[str]
    ):
        box.rules.append(
            {
                "match": ["issue view", str(EPIC), "--json assignees"],
                "stdout": json.dumps(
                    {"assignees": [{"login": a} for a in assignees]}
                ),
            }
        )
        result = box.run("release-epic.sh", str(EPIC), "3 merged, 1 parked")
        assert result.returncode == 0, result.stderr
        calls = box.calls()
        removed = any(
            f"issue edit {EPIC}" in c and "--remove-assignee me" in c
            for c in calls
        )
        assert removed == bool(assignees)
        assert any(
            f"issue comment {EPIC}" in c and "3 merged, 1 parked" in c
            for c in calls
        )
