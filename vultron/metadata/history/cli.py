"""CLI entry point for the ``append-history`` tool.

Usage::

    uv run append-history <type> --title "..." --source "..."
    uv run append-history <type> --title "..." --source "..." --file /path/to/body.md
    uv run append-history --from-file plan/incoming/learnings/20260622-SLUG.md

``<type>`` must be one of the ``HistoryEntryType`` values
(``idea``, ``implementation``, ``learning``, ``priority``).

Normal mode (``<type>`` required):

1. Parses ``<type>`` against ``HistoryEntryType``; exits 1 on unknown type.
2. Reads body text from stdin or ``--file <path>``.
3. Constructs a YAML frontmatter block from ``--title``, ``--source``, the
   entry type, and an auto-generated UTC timestamp (HM-07-001).
4. Validates the constructed frontmatter via ``HistoryEntryFrontmatter``
   (includes future-date and tz-aware checks, HM-06-004, HM-06-005).
5. Creates ``plan/history/YYMM/<type>/`` if missing.
6. Writes content (frontmatter + body) to
   ``plan/history/YYMM/<type>/<entry-id>.md``.
7. Regenerates ``plan/history/YYMM/README.md``.
8. Prints the written file path to stdout.

``--from-file`` mode (for ``plan/incoming/learnings/`` processing):

1. Reads the source file as complete content (frontmatter + body).
2. Parses and validates the frontmatter to obtain type, title, source,
   and timestamp (HM-02-001).
3. Moves the entry to ``plan/history/YYMM/<type>/`` using the frontmatter
   timestamp to determine the ``YYMM`` directory.
4. Deletes the source file from ``plan/incoming/``.
5. Prints the written file path to stdout.

``--from-file`` is mutually exclusive with ``<type>``, ``--title``,
``--source``, ``--file``, and ``--timestamp``.

See ``specs/history-management.yaml`` HM-03, HM-06, HM-07.
See ``specs/build-workflow.yaml`` BW-01 for the incoming-learnings queue.
"""

from __future__ import annotations

import argparse
import datetime
import sys
from pathlib import Path
from typing import NoReturn

import yaml
from pydantic import ValidationError

from vultron.metadata.history.models import (
    HistoryEntryFrontmatter,
    NewHistoryEntry,
)
from vultron.metadata.history.readme_gen import regenerate_readme
from vultron.metadata.history.types import HistoryEntryType, LearningSignalType

