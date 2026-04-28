"""CLI entry point for the ``append-history`` tool.

Usage::

    uv run append-history <type>           # reads content from stdin
    uv run append-history <type> --file /path/to/entry.md

``<type>`` must be one of the ``HistoryEntryType`` values
(``idea``, ``implementation``, ``priority``).

The tool:

1. Parses ``<type>`` against ``HistoryEntryType``; exits 1 on unknown type.
2. Reads entry content from stdin or ``--file <path>``.
3. Determines the current month: ``datetime.date.today()`` → ``YYMM``.
4. Extracts ``<entry-id>`` from the content's YAML frontmatter ``source``
   field; falls back to ``<type>-<YYMMDDHHMMSS>`` if absent.
5. Creates ``plan/history/YYMM/<type>/`` if missing.
6. Writes content to ``plan/history/YYMM/<type>/<entry-id>.md``.
7. Regenerates ``plan/history/YYMM/README.md``.
8. Prints the written file path to stdout.

See ``specs/history-management.yaml`` HM-03.
"""

from __future__ import annotations

import argparse
import datetime
import sys
from pathlib import Path

import frontmatter

from vultron.metadata.history.readme_gen import regenerate_readme
from vultron.metadata.history.types import HistoryEntryType


def _find_repo_root(start: Path | None = None) -> Path:
    """Return the repository root by searching upward for ``pyproject.toml``.

    Works regardless of the caller's working directory.
    """
    current = (start or Path.cwd()).resolve()
    for parent in [current, *current.parents]:
        if (parent / "pyproject.toml").exists():
            return parent
    return current  # fallback: use cwd if pyproject.toml not found


def _extract_entry_id(content: str, entry_type: str) -> str:
    """Extract the ``source`` field from YAML frontmatter as the entry ID.

    Falls back to ``<type>-<YYMMDDHHMMSS>`` if ``source`` is absent or empty.
    """
    try:
        post = frontmatter.loads(content)
        source = str(post.metadata.get("source", "")).strip()
        if source:
            return source
    except Exception:  # noqa: BLE001
        pass

    timestamp = datetime.datetime.now().strftime("%y%m%d%H%M%S")
    return f"{entry_type}-{timestamp}"


def _build_parser() -> argparse.ArgumentParser:
    valid_types = ", ".join(t.value for t in HistoryEntryType)
    parser = argparse.ArgumentParser(
        prog="append-history",
        description=(
            "Append a write-once entry to the project history archive under "
            "plan/history/. Content is read from stdin by default."
        ),
    )
    parser.add_argument(
        "entry_type",
        metavar="type",
        help=f"History entry type. One of: {valid_types}",
    )
    parser.add_argument(
        "--file",
        metavar="PATH",
        default=None,
        help="Read entry content from FILE instead of stdin.",
    )
    return parser


def main() -> None:
    """Entry point for ``uv run append-history``."""
    parser = _build_parser()
    args = parser.parse_args()

    # Validate type.
    try:
        entry_type = HistoryEntryType(args.entry_type)
    except ValueError:
        valid = ", ".join(t.value for t in HistoryEntryType)
        print(
            f"Error: unknown history type '{args.entry_type}'. "
            f"Valid values: {valid}",
            file=sys.stderr,
        )
        sys.exit(1)

    # Read content.
    if args.file:
        file_path = Path(args.file)
        if not file_path.exists():
            print(f"Error: file not found: {file_path}", file=sys.stderr)
            sys.exit(1)
        content = file_path.read_text(encoding="utf-8")
    else:
        content = sys.stdin.read()

    if not content.strip():
        print("Error: entry content is empty.", file=sys.stderr)
        sys.exit(1)

    # Determine paths.
    repo_root = _find_repo_root()
    today = datetime.date.today()
    yymm = today.strftime("%y%m")
    entry_id = _extract_entry_id(content, entry_type.value)

    entry_dir = repo_root / "plan" / "history" / yymm / entry_type.value
    entry_dir.mkdir(parents=True, exist_ok=True)

    entry_file = entry_dir / f"{entry_id}.md"
    entry_file.write_text(content, encoding="utf-8")

    # Regenerate the monthly README.
    month_dir = repo_root / "plan" / "history" / yymm
    regenerate_readme(month_dir)

    print(str(entry_file))


if __name__ == "__main__":
    main()
