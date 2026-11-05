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

The window is read as consecutive merge-date slices of the search API. A
merge date never changes, so a PR updated while the read runs cannot move out
of the slice it belongs to, as it could in a list ordered by update time. The
search API returns at most :data:`SEARCH_RESULT_CAP` results per query, so a
slice that matches more is halved and read again.

:func:`parse_search_pages` is pure and does the reading; :func:`fetch_window`
only loops :data:`~vultron.metadata.planning.gh.Runner` calls over it.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta

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

SEARCH_RESULT_CAP = 1000
"""The most results GitHub's search API returns for one query."""

DEFAULT_SLICE = timedelta(days=14)
"""The merge-date span one search query covers before any halving."""

MIN_SLICE = timedelta(hours=1)
"""Below this a slice is not halved again: the cap cannot be the reason."""

NESTED_LIMIT = 50
"""How many closing Issues, labels and linked PRs the query reads per node."""

QUERY = f"""
query($q: String!, $pageSize: Int!, $endCursor: String) {{
  search(query: $q, type: ISSUE, first: $pageSize, after: $endCursor) {{
    issueCount
    pageInfo {{ hasNextPage endCursor }}
    nodes {{
      ... on PullRequest {{
        number additions deletions mergedAt
        closingIssuesReferences(first: {NESTED_LIMIT}) {{
          totalCount
          nodes {{
            number state body
            labels(first: {NESTED_LIMIT}) {{ totalCount nodes {{ name }} }}
            closedByPullRequestsReferences(
              first: {NESTED_LIMIT}, includeClosedPrs: true
            ) {{
              totalCount
              nodes {{ number merged }}
            }}
          }}
        }}
      }}
    }}
  }}
}}
"""
"""One page of merged PRs matching a search, and the Issues each closes."""

_WHAT = "could not read the PR query"

JsonObject = dict[str, object]
"""A JSON object as ``json.loads`` returns it, before its fields are checked."""


def _object(value: object, where: str) -> JsonObject:
    if not isinstance(value, dict):
        raise GhError(f"{_WHAT}: {where} is not an object")
    return value


def _list(value: object, where: str) -> list[object]:
    if not isinstance(value, list):
        raise GhError(f"{_WHAT}: {where} is not a list")
    return value


