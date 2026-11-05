"""Build, validate and write one history entry file (:func:`append_history_entry`)."""

from __future__ import annotations

import contextlib
import datetime
from pathlib import Path

import yaml

from vultron.metadata.base import repo_root as _find_repo_root
from vultron.metadata.file_loading import (
    MetadataLoadError,
    loads_frontmatter,
    validate,
)
from vultron.metadata.history.models import (
    HistoryEntryFrontmatter,
    NewHistoryEntry,
)
from vultron.metadata.history.readme_gen import regenerate_readme
from vultron.metadata.history.types import (
    HistoryEntryType,
    LearningSignalType,
)

_UTC = datetime.UTC


def _check_body_has_no_frontmatter(body: str) -> None:
    """Raise ValueError if *body* opens with a YAML mapping frontmatter block.

    In stdin or ``--file`` mode the caller supplies body text only; the tool
    builds frontmatter from ``--title`` and ``--source`` (HM-07-005).
    A body whose first non-blank content is a ``---``-delimited YAML mapping
    violates HM-07-002.

    ``--from-file`` mode is exempt: that path calls :func:`_validate_frontmatter`,
    which *requires* a mapping block.

    Args:
        body: Raw body text from stdin or ``--file``.

    Raises:
        ValueError: If *body* contains a YAML mapping frontmatter block
            (HM-07-002).
    """
    try:
        post = loads_frontmatter(body)
    except MetadataLoadError:
        # The ``---`` block exists but is not a YAML mapping (e.g. a list).
        # That is not a frontmatter mapping; let the normal build proceed.
        return
    if post.metadata:
        raise ValueError(
            "body must not include a YAML frontmatter block (HM-07-002): "
            "append-history builds frontmatter from --title and --source; "
            "supply only the body text"
        )


def _validate_frontmatter(content: str) -> HistoryEntryFrontmatter:
    """Parse and validate YAML frontmatter from *content*.

    Raises:
        ValueError: If the frontmatter is malformed, missing, or fails
            required-field validation (HM-02-001, HM-06-002, HM-06-010).
    """
    # The no-path form: the content has not been written anywhere yet.
    post = loads_frontmatter(content)

    if not post.metadata:
        raise MetadataLoadError(
            "missing frontmatter block: entry must begin with a YAML "
            "frontmatter block containing title, type, timestamp, and source"
        )

    return validate(
        HistoryEntryFrontmatter,
        post.metadata,
        prefix="invalid history frontmatter",
    )


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
    discriminator: str | None = None,
) -> Path:
    """Write a history entry and regenerate the monthly README.

    Args:
        entry_type: Valid history entry type.
        content: Full markdown content including YAML frontmatter.
        repo_root: Optional repository root override.
        target_date: Optional historical date for backfill callers (controls
            the ``YYMM`` directory; defaults to today).
        discriminator: Optional per-entry suffix used to disambiguate a second
            entry sharing the same ``source``. One work item may legitimately
            produce several learnings (BW-01-009; BW-01-003 names incoming files
            ``YYYYMMDD-SLUG`` precisely so concurrent PRs do not collide), so
            ``<entry-id>`` alone is not unique. When the plain
            ``<entry-id>.md`` path is taken and a discriminator is supplied,
            the entry is written to ``<entry-id>-<discriminator>.md``
            (HM-01-009). Write-once is preserved: an existing file is never
            overwritten (HM-01-010).

    Returns:
        Path to the written history entry.

    Raises:
        ValueError: If content is empty, frontmatter is invalid, or the
            frontmatter ``type`` field does not match *entry_type*.
        FileExistsError: If the target entry file already exists and no
            discriminator was supplied, or if the discriminated path is also
            taken.
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
    resolved_date = target_date or datetime.datetime.now(_UTC).date()
    yymm = resolved_date.strftime("%y%m")
    entry_id = _sanitize_entry_id(validated.source)

    entry_dir = resolved_root / "plan" / "history" / yymm / entry_type.value
    entry_dir.mkdir(parents=True, exist_ok=True)

    entry_file = entry_dir / f"{entry_id}.md"
    if entry_file.exists() and discriminator:
        disc = _sanitize_entry_id(discriminator)
        # The incoming slug often already embeds the entry id; don't repeat it.
        stem = (
            disc
            if (disc == entry_id or disc.startswith(entry_id + "-"))
            else f"{entry_id}-{disc}"
        )
        entry_file = entry_dir / f"{stem}.md"
    if entry_file.exists():
        raise FileExistsError(f"history entry already exists: {entry_file}")

    entry_file.write_text(content, encoding="utf-8")

    month_dir = resolved_root / "plan" / "history" / yymm
    try:
        regenerate_readme(month_dir)
    except Exception as exc:
        entry_file.unlink(missing_ok=True)
        with contextlib.suppress(OSError):
            entry_dir.rmdir()
        raise ValueError(
            f"README generation failed; entry rolled back: {exc}"
        ) from exc
    return entry_file
