"""CLI entry point for the ``append-history`` tool.

Usage::

    uv run append-history <type>           # reads content from stdin
    uv run append-history <type> --file /path/to/entry.md

``<type>`` must be one of the ``HistoryEntryType`` values
(``idea``, ``implementation``, ``learning``, ``priority``).

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
from pydantic import ValidationError

from vultron.metadata.history.models import HistoryEntryFrontmatter
from vultron.metadata.history.readme_gen import regenerate_readme
from vultron.metadata.history.types import HistoryEntryType


def _find_repo_root(start: Path | None = None) -> Path:
    """Return the repository root by searching upward for ``pyproject.toml``.

    Works regardless of the caller's working directory.

    Raises:
        FileNotFoundError: If ``pyproject.toml`` cannot be found in any
            parent directory, indicating the tool was invoked outside a
            Vultron repository.
    """
    origin = (start or Path.cwd()).resolve()
    for parent in [origin, *origin.parents]:
        if (parent / "pyproject.toml").exists():
            return parent
    raise FileNotFoundError(
        f"Could not locate repository root (pyproject.toml) starting from {origin}"
    )


def _validate_frontmatter(content: str) -> HistoryEntryFrontmatter:
    """Parse and validate YAML frontmatter from *content*.

    Raises:
        ValueError: If the frontmatter is malformed, missing, or fails
            required-field validation (HM-02-001).
    """
    try:
        post = frontmatter.loads(content)
    except Exception as exc:  # noqa: BLE001
        raise ValueError(f"malformed YAML frontmatter: {exc}") from exc

    if not post.metadata:
        raise ValueError(
            "missing frontmatter block: entry must begin with a YAML "
            "frontmatter block containing title, type, date, and source"
        )

    try:
        return HistoryEntryFrontmatter.model_validate(post.metadata)
    except ValidationError as exc:
        # Collect field names for a concise, actionable error message.
        missing = [e["loc"][0] for e in exc.errors() if e["loc"]]
        fields = ", ".join(str(f) for f in missing) if missing else str(exc)
        raise ValueError(
            f"invalid history frontmatter: missing or invalid field(s): {fields}"
        ) from exc


def _sanitize_entry_id(entry_id: str) -> str:
    """Validate and sanitize *entry_id* to prevent path traversal.

    Raises:
        ValueError: If *entry_id* contains path separators or ``..``
            components that could write outside the intended directory.
    """
    if not entry_id:
        raise ValueError("entry_id must not be empty")
    # Reject path separators and parent-directory traversal.
    if "/" in entry_id or "\\" in entry_id:
        raise ValueError(f"entry_id contains path separators: {entry_id!r}")
    if ".." in entry_id:
        raise ValueError(f"entry_id contains '..' component: {entry_id!r}")
    # Verify the resolved filename stays within the intended directory by
    # checking Path properties (no directory component allowed).
    p = Path(entry_id)
    if p.parent != Path("."):
        raise ValueError(
            f"entry_id must be a plain filename, not a path: {entry_id!r}"
        )
    return entry_id


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
    parser.add_argument(
        "--date",
        metavar="YYYY-MM-DD",
        default=None,
        help=argparse.SUPPRESS,
    )
    return parser


def _parse_iso_date(value: str) -> datetime.date:
    """Parse an ISO date string for internal backfill callers."""
    try:
        return datetime.date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(
            f"invalid date '{value}'; expected YYYY-MM-DD"
        ) from exc


def append_history_entry(
    entry_type: HistoryEntryType,
    content: str,
    *,
    repo_root: Path | None = None,
    target_date: datetime.date | None = None,
) -> Path:
    """Write a history entry and regenerate the monthly README.

    Args:
        entry_type: Valid history entry type.
        content: Full markdown content including YAML frontmatter.
        repo_root: Optional repository root override.
        target_date: Optional historical date for backfill callers.

    Returns:
        Path to the written history entry.

    Raises:
        ValueError: If content is empty, frontmatter is invalid, or the
            frontmatter ``type`` field does not match *entry_type*.
        FileExistsError: If the target entry file already exists.
    """
    if not content.strip():
        raise ValueError("entry content is empty")

    validated = _validate_frontmatter(content)
    if validated.type != entry_type:
        raise ValueError(
            f"type mismatch: CLI argument is '{entry_type}' but frontmatter "
            f"'type' field is '{validated.type}'"
        )

    resolved_root = _find_repo_root(repo_root)
    resolved_date = target_date or datetime.date.today()
    yymm = resolved_date.strftime("%y%m")
    entry_id = _sanitize_entry_id(validated.source)

    entry_dir = resolved_root / "plan" / "history" / yymm / entry_type.value
    entry_dir.mkdir(parents=True, exist_ok=True)

    entry_file = entry_dir / f"{entry_id}.md"
    if entry_file.exists():
        raise FileExistsError(f"history entry already exists: {entry_file}")

    entry_file.write_text(content, encoding="utf-8")

    month_dir = resolved_root / "plan" / "history" / yymm
    try:
        regenerate_readme(month_dir)
    except Exception as exc:
        entry_file.unlink(missing_ok=True)
        raise ValueError(
            f"README generation failed; entry rolled back: {exc}"
        ) from exc
    return entry_file


def main() -> None:
    """Entry point for ``uv run append-history``."""
    parser = _build_parser()
    args = parser.parse_args()

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

    if args.file:
        file_path = Path(args.file)
        if not file_path.exists():
            print(f"Error: file not found: {file_path}", file=sys.stderr)
            sys.exit(1)
        content = file_path.read_text(encoding="utf-8")
    else:
        content = sys.stdin.read()

    try:
        target_date = (
            _parse_iso_date(args.date) if args.date is not None else None
        )
        entry_file = append_history_entry(
            entry_type,
            content,
            target_date=target_date,
        )
    except (FileExistsError, FileNotFoundError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    print(str(entry_file))


if __name__ == "__main__":
    main()
