"""Backfill tool for legacy implementation history entries.

This tool creates a reviewable manifest from
``plan/history/IMPLEMENTATION_HISTORY.md`` and can later write immutable
history entry files from that manifest after review.
"""

from __future__ import annotations

import argparse
import datetime
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import TypedDict

import yaml

from vultron.metadata.history.cli import _find_repo_root, append_history_entry
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


class ManifestEntry(TypedDict):
    """Structured metadata for one backfilled legacy section."""

    heading_line: int
    raw_heading: str
    title: str
    candidate_source: str | None
    source: str
    source_origin: str
    canonical_date: str | None
    target_month: str
    target_path: str
    advisory_dates: list[str]
    flags: list[str]
    entry_markdown: str


class BackfillManifest(TypedDict):
    """Reviewable manifest for implementation history backfill."""

    kind: str
    generated_at: str
    legacy_file: str
    entry_count: int
    status: str
    blocking_entry_count: int
    entries: list[ManifestEntry]


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="backfill-implementation-history",
        description=(
            "Build a dry-run manifest for legacy implementation history "
            "backfill, or write reviewed entries from an existing manifest."
        ),
    )
    parser.add_argument(
        "--legacy-file",
        default="plan/history/IMPLEMENTATION_HISTORY.md",
        help="Legacy implementation history file to parse.",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Write the generated manifest to PATH instead of stdout.",
    )
    parser.add_argument(
        "--manifest",
        default=None,
        help="Reviewed manifest JSON to write from.",
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help="Write immutable history files from --manifest.",
    )
    return parser


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
        tzinfo=datetime.timezone.utc,
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


def build_manifest(repo_root: Path, legacy_file: Path) -> BackfillManifest:
    """Build a reviewable manifest for legacy implementation history backfill."""
    legacy_rel_path = str(legacy_file.relative_to(repo_root))
    text = legacy_file.read_text(encoding="utf-8")
    sections = split_legacy_sections(text)
    blame_dates = _blame_dates_for_file(repo_root, legacy_file)
    entries: list[ManifestEntry] = []
    used_paths: set[Path] = set()

    for section in sections:
        canonical_date = blame_dates.get(section.heading_line)
        title = normalize_title(section.raw_heading)
        advisory_dates = _extract_advisory_dates(section.raw_heading)
        flags: list[str] = []
        source_origin = "existing-id"
        candidate_source = _extract_source_candidate(title)

        if canonical_date is None:
            target_month = "unknown"
            source = _build_synthetic_source(
                "unknown-date",
                title,
                target_month,
                repo_root,
                used_paths,
            )
            source_origin = "synthetic"
            flags.extend(["missing_canonical_date", "synthetic_source"])
            entry_markdown = ""
            target_path = (
                repo_root
                / "plan"
                / "history"
                / target_month
                / "implementation"
                / f"{source}.md"
            )
        else:
            target_month = datetime.date.fromisoformat(
                canonical_date
            ).strftime("%y%m")
            if candidate_source is None:
                source = _build_synthetic_source(
                    canonical_date,
                    title,
                    target_month,
                    repo_root,
                    used_paths,
                )
                source_origin = "synthetic"
                flags.append("synthetic_source")
            else:
                candidate_path = (
                    repo_root
                    / "plan"
                    / "history"
                    / target_month
                    / "implementation"
                    / f"{candidate_source}.md"
                )
                if candidate_path in used_paths or candidate_path.exists():
                    source = _build_synthetic_source(
                        canonical_date,
                        title,
                        target_month,
                        repo_root,
                        used_paths,
                    )
                    source_origin = "synthetic"
                    flags.extend(["source_conflict", "synthetic_source"])
                else:
                    source = candidate_source

            if advisory_dates and canonical_date not in advisory_dates:
                flags.append("advisory_date_mismatch")

            entry_markdown = _render_entry_markdown(
                title=title,
                source=source,
                canonical_date=canonical_date,
                raw_heading=section.raw_heading,
                legacy_rel_path=legacy_rel_path,
                heading_line=section.heading_line,
                advisory_dates=advisory_dates,
                body=section.body,
            )
            target_path = (
                repo_root
                / "plan"
                / "history"
                / target_month
                / "implementation"
                / f"{source}.md"
            )

        used_paths.add(target_path)
        entries.append(
            ManifestEntry(
                heading_line=section.heading_line,
                raw_heading=section.raw_heading,
                title=title,
                candidate_source=candidate_source,
                source=source,
                source_origin=source_origin,
                canonical_date=canonical_date,
                target_month=target_month,
                target_path=str(target_path.relative_to(repo_root)),
                advisory_dates=advisory_dates,
                flags=flags,
                entry_markdown=entry_markdown,
            )
        )

    blocking_entries: list[ManifestEntry] = [
        entry
        for entry in entries
        if "missing_canonical_date" in entry["flags"]
        or not entry["entry_markdown"]
    ]
    manifest: BackfillManifest = BackfillManifest(
        kind="implementation-history-backfill-manifest",
        generated_at=datetime.datetime.now(datetime.UTC).isoformat(
            timespec="seconds"
        ),
        legacy_file=legacy_rel_path,
        entry_count=len(entries),
        status="blocked" if blocking_entries else "ready",
        blocking_entry_count=len(blocking_entries),
        entries=entries,
    )
    return manifest


