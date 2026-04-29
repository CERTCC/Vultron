"""Tests for legacy implementation history backfill tooling."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from vultron.metadata.history.backfill_implementation import (
    build_manifest,
    normalize_title,
    split_legacy_sections,
    write_manifest,
)


@pytest.fixture()
def fake_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Create a minimal fake repo root with pyproject.toml and plan/history/."""
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'test'\n")
    (tmp_path / "plan" / "history").mkdir(parents=True)
    monkeypatch.chdir(tmp_path)
    return tmp_path


def test_split_legacy_sections_preserves_one_section_per_heading() -> None:
    text = """# Header

## First heading

Body one.

---

## Second heading

Body two.
"""
    sections = split_legacy_sections(text)
    assert [section.raw_heading for section in sections] == [
        "First heading",
        "Second heading",
    ]
    assert sections[0].body == "Body one."
    assert sections[1].body == "Body two."


@pytest.mark.parametrize(
    ("raw_heading", "expected"),
    [
        (
            "Phase BT-1 — Behavior Tree Integration POC (COMPLETE 2026-02-18)",
            "BT-1 — Behavior Tree Integration POC",
        ),
        (
            "2026-03-10 — P60-1 complete: moved vocabulary package",
            "P60-1 complete: moved vocabulary package",
        ),
    ],
)
def test_normalize_title_removes_legacy_wrappers(
    raw_heading: str, expected: str
) -> None:
    assert normalize_title(raw_heading) == expected


def test_build_manifest_uses_git_date_and_existing_id(
    fake_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    legacy_file = fake_repo / "plan" / "history" / "IMPLEMENTATION_HISTORY.md"
    legacy_file.write_text(
        "## Phase BT-1 — Behavior Tree Integration POC (COMPLETE 2026-02-18)\n\n"
        "- Implemented the tree.\n"
    )

    monkeypatch.setattr(
        "vultron.metadata.history.backfill_implementation._blame_dates_for_file",
        lambda repo_root, file_path: {1: "2026-02-24"},
    )

    manifest = build_manifest(fake_repo, legacy_file)
    assert manifest["status"] == "ready"
    entry = manifest["entries"][0]
    assert entry["canonical_date"] == "2026-02-24"
    assert entry["source"] == "BT-1"
    assert entry["source_origin"] == "existing-id"
    assert "advisory_date_mismatch" in entry["flags"]


def test_build_manifest_synthesizes_for_multi_id_heading(
    fake_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    legacy_file = fake_repo / "plan" / "history" / "IMPLEMENTATION_HISTORY.md"
    legacy_file.write_text(
        "## CA-1 + CA-3: CaseActor broadcast on case update\n\n"
        "- Broadcast logic complete.\n"
    )

    monkeypatch.setattr(
        "vultron.metadata.history.backfill_implementation._blame_dates_for_file",
        lambda repo_root, file_path: {1: "2026-03-25"},
    )

    manifest = build_manifest(fake_repo, legacy_file)
    entry = manifest["entries"][0]
    assert entry["source"].startswith(
        "LEGACY-2026-03-25-ca-1-ca-3-caseactor-broadcast-on-case-update"
    )
    assert entry["source_origin"] == "synthetic"
    assert "synthetic_source" in entry["flags"]


def test_build_manifest_resolves_duplicate_candidate_sources(
    fake_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    legacy_file = fake_repo / "plan" / "history" / "IMPLEMENTATION_HISTORY.md"
    legacy_file.write_text(
        "## SPEC-AUDIT-1 — First pass\n\n"
        "- One.\n\n"
        "## SPEC-AUDIT-1 — Second pass\n\n"
        "- Two.\n"
    )

    monkeypatch.setattr(
        "vultron.metadata.history.backfill_implementation._blame_dates_for_file",
        lambda repo_root, file_path: {1: "2026-03-30", 5: "2026-03-30"},
    )

    manifest = build_manifest(fake_repo, legacy_file)
    first, second = manifest["entries"]
    assert first["source"] == "SPEC-AUDIT-1"
    assert second["source"].startswith(
        "LEGACY-2026-03-30-spec-audit-1-second-pass"
    )
    assert "source_conflict" in second["flags"]


def test_write_manifest_creates_historical_entries_and_readme(
    fake_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    legacy_file = fake_repo / "plan" / "history" / "IMPLEMENTATION_HISTORY.md"
    legacy_file.write_text(
        "## BUG-001: outbox_handler early-return fix\n\n" "- Fixed the bug.\n"
    )

    monkeypatch.setattr(
        "vultron.metadata.history.backfill_implementation._blame_dates_for_file",
        lambda repo_root, file_path: {1: "2026-03-24"},
    )

    manifest = build_manifest(fake_repo, legacy_file)
    written_paths = write_manifest(fake_repo, manifest)
    assert len(written_paths) == 1
    written_path = written_paths[0]
    assert written_path == (
        fake_repo
        / "plan"
        / "history"
        / "2603"
        / "implementation"
        / "BUG-001.md"
    )
    assert written_path.exists()
    assert (fake_repo / "plan" / "history" / "2603" / "README.md").exists()

    parsed = json.loads(json.dumps(manifest))
    assert parsed["status"] == "ready"
