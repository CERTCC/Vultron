"""Build the reviewable backfill manifest and write entries from it."""

from __future__ import annotations

import datetime
import json
import sys
from pathlib import Path
from typing import TypedDict

from vultron.metadata.history.backfill_implementation.legacy import (
    _blame_dates_for_file,
    _build_synthetic_source,
    _extract_advisory_dates,
    _extract_source_candidate,
    _render_entry_markdown,
    normalize_title,
    split_legacy_sections,
)
from vultron.metadata.history.cli import append_history_entry
from vultron.metadata.history.types import HistoryEntryType


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
