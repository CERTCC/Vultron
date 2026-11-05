#  Copyright (c) 2026 Carnegie Mellon University and Contributors.
#  - see Contributors.md for a full list of Contributors
#  - see ContributionInstructions.md for information on how you can Contribute to this project
#  Vultron Multiparty Coordinated Vulnerability Disclosure Protocol Prototype is
#  licensed under a MIT (SEI)-style license, please see LICENSE.md distributed
#  with this Software or contact permission@sei.cmu.edu for full terms.
#  Created, in part, with funding and support from the United States Government
#  (see Acknowledgments file). This program may include and/or can make use of
#  certain third party source code, object code, documentation and other files
#  ("Third Party Software"). See LICENSE.md for more details.
#  Carnegie Mellon®, CERT® and CERT Coordination Center® are registered in the
#  U.S. Patent and Trademark Office by Carnegie Mellon University
"""Read a calibration window of merged PRs from GitHub through ``gh``.

The query walks merged PRs newest-updated first and stops at the first page
that reaches past the window: a PR merged in the window was updated no earlier
than it merged, so nothing after that page can qualify. The search API would
be simpler but returns at most 1000 results, which a 60-day window exceeds.

:func:`parse_page` is pure and does the reading; :func:`fetch_window` only
loops :data:`~vultron.metadata.planning.gh.Runner` calls over it.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from vultron.metadata.planning.gh import (
    GhError,
    Runner,
    graphql_errors,
    run_gh,
)
from vultron.metadata.planning.size_calibration.measures import count_acs
from vultron.metadata.planning.size_calibration.model import (
    CalibrationData,
    ClosedIssue,
    MergedPr,
)

PAGE_SIZE = 50
"""PRs per page: each carries its closing Issues' bodies, so pages stay small."""

QUERY = """
query($owner: String!, $name: String!, $pageSize: Int!, $endCursor: String) {
  repository(owner: $owner, name: $name) {
    pullRequests(
      states: MERGED, first: $pageSize, after: $endCursor,
      orderBy: {field: UPDATED_AT, direction: DESC}
    ) {
      pageInfo { hasNextPage endCursor }
      nodes {
        number additions deletions mergedAt updatedAt
        closingIssuesReferences(first: 25) {
          nodes {
            number state body
            labels(first: 50) { nodes { name } }
            closedByPullRequestsReferences(first: 25, includeClosedPrs: true) {
              nodes { number merged }
            }
          }
        }
      }
    }
  }
}
"""
"""One page of merged PRs and the Issues each closes."""


def _timestamp(value: str) -> datetime:
    """A GitHub ISO-8601 timestamp as an aware ``datetime``."""
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _parse_issue(node: dict[str, Any]) -> ClosedIssue:
    labels = (node.get("labels") or {}).get("nodes") or []
    closers = (node.get("closedByPullRequestsReferences") or {}).get(
        "nodes"
    ) or []
    return ClosedIssue(
        number=int(node["number"]),
        closed=node["state"] == "CLOSED",
        size_labels=tuple(
            label["name"]
            for label in labels
            if str(label["name"]).startswith("size:")
        ),
        ac_count=count_acs(node.get("body") or ""),
        merged_closing_prs=tuple(
            int(pr["number"]) for pr in closers if pr.get("merged")
        ),
    )


@dataclass(frozen=True)
class Page:
    """What one page of the query contributed, and whether to read on."""

    prs: tuple[MergedPr, ...]
    issues: tuple[ClosedIssue, ...]
    next_cursor: str | None


def parse_page(payload: object, since: datetime) -> Page:
    """The PRs merged at or after ``since`` on one page, and their Issues.

    ``next_cursor`` is ``None`` when there is no next page or this page
    already reached a PR last updated before ``since``.

    Raises:
        GhError: If the page carries GraphQL errors or is not the expected
            shape.
    """
    if not isinstance(payload, dict):
        raise GhError(
            "could not read the PR query: expected a JSON object, "
            f"got {type(payload).__name__}"
        )
    errors = graphql_errors(payload)
    if errors:
        raise GhError("the PR query failed: " + "; ".join(errors))
    try:
        connection = payload["data"]["repository"]["pullRequests"]
        prs: list[MergedPr] = []
        issues: list[ClosedIssue] = []
        reached_past = False
        for node in connection["nodes"]:
            if _timestamp(node["updatedAt"]) < since:
                reached_past = True
            merged_at = _timestamp(node["mergedAt"])
            if merged_at < since:
                continue
            closing = [
                _parse_issue(issue)
                for issue in node["closingIssuesReferences"]["nodes"]
            ]
            issues.extend(closing)
            prs.append(
                MergedPr(
                    number=int(node["number"]),
                    merged_at=merged_at,
                    diff_lines=int(node["additions"]) + int(node["deletions"]),
                    closes=tuple(issue.number for issue in closing),
                )
            )
        info = connection["pageInfo"]
        more = bool(info["hasNextPage"]) and not reached_past
        cursor = str(info["endCursor"]) if more else None
    except (KeyError, TypeError, ValueError, AttributeError) as exc:
        raise GhError(f"could not read the PR query: {exc!r}") from exc
    return Page(tuple(prs), tuple(issues), cursor)


def fetch_window(
    repo: str,
    since: datetime,
    until: datetime,
    run: Runner = run_gh,
) -> CalibrationData:
    """Every PR merged on *repo* (``OWNER/NAME``) from ``since``, and its Issues.

    ``until`` is the moment the window ends, normally now; it is recorded for
    the report header, since GitHub holds no PR merged after it yet.

    Raises:
        GhError: If *repo* is malformed or a response cannot be read.
        subprocess.CalledProcessError: If ``gh`` exits non-zero.
    """
    owner, sep, name = repo.partition("/")
    if not (sep and owner and name) or "/" in name:
        raise GhError(f"repo must be OWNER/NAME, got {repo!r}")
    prs: dict[int, MergedPr] = {}
    issues: dict[int, ClosedIssue] = {}
    cursor: str | None = None
    while True:
        args = [
            "api",
            "graphql",
            "-f",
            f"query={QUERY}",
            "-f",
            f"owner={owner}",
            "-f",
            f"name={name}",
            "-F",
            f"pageSize={PAGE_SIZE}",
        ]
        if cursor is not None:
            args += ["-f", f"endCursor={cursor}"]
        try:
            payload = json.loads(run(args))
        except json.JSONDecodeError as exc:
            raise GhError(f"could not read the PR query: {exc}") from exc
        page = parse_page(payload, since)
        prs.update((pr.number, pr) for pr in page.prs)
        issues.update((issue.number, issue) for issue in page.issues)
        if page.next_cursor is None:
            break
        cursor = page.next_cursor
    return CalibrationData(
        since=since,
        until=until,
        prs=tuple(sorted(prs.values(), key=lambda pr: pr.number)),
        issues=tuple(sorted(issues.values(), key=lambda i: i.number)),
    )
