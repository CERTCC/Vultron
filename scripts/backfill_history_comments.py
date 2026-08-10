"""One-time backfill: post plan/history/2608/{implementation,idea}/ISSUE-N.md
files as GitHub issue comments, then git-rm the files.

Usage::

    python scripts/backfill_history_comments.py [--dry-run]

Implements ISSUE-2160 AC-1 through AC-4.

AC-1: For each plan/history/2608/{implementation,idea}/ISSUE-N.md file,
      post the file body as a comment on issue #N and git-rm the file.
AC-2: Files whose filename does NOT match ISSUE-N.md are left in place.
AC-3: A single commit (done by the caller, not this script) removes all
      backfilled files.
AC-4: After the run, only non-ISSUE-N entries remain.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

_ISSUE_RE = re.compile(r"^ISSUE-(\d+)\.md$")
_REPO = "CERTCC/Vultron"
_HISTORY_BASE = Path("plan/history/2608")
_ENTRY_TYPES = ("implementation", "idea")


def _parse_frontmatter_fields(text: str) -> dict[str, str]:
    """Extract title and type from YAML frontmatter (minimal parser)."""
    result: dict[str, str] = {}
    in_fm = False
    for i, line in enumerate(text.splitlines()):
        if i == 0 and line.strip() == "---":
            in_fm = True
            continue
        if in_fm and line.strip() == "---":
            break
        if in_fm:
            m = re.match(r"^(\w+):\s*(.+)$", line)
            if m:
                result[m.group(1)] = m.group(2).strip("'\"")
    return result


def _body_only(text: str) -> str:
    """Strip YAML frontmatter and return the body."""
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        return text
    end = None
    for i, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            end = i
            break
    if end is None:
        return text
    body = "".join(lines[end + 1 :])
    return body.lstrip("\n")


def _post_comment(
    issue_number: int, entry_type: str, title: str, body: str
) -> str:
    """Post a GitHub comment and return the URL."""
    heading = f"**History: {entry_type} — {title}**"
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
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"gh issue comment #{issue_number} failed (exit {result.returncode}): "
            f"{result.stderr.strip()}"
        )
    return result.stdout.strip()


def _git_rm(path: Path) -> None:
    result = subprocess.run(
        ["git", "rm", str(path)],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"git rm {path} failed (exit {result.returncode}): "
            f"{result.stderr.strip()}"
        )


def collect_targets() -> list[tuple[str, Path]]:
    """Return (entry_type, path) pairs for each ISSUE-N.md file to backfill."""
    targets = []
    for entry_type in _ENTRY_TYPES:
        d = _HISTORY_BASE / entry_type
        if not d.is_dir():
            continue
        for p in sorted(d.glob("*.md")):
            if _ISSUE_RE.match(p.name):
                targets.append((entry_type, p))
    return targets


def main() -> None:  # noqa: C901
    parser = argparse.ArgumentParser(
        description="Backfill plan/history/2608 ISSUE-N.md files as GitHub comments."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would happen without posting or deleting anything.",
    )
    args = parser.parse_args()

    targets = collect_targets()
    if not targets:
        print("No ISSUE-N.md files found to backfill.")
        return

    print(f"Found {len(targets)} file(s) to backfill.")
    errors: list[str] = []

    for entry_type, path in targets:
        issue_number = int(_ISSUE_RE.match(path.name).group(1))  # type: ignore[union-attr]
        text = path.read_text(encoding="utf-8")
        fm = _parse_frontmatter_fields(text)
        title = fm.get("title", path.stem)
        body = _body_only(text)

        if args.dry_run:
            print(
                f"[dry-run] Would post {path} → issue #{issue_number} "
                f"({entry_type}: {title!r}) and git-rm it."
            )
            continue

        try:
            url = _post_comment(issue_number, entry_type, title, body)
            print(f"  Posted {path.name} → {url}")
        except RuntimeError as exc:
            print(f"  ERROR posting {path.name}: {exc}", file=sys.stderr)
            errors.append(str(exc))
            continue

        try:
            _git_rm(path)
            print(f"  git rm {path}")
        except RuntimeError as exc:
            print(
                f"  ERROR git-rm {path.name}: {exc}",
                file=sys.stderr,
            )
            errors.append(str(exc))

    if errors:
        print(f"\n{len(errors)} error(s) occurred:", file=sys.stderr)
        for e in errors:
            print(f"  {e}", file=sys.stderr)
        sys.exit(1)

    if not args.dry_run:
        print(f"\nBackfill complete: {len(targets)} file(s) processed.")


if __name__ == "__main__":
    main()
