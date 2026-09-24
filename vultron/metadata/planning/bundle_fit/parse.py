"""Reading ``query-epic-subissues.sh``'s GraphQL payload into ``Candidate``s.

This is the only module that knows the shape of GitHub's response, which keeps
``select`` a pure function over records. The shell script owns the query; this
module owns the field names it produces.
"""

from __future__ import annotations

from vultron.metadata.planning.bundle_fit.model import (
    PLANNING_PROJECT_NUMBER,
    Candidate,
)


def _schedule_of(node: dict, project_number: int) -> str | None:
    """Read the Schedule single-select value from one project item set."""
    for item in (node.get("projectItems") or {}).get("nodes") or []:
        if ((item.get("project") or {}).get("number")) != project_number:
            continue
        value = item.get("fieldValueByName")
        if value and value.get("name"):
            return str(value["name"])
    return None


def graphql_errors(payload: dict) -> list[str]:
    """Messages from a GraphQL ``errors`` block, if the query failed.

    A failed GraphQL query still returns HTTP 200 with ``data`` null or partial,
    so a reader that looks only at ``data`` reports "no sub-issues found" for a
    bad Epic number, a token without the ``read:project`` scope that
    ``projectItems`` needs, and a rate limit alike. Error messages are this
    package's product, so the real cause is surfaced verbatim.
    """
    return [
        str(error.get("message") or error)
        for error in payload.get("errors") or []
        if isinstance(error, dict)
    ]


def parse_graphql(
    payload: dict, project_number: int = PLANNING_PROJECT_NUMBER
) -> tuple[int | None, str | None, list[Candidate]]:
    """Parse ``query-epic-subissues.sh`` output into Epic number, tier, leaves."""
    issue = ((payload.get("data") or {}).get("repository") or {}).get(
        "issue"
    ) or {}
    epic = issue.get("number")
    epic_schedule = _schedule_of(issue, project_number)

    candidates: list[Candidate] = []
    for node in (issue.get("subIssues") or {}).get("nodes") or []:
        candidates.append(
            Candidate(
                number=node["number"],
                title=node.get("title") or "",
                state=node.get("state") or "OPEN",
                issue_type=(node.get("issueType") or {}).get("name"),
                labels=[
                    label["name"]
                    for label in (node.get("labels") or {}).get("nodes") or []
                ],
                assignees=[
                    a["login"]
                    for a in (node.get("assignees") or {}).get("nodes") or []
                ],
                # Fail closed: eligibility requires every blocker CLOSED, so a
                # blocker whose state is absent or null counts as blocking. The
                # inverse test (== "OPEN") would make a malformed payload look
                # workable.
                open_blockers=[
                    b["number"]
                    for b in (node.get("blockedBy") or {}).get("nodes") or []
                    if b.get("state") != "CLOSED"
                ],
                child_count=(node.get("subIssues") or {}).get("totalCount")
                or 0,
                schedule=_schedule_of(node, project_number),
            )
        )
    return epic, epic_schedule, candidates
