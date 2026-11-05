"""Mirror a history entry onto its GitHub issue as a comment."""

from __future__ import annotations

import subprocess

from vultron.metadata.base import (
    GH_LOOKUP_ERRORS,
    gh_issue_missing,
    gh_issue_view,
    gh_lookup_failure,
)
from vultron.metadata.history.cli.source import SourceRefusedError
from vultron.metadata.history.types import (
    HistoryEntryType,
)

#: The repository whose issues receive history comments (HM-08-001).
_REPO = "CERTCC/Vultron"


def _confirm_issue(n: int) -> int:
    """Return *n* when GitHub has issue *n* in CERTCC/Vultron (HM-08-001).

    ``gh issue view`` answers for a pull request too, so the lookup reads the
    URL and refuses a ``/pull/`` one.

    Raises:
        SourceRefusedError: *n* names no issue, or names a pull request
            (HM-08-009). Nothing is written in either case.
        RuntimeError: ``gh`` could not answer (missing, unauthenticated,
            offline), so the tool cannot tell whether the issue exists and
            stops (HM-08-007).
    """
    try:
        url = str(gh_issue_view(f"#{n}", ["url"], repo=_REPO)["url"])
    except GH_LOOKUP_ERRORS as exc:
        if gh_issue_missing(exc):
            raise SourceRefusedError(
                f"--source ISSUE-{n}: {_REPO} has no issue #{n}"
            ) from exc
        raise RuntimeError(
            f"cannot tell whether --source ISSUE-{n} names an issue in "
            f"{_REPO}: {gh_lookup_failure(exc)}"
        ) from exc
    if "/pull/" in url:
        raise SourceRefusedError(
            f"--source ISSUE-{n}: #{n} is a pull request, not an issue"
        )
    return n


def _post_github_comment(
    issue_number: int,
    entry_type: HistoryEntryType,
    title: str,
    body: str,
) -> str:
    """Post a GitHub comment and return the comment URL.

    The comment body is prefixed with a heading line per HM-08-005:
    ``**History: <type> — <title>**``

    Args:
        issue_number: GitHub issue number.
        entry_type: History entry type (``implementation`` or ``idea``).
        title: Entry title from ``--title``.
        body: Entry body text (no frontmatter).

    Returns:
        The URL of the newly created comment.

    Raises:
        RuntimeError: If the ``gh`` CLI invocation fails.
    """
    heading = f"**History: {entry_type.value} — {title}**"
    comment_body = f"{heading}\n\n{body}"
    result = subprocess.run(
        [
            "gh",
            "issue",
            "comment",
            str(issue_number),
            "--repo",
            _REPO,
            "--body",
            comment_body,
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"gh issue comment failed (exit {result.returncode}): "
            f"{result.stderr.strip()}"
        )
    # ``gh issue comment`` prints the comment URL to stdout.
    url = result.stdout.strip()
    return url