def write_manifest(repo_root: Path, manifest: BackfillManifest) -> list[Path]:
    """Write immutable history files from a reviewed manifest."""
    if manifest["kind"] != "implementation-history-backfill-manifest":
        raise ValueError(
            "manifest kind is not implementation-history-backfill"
        )
    if manifest["status"] != "ready":
        raise ValueError("manifest is not ready for write")

    raw_entries = manifest["entries"]

    target_paths: list[Path] = []
    for raw_entry in raw_entries:
        target_path_text = raw_entry["target_path"]
        target_path = repo_root / target_path_text
        if target_path.exists():
            raise FileExistsError(
                f"history entry already exists: {target_path}"
            )
        target_paths.append(target_path)

    written_paths: list[Path] = []
    for raw_entry in raw_entries:
        entry_markdown = raw_entry["entry_markdown"]
        canonical_date = raw_entry["canonical_date"]
        target_path_text = raw_entry["target_path"]
        if not entry_markdown.strip():
            raise ValueError("manifest entry is missing entry_markdown")
        if canonical_date is None:
            raise ValueError("manifest entry is missing canonical_date")

        written_path = append_history_entry(
            HistoryEntryType.implementation,
            entry_markdown,
            repo_root=repo_root,
            target_date=datetime.date.fromisoformat(canonical_date),
        )
        expected_path = repo_root / target_path_text
        if written_path != expected_path:
            raise ValueError(
                "written path does not match manifest target path: "
                f"{written_path} != {expected_path}"
            )
        written_paths.append(written_path)
    return written_paths


def _write_manifest_output(
    manifest: BackfillManifest, output: Path | None
) -> None:
    """Write a manifest to stdout or to a file."""
    rendered = json.dumps(manifest, indent=2) + "\n"
    if output is None:
        sys.stdout.write(rendered)
        return
    output.write_text(rendered, encoding="utf-8")
    print(str(output))


