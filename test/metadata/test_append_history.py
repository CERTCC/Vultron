"""Tests for the append-history CLI tool.

Covers: HM-03-001 through HM-03-006 (entry creation, README regeneration,
type validation, stdin mode, --file mode), HM-06-001 through HM-06-005
(timestamp field, future-date rejection), HM-07-001 through HM-07-003
(--title, --source CLI params), HM-08-001 through HM-08-005 (GitHub comment
output mode).
"""

from __future__ import annotations

import dataclasses
import datetime
import io
import subprocess
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

_UTC = datetime.UTC

# Body-only content (no frontmatter) — the tool now builds frontmatter.
_IDEA_BODY = "This is a test idea body.\n"
_IMPL_BODY = "Completed a test task.\n"

_DEFAULT_TITLE = "Test Idea"
_DEFAULT_SOURCE = "IDEA-26043001"
_IMPL_TITLE = "Test Implementation Task"
_IMPL_SOURCE = "ISSUE-1-test-task"
#: A source each type writes to a file with (HM-08-003 for idea/implementation).
_VALID_SOURCE = {
    "idea": "IDEA-26043002",
    "implementation": "ISSUE-1-detail",
    "learning": "SRC-LEARNING",
    "priority": "SRC-PRIORITY",
}


@pytest.fixture()
def fake_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Create a minimal fake repo root with pyproject.toml and plan/."""
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'test'\n")
    (tmp_path / "plan").mkdir()
    monkeypatch.chdir(tmp_path)
    return tmp_path


@pytest.fixture(autouse=True)
def _no_real_gh(monkeypatch: pytest.MonkeyPatch) -> None:
    """No test asks the real GitHub whether an issue exists.

    An unstubbed ``ISSUE-N`` run would look up, and could comment on, a real
    issue. Tests that need an answer stub ``gh_issue_view`` themselves.
    """

    def refuse(
        ref: str, fields: list[str], *, repo: str | None = None
    ) -> dict[str, object]:
        raise AssertionError(f"unstubbed gh lookup of {ref} in {repo}")

    monkeypatch.setattr(
        "vultron.metadata.history.cli.github.gh_issue_view", refuse
    )


def _gh_not_found(n: int) -> subprocess.CalledProcessError:
    """The error ``gh issue view N`` raises when N names no issue."""
    return subprocess.CalledProcessError(
        1,
        ["gh", "issue", "view", str(n)],
        stderr="GraphQL: Could not resolve to an issue or pull request with"
        f" the number of {n}. (repository.issue)\n",
    )


def _stub_issues(
    monkeypatch: pytest.MonkeyPatch,
    existing: set[int],
    pulls: frozenset[int] = frozenset(),
) -> list[tuple[str, str | None]]:
    """Answer lookups: *existing* are issues, *pulls* are pull requests.

    Returns the ``(ref, repo)`` of each lookup made.
    """
    lookups: list[tuple[str, str | None]] = []

    def fake_view(
        ref: str, fields: list[str], *, repo: str | None = None
    ) -> dict[str, object]:
        lookups.append((ref, repo))
        n = int(ref.removeprefix("#"))
        base = "https://github.com/CERTCC/Vultron"
        if n in pulls:
            return {"url": f"{base}/pull/{n}"}
        if n not in existing:
            raise _gh_not_found(n)
        return {"url": f"{base}/issues/{n}"}

    monkeypatch.setattr(
        "vultron.metadata.history.cli.github.gh_issue_view", fake_view
    )
    return lookups


def _fail_lookups(monkeypatch: pytest.MonkeyPatch, error: Exception) -> None:
    """Make every issue lookup raise *error*, as a broken ``gh`` would."""

    def fail(
        ref: str, fields: list[str], *, repo: str | None = None
    ) -> dict[str, object]:
        raise error

    monkeypatch.setattr(
        "vultron.metadata.history.cli.github.gh_issue_view", fail
    )


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
        # Path should be plan/history/YYMM/idea/IDEA-26043001.md
        assert written_path.parent.name == "idea"
        assert written_path.stem == "IDEA-26043001"

    def test_written_path_printed_to_stdout(self, fake_repo: Path) -> None:
        result = _run_append("idea", cwd=fake_repo)
        assert result.returncode == 0
        printed = result.stdout.strip()
        assert "IDEA-26043001" in printed

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
        assert "IDEA-26043001" in readme_text
        assert "Test Idea" in readme_text

    def test_readme_has_time_utc_column(self, fake_repo: Path) -> None:
        """README table must include a Time (UTC) column (HM-06-006)."""
        result = _run_append("idea", cwd=fake_repo)
        assert result.returncode == 0
        month_dir = Path(result.stdout.strip()).parent.parent
        readme_text = (month_dir / "README.md").read_text()
        assert "Time (UTC)" in readme_text

    @pytest.mark.spec("HM-06-006")
    def test_readme_has_date_and_time_columns(self, fake_repo: Path) -> None:
        """Each row shows the timestamp's date and its HH:MM time (HM-06-006)."""
        result = _run_append(
            "implementation",
            body=_IMPL_BODY,
            title=_IMPL_TITLE,
            source="ISSUE-1-dated",
            extra_args=["--timestamp", "2025-12-15T09:30:45+00:00"],
            cwd=fake_repo,
        )
        assert result.returncode == 0
        readme_text = (
            fake_repo / "plan" / "history" / "2512" / "README.md"
        ).read_text()
        assert "| Date | Time (UTC) |" in readme_text
        row = next(
            line
            for line in readme_text.splitlines()
            if "ISSUE-1-dated" in line
        )
        cells = [cell.strip() for cell in row.strip("|").split("|")]
        assert "2025-12-15" in cells
        assert "09:30" in cells

    @pytest.mark.spec("HM-06-011")
    def test_readme_sorted_newest_first(self, fake_repo: Path) -> None:
        """The index lists the newest entry first, whatever the write order."""
        for source, stamp in (
            ("ISSUE-1-older", "2025-12-01T08:00:00+00:00"),
            ("ISSUE-1-newer", "2025-12-15T09:30:00+00:00"),
            ("ISSUE-1-middle", "2025-12-10T12:00:00+00:00"),
        ):
            result = _run_append(
                "implementation",
                body=_IMPL_BODY,
                title=_IMPL_TITLE,
                source=source,
                extra_args=["--timestamp", stamp],
                cwd=fake_repo,
            )
            assert result.returncode == 0
        readme_text = (
            fake_repo / "plan" / "history" / "2512" / "README.md"
        ).read_text()
        positions = [
            readme_text.index(source)
            for source in ("ISSUE-1-newer", "ISSUE-1-middle", "ISSUE-1-older")
        ]
        assert positions == sorted(positions)

    @pytest.mark.spec("HM-02-007")
    def test_hand_edit_replaced_on_next_run(self, fake_repo: Path) -> None:
        """A hand edit to the index does not survive the next run."""
        first = _run_append("idea", cwd=fake_repo)
        assert first.returncode == 0
        readme = Path(first.stdout.strip()).parent.parent / "README.md"
        readme.write_text(readme.read_text() + "\nHAND-EDITED LINE\n")
        second = _run_append(
            "implementation",
            body=_IMPL_BODY,
            title=_IMPL_TITLE,
            source=_IMPL_SOURCE,
            cwd=fake_repo,
        )
        assert second.returncode == 0
        assert "HAND-EDITED LINE" not in readme.read_text()

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
        assert "IDEA-26043001" in readme_text
        assert "ISSUE-1-test-task" in readme_text


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
            source=_VALID_SOURCE[valid_type],
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
    """HM-01-010: history entries are write-once; overwrite must be rejected."""

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
            source="ISSUE-1-new-entry",
            cwd=fake_repo,
        )

        assert result.returncode != 0
        new_file = impl_dir / "ISSUE-1-new-entry.md"
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

    @pytest.mark.parametrize(
        ("entry_type", "source", "accepted"),
        [
            ("implementation", "ISSUE-4646", False),
            ("implementation", "TASK-4646", False),
            ("implementation", "ISSUE-4646-detail", True),
            ("idea", "IDEA-26042702", True),
            ("idea", "IDEA-2066", False),
        ],
    )
    @pytest.mark.spec("HM-08-008")
    def test_implementation_and_idea_files_follow_the_vocabulary(
        self,
        fake_repo: Path,
        tmp_path: Path,
        entry_type: str,
        source: str,
        accepted: bool,
    ) -> None:
        """Only a file form is archived; ISSUE-N belongs on the issue and any
        other source is refused, with the source file left in place."""
        src = _make_incoming_file(
            tmp_path,
            content=(
                f"---\ntitle: T\ntype: {entry_type}\n"
                "timestamp: '2026-06-22T10:00:00+00:00'\n"
                f"source: {source}\n---\n\nBody.\n"
            ),
            filename=f"{source}.md",
        )
        result = _run_from_file(src)
        assert (result.returncode == 0) is accepted, result.stderr
        assert src.exists() is not accepted

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

    def test_second_entry_for_same_source_gets_discriminated_path(
        self, fake_repo: Path, tmp_path: Path
    ) -> None:
        """A work item may produce several learnings (HM-01-002, BW-01-009).

        The second entry is written alongside the first under a slug-suffixed
        name rather than failing, but the first is never overwritten.
        """
        src1 = _make_incoming_file(tmp_path, filename=f"{_LEARNING_SOURCE}.md")
        first = _run_from_file(src1)
        assert first.returncode == 0
        first_path = Path(first.stdout.strip())
        first_bytes = first_path.read_bytes()

        src2 = _make_incoming_file(
            tmp_path, filename=f"{_LEARNING_SOURCE}-copy.md"
        )
        result = _run_from_file(src2)

        assert result.returncode == 0
        second_path = Path(result.stdout.strip())
        assert second_path != first_path
        assert second_path.name == f"{_LEARNING_SOURCE}-copy.md"
        assert second_path.exists()
        # Write-once: the original entry is untouched.
        assert first_path.read_bytes() == first_bytes

    def test_duplicate_source_and_slug_exits_nonzero(
        self, fake_repo: Path, tmp_path: Path
    ) -> None:
        """Re-archiving the identical incoming filename still fails."""
        src1 = _make_incoming_file(tmp_path, filename=f"{_LEARNING_SOURCE}.md")
        assert _run_from_file(src1).returncode == 0
        src2 = _make_incoming_file(tmp_path, filename=f"{_LEARNING_SOURCE}.md")
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


