"""Mirror a history entry onto its GitHub issue as a comment."""

from __future__ import annotations

import re
import subprocess

from vultron.metadata.base import (
    GH_LOOKUP_ERRORS,
    gh_issue_missing,
    gh_issue_state,
    gh_lookup_failure,
)
from vultron.metadata.history.types import (
    HistoryEntryType,
)

#: The repository whose issues receive history comments (HM-08-001).
_REPO = "CERTCC/Vultron"

#: A source that may name an issue: ``<PREFIX>-N`` (a run of letters, a
#: hyphen, then digits), such as ``ISSUE-N``, ``TASK-N`` or ``BUG-N``, or a
#: bare number. ``TASK-BTND5`` and ``ISSUE-4646-detail`` do not match.
_ISSUE_SOURCE_RE = re.compile(r"^(?:[A-Za-z]+-)?(\d+)$")


_GITHUB_COMMENT_TYPES = frozenset(
    {HistoryEntryType.implementation, HistoryEntryType.idea}
)


def _parse_issue_number(source: str) -> int | None:
    """Return the N of a ``<PREFIX>-N`` or bare-number *source*, else None.

    Only the form is checked here; :func:`_resolve_issue_number` asks GitHub
    whether issue N exists. Zero is no issue number.
    """
    m = _ISSUE_SOURCE_RE.match(source.strip())
    if m is None:
        return None
    n = int(m.group(1))
    return n if n > 0 else None


def _resolve_issue_number(source: str) -> int | None:
    """Return the existing issue that *source* names, else None.

    *source* names issue N when it has the ``<PREFIX>-N`` or bare-number form
    (:func:`_parse_issue_number`) and ``gh issue view N`` finds N in
    CERTCC/Vultron (HM-08-001). A number GitHub has no issue for, such as the
    date in ``IDEA-26042702``, returns None, and so does any other form
    (HM-08-003).

    Raises:
        RuntimeError: ``gh`` could not answer (missing, unauthenticated,
            offline). The tool then cannot tell a comment from a file, so it
            stops rather than guess.
    """
    n = _parse_issue_number(source)
    if n is None:
        return None
    try:
        gh_issue_state(f"#{n}", repo=_REPO)
    except GH_LOOKUP_ERRORS as exc:
        if gh_issue_missing(exc):
            return None
        raise RuntimeError(
            f"cannot tell whether --source {source!r} names an issue in "
            f"{_REPO}: {gh_lookup_failure(exc)}"
        ) from exc
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
