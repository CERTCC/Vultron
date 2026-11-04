"""Mirror a history entry onto its GitHub issue as a comment."""

from __future__ import annotations

import re
import subprocess

from vultron.metadata.history.types import (
    HistoryEntryType,
)

_ISSUE_NUMBER_RE = re.compile(r"^(?:ISSUE-)?(\d+)$", re.IGNORECASE)


_GITHUB_COMMENT_TYPES = frozenset(
    {HistoryEntryType.implementation, HistoryEntryType.idea}
)


def _resolve_issue_number(source: str) -> int | None:
    """Return a GitHub issue number if *source* resolves to one, else None.

    Accepts ``ISSUE-N`` (case-insensitive) or a bare positive integer.
    Returns ``None`` for all other formats (HM-08-001, HM-08-003).
    """
    m = _ISSUE_NUMBER_RE.match(source.strip())
    if m is None:
        return None
    n = int(m.group(1))
    return n if n > 0 else None


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
            "CERTCC/Vultron",
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