class TestClassifySource:
    """The implementation and idea source vocabulary (HM-08-001/003/008)."""

    @pytest.mark.parametrize(
        ("entry_type", "source", "expected"),
        [
            ("implementation", "ISSUE-2159", 2159),
            ("idea", "ISSUE-42", 42),
            ("implementation", "ISSUE-4646-detail", None),
            ("implementation", "ISSUE-12-pr-body-record", None),
            ("idea", "IDEA-26042702", None),
        ],
    )
    def test_accepted_forms(
        self, entry_type: str, source: str, expected: int | None
    ) -> None:
        from vultron.metadata.history.cli.source import classify_source
        from vultron.metadata.history.types import HistoryEntryType

        assert (
            classify_source(HistoryEntryType(entry_type), source) == expected
        )

    @pytest.mark.parametrize(
        ("entry_type", "source", "suggestion"),
        [
            ("implementation", "TASK-4646", "ISSUE-4646"),
            ("implementation", "ADR-0041", "ISSUE-41"),
            ("implementation", "4646", "ISSUE-4646"),
            ("implementation", "issue-42", "ISSUE-42"),
            ("implementation", "ISSUE-042", "ISSUE-42"),
            ("implementation", "IDEA-26042702", None),
            ("implementation", "TASK-BTND5", None),
            ("implementation", "ISSUE-0", None),
            ("implementation", "ISSUE-12-Upper", None),
            ("implementation", "ISSUE-\u0664\u0662", None),
            ("implementation", "ISSUE-42\n", None),
            ("implementation", "ISSUE-42-detail\n", None),
            ("idea", "IDEA-2066", "ISSUE-2066"),
            ("idea", "ISSUE-4646-detail", None),
            ("idea", "IDEA-TEST-001", None),
            ("idea", "IDEA-26042702\n", None),
            ("idea", "BUG-2505", "ISSUE-2505"),
        ],
    )
    @pytest.mark.spec("HM-08-008")
    def test_other_forms_are_refused_naming_the_accepted_ones(
        self, entry_type: str, source: str, suggestion: str | None
    ) -> None:
        from vultron.metadata.history.cli.source import (
            SourceRefusedError,
            classify_source,
        )
        from vultron.metadata.history.types import HistoryEntryType

        with pytest.raises(SourceRefusedError) as info:
            classify_source(HistoryEntryType(entry_type), source)
        message = str(info.value)
        assert "ISSUE-N" in message
        file_form = (
            "ISSUE-N-<slug>"
            if entry_type == "implementation"
            else "IDEA-YYMMDDNN"
        )
        assert file_form in message
        if suggestion is not None:
            assert f"use {suggestion}" in message

    @pytest.mark.parametrize("entry_type", ["learning", "note", "priority"])
    def test_other_types_are_free_form(self, entry_type: str) -> None:
        from vultron.metadata.history.cli.source import classify_source
        from vultron.metadata.history.types import HistoryEntryType

        for source in ("TASK-4646", "ISSUE-12", "anything"):
            assert (
                classify_source(HistoryEntryType(entry_type), source) is None
            )


