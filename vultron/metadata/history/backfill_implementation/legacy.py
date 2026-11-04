"""Read ``IMPLEMENTATION_HISTORY.md``: its sections, dates, titles and sources."""

from __future__ import annotations

import datetime
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

import yaml

from vultron.metadata.history.types import HistoryEntryType

_HEADING_RE = re.compile(r"^##\s+(.+)$", re.MULTILINE)


_DATE_RE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")


_DATE_PREFIX_RE = re.compile(r"^\d{4}-\d{2}-\d{2}\s+[—-]\s+")


_PHASE_PREFIX_RE = re.compile(r"^Phase\s+")


_STATUS_SUFFIX_RE = re.compile(
    r"\s+\((?:COMPLETE|archived)\b[^)]*\)$",
    re.IGNORECASE,
)


_CLEAR_ID_RE = re.compile(
    r"^(?P<source>[A-Z][A-Z0-9]*(?:-[A-Z0-9.]+)+[A-Za-z0-9]?)\b"
)


_MAX_SLUG_LENGTH = 48


@dataclass(frozen=True)
class LegacySection:
    """A single ``##`` section from the legacy implementation history file."""

    heading_line: int
    raw_heading: str
    body: str


def _line_number(text: str, offset: int) -> int:
    """Return the 1-based line number for a character offset."""
    return text.count("\n", 0, offset) + 1


def split_legacy_sections(text: str) -> list[LegacySection]:
    """Split a legacy history file into one section per ``##`` heading."""
    matches = list(_HEADING_RE.finditer(text))
    sections: list[LegacySection] = []
    for index, match in enumerate(matches):
        body_start = match.end()
        body_end = (
            matches[index + 1].start()
            if index + 1 < len(matches)
            else len(text)
        )
        body = text[body_start:body_end].strip()
        body = re.sub(r"\n?---\s*\Z", "", body).strip()
        sections.append(
            LegacySection(
                heading_line=_line_number(text, match.start()),
                raw_heading=match.group(1).strip(),
                body=body,
            )
        )
    return sections


def _blame_dates_for_file(
    repo_root: Path, legacy_file: Path
) -> dict[int, str]:
    """Return a mapping of line number to git blame date for a file."""
    relative_path = legacy_file.relative_to(repo_root)
    command = [
        "git",
        "--no-pager",
        "blame",
        "-M",
        "-C",
        "--date=short",
        "--",
        str(relative_path),
    ]
    result = subprocess.run(
        command,
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=True,
    )
    blame_dates: dict[int, str] = {}
    for line in result.stdout.splitlines():
        match = re.search(r"\((?:.+?)\s+(\d{4}-\d{2}-\d{2})\s+(\d+)\)\s", line)
        if match is None:
            continue
        blame_dates[int(match.group(2))] = match.group(1)
    return blame_dates


def _extract_advisory_dates(raw_heading: str) -> list[str]:
    """Extract any ISO dates visible in the legacy heading text."""
    dates = list(dict.fromkeys(_DATE_RE.findall(raw_heading)))
    return dates


def normalize_title(raw_heading: str) -> str:
    """Normalize a legacy heading into a frontmatter title."""
    title = _DATE_PREFIX_RE.sub("", raw_heading.strip())
    title = _PHASE_PREFIX_RE.sub("", title)
    title = _STATUS_SUFFIX_RE.sub("", title)
    return title.strip()


def _extract_source_candidate(title: str) -> str | None:
    """Return a reusable task-like identifier when the title starts with one."""
    match = _CLEAR_ID_RE.match(title)
    if match is None:
        return None

    candidate = match.group("source")
    remainder = title[len(candidate) :].lstrip()
    if not remainder:
        return candidate
    if remainder.startswith((",", "/", "+", "&")):
        return None
    if remainder.startswith(
        ("—", ":", "complete", "partial", "verified", "(")
    ):
        return candidate
    return None


def _slugify_title(title: str) -> str:
    """Create a filesystem-safe slug for synthetic legacy source IDs."""
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    if not slug:
        return "entry"
    return slug[:_MAX_SLUG_LENGTH].rstrip("-")


def _build_synthetic_source(
    canonical_date: str,
    title: str,
    target_month: str,
    repo_root: Path,
    used_paths: set[Path],
) -> str:
    """Create a deterministic synthetic source ID that avoids path collisions."""
    slug = _slugify_title(title)
    base = f"LEGACY-{canonical_date}-{slug}"
    attempt = base
    suffix = 2
    while True:
        target_path = (
            repo_root
            / "plan"
            / "history"
            / target_month
            / "implementation"
            / f"{attempt}.md"
        )
        if target_path not in used_paths and not target_path.exists():
            return attempt
        attempt = f"{base}-{suffix}"
        suffix += 1


def _render_entry_markdown(
    *,
    title: str,
    source: str,
    canonical_date: str,
    raw_heading: str,
    legacy_rel_path: str,
    heading_line: int,
    advisory_dates: list[str],
    body: str,
) -> str:
    """Render a backfilled implementation history entry."""
    ts = datetime.datetime(
        *datetime.date.fromisoformat(canonical_date).timetuple()[:3],
        tzinfo=datetime.UTC,
    ).isoformat()
    metadata: dict[str, object] = {
        "title": title,
        "type": HistoryEntryType.implementation.value,
        "timestamp": ts,
        "source": source,
        "legacy_file": legacy_rel_path,
        "legacy_line": heading_line,
        "legacy_heading": raw_heading,
        "date_source": "git-blame",
    }
    if advisory_dates:
        metadata["legacy_heading_dates"] = advisory_dates

    frontmatter = yaml.safe_dump(
        metadata,
        sort_keys=False,
        default_flow_style=False,
        width=72,
    ).strip()

    body_lines = [
        f"## {title}",
        "",
        f"**Backfilled from**: `{legacy_rel_path}:{heading_line}`",
        f"**Canonical date**: {canonical_date} (git blame)",
        "**Legacy heading**",
        "```text",
        raw_heading,
        "```",
    ]
    if advisory_dates:
        body_lines.append(
            "**Legacy heading dates**: " + ", ".join(advisory_dates)
        )
    if body:
        body_lines.extend(["", body])

    return (
        f"---\n{frontmatter}\n---\n\n" + "\n".join(body_lines).rstrip() + "\n"
    )
