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

    def test_timestamp_entry_readable_by_readme_gen(
        self, fake_repo: Path
    ) -> None:
        """Entries with timestamp: field are read correctly (HM-06-002)."""
        from vultron.metadata.history.readme_gen import regenerate_readme

        month_dir = fake_repo / "plan" / "history" / "2604"
        idea_dir = month_dir / "idea"
        idea_dir.mkdir(parents=True)
        entry = idea_dir / "TS-001.md"
        entry.write_text(
            "---\ntitle: New\ntype: idea\ntimestamp: '2026-04-01T00:00:00+00:00'\nsource: TS-001\n---\n\nEntry body.\n"
        )
        readme = regenerate_readme(month_dir)
        assert readme.exists()
        text = readme.read_text()
        assert "TS-001" in text
        assert "Time (UTC)" in text

    def test_legacy_date_entry_rejected_by_readme_gen(
        self, fake_repo: Path
    ) -> None:
        """Entries with only date: field fail clearly — date: is no longer supported."""
        from vultron.metadata.history.readme_gen import regenerate_readme

        month_dir = fake_repo / "plan" / "history" / "2604"
        idea_dir = month_dir / "idea"
        idea_dir.mkdir(parents=True)
        legacy = idea_dir / "LEGACY-001.md"
        legacy.write_text(
            "---\ntitle: Legacy\ntype: idea\ndate: 2026-04-01\nsource: LEGACY-001\n---\n\nOld entry.\n"
        )
        with pytest.raises(ValueError, match="timestamp"):
            regenerate_readme(month_dir)


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


_LEARNING_SOURCE = "20260622-AST-RATCHET-LAMBDA"
_LEARNING_TITLE = "AST ratchet lambda guard"
_LEARNING_CONTENT = (
    "---\n"
    f"title: '{_LEARNING_TITLE}'\n"
    "type: learning\n"
    "timestamp: '2026-06-22T10:00:00+00:00'\n"
    f"source: {_LEARNING_SOURCE}\n"
    "---\n"
    "\n"
    "Guard ast.Lambda in the scope walker.\n"
)
_LEARNING_CONTENT_WITH_SIGNAL = (
    "---\n"
    f"title: '{_LEARNING_TITLE}'\n"
    "type: learning\n"
    "timestamp: '2026-06-22T10:00:00+00:00'\n"
    f"source: {_LEARNING_SOURCE}\n"
    "signal: spec-gap\n"
    "---\n"
    "\n"
    "Guard ast.Lambda in the scope walker.\n"
)


def _make_incoming_file(
    tmp_path: Path,
    content: str = _LEARNING_CONTENT,
    filename: str = f"{_LEARNING_SOURCE}.md",
) -> Path:
    """Write *content* to *tmp_path*/<filename> and return the path."""
    f = tmp_path / filename
    f.write_text(content)
    return f


def _run_from_file(
    source_path: Path,
    extra_args: list[str] | None = None,
) -> _RunResult:
    """Run ``append-history --from-file <source_path>``."""
    cmd = ["append-history", "--from-file", str(source_path)]
    if extra_args:
        cmd.extend(extra_args)
    return _run_with_cmd(cmd, body="")


