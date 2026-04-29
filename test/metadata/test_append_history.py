"""Tests for the append-history CLI tool.

Covers: HM-03-001 through HM-03-006 (entry creation, README regeneration,
type validation, stdin mode, --file mode).
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

_VALID_CONTENT = """\
---
title: Test Idea
type: idea
date: 2026-04-28
source: IDEA-TEST-001
---

This is a test idea body.
"""

_IMPL_CONTENT = """\
---
title: Test Implementation Task
type: implementation
date: 2026-04-28
source: TASK-TEST-001
---

Completed a test task.
"""


@pytest.fixture()
def fake_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Create a minimal fake repo root with pyproject.toml and plan/."""
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'test'\n")
    (tmp_path / "plan").mkdir()
    monkeypatch.chdir(tmp_path)
    return tmp_path


def _run_append(
    entry_type: str,
    content: str = _VALID_CONTENT,
    extra_args: list[str] | None = None,
    cwd: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    cmd = [sys.executable, "-m", "vultron.metadata.history.cli", entry_type]
    if extra_args:
        cmd.extend(extra_args)
    return subprocess.run(
        cmd,
        input=content,
        text=True,
        capture_output=True,
        cwd=str(cwd) if cwd else None,
    )


class TestAppendHistoryEntryCreation:
    """HM-03-001, HM-03-004, HM-03-005: entry file created at correct path."""

    def test_creates_entry_file_at_correct_path(self, fake_repo: Path) -> None:
        result = _run_append("idea", cwd=fake_repo)
        assert result.returncode == 0
        written_path = Path(result.stdout.strip())
        assert written_path.exists()
        # Path should be plan/history/YYMM/idea/IDEA-TEST-001.md
        assert written_path.parent.name == "idea"
        assert written_path.stem == "IDEA-TEST-001"

    def test_written_path_printed_to_stdout(self, fake_repo: Path) -> None:
        result = _run_append("idea", cwd=fake_repo)
        assert result.returncode == 0
        printed = result.stdout.strip()
        assert "IDEA-TEST-001" in printed

    def test_entry_content_preserved(self, fake_repo: Path) -> None:
        result = _run_append("idea", cwd=fake_repo)
        assert result.returncode == 0
        written_path = Path(result.stdout.strip())
        assert "This is a test idea body." in written_path.read_text()

    def test_fallback_id_when_source_absent(self, fake_repo: Path) -> None:
        content = (
            "---\ntitle: No Source\ntype: idea\ndate: 2026-04-28\n---\n\nBody."
        )
        result = _run_append("idea", content=content, cwd=fake_repo)
        assert result.returncode == 0
        written_path = Path(result.stdout.strip())
        # Falls back to idea-<timestamp>
        assert written_path.stem.startswith("idea-")

    def test_creates_type_subdirectory(self, fake_repo: Path) -> None:
        result = _run_append(
            "implementation", content=_IMPL_CONTENT, cwd=fake_repo
        )
        assert result.returncode == 0
        written_path = Path(result.stdout.strip())
        assert written_path.parent.name == "implementation"


class TestAppendHistoryReadmeRegeneration:
    """HM-03-006: README.md regenerated after append."""

    def test_readme_created_after_append(self, fake_repo: Path) -> None:
        result = _run_append("idea", cwd=fake_repo)
        assert result.returncode == 0
        written_path = Path(result.stdout.strip())
        month_dir = written_path.parent.parent
        readme = month_dir / "README.md"
        assert readme.exists()

    def test_readme_contains_entry_summary(self, fake_repo: Path) -> None:
        result = _run_append("idea", cwd=fake_repo)
        assert result.returncode == 0
        written_path = Path(result.stdout.strip())
        month_dir = written_path.parent.parent
        readme_text = (month_dir / "README.md").read_text()
        assert "IDEA-TEST-001" in readme_text
        assert "Test Idea" in readme_text

    def test_readme_updated_after_second_append(self, fake_repo: Path) -> None:
        _run_append("idea", cwd=fake_repo)
        result = _run_append(
            "implementation", content=_IMPL_CONTENT, cwd=fake_repo
        )
        assert result.returncode == 0
        written_path = Path(result.stdout.strip())
        month_dir = written_path.parent.parent
        readme_text = (month_dir / "README.md").read_text()
        assert "IDEA-TEST-001" in readme_text
        assert "TASK-TEST-001" in readme_text


class TestAppendHistoryTypeValidation:
    """HM-03-001: invalid type exits non-zero with clear message."""

    def test_invalid_type_exits_nonzero(self, fake_repo: Path) -> None:
        result = _run_append("bogus_type", cwd=fake_repo)
        assert result.returncode != 0

    def test_invalid_type_error_message(self, fake_repo: Path) -> None:
        result = _run_append("bogus_type", cwd=fake_repo)
        assert "bogus_type" in result.stderr
        assert "idea" in result.stderr

    @pytest.mark.parametrize(
        "valid_type", ["idea", "implementation", "learning", "priority"]
    )
    def test_all_valid_types_accepted(
        self, valid_type: str, fake_repo: Path
    ) -> None:
        content = (
            f"---\ntitle: T\ntype: {valid_type}\ndate: 2026-04-28\n"
            f"source: SRC-{valid_type.upper()}\n---\n\nBody.\n"
        )
        result = _run_append(valid_type, content=content, cwd=fake_repo)
        assert result.returncode == 0


class TestAppendHistoryInputModes:
    """HM-03-002, HM-03-003: stdin and --file modes."""

    def test_stdin_mode(self, fake_repo: Path) -> None:
        result = _run_append("idea", cwd=fake_repo)
        assert result.returncode == 0
        assert Path(result.stdout.strip()).exists()

    def test_file_mode(self, fake_repo: Path, tmp_path: Path) -> None:
        entry_file = tmp_path / "entry.md"
        entry_file.write_text(_VALID_CONTENT)
        result = _run_append(
            "idea",
            content="",
            extra_args=["--file", str(entry_file)],
            cwd=fake_repo,
        )
        assert result.returncode == 0
        assert Path(result.stdout.strip()).exists()

    def test_missing_file_exits_nonzero(self, fake_repo: Path) -> None:
        result = _run_append(
            "idea",
            content="",
            extra_args=["--file", "/nonexistent/path/entry.md"],
            cwd=fake_repo,
        )
        assert result.returncode != 0

    def test_empty_stdin_exits_nonzero(self, fake_repo: Path) -> None:
        result = _run_append("idea", content="", cwd=fake_repo)
        assert result.returncode != 0


class TestAppendHistoryWriteOnce:
    """HM-01-005: history entries are write-once; overwrite must be rejected."""

    def test_duplicate_write_exits_nonzero(self, fake_repo: Path) -> None:
        _run_append("idea", cwd=fake_repo)
        result = _run_append("idea", cwd=fake_repo)
        assert result.returncode != 0

    def test_duplicate_write_error_message(self, fake_repo: Path) -> None:
        _run_append("idea", cwd=fake_repo)
        result = _run_append("idea", cwd=fake_repo)
        assert "already exists" in result.stderr.lower()


class TestAppendHistoryEntryIdSanitization:
    """Security: entry_id from frontmatter must not allow path traversal."""

    @pytest.mark.parametrize(
        "bad_source",
        [
            "../outside",
            "../../etc/passwd",
            "a/b",
            "a\\b",
        ],
    )
    def test_path_traversal_rejected(
        self, bad_source: str, fake_repo: Path
    ) -> None:
        content = (
            f"---\ntitle: T\ntype: idea\ndate: 2026-04-28\n"
            f"source: {bad_source}\n---\n\nBody.\n"
        )
        result = _run_append("idea", content=content, cwd=fake_repo)
        assert result.returncode != 0