def _coerce_manifest_entry(data: object) -> ManifestEntry:
    """Validate and coerce JSON-loaded manifest entry data."""
    if not isinstance(data, dict):
        raise ValueError("manifest entry is malformed")

    heading_line = data.get("heading_line")
    raw_heading = data.get("raw_heading")
    title = data.get("title")
    candidate_source = data.get("candidate_source")
    source = data.get("source")
    source_origin = data.get("source_origin")
    canonical_date = data.get("canonical_date")
    target_month = data.get("target_month")
    target_path = data.get("target_path")
    advisory_dates = data.get("advisory_dates")
    flags = data.get("flags")
    entry_markdown = data.get("entry_markdown")

    if not isinstance(heading_line, int):
        raise ValueError("manifest entry heading_line is missing")
    if not isinstance(raw_heading, str):
        raise ValueError("manifest entry raw_heading is missing")
    if not isinstance(title, str):
        raise ValueError("manifest entry title is missing")
    if candidate_source is not None and not isinstance(candidate_source, str):
        raise ValueError("manifest entry candidate_source is malformed")
    if not isinstance(source, str):
        raise ValueError("manifest entry source is missing")
    if not isinstance(source_origin, str):
        raise ValueError("manifest entry source_origin is missing")
    if canonical_date is not None and not isinstance(canonical_date, str):
        raise ValueError("manifest entry canonical_date is malformed")
    if not isinstance(target_month, str):
        raise ValueError("manifest entry target_month is missing")
    if not isinstance(target_path, str):
        raise ValueError("manifest entry target_path is missing")
    if not isinstance(advisory_dates, list) or not all(
        isinstance(item, str) for item in advisory_dates
    ):
        raise ValueError("manifest entry advisory_dates is malformed")
    if not isinstance(flags, list) or not all(
        isinstance(item, str) for item in flags
    ):
        raise ValueError("manifest entry flags is malformed")
    if not isinstance(entry_markdown, str):
        raise ValueError("manifest entry entry_markdown is missing")

    return ManifestEntry(
        heading_line=heading_line,
        raw_heading=raw_heading,
        title=title,
        candidate_source=candidate_source,
        source=source,
        source_origin=source_origin,
        canonical_date=canonical_date,
        target_month=target_month,
        target_path=target_path,
        advisory_dates=advisory_dates,
        flags=flags,
        entry_markdown=entry_markdown,
    )


def _coerce_manifest(data: object) -> BackfillManifest:
    """Validate and coerce JSON-loaded manifest data."""
    if not isinstance(data, dict):
        raise ValueError("manifest is malformed")

    kind = data.get("kind")
    generated_at = data.get("generated_at")
    legacy_file = data.get("legacy_file")
    entry_count = data.get("entry_count")
    status = data.get("status")
    blocking_entry_count = data.get("blocking_entry_count")
    raw_entries = data.get("entries")

    if not isinstance(kind, str):
        raise ValueError("manifest kind is missing")
    if not isinstance(generated_at, str):
        raise ValueError("manifest generated_at is missing")
    if not isinstance(legacy_file, str):
        raise ValueError("manifest legacy_file is missing")
    if not isinstance(entry_count, int):
        raise ValueError("manifest entry_count is missing")
    if not isinstance(status, str):
        raise ValueError("manifest status is missing")
    if not isinstance(blocking_entry_count, int):
        raise ValueError("manifest blocking_entry_count is missing")
    if not isinstance(raw_entries, list):
        raise ValueError("manifest entries are missing or malformed")

    entries = [_coerce_manifest_entry(raw_entry) for raw_entry in raw_entries]
    return BackfillManifest(
        kind=kind,
        generated_at=generated_at,
        legacy_file=legacy_file,
        entry_count=entry_count,
        status=status,
        blocking_entry_count=blocking_entry_count,
        entries=entries,
    )


def main() -> None:
    """CLI entry point for implementation history backfill."""
    parser = _build_parser()
    args = parser.parse_args()
    repo_root = _find_repo_root()

    try:
        if args.write:
            if args.manifest is None:
                raise ValueError("--write requires --manifest")
            manifest_path = Path(args.manifest)
            manifest = _coerce_manifest(
                json.loads(manifest_path.read_text(encoding="utf-8"))
            )
            written_paths = write_manifest(repo_root, manifest)
            print(
                f"Wrote {len(written_paths)} implementation history entries."
            )
            return

        legacy_file = (repo_root / args.legacy_file).resolve()
        manifest = build_manifest(repo_root, legacy_file)
        output_path = Path(args.output).resolve() if args.output else None
        _write_manifest_output(manifest, output_path)
    except (
        FileExistsError,
        OSError,
        subprocess.CalledProcessError,
        ValueError,
        json.JSONDecodeError,
    ) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
