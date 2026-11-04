"""GitHub API access: the token, the GraphQL and REST queries, and the
paginated fetchers for issues, merged PRs and workflow runs."""

from __future__ import annotations

import subprocess
import sys
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta

import httpx2 as httpx

from .periods import _iso_z, iso_to_date

REPO_OWNER = "CERTCC"
REPO_NAME = "Vultron"

# The REST workflow-runs endpoint returns at most this many results for any
# filtered query, whatever the page number.  Windows are split until each
# fits under it.
_REST_RESULT_CAP = 1000
_RUNS_PER_PAGE = 100

# GraphQL query to fetch merged PRs with their commits, comments, and reviews.
# Ordered by UPDATED_AT so paging can stop at the window start: a PR's
# mergedAt never follows its updatedAt.
PR_GRAPHQL_QUERY = """
query($owner: String!, $name: String!, $cursor: String) {
  repository(owner: $owner, name: $name) {
    pullRequests(
      first: 50,
      after: $cursor,
      states: [MERGED],
      orderBy: {field: UPDATED_AT, direction: DESC}
    ) {
      pageInfo { hasNextPage endCursor }
      nodes {
        number
        createdAt
        updatedAt
        mergedAt
        body
        headRefName
        baseRefName
        mergeCommit { oid }
        commits(first: 250) {
          nodes {
            commit {
              messageHeadline
              parents { totalCount }
            }
          }
        }
        comments(first: 100) {
          nodes { body createdAt }
        }
        reviews(first: 100) {
          nodes { body createdAt }
        }
      }
    }
  }
}
"""


def get_github_token() -> str:
    result = subprocess.run(
        ["gh", "auth", "token"], capture_output=True, text=True, check=True
    )
    return result.stdout.strip()


# filterBy.since isn't a variable in the same position — use a parameterized query
GRAPHQL_QUERY = """
query($owner: String!, $name: String!, $cursor: String, $since: DateTime!) {
  repository(owner: $owner, name: $name) {
    issues(
      first: 100,
      after: $cursor,
      orderBy: {field: CREATED_AT, direction: ASC},
      filterBy: {since: $since}
    ) {
      pageInfo { hasNextPage endCursor }
      nodes {
        number
        createdAt
        closedAt
        state
        stateReason
        issueType { name }
        labels(first: 100) { nodes { name } }
        timelineItems(itemTypes: [CLOSED_EVENT], last: 1) {
          nodes {
            ... on ClosedEvent {
              closer { ... on PullRequest { headRefName } }
            }
          }
        }
      }
    }
  }
}
"""


def _graphql_paginate(
    query: str,
    variables: dict,
    token: str,
    page_extractor: Callable[[dict], dict],
    label: str = "items",
    timeout: int = 30,
    stop_after: Callable[[list[dict]], bool] | None = None,
) -> list[dict]:
    """Paginate a GitHub GraphQL query and return all nodes.

    ``page_extractor`` receives the ``data`` dict from the GraphQL response
    and must return a dict with ``nodes`` (list) and ``pageInfo`` (object with
    ``hasNextPage`` and ``endCursor``).

    ``stop_after``, when given, is called with each page's nodes; paging
    stops after the first page for which it returns ``True``.
    """
    url = "https://api.github.com/graphql"
    headers = {"Authorization": f"bearer {token}"}
    nodes: list[dict] = []
    cursor = None

    with httpx.Client(headers=headers, timeout=timeout) as client:
        while True:
            resp = client.post(
                url,
                json={
                    "query": query,
                    "variables": {**variables, "cursor": cursor},
                },
            )
            resp.raise_for_status()
            body = resp.json()
            if "errors" in body:
                raise RuntimeError(f"GraphQL errors: {body['errors']}")

            page = page_extractor(body["data"])
            nodes.extend(page["nodes"])
            print(
                f"  fetched {len(nodes)} {label}...",
                file=sys.stderr,
                end="\r",
            )

            if not page["pageInfo"]["hasNextPage"]:
                break
            if stop_after is not None and stop_after(page["nodes"]):
                break
            cursor = page["pageInfo"]["endCursor"]

    print(f"  fetched {len(nodes)} {label} total    ", file=sys.stderr)
    return nodes


def fetch_all_issues(
    owner: str, name: str, since: str, token: str
) -> list[dict]:
    return _graphql_paginate(
        GRAPHQL_QUERY,
        {"owner": owner, "name": name, "since": f"{since}T00:00:00Z"},
        token,
        lambda data: data["repository"]["issues"],
        label="issues",
    )


