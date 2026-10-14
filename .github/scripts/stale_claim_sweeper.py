#!/usr/bin/env python3
"""Flag orphaned claims with ``stale-claim`` (PAD-10, PAD-19-005).

Two kinds of claim are swept:

- An **issue claim** is an open, assigned Issue with a claim branch
  ``<prefix>/<N>-<slug>`` on GitHub, under any prefix (PAD-04-001). It is
  orphaned when the branch has no open PR and neither its last commit nor the
  claim itself is within the stale window.
- An **Epic claim** is an open, assigned Epic: an epic run (PAD-19-001). It is
  orphaned when it was claimed before the window and none of the issues it
  holds (descendants whose nearest Epic it is) has an open PR or claim-branch
  activity within it.

The claim time (the issue's latest ``assigned`` event) counts as activity
because GitHub creates a claim branch at the ``main`` tip, whose commit can be
older than the window the moment the claim is taken.

The decisions (``claim_issue_number``, ``claim_activity``,
``is_stale_issue_claim``, ``is_stale_epic_claim``) are pure functions the test suite pins without the
GitHub API; everything else is thin ``gh`` plumbing. Flagging is idempotent: a
claim that already carries ``stale-claim`` is skipped.

Usage: stale_claim_sweeper.py [--dry-run] [--repo OWNER/NAME] [--days N]
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from collections.abc import Iterable
from datetime import UTC, datetime, timedelta

LABEL = "stale-claim"
EPIC_TYPE = "Epic"
STALE_DAYS = 3
SWEEPER_URL = (
    "https://github.com/{repo}/actions/workflows/stale_claim_sweeper.yml"
)

# `<prefix>/<issue-number>-<slug>` for any claim prefix (task/, bug/, plan/, …).
_CLAIM_BRANCH_RE = re.compile(r"^[a-z][a-z0-9-]*/(\d+)-.+$")


def claim_issue_number(branch: str) -> int | None:
    """The issue a claim branch is named for, or ``None`` for any other branch."""
    match = _CLAIM_BRANCH_RE.match(branch)
    return int(match.group(1)) if match else None


def _latest(*stamps: str | None) -> str | None:
    """The latest of some ISO-8601 UTC stamps (``Z`` form sorts as text)."""
    present = [s for s in stamps if s]
    return max(present) if present else None


def claim_activity(
    last_commit: str | None, claimed_at: str | None
) -> str | None:
    """When a claim branch was last active: its last commit or the claim itself.

    GitHub creates the branch at the ``main`` tip, so a fresh claim's only
    commit can be older than the stale window (PAD-10-001).
    """
    return _latest(last_commit, claimed_at)


def is_stale_issue_claim(
    *,
    activity: str | None,
    has_open_pr: bool,
    cutoff: str,
) -> bool:
    """An assigned issue's claim branch is orphaned (PAD-10-001).

    ``activity`` is ``claim_activity`` for the branch.
    """
    if has_open_pr:
        return False
    # No readable activity at all is not evidence of abandonment.
    return activity is not None and activity < cutoff


def is_stale_epic_claim(
    *,
    claimed_at: str | None,
    child_activity: Iterable[str | None],
    child_has_open_pr: bool,
    cutoff: str,
) -> bool:
    """An assigned Epic's epic run is orphaned (PAD-19-005).

    ``child_activity`` is ``claim_activity`` for each claim branch of an issue
    the run owns.
    """
    if claimed_at is None or claimed_at >= cutoff or child_has_open_pr:
        return False
    return not any(a is not None and a >= cutoff for a in child_activity)


def _gh(*args: str) -> str:
    return subprocess.run(  # noqa: S603 - fixed argv, no shell
        ["gh", *args],  # noqa: S607
        check=True,
        capture_output=True,
        text=True,
    ).stdout


def _paginated(endpoint: str) -> list[dict[str, object]]:
    """All items of a REST list endpoint (``--slurp`` yields one list per page)."""
    pages = json.loads(_gh("api", "--paginate", "--slurp", endpoint))
    return [item for page in pages for item in page]


def _values(items: object, key: str) -> list[str]:
    """``item[key]`` for each dict in a REST list (``login``, ``name``)."""
    if not isinstance(items, list):
        return []
    return [str(i[key]) for i in items if isinstance(i, dict) and key in i]


def _type_name(issue: dict[str, object]) -> str:
    issue_type = issue.get("type")
    return (
        str(issue_type.get("name", "")) if isinstance(issue_type, dict) else ""
    )


class Sweeper:
    """Reads GitHub once per run and flags each orphaned claim."""

    def __init__(self, repo: str, cutoff: str, dry_run: bool) -> None:
        self.repo = repo
        self.cutoff = cutoff
        self.dry_run = dry_run
        self.flagged = 0
        issues = _paginated(f"repos/{repo}/issues?state=open&per_page=100")
        self.open_issues = {
            int(str(i["number"])): i for i in issues if "pull_request" not in i
        }
        refs = _paginated(f"repos/{repo}/git/matching-refs/heads?per_page=100")
        self.branches: list[tuple[str, int, str]] = []
        for ref in refs:
            name = str(ref["ref"]).removeprefix("refs/heads/")
            number = claim_issue_number(name)
            obj = ref.get("object")
            if number is not None and isinstance(obj, dict):
                self.branches.append((name, number, str(obj["sha"])))
        prs = json.loads(
            _gh(
                "pr",
                "list",
                "--repo",
                repo,
                "--state",
                "open",
                "--limit",
                "1000",
                "--json",
                "headRefName,closingIssuesReferences",
            )
        )
        self.pr_heads = {str(pr["headRefName"]) for pr in prs}
        self.pr_closes = {
            int(ref["number"])
            for pr in prs
            for ref in pr.get("closingIssuesReferences") or []
        }

    def _last_commit(self, sha: str) -> str | None:
        try:
            return (
                _gh(
                    "api",
                    f"repos/{self.repo}/commits/{sha}",
                    "--jq",
                    ".commit.committer.date",
                ).strip()
                or None
            )
        except subprocess.CalledProcessError:
            return None

    def _claimed_at(self, number: int) -> str | None:
        events = _paginated(
            f"repos/{self.repo}/issues/{number}/events?per_page=100"
        )
        return _latest(
            *(
                str(e["created_at"])
                for e in events
                if e.get("event") == "assigned"
            )
        )

    def _branch_activity(self, number: int, sha: str) -> str | None:
        return claim_activity(self._last_commit(sha), self._claimed_at(number))

    def _owned_by_run(self, epic: int) -> set[int]:
        """Every descendant whose nearest Epic is ``epic`` (PAD-19-002).

        The walk stops at a nested Epic: its Tasks belong to that Epic's run.
        """
        owned: set[int] = set()
        frontier = [epic]
        while frontier:
            parent = frontier.pop()
            for sub in _paginated(
                f"repos/{self.repo}/issues/{parent}/sub_issues?per_page=100"
            ):
                number = int(str(sub["number"]))
                if _type_name(sub) == EPIC_TYPE or number in owned:
                    continue
                owned.add(number)
                frontier.append(number)
        return owned

    def _claimable(self, number: int) -> dict[str, object] | None:
        """The open, assigned, not-yet-flagged issue, or ``None``."""
        issue = self.open_issues.get(number)
        if issue is None or not _values(issue.get("assignees"), "login"):
            return None
        if LABEL in _values(issue.get("labels"), "name"):
            return None
        return issue

    def _flag(self, number: int, what: str, remedies: list[str]) -> None:
        print(
            f"#{number}: FLAG — {what}{' (dry run)' if self.dry_run else ''}"
        )
        self.flagged += 1
        if self.dry_run:
            return
        _gh(
            "issue",
            "edit",
            str(number),
            "--repo",
            self.repo,
            "--add-label",
            LABEL,
        )
        body = "\n\n".join(
            [
                "**Stale claim detected** 🔍",
                f"{what} This issue has been labeled `{LABEL}`.",
                "A human should review it:\n\n" + "\n".join(remedies),
                f"*Posted automatically by the [stale-claim sweeper]"
                f"({SWEEPER_URL.format(repo=self.repo)}) workflow.*",
            ]
        )
        _gh(
            "issue",
            "comment",
            str(number),
            "--repo",
            self.repo,
            "--body",
            body,
        )

    def sweep_issue_claims(self) -> None:
        for branch, number, sha in self.branches:
            issue = self._claimable(number)
            if issue is None or _type_name(issue) == EPIC_TYPE:
                continue
            activity = self._branch_activity(number, sha)
            if not is_stale_issue_claim(
                activity=activity,
                has_open_pr=branch in self.pr_heads,
                cutoff=self.cutoff,
            ):
                print(f"#{number}: ok ({branch})")
                continue
            self._flag(
                number,
                f"Branch `{branch}` was last active on "
                f"`{activity}` (before `{self.cutoff}`) "
                "and has no open PR.",
                [
                    f"- Reassign and continue the work, then remove the `{LABEL}` "
                    "label, or",
                    "- Delete the branch, unassign the issue, and remove the "
                    f"`{LABEL}` label",
                ],
            )

    def sweep_epic_claims(self) -> None:
        for number, issue in sorted(self.open_issues.items()):
            if (
                _type_name(issue) != EPIC_TYPE
                or self._claimable(number) is None
            ):
                continue
            claimed_at = self._claimed_at(number)
            children = self._owned_by_run(number)
            child_branches = [
                (branch, n, sha)
                for branch, n, sha in self.branches
                if n in children
            ]
            has_pr = bool(children & self.pr_closes) or any(
                branch in self.pr_heads for branch, _, _ in child_branches
            )
            stale = is_stale_epic_claim(
                claimed_at=claimed_at,
                child_activity=(
                    self._branch_activity(n, sha)
                    for _, n, sha in child_branches
                ),
                child_has_open_pr=has_pr,
                cutoff=self.cutoff,
            )
            if not stale:
                print(f"#{number}: ok (epic run)")
                continue
            self._flag(
                number,
                f"This Epic was claimed for an epic run on `{claimed_at}`, and "
                f"since `{self.cutoff}` none of its children has an open PR or "
                "claim-branch activity.",
                [
                    "- Resume the run (`/work-epic-tasks`), then remove the "
                    f"`{LABEL}` label, or",
                    "- Release it with `.agents/skills/shared/release-epic.sh` "
                    f"and remove the `{LABEL}` label",
                ],
            )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Flag orphaned issue and Epic claims with stale-claim."
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY"))
    parser.add_argument("--days", type=int, default=STALE_DAYS)
    args = parser.parse_args(argv)
    if not args.repo:
        parser.error("--repo or GITHUB_REPOSITORY is required")
    cutoff = (datetime.now(UTC) - timedelta(days=args.days)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    print(f"Stale cutoff: {cutoff}")
    sweeper = Sweeper(args.repo, cutoff, args.dry_run)
    sweeper.sweep_issue_claims()
    sweeper.sweep_epic_claims()
    verb = "would flag" if args.dry_run else "flagged"
    print(f"=== Sweep complete; {verb} {sweeper.flagged} claim(s). ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
