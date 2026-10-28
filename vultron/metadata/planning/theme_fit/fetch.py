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
"""Read every open Issue with one paginated GraphQL query.

This is the only module that knows the shape of GitHub's response. Each Issue
brings its labels, issue type, body, three levels of parent, and its Project
#24 items, so an Epic's ``Schedule`` value arrives with it; querying the
project's own item list instead would page through every item on the board.
"""

from __future__ import annotations

import json
from typing import Any

from vultron.metadata.planning.bundle_fit.model import PLANNING_PROJECT_NUMBER
from vultron.metadata.planning.bundle_fit.parse import (
    graphql_errors,
    schedule_of,
)
from vultron.metadata.planning.gh import GhError, Runner, run_gh
from vultron.metadata.planning.theme_fit.model import Ancestor, OpenIssue

QUERY = """
query($owner: String!, $name: String!, $endCursor: String) {
  repository(owner: $owner, name: $name) {
    nameWithOwner
    issues(states: OPEN, first: 100, after: $endCursor) {
      pageInfo { hasNextPage endCursor }
      nodes {
        number title body
        issueType { name }
        labels(first: 50) { nodes { name } }
        parent {
          number issueType { name } repository { nameWithOwner }
          parent {
            number issueType { name } repository { nameWithOwner }
            parent {
              number issueType { name } repository { nameWithOwner }
            }
          }
        }
        projectItems(first: 10) {
          nodes {
            project { number }
            fieldValueByName(name: "Schedule") {
              ... on ProjectV2ItemFieldSingleSelectValue { name }
            }
          }
        }
      }
    }
  }
}
"""
"""The GraphQL query ``gh api graphql --paginate`` runs."""


def _foreign_repo(parent: dict[str, Any], home: str | None) -> str | None:
    """The parent's repository when it is not *home*, else ``None``."""
    repo = (parent.get("repository") or {}).get("nameWithOwner")
    if home is None or repo is None or repo.casefold() == home.casefold():
        return None
    return str(repo)


def _ancestors(
    node: dict[str, Any], home: str | None = None
) -> tuple[Ancestor, ...]:
    """The fetched parent chain, ending at the first parent outside *home*."""
    chain: list[Ancestor] = []
    parent = node.get("parent")
    while parent:
        foreign = _foreign_repo(parent, home)
        chain.append(
            Ancestor(
                number=int(parent["number"]),
                issue_type=(parent.get("issueType") or {}).get("name"),
                repo=foreign,
            )
        )
        if foreign is not None:
            break
        parent = parent.get("parent")
    return tuple(chain)


def parse_issue(
    node: dict[str, Any],
    project_number: int = PLANNING_PROJECT_NUMBER,
    home: str | None = None,
) -> OpenIssue:
    """One GraphQL issue node as an :class:`OpenIssue`.

    *home* is the ``OWNER/NAME`` of the repository being checked; a parent
    from any other repository is marked with its own (``Ancestor.repo``).

    Raises:
        KeyError, TypeError, ValueError: If a required field is missing or
            has the wrong shape.
    """
    return OpenIssue(
        number=int(node["number"]),
        title=str(node["title"]),
        issue_type=(node.get("issueType") or {}).get("name"),
        labels=frozenset(
            str(label["name"])
            for label in (node.get("labels") or {}).get("nodes") or []
        ),
        body=str(node.get("body") or ""),
        ancestors=_ancestors(node, home),
        schedule=schedule_of(node, project_number),
    )


def parse_pages(
    pages: object, project_number: int = PLANNING_PROJECT_NUMBER
) -> tuple[OpenIssue, ...]:
    """Every issue in the ``--slurp``-ed list of GraphQL pages.

    Raises:
        GhError: If a page carries GraphQL errors or is not the expected shape.
    """
    if not isinstance(pages, list):
        raise GhError(
            "could not read the issue query: expected a JSON list of pages, "
            f"got {type(pages).__name__}"
        )
    issues: list[OpenIssue] = []
    try:
        for page in pages:
            errors = graphql_errors(page)
            if errors:
                raise GhError("the issue query failed: " + "; ".join(errors))
            repository = page["data"]["repository"]
            home = repository.get("nameWithOwner")
            nodes = repository["issues"]["nodes"]
            issues.extend(parse_issue(n, project_number, home) for n in nodes)
    except (KeyError, TypeError, ValueError, AttributeError) as exc:
        raise GhError(f"could not read the issue query: {exc!r}") from exc
    return tuple(issues)


def fetch_open_issues(
    repo: str,
    run: Runner = run_gh,
    project_number: int = PLANNING_PROJECT_NUMBER,
) -> tuple[OpenIssue, ...]:
    """Every open Issue on *repo* (``OWNER/NAME``).

    Raises:
        GhError: If *repo* is malformed or the response cannot be read.
        subprocess.CalledProcessError: If ``gh`` exits non-zero.
    """
    owner, sep, name = repo.partition("/")
    if not (sep and owner and name) or "/" in name:
        raise GhError(f"--repo must be OWNER/NAME, got {repo!r}")
    raw = run(
        [
            "api",
            "graphql",
            "--paginate",
            "--slurp",
            "-f",
            f"query={QUERY}",
            "-f",
            f"owner={owner}",
            "-f",
            f"name={name}",
        ]
    )
    try:
        pages = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise GhError(f"could not read the issue query: {exc}") from exc
    return parse_pages(pages, project_number)
