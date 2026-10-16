#!/usr/bin/env python3
"""Keep the ``needs-planning`` label on Epics in step with their open children.

An open Epic carries ``needs-planning`` while it has no sub-issues at all (not
yet planned) or at least one open, unblocked sub-issue of type Concern or Idea
(unplanned work that can be planned right now).
The label is a live signal of a planning opportunity, so a Concern or Idea
that is blocked by an open issue does not count: the label comes off when the
Epic has children and none of them is an open, unblocked Concern or Idea, and
goes back on once a blocker closes.

The decision (``wanted_label_change``) is a pure function so the test suite can
pin it without the GitHub API.
Everything else is thin ``gh`` plumbing.
The run is idempotent: it edits an Epic only when its label disagrees with its
children, so it is safe on every trigger and on a schedule.

Usage: reconcile_needs_planning.py [--dry-run] [--repo OWNER/NAME]
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from collections.abc import Iterable

LABEL = "needs-planning"
EPIC_TYPE = "Epic"
UNPLANNED_TYPES = frozenset({"Concern", "Idea"})


def wanted_label_change(
    has_label: bool, children: Iterable[tuple[str, str, bool]]
) -> str | None:
    """Return ``"add"``, ``"remove"``, or ``None`` (already correct).

    ``children`` is ``(state, type_name, blocked)`` per direct sub-issue;
    ``state`` is ``"open"`` or ``"closed"``, ``type_name`` may be empty
    (untyped), and ``blocked`` is true while any of its blockers is open.
    """
    kids = list(children)
    needs = not kids or any(
        state == "open" and type_name in UNPLANNED_TYPES and not blocked
        for state, type_name, blocked in kids
    )
    if needs and not has_label:
        return "add"
    if not needs and has_label:
        return "remove"
    return None


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


def _type_name(issue: dict[str, object]) -> str:
    issue_type = issue.get("type")
    return (
        str(issue_type.get("name", "")) if isinstance(issue_type, dict) else ""
    )


def open_epics(repo: str) -> list[dict[str, object]]:
    items = _paginated(f"repos/{repo}/issues?state=open&per_page=100")
    return [
        i
        for i in items
        if "pull_request" not in i and _type_name(i) == EPIC_TYPE
    ]


def _is_blocked(issue: dict[str, object]) -> bool:
    """True while the issue has an open blocker (``blocked_by`` counts open ones)."""
    summary = issue.get("issue_dependencies_summary")
    return isinstance(summary, dict) and int(summary.get("blocked_by", 0)) > 0


def children_of(repo: str, number: int) -> list[tuple[str, str, bool]]:
    subs = _paginated(f"repos/{repo}/issues/{number}/sub_issues?per_page=100")
    return [(str(s["state"]), _type_name(s), _is_blocked(s)) for s in subs]


def reconcile(repo: str, dry_run: bool) -> int:
    changed = 0
    for epic in open_epics(repo):
        number = int(str(epic["number"]))
        labels = epic.get("labels", [])
        has_label = isinstance(labels, list) and any(
            isinstance(lab, dict) and lab.get("name") == LABEL
            for lab in labels
        )
        change = wanted_label_change(has_label, children_of(repo, number))
        if change is None:
            print(
                f"#{number}: ok (label {'present' if has_label else 'absent'})"
            )
            continue
        print(f"#{number}: {change} {LABEL}{' (dry run)' if dry_run else ''}")
        changed += 1
        if dry_run:
            continue
        flag = "--add-label" if change == "add" else "--remove-label"
        _gh("issue", "edit", str(number), "--repo", repo, flag, LABEL)
    print(
        f"Reconciled; {changed} Epic(s) {'would change' if dry_run else 'changed'}."
    )
    return changed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY"))
    args = parser.parse_args(argv)
    if not args.repo:
        parser.error("--repo or GITHUB_REPOSITORY is required")
    reconcile(args.repo, args.dry_run)
    return 0


if __name__ == "__main__":
    sys.exit(main())