def _int(value: object, where: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise GhError(f"{_WHAT}: {where} is not an integer")
    return value


def _str(value: object, where: str) -> str:
    if not isinstance(value, str):
        raise GhError(f"{_WHAT}: {where} is not a string")
    return value


def _timestamp(value: object, where: str) -> datetime:
    """A GitHub ISO-8601 timestamp as an aware ``datetime``."""
    text = _str(value, where)
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise GhError(f"{_WHAT}: {where} is not a timestamp") from exc


def _connection(
    parent: JsonObject, key: str, where: str
) -> tuple[list[JsonObject], bool]:
    """A nested connection's nodes, and whether they are all of them."""
    connection = _object(parent.get(key), f"{where}.{key}")
    nodes = [
        _object(node, f"{where}.{key} node")
        for node in _list(connection.get("nodes"), f"{where}.{key}.nodes")
    ]
    total = _int(connection.get("totalCount"), f"{where}.{key}.totalCount")
    return nodes, total <= len(nodes)


def _parse_issue(node: JsonObject) -> ClosedIssue:
    number = _int(node.get("number"), "issue number")
    where = f"issue #{number}"
    labels, all_labels = _connection(node, "labels", where)
    if not all_labels:
        raise GhError(
            f"{_WHAT}: {where} has more than {NESTED_LIMIT} labels, so its "
            "size: estimate may be among the unread ones"
        )
    closers, all_closers = _connection(
        node, "closedByPullRequestsReferences", where
    )
    names = [_str(label.get("name"), f"{where} label") for label in labels]
    body = node.get("body")
    return ClosedIssue(
        number=number,
        closed=_str(node.get("state"), f"{where} state") == "CLOSED",
        size_labels=tuple(name for name in names if name.startswith("size:")),
        ac_count=count_acs(body if isinstance(body, str) else ""),
        merged_closing_prs=tuple(
            _int(pr.get("number"), f"{where} closer")
            for pr in closers
            if pr.get("merged") is True
        ),
        closers_complete=all_closers,
    )


def _parse_pr(node: JsonObject) -> tuple[MergedPr, tuple[ClosedIssue, ...]]:
    number = _int(node.get("number"), "PR number")
    where = f"PR #{number}"
    issue_nodes, all_issues = _connection(
        node, "closingIssuesReferences", where
    )
    if not all_issues:
        raise GhError(
            f"{_WHAT}: {where} closes more than {NESTED_LIMIT} Issues"
        )
    issues = tuple(_parse_issue(issue) for issue in issue_nodes)
    pr = MergedPr(
        number=number,
        merged_at=_timestamp(node.get("mergedAt"), f"{where} mergedAt"),
        diff_lines=_int(node.get("additions"), f"{where} additions")
        + _int(node.get("deletions"), f"{where} deletions"),
        closes=tuple(issue.number for issue in issues),
    )
    return pr, issues


@dataclass(frozen=True)
class SliceResult:
    """What one search slice returned."""

    prs: tuple[MergedPr, ...]
    issues: tuple[ClosedIssue, ...]
    issue_count: int


def parse_search_pages(pages: object) -> SliceResult:
    """Every PR on the ``--slurp``-ed pages of one search, and its Issues.

    ``issue_count`` is the search's total match count, which exceeds the PRs
    read when the search hit :data:`SEARCH_RESULT_CAP`.

    Raises:
        GhError: If a page carries GraphQL errors or is not the expected
            shape, or a node lists more nested items than the query read.
    """
    prs: list[MergedPr] = []
    issues: list[ClosedIssue] = []
    issue_count = 0
    for raw_page in _list(pages, "the response"):
        page = _object(raw_page, "a page")
        errors = graphql_errors(page)
        if errors:
            raise GhError("the PR query failed: " + "; ".join(errors))
        data = _object(page.get("data"), "data")
        search = _object(data.get("search"), "search")
        issue_count = _int(search.get("issueCount"), "search.issueCount")
        for node in _list(search.get("nodes"), "search.nodes"):
            pr, closing = _parse_pr(_object(node, "a search node"))
            prs.append(pr)
            issues.extend(closing)
    return SliceResult(tuple(prs), tuple(issues), issue_count)


def _search_term(repo: str, start: datetime, end: datetime) -> str:
    stamp = "%Y-%m-%dT%H:%M:%SZ"
    return (
        f"repo:{repo} is:pr is:merged "
        f"merged:{start.strftime(stamp)}..{end.strftime(stamp)}"
    )


def _read_slice(
    repo: str, start: datetime, end: datetime, run: Runner
) -> SliceResult:
    raw = run(
        [
            "api",
            "graphql",
            "--paginate",
            "--slurp",
            "-f",
            f"query={QUERY}",
            "-f",
            f"q={_search_term(repo, start, end)}",
            "-F",
            f"pageSize={PAGE_SIZE}",
        ]
    )
    try:
        pages = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise GhError(f"{_WHAT}: {exc}") from exc
    return parse_search_pages(pages)


def _slices(
    since: datetime, until: datetime, span: timedelta
) -> list[tuple[datetime, datetime]]:
    """Consecutive ``(start, end)`` spans covering ``since`` to ``until``."""
    slices: list[tuple[datetime, datetime]] = []
    start = since
    while True:
        end = min(start + span, until)
        slices.append((start, end))
        if end >= until:
            return slices
        start = end


def fetch_window(
    repo: str,
    since: datetime,
    until: datetime,
    run: Runner = run_gh,
    slice_span: timedelta = DEFAULT_SLICE,
) -> CalibrationData:
    """Every PR on *repo* (``OWNER/NAME``) merged from ``since`` to ``until``.

    Both ends are inclusive. Each slice of ``slice_span`` that matches more
    than :data:`SEARCH_RESULT_CAP` PRs is halved until it fits.

    Raises:
        GhError: If *repo* is malformed, the window is empty or reversed, a
            response cannot be read, or a slice shorter than
            :data:`MIN_SLICE` still exceeds the cap.
        subprocess.CalledProcessError: If ``gh`` exits non-zero.
    """
    owner, sep, name = repo.partition("/")
    if not (sep and owner and name) or "/" in name:
        raise GhError(f"repo must be OWNER/NAME, got {repo!r}")
    if until <= since or slice_span <= timedelta(0):
        raise GhError(f"cannot read the window {since}..{until}")
    pending = _slices(since, until, slice_span)
    prs: dict[int, MergedPr] = {}
    issues: dict[int, ClosedIssue] = {}
    while pending:
        start, end = pending.pop(0)
        result = _read_slice(repo, start, end, run)
        if result.issue_count > SEARCH_RESULT_CAP:
            if end - start < MIN_SLICE:
                raise GhError(
                    f"more than {SEARCH_RESULT_CAP} PRs merged between "
                    f"{start} and {end}; the search API cannot list them"
                )
            middle = start + (end - start) / 2
            pending[:0] = [(start, middle), (middle, end)]
            continue
        # Slice ends are inclusive, so a PR merged on a boundary is read twice.
        for pr in result.prs:
            if since <= pr.merged_at <= until:
                prs[pr.number] = pr
        issues.update((issue.number, issue) for issue in result.issues)
    return CalibrationData(
        since=since,
        until=until,
        prs=tuple(sorted(prs.values(), key=lambda pr: pr.number)),
        issues=tuple(issue for _, issue in sorted(issues.items())),
    )