class TestFromFileMode:
    """append-history --from-file: move a pre-formatted incoming learning file."""

    def test_archives_file_to_history(
        self, fake_repo: Path, tmp_path: Path
    ) -> None:
        """Valid file is moved to plan/history/YYMM/learning/ (BW-01-004)."""
        src = _make_incoming_file(tmp_path)
        result = _run_from_file(src)
        assert result.returncode == 0
        dest = Path(result.stdout.strip())
        assert dest.exists()
        assert dest.parent.name == "learning"
        assert dest.stem == _LEARNING_SOURCE

    def test_source_file_deleted_after_archive(
        self, fake_repo: Path, tmp_path: Path
    ) -> None:
        """Source file is removed from plan/incoming/ on success (BW-01-004)."""
        src = _make_incoming_file(tmp_path)
        result = _run_from_file(src)
        assert result.returncode == 0
        assert not src.exists()

    def test_body_content_preserved(
        self, fake_repo: Path, tmp_path: Path
    ) -> None:
        src = _make_incoming_file(tmp_path)
        result = _run_from_file(src)
        assert result.returncode == 0
        assert "Guard ast.Lambda" in Path(result.stdout.strip()).read_text()

    def test_timestamp_determines_yymm_directory(
        self, fake_repo: Path, tmp_path: Path
    ) -> None:
        """Frontmatter timestamp controls which YYMM directory is used."""
        src = _make_incoming_file(tmp_path)
        result = _run_from_file(src)
        assert result.returncode == 0
        dest = Path(result.stdout.strip())
        assert dest.parent.parent.name == "2606"

    def test_missing_source_file_exits_nonzero(self, fake_repo: Path) -> None:
        result = _run_from_file(Path("/nonexistent/20260622-SLUG.md"))
        assert result.returncode != 0
        assert "not found" in result.stderr.lower()

    def test_file_without_frontmatter_exits_nonzero(
        self, fake_repo: Path, tmp_path: Path
    ) -> None:
        src = _make_incoming_file(tmp_path, content="No frontmatter here.\n")
        result = _run_from_file(src)
        assert result.returncode != 0

    def test_file_with_missing_required_fields_exits_nonzero(
        self, fake_repo: Path, tmp_path: Path
    ) -> None:
        content = "---\ntitle: Only title\n---\nBody.\n"
        src = _make_incoming_file(tmp_path, content=content)
        result = _run_from_file(src)
        assert result.returncode != 0

    def test_future_timestamp_rejected(
        self, fake_repo: Path, tmp_path: Path
    ) -> None:
        future = (
            datetime.datetime.now(_UTC) + datetime.timedelta(hours=1)
        ).isoformat()
        content = (
            "---\n"
            "title: Future entry\n"
            "type: learning\n"
            f"timestamp: '{future}'\n"
            "source: 20260622-FUTURE\n"
            "---\n"
            "Body.\n"
        )
        src = _make_incoming_file(
            tmp_path, content=content, filename="20260622-FUTURE.md"
        )
        result = _run_from_file(src)
        assert result.returncode != 0
        assert "future" in result.stderr.lower()

    def test_duplicate_destination_exits_nonzero(
        self, fake_repo: Path, tmp_path: Path
    ) -> None:
        src1 = _make_incoming_file(tmp_path, filename=f"{_LEARNING_SOURCE}.md")
        _run_from_file(src1)
        # Recreate the source so the second run has something to read.
        src2 = _make_incoming_file(
            tmp_path, filename=f"{_LEARNING_SOURCE}-copy.md"
        )
        content_dup = _LEARNING_CONTENT.replace(
            _LEARNING_SOURCE, _LEARNING_SOURCE
        )
        src2.write_text(content_dup)
        result = _run_from_file(src2)
        assert result.returncode != 0
        assert "already exists" in result.stderr.lower()

    def test_incompatible_with_title_flag(
        self, fake_repo: Path, tmp_path: Path
    ) -> None:
        src = _make_incoming_file(tmp_path)
        result = _run_from_file(src, extra_args=["--title", "override"])
        assert result.returncode != 0
        assert "--title" in result.stderr

    def test_incompatible_with_source_flag(
        self, fake_repo: Path, tmp_path: Path
    ) -> None:
        src = _make_incoming_file(tmp_path)
        result = _run_from_file(src, extra_args=["--source", "OTHER"])
        assert result.returncode != 0
        assert "--source" in result.stderr

    def test_incompatible_with_positional_type(
        self, fake_repo: Path, tmp_path: Path
    ) -> None:
        src = _make_incoming_file(tmp_path)
        cmd = ["append-history", "learning", "--from-file", str(src)]
        result = _run_with_cmd(cmd, body="")
        assert result.returncode != 0
        assert "positional type argument" in result.stderr


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


class TestSignalFlag:
    """--signal flag: emitted in frontmatter for learning entries (BW-07-002)."""

    def test_signal_written_to_frontmatter(self, fake_repo: Path) -> None:
        result = _run_append(
            "learning",
            body=_IDEA_BODY,
            title="Spec gap found",
            source="20260622-SPEC-GAP",
            extra_args=["--signal", "spec-gap"],
        )
        assert result.returncode == 0
        content = Path(result.stdout.strip()).read_text()
        assert "signal: spec-gap" in content

    def test_signal_absent_when_not_provided(self, fake_repo: Path) -> None:
        result = _run_append(
            "learning",
            body=_IDEA_BODY,
            title="Untagged learning",
            source="20260622-UNTAGGED",
        )
        assert result.returncode == 0
        content = Path(result.stdout.strip()).read_text()
        assert "signal:" not in content

    def test_signal_on_non_learning_type_rejected(
        self, fake_repo: Path
    ) -> None:
        result = _run_append(
            "idea",
            body=_IDEA_BODY,
            title="Idea with signal",
            source="IDEA-WITH-SIGNAL",
            extra_args=["--signal", "spec-gap"],
        )
        assert result.returncode != 0
        assert "learning" in result.stderr

    def test_unknown_signal_value_rejected(self, fake_repo: Path) -> None:
        result = _run_append(
            "learning",
            body=_IDEA_BODY,
            title="Bad signal",
            source="20260622-BAD-SIGNAL",
            extra_args=["--signal", "not-a-real-signal"],
        )
        assert result.returncode != 0
        assert "unknown signal" in result.stderr.lower()

    def test_from_file_preserves_signal_field(
        self, fake_repo: Path, tmp_path: Path
    ) -> None:
        """--from-file path preserves signal: frontmatter verbatim."""
        src = _make_incoming_file(
            tmp_path,
            content=_LEARNING_CONTENT_WITH_SIGNAL,
            filename=f"{_LEARNING_SOURCE}.md",
        )
        result = _run_from_file(src)
        assert result.returncode == 0
        content = Path(result.stdout.strip()).read_text()
        assert "signal: spec-gap" in content
