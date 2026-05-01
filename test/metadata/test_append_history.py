"""Tests for the append-history CLI tool.

Covers: HM-03-001 through HM-03-006 (entry creation, README regeneration,
type validation, stdin mode, --file mode), HM-06-001 through HM-06-005
(timestamp field, future-date rejection), HM-07-001 through HM-07-003
(--title, --source CLI params).
"""

from __future__ import annotations

import dataclasses
import datetime
import io
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

import pytest

_UTC = datetime.timezone.utc

# Body-only content (no frontmatter) — the tool now builds frontmatter.
_IDEA_BODY = "This is a test idea body.\n"
_IMPL_BODY = "Completed a test task.\n"

_DEFAULT_TITLE = "Test Idea"
_DEFAULT_SOURCE = "IDEA-TEST-001"
_IMPL_TITLE = "Test Implementation Task"
_IMPL_SOURCE = "TASK-TEST-001"


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
    body: str = _IDEA_BODY,
    title: str = _DEFAULT_TITLE,
    source: str = _DEFAULT_SOURCE,
    extra_args: list[str] | None = None,
    cwd: Path | None = None,
) -> _RunResult:
    """Run append-history CLI logic in-process, returning a result object.

    The ``cwd`` parameter is accepted for interface compatibility but ignored:
    callers use the ``fake_repo`` fixture which applies ``monkeypatch.chdir``
    before ``_run_append`` is called, so ``Path.cwd()`` is already correct.
    """
    from vultron.metadata.history.cli import main  # local import avoids leak

    cmd = ["append-history", entry_type, "--title", title, "--source", source]
    if extra_args:
        cmd.extend(extra_args)

    stdout_buf = io.StringIO()
    stderr_buf = io.StringIO()
    exit_code = 0

    try:
        with (
            patch("sys.argv", cmd),
            patch("sys.stdin", io.StringIO(body or "")),
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

    def test_entry_body_preserved(self, fake_repo: Path) -> None:
        result = _run_append("idea", body=_IDEA_BODY, cwd=fake_repo)
        assert result.returncode == 0
        written_path = Path(result.stdout.strip())
        assert "This is a test idea body." in written_path.read_text()

    def test_entry_has_timestamp_not_date(self, fake_repo: Path) -> None:
        """New entries must use timestamp: field, not legacy date: (HM-06-001)."""
        result = _run_append("idea", cwd=fake_repo)
        assert result.returncode == 0
        content = Path(result.stdout.strip()).read_text()
        assert "timestamp:" in content
        assert "\ndate:" not in content

    def test_missing_source_arg_exits_nonzero(self, fake_repo: Path) -> None:
        """--source is a required CLI argument (HM-07-001)."""
        cmd = ["append-history", "idea", "--title", "T"]
        result = _run_with_cmd(cmd, _IDEA_BODY)
        assert result.returncode != 0

    def test_missing_title_arg_exits_nonzero(self, fake_repo: Path) -> None:
        """--title is a required CLI argument (HM-07-001)."""
        cmd = ["append-history", "idea", "--source", "SRC-NOTITLE"]
        result = _run_with_cmd(cmd, _IDEA_BODY)
        assert result.returncode != 0

    def test_creates_type_subdirectory(self, fake_repo: Path) -> None:
        result = _run_append(
            "implementation",
            body=_IMPL_BODY,
            title=_IMPL_TITLE,
            source=_IMPL_SOURCE,
            cwd=fake_repo,
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

    def test_hidden_timestamp_override_targets_historical_month(
        self, fake_repo: Path
    ) -> None:
        result = _run_append(
            "implementation",
            body=_IMPL_BODY,
            title=_IMPL_TITLE,
            source=_IMPL_SOURCE,
            extra_args=["--timestamp", "2025-12-31T00:00:00+00:00"],
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

    def test_readme_has_time_utc_column(self, fake_repo: Path) -> None:
        """README table must include a Time (UTC) column (HM-06-006)."""
        result = _run_append("idea", cwd=fake_repo)
        assert result.returncode == 0
        month_dir = Path(result.stdout.strip()).parent.parent
        readme_text = (month_dir / "README.md").read_text()
        assert "Time (UTC)" in readme_text

    def test_readme_updated_after_second_append(self, fake_repo: Path) -> None:
        _run_append("idea", cwd=fake_repo)
        result = _run_append(
            "implementation",
            body=_IMPL_BODY,
            title=_IMPL_TITLE,
            source=_IMPL_SOURCE,
            cwd=fake_repo,
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
        result = _run_append(
            valid_type,
            body="Body.\n",
            title="T",
            source=f"SRC-{valid_type.upper()}",
            cwd=fake_repo,
        )
        assert result.returncode == 0


class TestAppendHistoryInputModes:
    """HM-03-002, HM-03-003: stdin and --file modes (body-only content)."""

    def test_stdin_mode(self, fake_repo: Path) -> None:
        result = _run_append("idea", cwd=fake_repo)
        assert result.returncode == 0
        assert Path(result.stdout.strip()).exists()

    def test_file_mode(self, fake_repo: Path, tmp_path: Path) -> None:
        body_file = tmp_path / "body.md"
        body_file.write_text(_IDEA_BODY)
        result = _run_append(
            "idea",
            body="",
            extra_args=["--file", str(body_file)],
            cwd=fake_repo,
        )
        assert result.returncode == 0
        assert Path(result.stdout.strip()).exists()

    def test_file_body_content_preserved(
        self, fake_repo: Path, tmp_path: Path
    ) -> None:
        body_file = tmp_path / "body.md"
        body_file.write_text("Custom body from file.\n")
        result = _run_append(
            "idea",
            body="",
            extra_args=["--file", str(body_file)],
            cwd=fake_repo,
        )
        assert result.returncode == 0
        written = Path(result.stdout.strip()).read_text()
        assert "Custom body from file." in written

    def test_missing_file_exits_nonzero(self, fake_repo: Path) -> None:
        result = _run_append(
            "idea",
            body="",
            extra_args=["--file", "/nonexistent/path/body.md"],
            cwd=fake_repo,
        )
        assert result.returncode != 0

    def test_empty_stdin_exits_nonzero(self, fake_repo: Path) -> None:
        result = _run_append("idea", body="", cwd=fake_repo)
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
    """Security: source from --source must not allow path traversal."""

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
        result = _run_append(
            "idea",
            body=_IDEA_BODY,
            title="T",
            source=bad_source,
            cwd=fake_repo,
        )
        assert result.returncode != 0


class TestTimestampSupport:
    """HM-06-001 through HM-06-005: timestamp field, future-date rejection."""

    def test_created_entry_has_timestamp_field(self, fake_repo: Path) -> None:
        result = _run_append("idea", cwd=fake_repo)
        assert result.returncode == 0
        content = Path(result.stdout.strip()).read_text()
        assert "timestamp:" in content

    def test_created_entry_timestamp_is_utc(self, fake_repo: Path) -> None:
        result = _run_append("idea", cwd=fake_repo)
        assert result.returncode == 0
        content = Path(result.stdout.strip()).read_text()
        # The serialised timestamp must contain a UTC offset.
        assert "+00:00" in content

    def test_future_timestamp_rejected(self, fake_repo: Path) -> None:
        """Timestamps more than 60 s in the future must be rejected (HM-06-004)."""
        future = (
            datetime.datetime.now(_UTC) + datetime.timedelta(hours=1)
        ).isoformat()
        result = _run_append(
            "idea",
            extra_args=["--timestamp", future],
            cwd=fake_repo,
        )
        assert result.returncode != 0
        assert "future" in result.stderr.lower()

    def test_past_timestamp_accepted(self, fake_repo: Path) -> None:
        past = "2025-01-01T00:00:00+00:00"
        result = _run_append(
            "idea",
            extra_args=["--timestamp", past],
            cwd=fake_repo,
        )
        assert result.returncode == 0

    def test_naive_timestamp_rejected(self, fake_repo: Path) -> None:
        """Timestamps without a timezone offset must be rejected (HM-06-005)."""
        result = _run_append(
            "idea",
            extra_args=["--timestamp", "2025-01-01T00:00:00"],
            cwd=fake_repo,
        )
        assert result.returncode != 0

    def test_legacy_date_entry_readable_by_readme_gen(
        self, fake_repo: Path
    ) -> None:
        """Existing entries with date: field must be readable (HM-06-003)."""
        from vultron.metadata.history.readme_gen import regenerate_readme

        month_dir = fake_repo / "plan" / "history" / "2604"
        idea_dir = month_dir / "idea"
        idea_dir.mkdir(parents=True)
        legacy = idea_dir / "LEGACY-001.md"
        legacy.write_text(
            "---\ntitle: Legacy\ntype: idea\ndate: 2026-04-01\nsource: LEGACY-001\n---\n\nOld entry.\n"
        )
        readme = regenerate_readme(month_dir)
        assert readme.exists()
        assert "LEGACY-001" in readme.read_text()
        assert "Time (UTC)" in readme.read_text()


class TestFrontmatterValidation:
    """append-history rejects entries with missing CLI arguments."""

    def test_empty_source_exits_nonzero(self, fake_repo: Path) -> None:
        result = _run_append(
            "idea", body=_IDEA_BODY, title="T", source="   ", cwd=fake_repo
        )
        assert result.returncode != 0

    def test_empty_title_exits_nonzero(self, fake_repo: Path) -> None:
        result = _run_append(
            "idea", body=_IDEA_BODY, title="   ", source="SRC-1", cwd=fake_repo
        )
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
            "---\ntitle: Missing fields\n---\n\nNo type, timestamp, or source.\n"
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
        yymm = datetime.datetime.now(_UTC).strftime("%y%m")
        month_dir = fake_repo / "plan" / "history" / yymm
        impl_dir = month_dir / "implementation"
        impl_dir.mkdir(parents=True)
        bad_entry = impl_dir / "BAD-PREEXISTING.md"
        bad_entry.write_text(
            "---\ntitle: Bad\n---\n\nNo type/timestamp/source.\n"
        )

        result = _run_append(
            "implementation",
            body=_IMPL_BODY,
            title=_IMPL_TITLE,
            source="NEW-ENTRY",
            cwd=fake_repo,
        )

        assert result.returncode != 0
        new_file = impl_dir / "NEW-ENTRY.md"
        assert not new_file.exists(), "new entry file should be rolled back"


def _run_with_cmd(
    cmd: list[str],
    body: str = _IDEA_BODY,
) -> _RunResult:
    """Run append-history with an explicit command list."""
    from vultron.metadata.history.cli import main

    stdout_buf = io.StringIO()
    stderr_buf = io.StringIO()
    exit_code = 0

    try:
        with (
            patch("sys.argv", cmd),
            patch("sys.stdin", io.StringIO(body)),
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
