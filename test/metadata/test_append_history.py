"""Tests for the append-history CLI tool.

Covers: HM-03-001 through HM-03-006 (entry creation, README regeneration,
type validation, stdin mode, --file mode).
"""

from __future__ import annotations

import dataclasses
import io
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

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


@dataclasses.dataclass
class _RunResult:
    returncode: int
    stdout: str
    stderr: str


def _run_append(
    entry_type: str,
    content: str = _VALID_CONTENT,
    extra_args: list[str] | None = None,
    cwd: Path | None = None,
) -> _RunResult:
    """Run append-history CLI logic in-process, returning a result object.

    Replaces the subprocess-based approach to eliminate per-test Python
    startup overhead (~0.2-0.4 s per invocation).  The ``cwd`` parameter is
    accepted for interface compatibility but ignored: callers use the
    ``fake_repo`` fixture which applies ``monkeypatch.chdir`` before
    ``_run_append`` is called, so ``Path.cwd()`` is already the desired
    directory.
    """
    from vultron.metadata.history.cli import main  # local import avoids leak

    cmd = ["append-history", entry_type]
    if extra_args:
        cmd.extend(extra_args)

    stdout_buf = io.StringIO()
    stderr_buf = io.StringIO()
    exit_code = 0

    try:
        with (
            patch("sys.argv", cmd),
            patch("sys.stdin", io.StringIO(content or "")),
            redirect_stdout(stdout_buf),
            redirect_stderr(stderr_buf),
        ):
            main()
    except SystemExit as exc:
        exit_code = exc.code if isinstance(exc.code, int) else 1

    return _RunResult(
        returncode=exit_code,
        stdout=stdout_buf.getvalue(),
        stderr=stderr_buf.getvalue(),
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

    def test_missing_source_exits_nonzero(self, fake_repo: Path) -> None:
        content = (
            "---\ntitle: No Source\ntype: idea\ndate: 2026-04-28\n---\n\nBody."
        )
        result = _run_append("idea", content=content, cwd=fake_repo)
        assert result.returncode != 0
        assert "source" in result.stderr.lower()

    def test_creates_type_subdirectory(self, fake_repo: Path) -> None:
        result = _run_append(
            "implementation", content=_IMPL_CONTENT, cwd=fake_repo
        )
        assert result.returncode == 0
        written_path = Path(result.stdout.strip())
        assert written_path.parent.name == "implementation"

    def test_rejects_existing_target_file(self, fake_repo: Path) -> None:
        first = _run_append("idea", cwd=fake_repo)
        assert first.returncode == 0
        second = _run_append("idea", cwd=fake_repo)
        assert second.returncode != 0
        assert "already exists" in second.stderr

    def test_hidden_date_override_targets_historical_month(
        self, fake_repo: Path
    ) -> None:
        result = _run_append(
            "implementation",
            content=_IMPL_CONTENT,
            extra_args=["--date", "2025-12-31"],
            cwd=fake_repo,
        )
        assert result.returncode == 0
        written_path = Path(result.stdout.strip())
        assert written_path.parent.parent.name == "2512"


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


class TestFrontmatterValidation:
    """append-history rejects entries with missing or invalid frontmatter fields."""

    @pytest.mark.parametrize(
        "missing_field,content",
        [
            (
                "source",
                "---\ntitle: T\ntype: idea\ndate: 2026-04-28\n---\n\nBody.\n",
            ),
            (
                "title",
                "---\ntype: idea\ndate: 2026-04-28\nsource: SRC-1\n---\n\nBody.\n",
            ),
            (
                "date",
                "---\ntitle: T\ntype: idea\nsource: SRC-2\n---\n\nBody.\n",
            ),
            (
                "type",
                "---\ntitle: T\ndate: 2026-04-28\nsource: SRC-3\n---\n\nBody.\n",
            ),
        ],
    )
    def test_missing_required_field_exits_nonzero(
        self, missing_field: str, content: str, fake_repo: Path
    ) -> None:
        result = _run_append("idea", content=content, cwd=fake_repo)
        assert result.returncode != 0
        assert missing_field in result.stderr.lower()

    @pytest.mark.parametrize(
        "field,content",
        [
            (
                "source",
                "---\ntitle: T\ntype: idea\ndate: 2026-04-28\nsource: '   '\n---\n\nBody.\n",
            ),
            (
                "title",
                "---\ntitle: '   '\ntype: idea\ndate: 2026-04-28\nsource: SRC-4\n---\n\nBody.\n",
            ),
        ],
    )
    def test_whitespace_only_field_exits_nonzero(
        self, field: str, content: str, fake_repo: Path
    ) -> None:
        result = _run_append("idea", content=content, cwd=fake_repo)
        assert result.returncode != 0

    def test_no_frontmatter_block_exits_nonzero(self, fake_repo: Path) -> None:
        result = _run_append(
            "idea", content="Just plain text.\n", cwd=fake_repo
        )
        assert result.returncode != 0

    def test_frontmatter_type_mismatch_with_cli_arg_exits_nonzero(
        self, fake_repo: Path
    ) -> None:
        content = "---\ntitle: T\ntype: implementation\ndate: 2026-04-28\nsource: SRC-5\n---\n\nBody.\n"
        result = _run_append("idea", content=content, cwd=fake_repo)
        assert result.returncode != 0
        assert "type" in result.stderr.lower()

    def test_invalid_date_format_exits_nonzero(self, fake_repo: Path) -> None:
        content = "---\ntitle: T\ntype: idea\ndate: not-a-date\nsource: SRC-6\n---\n\nBody.\n"
        result = _run_append("idea", content=content, cwd=fake_repo)
        assert result.returncode != 0


class TestReadmeGenValidation:
    """readme_gen raises on malformed existing entry files."""

    def test_missing_field_raises(self, fake_repo: Path) -> None:
        from vultron.metadata.history.readme_gen import regenerate_readme

        month_dir = fake_repo / "plan" / "history" / "2604"
        impl_dir = month_dir / "implementation"
        impl_dir.mkdir(parents=True)
        bad_entry = impl_dir / "BAD-ENTRY.md"
        bad_entry.write_text(
            "---\ntitle: Missing fields\n---\n\nNo type, date, or source.\n"
        )
        with pytest.raises((ValueError, Exception)):
            regenerate_readme(month_dir)

    def test_no_frontmatter_raises(self, fake_repo: Path) -> None:
        from vultron.metadata.history.readme_gen import regenerate_readme

        month_dir = fake_repo / "plan" / "history" / "2604"
        impl_dir = month_dir / "implementation"
        impl_dir.mkdir(parents=True)
        bad_entry = impl_dir / "NO-FM.md"
        bad_entry.write_text("Just plain text, no frontmatter at all.\n")
        with pytest.raises((ValueError, Exception)):
            regenerate_readme(month_dir)

    def test_rollback_on_existing_malformed_entry(
        self, fake_repo: Path
    ) -> None:
        """Append fails without leaving a new entry file when README regen fails."""
        import datetime

        yymm = datetime.date.today().strftime("%y%m")
        month_dir = fake_repo / "plan" / "history" / yymm
        impl_dir = month_dir / "implementation"
        impl_dir.mkdir(parents=True)
        bad_entry = impl_dir / "BAD-PREEXISTING.md"
        bad_entry.write_text("---\ntitle: Bad\n---\n\nNo type/date/source.\n")

        content = "---\ntitle: New\ntype: implementation\ndate: 2026-04-30\nsource: NEW-ENTRY\n---\n\nBody.\n"
        result = _run_append("implementation", content=content, cwd=fake_repo)

        assert result.returncode != 0
        new_file = impl_dir / "NEW-ENTRY.md"
        assert not new_file.exists(), "new entry file should be rolled back"