_UTC = datetime.timezone.utc


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
            required-field validation (HM-02-001, HM-06-002).
    """
    import frontmatter as _fm

    try:
        post = _fm.loads(content)
    except Exception as exc:  # noqa: BLE001
        raise ValueError(f"malformed YAML frontmatter: {exc}") from exc

    if not post.metadata:
        raise ValueError(
            "missing frontmatter block: entry must begin with a YAML "
            "frontmatter block containing title, type, timestamp, and source"
        )

    try:
        return HistoryEntryFrontmatter.model_validate(post.metadata)
    except ValidationError as exc:
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
    if "/" in entry_id or "\\" in entry_id:
        raise ValueError(f"entry_id contains path separators: {entry_id!r}")
    if ".." in entry_id:
        raise ValueError(f"entry_id contains '..' component: {entry_id!r}")
    p = Path(entry_id)
    if p.parent != Path("."):
        raise ValueError(
            f"entry_id must be a plain filename, not a path: {entry_id!r}"
        )
    return entry_id


def _check_timestamp_not_future(ts: datetime.datetime) -> None:
    """Raise ValueError if *ts* is more than 60 seconds in the future (HM-06-004)."""
    now = datetime.datetime.now(_UTC)
    tolerance = datetime.timedelta(seconds=60)
    if ts > now + tolerance:
        raise ValueError(
            f"timestamp {ts.isoformat()} is in the future "
            f"(current UTC time: {now.isoformat()}); "
            "new history entries must not have future timestamps"
        )


def _build_content(
    entry_type: HistoryEntryType,
    title: str,
    source: str,
    body: str,
    timestamp: datetime.datetime | None = None,
    signal: LearningSignalType | None = None,
) -> str:
    """Construct the full entry markdown (frontmatter + body).

    Uses :class:`NewHistoryEntry` as the timestamper-of-record: if
    *timestamp* is ``None`` the model self-timestamps to UTC now
    (HM-06-001, HM-07-002).  Pass *timestamp* only for backfill overrides.

    The frontmatter ``timestamp`` is serialised as a quoted ISO 8601 string
    so that YAML parsers treat it as a string rather than a native datetime
    (ensuring round-trip fidelity of the UTC offset, HM-06-001).

    The optional *signal* field is only emitted for ``learning`` entries and
    only when a value is provided (BW-07-002).

    Returns:
        Full markdown string beginning with a YAML frontmatter block.
    """
    if timestamp is not None:
        entry = NewHistoryEntry(
            type=entry_type,
            title=title,
            source=source,
            timestamp=timestamp,
            signal=signal,
        )
    else:
        entry = NewHistoryEntry(
            type=entry_type, title=title, source=source, signal=signal
        )

    fm: dict[str, object] = {
        "title": entry.title,
        "type": str(entry.type.value),
        "source": entry.source,
        # Store as a plain string so YAML parsers don't strip the tz offset.
        "timestamp": entry.timestamp.isoformat(),
    }
    if entry.signal is not None:
        fm["signal"] = str(entry.signal.value)
    fm_yaml = yaml.safe_dump(fm, default_flow_style=False, allow_unicode=True)
    sep = "\n" if body and not body.startswith("\n") else ""
    return f"---\n{fm_yaml}---\n{sep}{body}"


def _build_parser() -> argparse.ArgumentParser:
    valid_types = ", ".join(t.value for t in HistoryEntryType)
    parser = argparse.ArgumentParser(
        prog="append-history",
        description=(
            "Append a write-once entry to the project history archive under "
            "plan/history/. Body text is read from stdin by default. "
            "Use --from-file to move a pre-formatted incoming learning file."
        ),
    )
    parser.add_argument(
        "entry_type",
        metavar="type",
        nargs="?",
        default=None,
        help=(
            f"History entry type. One of: {valid_types}. "
            "Required unless --from-file is provided."
        ),
    )
    parser.add_argument(
        "--title",
        default=None,
        metavar="TEXT",
        help=(
            "Human-readable summary for the entry frontmatter. "
            "Required unless --from-file is provided."
        ),
    )
    parser.add_argument(
        "--source",
        default=None,
        metavar="ID",
        help=(
            "Originating identifier (e.g. IDEA-26043001, TASK-FOO). "
            "Required unless --from-file is provided."
        ),
    )
    parser.add_argument(
        "--file",
        metavar="PATH",
        default=None,
        help="Read body text from FILE instead of stdin. Incompatible with --from-file.",
    )
    parser.add_argument(
        "--from-file",
        metavar="PATH",
        default=None,
        dest="from_file",
        help=(
            "Move a pre-formatted incoming learning file (with YAML frontmatter) "
            "to plan/history/YYMM/<type>/ and delete the source. "
            "Incompatible with type, --title, --source, --file, --timestamp."
        ),
    )
    parser.add_argument(
        "--timestamp",
        metavar="DATETIME",
        default=None,
        help=argparse.SUPPRESS,  # backfill only
    )
    valid_signals = ", ".join(s.value for s in LearningSignalType)
    parser.add_argument(
        "--signal",
        metavar="TYPE",
        default=None,
        help=(
            f"Optional signal classification for learning entries (BW-07-002). "
            f"One of: {valid_signals}. Ignored for non-learning entry types."
        ),
    )
    return parser


def _parse_iso_datetime(value: str) -> datetime.datetime:
    """Parse an ISO 8601 datetime string for the hidden ``--timestamp`` flag."""
    try:
        dt = datetime.datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(
            f"invalid datetime '{value}'; expected ISO 8601 with UTC offset "
            "(e.g. 2026-05-01T15:30:00+00:00)"
        ) from exc
    if dt.tzinfo is None:
        raise ValueError(
            f"datetime '{value}' has no timezone; provide a UTC offset "
            "(e.g. +00:00)"
        )
    return dt.astimezone(_UTC)


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
        target_date: Optional historical date for backfill callers (controls
            the ``YYMM`` directory; defaults to today).

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


def _fail(message: str, *, exit_code: int = 1) -> NoReturn:
    print(f"Error: {message}", file=sys.stderr)
    sys.exit(exit_code)


def _parse_entry_type(value: str) -> HistoryEntryType:
    try:
        return HistoryEntryType(value)
    except ValueError:
        valid = ", ".join(t.value for t in HistoryEntryType)
        _fail(f"unknown history type '{value}'. Valid values: {valid}")


def _read_body(file_arg: str | None) -> str:
    if file_arg is None:
        body = sys.stdin.read()
    else:
        file_path = Path(file_arg)
        if not file_path.exists():
            _fail(f"file not found: {file_path}")
        body = file_path.read_text(encoding="utf-8")

    if body.strip():
        return body
    _fail("body text is empty; provide content via stdin or --file")


def _parse_timestamp(value: str | None) -> datetime.datetime | None:
    if value is None:
        return None
    try:
        return _parse_iso_datetime(value)
    except ValueError as exc:
        _fail(str(exc))


def _parse_signal(
    value: str | None, entry_type: HistoryEntryType
) -> LearningSignalType | None:
    """Parse and validate the optional ``--signal`` flag value."""
    if value is None:
        return None
    if entry_type != HistoryEntryType.learning:
        _fail(
            f"--signal is only valid for 'learning' entries, "
            f"not '{entry_type}'"
        )
    try:
        return LearningSignalType(value)
    except ValueError:
        valid = ", ".join(s.value for s in LearningSignalType)
        _fail(f"unknown signal type '{value}'. Valid values: {valid}")


def _check_from_file_conflicts(args: argparse.Namespace) -> None:
    """Fail if --from-file is combined with incompatible normal-mode flags."""
    conflicts = []
    if args.entry_type is not None:
        conflicts.append("positional type argument")
    if args.title is not None:
        conflicts.append("--title")
    if args.source is not None:
        conflicts.append("--source")
    if args.file is not None:
        conflicts.append("--file")
    if args.timestamp is not None:
        conflicts.append("--timestamp")
    if conflicts:
        _fail(
            f"--from-file is incompatible with: {', '.join(conflicts)}. "
            "Provide only --from-file when moving a pre-formatted incoming file."
        )


def _handle_from_file_mode(source_path: Path) -> None:
    """Archive a pre-formatted incoming learning file into plan/history/.

    Reads the file's YAML frontmatter to determine the entry type, source
    identifier, and timestamp, then delegates to :func:`append_history_entry`.
    The source file is deleted after a successful write.

    Args:
        source_path: Path to the incoming learning file with YAML frontmatter.

    Raises:
        SystemExit: On any validation or write error (via :func:`_fail`).
    """
    if not source_path.exists():
        _fail(f"file not found: {source_path}")

    content = source_path.read_text(encoding="utf-8")

    try:
        fm = _validate_frontmatter(content)
    except ValueError as exc:
        _fail(str(exc))

    try:
        _check_timestamp_not_future(fm.timestamp)
    except ValueError as exc:
        _fail(str(exc))
    target_date = fm.timestamp.date()

    try:
        entry_file = append_history_entry(
            fm.type,
            content,
            target_date=target_date,
        )
    except (FileExistsError, FileNotFoundError, ValueError) as exc:
        _fail(str(exc))

    source_path.unlink()
    print(str(entry_file))


def main() -> None:
    """Entry point for ``uv run append-history``."""
    parser = _build_parser()
    args = parser.parse_args()

    if args.from_file is not None:
        _check_from_file_conflicts(args)
        _handle_from_file_mode(Path(args.from_file))
        return

    # Normal mode — require entry_type, --title, --source.
    if not args.entry_type:
        _fail(
            "entry type is required when --from-file is not provided. "
            f"Valid values: {', '.join(t.value for t in HistoryEntryType)}"
        )
    if not args.title:
        _fail("--title is required when --from-file is not provided")
    if not args.source:
        _fail("--source is required when --from-file is not provided")

    entry_type = _parse_entry_type(args.entry_type)
    body = _read_body(args.file)
    timestamp = _parse_timestamp(args.timestamp)
    signal = _parse_signal(args.signal, entry_type)

    try:
        content = _build_content(
            entry_type, args.title, args.source, body, timestamp, signal
        )
        # Future-date check only for explicit --timestamp overrides (HM-06-004).
        # Auto-generated timestamps from NewHistoryEntry.default_factory are
        # always "now" and cannot be in the future.
        if timestamp is not None:
            _check_timestamp_not_future(timestamp)
        target_date = timestamp.date() if timestamp is not None else None
        entry_file = append_history_entry(
            entry_type,
            content,
            target_date=target_date,
        )
    except (FileExistsError, FileNotFoundError, ValueError) as exc:
        _fail(str(exc))

    print(str(entry_file))


if __name__ == "__main__":
    main()