class TestConfirmIssue:
    """``ISSUE-N`` posts only when N is an issue (HM-08-001, -007, -009)."""

    @pytest.mark.spec("HM-08-001")
    def test_existing_issue_is_confirmed(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from vultron.metadata.history.cli.github import _confirm_issue

        lookups = _stub_issues(monkeypatch, {4646})
        assert _confirm_issue(4646) == 4646
        assert lookups == [("#4646", "CERTCC/Vultron")]

    @pytest.mark.spec("HM-08-009")
    def test_missing_issue_is_refused(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from vultron.metadata.history.cli.github import _confirm_issue
        from vultron.metadata.history.cli.source import SourceRefusedError

        _stub_issues(monkeypatch, {4646})
        with pytest.raises(SourceRefusedError, match="no issue #99999"):
            _confirm_issue(99999)

    @pytest.mark.spec("HM-08-009")
    def test_pull_request_is_refused(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from vultron.metadata.history.cli.github import _confirm_issue
        from vultron.metadata.history.cli.source import SourceRefusedError

        _stub_issues(monkeypatch, set(), pulls=frozenset({5837}))
        with pytest.raises(SourceRefusedError, match="pull request"):
            _confirm_issue(5837)

    @pytest.mark.parametrize(
        "error",
        [
            subprocess.CalledProcessError(1, ["gh"], stderr="HTTP 401\n"),
            FileNotFoundError("gh"),
        ],
    )
    @pytest.mark.spec("HM-08-007")
    def test_lookup_that_cannot_answer_raises(
        self, monkeypatch: pytest.MonkeyPatch, error: Exception
    ) -> None:
        """No answer is not "no such issue": the tool stops, never guesses."""
        from vultron.metadata.history.cli.github import _confirm_issue

        _fail_lookups(monkeypatch, error)
        with pytest.raises(RuntimeError, match="ISSUE-4646"):
            _confirm_issue(4646)


_COMMENT_URL = (
    "https://github.com/CERTCC/Vultron/issues/2159#issuecomment-9999"
)


class TestGitHubCommentMode:
    """HM-08: the CLI's comment mode, file forms and refusals."""

    @pytest.fixture()
    def existing(self, monkeypatch: pytest.MonkeyPatch) -> set[int]:
        """Issues that exist; #5837 is a pull request."""
        issues: set[int] = {42, 2159, 4646}
        _stub_issues(monkeypatch, issues, pulls=frozenset({5837}))
        return issues

    def _run_with_mock_gh(
        self,
        entry_type: str,
        source: str,
        body: str = "Entry body.\n",
        title: str = "Test Title",
        gh_returncode: int = 0,
        gh_stdout: str = _COMMENT_URL,
        gh_stderr: str = "",
    ) -> tuple[_RunResult, MagicMock]:
        """Run append-history with ``gh issue comment`` mocked."""
        mock_result = MagicMock()
        mock_result.returncode = gh_returncode
        mock_result.stdout = gh_stdout
        mock_result.stderr = gh_stderr

        with patch(
            "vultron.metadata.history.cli.github.subprocess.run",
            return_value=mock_result,
        ) as mock_run:
            result = _run_append(
                entry_type, body=body, title=title, source=source
            )
        return result, mock_run

    @staticmethod
    def _history_files(repo: Path) -> list[Path]:
        history_dir = repo / "plan" / "history"
        return list(history_dir.rglob("*.md")) if history_dir.exists() else []

    @pytest.mark.parametrize(
        ("entry_type", "source", "issue"),
        [
            ("implementation", "ISSUE-2159", "2159"),
            ("idea", "ISSUE-42", "42"),
        ],
    )
    @pytest.mark.spec("HM-08-001", "HM-01-007", "HM-01-008")
    def test_issue_source_posts_comment(
        self,
        fake_repo: Path,
        existing: set[int],
        entry_type: str,
        source: str,
        issue: str,
    ) -> None:
        """ISSUE-N naming an existing issue posts on issue N (HM-08-001)."""
        result, mock_run = self._run_with_mock_gh(entry_type, source)
        assert result.returncode == 0, result.stderr
        argv = mock_run.call_args[0][0]
        assert argv[:4] == ["gh", "issue", "comment", issue]
        assert argv[argv.index("--repo") + 1] == "CERTCC/Vultron"
        assert not self._history_files(fake_repo)

    def test_prints_comment_url_to_stdout(
        self, fake_repo: Path, existing: set[int]
    ) -> None:
        """Comment URL is printed to stdout (HM-08-002)."""
        result, _ = self._run_with_mock_gh("implementation", "ISSUE-2159")
        assert result.returncode == 0
        assert result.stdout.strip() == _COMMENT_URL

    @pytest.mark.parametrize(
        ("entry_type", "source"),
        [
            ("implementation", "ISSUE-4646-detail"),
            ("idea", "IDEA-26042702"),
        ],
    )
    @pytest.mark.spec("HM-08-003")
    def test_file_form_writes_file_without_asking_github(
        self,
        fake_repo: Path,
        monkeypatch: pytest.MonkeyPatch,
        entry_type: str,
        source: str,
    ) -> None:
        """ISSUE-N-<slug> and IDEA-YYMMDDNN write a file; gh is never asked."""
        lookups = _stub_issues(monkeypatch, {4646})
        result, mock_run = self._run_with_mock_gh(entry_type, source)
        assert result.returncode == 0, result.stderr
        written = Path(result.stdout.strip())
        assert written.exists()
        assert f"source: {source}" in written.read_text()
        assert not mock_run.called
        assert lookups == []

    @pytest.mark.parametrize(
        ("entry_type", "source"),
        [
            ("implementation", "TASK-4646"),
            ("implementation", "ADR-0041"),
            ("implementation", "4646"),
            ("idea", "IDEA-2066"),
            ("idea", "ISSUE-4646-detail"),
        ],
    )
    @pytest.mark.spec("HM-08-008")
    def test_other_source_is_refused_and_writes_nothing(
        self,
        fake_repo: Path,
        existing: set[int],
        entry_type: str,
        source: str,
    ) -> None:
        """A source outside the vocabulary exits 1 and writes nothing."""
        result, mock_run = self._run_with_mock_gh(entry_type, source)
        assert result.returncode != 0
        assert "ISSUE-N" in result.stderr
        assert not mock_run.called
        assert not self._history_files(fake_repo)

    @pytest.mark.parametrize("source", ["ISSUE-99999", "ISSUE-5837"])
    @pytest.mark.spec("HM-08-009")
    def test_issue_source_naming_no_issue_is_refused(
        self, fake_repo: Path, existing: set[int], source: str
    ) -> None:
        """ISSUE-N for a missing issue or a pull request is refused, not
        filed (HM-08-009)."""
        result, mock_run = self._run_with_mock_gh("implementation", source)
        assert result.returncode != 0
        assert not mock_run.called
        assert not self._history_files(fake_repo)

    def test_learning_issue_source_writes_file(
        self, fake_repo: Path, existing: set[int]
    ) -> None:
        """learning type always writes a file regardless of source (HM-08-001)."""
        result = _run_append(
            "learning",
            body=_IDEA_BODY,
            title="Learning entry",
            source="ISSUE-2159",
        )
        assert result.returncode == 0
        written = Path(result.stdout.strip())
        assert written.exists()
        assert written.suffix == ".md"

    def test_comment_body_has_heading(
        self, fake_repo: Path, existing: set[int]
    ) -> None:
        """Comment body is prefixed with **History: <type> — <title>** (HM-08-005)."""
        _, mock_run = self._run_with_mock_gh(
            "implementation",
            "ISSUE-2159",
            body="My implementation summary.\n",
            title="Fix demo config cache leak",
        )

        assert mock_run.called
        args_passed = mock_run.call_args[0][0]
        posted_body = args_passed[args_passed.index("--body") + 1]
        assert posted_body.startswith(
            "**History: implementation — Fix demo config cache leak**"
        )
        assert "My implementation summary." in posted_body

    def test_gh_comment_failure_exits_nonzero(
        self, fake_repo: Path, existing: set[int]
    ) -> None:
        """A non-zero exit from gh causes append-history to exit non-zero."""
        result, _ = self._run_with_mock_gh(
            "implementation",
            "ISSUE-2159",
            gh_returncode=1,
            gh_stderr="authentication required",
        )
        assert result.returncode != 0
        assert not self._history_files(fake_repo)

    @pytest.mark.spec("HM-08-007")
    def test_lookup_failure_exits_nonzero_and_writes_nothing(
        self, fake_repo: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When gh cannot say whether the issue exists, no file and no
        comment is written (HM-08-007)."""
        _fail_lookups(
            monkeypatch,
            subprocess.CalledProcessError(1, ["gh"], stderr="HTTP 401\n"),
        )
        result, mock_run = self._run_with_mock_gh(
            "implementation", "ISSUE-4646"
        )
        assert result.returncode != 0
        assert "HTTP 401" in result.stderr
        assert not mock_run.called
        assert not self._history_files(fake_repo)

    def test_blank_title_is_refused_before_any_comment(
        self, fake_repo: Path, existing: set[int]
    ) -> None:
        """Comment mode validates the entry as file mode does."""
        result, mock_run = self._run_with_mock_gh(
            "implementation", "ISSUE-2159", title="   "
        )
        assert result.returncode != 0
        assert not mock_run.called


@pytest.mark.spec("HM-07-002")
class TestBodyFrontmatterRejection:
    """HM-07-002: stdin and --file mode refuse body that opens with frontmatter.

    --from-file mode moves a complete pre-formatted entry and is exempt.
    """

    _FM_BODY = (
        "---\n"
        "title: Hand-written title\n"
        "type: idea\n"
        "timestamp: '2026-06-22T10:00:00+00:00'\n"
        "source: IDEA-26062201\n"
        "---\n\n"
        "Body text.\n"
    )

    def test_stdin_with_frontmatter_exits_nonzero(
        self, fake_repo: Path
    ) -> None:
        """stdin body that opens with a YAML mapping block is refused (HM-07-002)."""
        result = _run_append(
            "idea",
            body=self._FM_BODY,
            title="T",
            source="IDEA-26110001",
            cwd=fake_repo,
        )
        assert result.returncode != 0

    def test_stdin_with_frontmatter_names_hm_07_002(
        self, fake_repo: Path
    ) -> None:
        """Error message cites HM-07-002 so the caller knows the rule."""
        result = _run_append(
            "idea",
            body=self._FM_BODY,
            title="T",
            source="IDEA-26110001",
            cwd=fake_repo,
        )
        assert "HM-07-002" in result.stderr

    def test_file_mode_with_frontmatter_exits_nonzero(
        self, fake_repo: Path, tmp_path: Path
    ) -> None:
        """--file body that opens with a YAML mapping block is refused (HM-07-002)."""
        body_file = tmp_path / "body-with-fm.md"
        body_file.write_text(self._FM_BODY)
        result = _run_append(
            "idea",
            body="",
            title="T",
            source="IDEA-26110002",
            extra_args=["--file", str(body_file)],
            cwd=fake_repo,
        )
        assert result.returncode != 0

    def test_file_mode_with_frontmatter_names_hm_07_002(
        self, fake_repo: Path, tmp_path: Path
    ) -> None:
        """--file error message cites HM-07-002."""
        body_file = tmp_path / "body-with-fm.md"
        body_file.write_text(self._FM_BODY)
        result = _run_append(
            "idea",
            body="",
            title="T",
            source="IDEA-26110002",
            extra_args=["--file", str(body_file)],
            cwd=fake_repo,
        )
        assert "HM-07-002" in result.stderr

    def test_stdin_with_leading_blank_lines_then_frontmatter_refused(
        self, fake_repo: Path
    ) -> None:
        """Blank lines before the block do not hide it: the first non-blank
        line is what counts (HM-07-002)."""
        result = _run_append(
            "idea",
            body="\n\n" + self._FM_BODY,
            title="T",
            source="IDEA-26110005",
            cwd=fake_repo,
        )
        assert result.returncode != 0
        assert "HM-07-002" in result.stderr

    def test_stdin_with_malformed_frontmatter_refused(
        self, fake_repo: Path
    ) -> None:
        """Hand-written frontmatter with a YAML typo is still refused.

        An unquoted ``: `` in a title makes the block malformed YAML; letting
        it through would write a second block into a write-once entry.
        """
        result = _run_append(
            "idea",
            body="---\ntitle: Fix: a thing\nsource: X\n---\n\nBody.\n",
            title="T",
            source="IDEA-26110006",
            cwd=fake_repo,
        )
        assert result.returncode != 0
        assert "HM-07-002" in result.stderr
        assert "malformed" in result.stderr

    def test_body_without_frontmatter_is_accepted(
        self, fake_repo: Path
    ) -> None:
        """A plain body (no --- block) still succeeds (regression guard)."""
        result = _run_append(
            "idea",
            body=_IDEA_BODY,
            title="T",
            source="IDEA-26110003",
            cwd=fake_repo,
        )
        assert result.returncode == 0

    def test_body_with_yaml_list_block_is_accepted(
        self, fake_repo: Path
    ) -> None:
        """A body whose --- block holds a YAML list is not frontmatter; accepted.

        _check_body_has_no_frontmatter suppresses MetadataLoadError (raised when
        the --- block is not a YAML mapping) and lets the normal build proceed.
        """
        list_block_body = "---\n- item1\n- item2\n---\nActual body text.\n"
        result = _run_append(
            "idea",
            body=list_block_body,
            title="T",
            source="IDEA-26110004",
            cwd=fake_repo,
        )
        assert result.returncode == 0

    def test_from_file_mode_with_frontmatter_unchanged(
        self, fake_repo: Path, tmp_path: Path
    ) -> None:
        """--from-file is exempt: it moves a complete pre-formatted entry."""
        src = _make_incoming_file(tmp_path, content=_LEARNING_CONTENT)
        result = _run_from_file(src)
        assert result.returncode == 0, result.stderr


@pytest.mark.spec("HM-01-011")
def test_monthly_readme_is_gitignored() -> None:
    """Git ignores every monthly index, so none can be committed (HM-01-011)."""
    repo_root = Path(__file__).resolve().parents[2]
    result = subprocess.run(
        [
            "git",
            "check-ignore",
            "--quiet",
            "--no-index",
            "plan/history/2601/README.md",
        ],
        cwd=repo_root,
        check=False,
    )
    assert result.returncode == 0
