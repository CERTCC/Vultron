"""The ``append-history`` argument parser and its two input modes."""

from __future__ import annotations

import argparse
import datetime
import sys
from pathlib import Path
from typing import NoReturn

from vultron.metadata.history.cli.entry import (
    _build_content,
    _check_timestamp_not_future,
    _parse_iso_datetime,
    _validate_frontmatter,
    append_history_entry,
)
from vultron.metadata.history.cli.github import (
    _confirm_issue,
    _post_github_comment,
)
from vultron.metadata.history.cli.source import classify_source
from vultron.metadata.history.types import (
    RETIRED_SIGNALS,
    HistoryEntryType,
    LearningSignalType,
)


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
            "Originating identifier. implementation and idea entries take "
            "ISSUE-N, posted as a comment on CERTCC/Vultron issue N; "
            "otherwise implementation takes ISSUE-N-<slug> and idea takes "
            "IDEA-YYMMDDNN, each written to a file. learning, note and "
            "priority sources are free-form. "
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
    valid_signals = ", ".join(
        s.value for s in LearningSignalType if s not in RETIRED_SIGNALS
    )
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
        signal = LearningSignalType(value)
    except ValueError:
        valid = ", ".join(s.value for s in LearningSignalType)
        _fail(f"unknown signal type '{value}'. Valid values: {valid}")
    if signal in RETIRED_SIGNALS:
        active = ", ".join(
            s.value for s in LearningSignalType if s not in RETIRED_SIGNALS
        )
        _fail(
            f"signal type '{value}' is retired (BW-07-002). Findings of this "
            f"kind are routed at discovery to a GitHub issue or an in-session "
            f"fix (BW-07-004), not to a learning file. Valid values: {active}"
        )
    return signal


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
        issue = classify_source(fm.type, fm.source)
    except ValueError as exc:
        _fail(str(exc))
    # An ISSUE-N implementation or idea entry is a comment, never a file
    # (HM-01-008); only the vocabulary's file forms may be archived here.
    if issue is not None:
        _fail(
            f"{source_path}: an {fm.type.value} entry with source "
            f"{fm.source} is posted as an issue comment; run "
            f"append-history {fm.type.value} --source {fm.source} instead"
        )

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
            discriminator=source_path.stem,
        )
    except (FileExistsError, FileNotFoundError, ValueError) as exc:
        _fail(str(exc))

    source_path.unlink()
    print(str(entry_file))


def _handle_normal_mode(args: argparse.Namespace) -> None:
    """Execute the normal (non-from-file) append-history flow."""
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

    # Validate the title, source and timestamp before either output mode, so
    # a comment is never posted for an entry a file would refuse. The source
    # vocabulary decides the mode: ISSUE-N is a comment, the file forms are
    # files, anything else is refused (HM-08-001, HM-08-003, HM-08-008).
    try:
        issue_number = classify_source(entry_type, args.source)
        content = _build_content(
            entry_type, args.title, args.source, body, timestamp, signal
        )
        # Future-date check only for explicit --timestamp overrides (HM-06-004).
        # Auto-generated timestamps from NewHistoryEntry.default_factory are
        # always "now" and cannot be in the future.
        if timestamp is not None:
            _check_timestamp_not_future(timestamp)
    except ValueError as exc:
        _fail(str(exc))

    # GitHub comment mode: ISSUE-N, once GitHub confirms issue N (HM-08-001,
    # HM-08-007, HM-08-009).
    if issue_number is not None:
        try:
            url = _post_github_comment(
                _confirm_issue(issue_number), entry_type, args.title, body
            )
        except (RuntimeError, ValueError) as exc:
            _fail(str(exc))
        print(url)
        return

    try:
        target_date = timestamp.date() if timestamp is not None else None
        entry_file = append_history_entry(
            entry_type,
            content,
            target_date=target_date,
        )
    except (FileExistsError, FileNotFoundError, ValueError) as exc:
        _fail(str(exc))

    print(str(entry_file))


def main() -> None:
    """Entry point for ``uv run append-history``."""
    parser = _build_parser()
    args = parser.parse_args()

    if args.from_file is not None:
        _check_from_file_conflicts(args)
        _handle_from_file_mode(Path(args.from_file))
        return

    _handle_normal_mode(args)