def fetch_merged_prs(
    owner: str, name: str, since: str, token: str
) -> list[dict]:
    """Fetch merged PRs with mergedAt >= since (YYYY-MM-DD).

    Returns PR dicts with ``number``, ``createdAt``, ``updatedAt``,
    ``mergedAt``, ``body``, ``headRefName``, ``baseRefName``, ``mergeCommit.oid``,
    ``commits.nodes``, ``comments.nodes``, and
    ``reviews.nodes``.

    GraphQL has no server-side ``mergedAt`` filter, so PRs are paged
    newest-updated first and filtered here.  Because a PR's ``mergedAt`` is
    never later than its ``updatedAt``, paging stops after the first page
    whose oldest ``updatedAt`` predates the window.
    """
    since_date = date.fromisoformat(since)

    def _page_predates_window(nodes: list[dict]) -> bool:
        if not nodes:
            return True
        oldest = iso_to_date(nodes[-1].get("updatedAt"))
        return oldest is not None and oldest < since_date

    all_prs = _graphql_paginate(
        PR_GRAPHQL_QUERY,
        {"owner": owner, "name": name},
        token,
        lambda data: data["repository"]["pullRequests"],
        label="PRs",
        timeout=60,
        stop_after=_page_predates_window,
    )
    return [
        pr
        for pr in all_prs
        if (d := iso_to_date(pr.get("mergedAt"))) is not None
        and d >= since_date
    ]


def _fetch_runs_in_window(
    client: httpx.Client,
    url: str,
    base_params: dict[str, str | int],
    lo: datetime,
    hi: datetime,
) -> list[dict]:
    """Fetch every run created in ``[lo, hi]``, splitting past the REST cap.

    The endpoint stops returning results after ``_REST_RESULT_CAP`` for any
    filtered query, so a window whose ``total_count`` exceeds the cap is
    halved and each half fetched on its own.
    """
    params: dict[str, str | int] = {
        **base_params,
        "created": f"{_iso_z(lo)}..{_iso_z(hi)}",
        "per_page": _RUNS_PER_PAGE,
        "page": 1,
    }
    resp = client.get(url, params=params)
    resp.raise_for_status()
    body = resp.json()
    total = int(body.get("total_count", 0))

    if total > _REST_RESULT_CAP:
        if hi - lo <= timedelta(seconds=1):
            raise RuntimeError(
                f"{total} workflow runs created in one second at {_iso_z(lo)};"
                f" cannot split below the {_REST_RESULT_CAP}-result cap"
            )
        mid = lo + (hi - lo) / 2
        mid = mid.replace(microsecond=0)
        return _fetch_runs_in_window(
            client, url, base_params, lo, mid
        ) + _fetch_runs_in_window(
            client, url, base_params, mid + timedelta(seconds=1), hi
        )

    runs: list[dict] = list(body.get("workflow_runs", []))
    page_num = 1
    while len(runs) < total:
        page_num += 1
        params["page"] = page_num
        resp = client.get(url, params=params)
        resp.raise_for_status()
        batch = resp.json().get("workflow_runs", [])
        if not batch:
            break
        runs.extend(batch)
    return runs


def fetch_workflow_runs(
    owner: str,
    name: str,
    since: str,
    token: str,
    event: str = "pull_request",
    branch: str | None = None,
    until: datetime | None = None,
) -> list[dict]:
    """Fetch completed GitHub Actions workflow runs created since ``since``.

    Returns run dicts (each with at least ``id``, ``head_branch``,
    ``head_sha``, ``conclusion``, ``created_at``, and ``pull_requests``) for
    runs created from ``since`` (YYYY-MM-DD, UTC midnight) up to ``until``
    (default: now).  The window is split as needed to stay under the
    endpoint's ``_REST_RESULT_CAP``; runs are de-duplicated by ``id``.
    """
    url = f"https://api.github.com/repos/{owner}/{name}/actions/runs"
    headers = {
        "Authorization": f"bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    base_params: dict[str, str | int] = {
        "event": event,
        "status": "completed",
    }
    if branch:
        base_params["branch"] = branch

    lo = datetime.combine(date.fromisoformat(since), datetime.min.time(), UTC)
    hi = (until or datetime.now(UTC)).replace(microsecond=0)
    tag = f"{event}/{branch or 'all'}"

    with httpx.Client(headers=headers, timeout=30) as client:
        fetched = _fetch_runs_in_window(client, url, base_params, lo, hi)

    by_id: dict[object, dict] = {}
    for run in fetched:
        by_id.setdefault(run.get("id"), run)
    runs = list(by_id.values())
    print(
        f"  fetched {len(runs)} workflow runs ({tag}) total    ",
        file=sys.stderr,
    )
    return runs
