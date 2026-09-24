"""Tests for the incoming-learnings frontmatter validator.

Covers: BW-02-001, BW-02-002, BW-02-004, BW-02-006.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from vultron.metadata.history import incoming
from vultron.metadata.history.incoming import (
    LEARNINGS_DIR,
    render_learnings_index,
    validate_incoming_learnings,
)

_GOOD = """---
title: "A thing was learned"
type: learning
timestamp: "2026-09-01T00:00:00Z"
source: ISSUE-2762
signal: concern
---

Body text.
"""


def _repo(tmp_path: Path, **files: str) -> Path:
    """Build a throwaway repo root containing the given learning files."""
    (tmp_path / "pyproject.toml").write_text("[project]\nname='x'\n")
    directory = tmp_path / LEARNINGS_DIR
    directory.mkdir(parents=True)
    for name, text in files.items():
        (directory / name).write_text(text, encoding="utf-8")
    return tmp_path


class TestValidateIncomingLearnings:
    def test_accepts_conformant_file(self, tmp_path: Path) -> None:
        root = _repo(tmp_path, **{"20260901-good.md": _GOOD})
        result = validate_incoming_learnings(root)
        assert set(result) == {"20260901-good.md"}
        assert result["20260901-good.md"].source == "ISSUE-2762"

    def test_missing_directory_is_not_an_error(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text("[project]\nname='x'\n")
        assert validate_incoming_learnings(tmp_path) == {}

    def test_skips_readme(self, tmp_path: Path) -> None:
        root = _repo(
            tmp_path,
            **{"20260901-good.md": _GOOD, "README.md": "# not an entry\n"},
        )
        assert set(validate_incoming_learnings(root)) == {"20260901-good.md"}

    @pytest.mark.spec("BW-02-004")
    def test_rejects_bare_date_timestamp(self, tmp_path: Path) -> None:
        """The defect that silently accumulated across 37 files."""
        bad = _GOOD.replace(
            'timestamp: "2026-09-01T00:00:00Z"', "timestamp: 2026-09-01"
        )
        root = _repo(tmp_path, **{"20260901-bare.md": bad})
        with pytest.raises(ValueError) as exc:
            validate_incoming_learnings(root)
        assert "20260901-bare.md" in str(exc.value)
        assert "timestamp" in str(exc.value)

    @pytest.mark.spec("BW-02-001")
    def test_rejects_unquoted_title_ending_in_colon(
        self, tmp_path: Path
    ) -> None:
        """An unquoted trailing colon makes the whole block invalid YAML."""
        bad = _GOOD.replace(
            'title: "A thing was learned"',
            "title: Chose degrade over fail-fast for an invite with no to:",
        )
        root = _repo(tmp_path, **{"20260901-colon.md": bad})
        with pytest.raises(ValueError) as exc:
            validate_incoming_learnings(root)
        assert "20260901-colon.md" in str(exc.value)

    @pytest.mark.spec("BW-02-001")
    def test_rejects_missing_required_field(self, tmp_path: Path) -> None:
        bad = _GOOD.replace("source: ISSUE-2762\n", "")
        root = _repo(tmp_path, **{"20260901-nosource.md": bad})
        with pytest.raises(ValueError) as exc:
            validate_incoming_learnings(root)
        assert "source" in str(exc.value)

    def test_rejects_signal_outside_the_enum(self, tmp_path: Path) -> None:
        """BW-07-002 defines the signal set; invented values must not pass."""
        bad = _GOOD.replace("signal: concern", "signal: deferred-bug")
        root = _repo(tmp_path, **{"20260901-signal.md": bad})
        with pytest.raises(ValueError) as exc:
            validate_incoming_learnings(root)
        assert "signal" in str(exc.value)

    def test_reports_every_offender_at_once(self, tmp_path: Path) -> None:
        """One pass should surface the whole backlog, not just the first file."""
        root = _repo(
            tmp_path,
            **{
                "20260901-a.md": _GOOD.replace(
                    'timestamp: "2026-09-01T00:00:00Z"',
                    "timestamp: 2026-09-01",
                ),
                "20260901-b.md": _GOOD.replace("type: learning\n", ""),
                "20260901-ok.md": _GOOD,
            },
        )
        with pytest.raises(ValueError) as exc:
            validate_incoming_learnings(root)
        message = str(exc.value)
        assert "20260901-a.md" in message
        assert "20260901-b.md" in message
        assert "2 file(s)" in message


class TestRealCorpus:
    @pytest.mark.spec("BW-02-001")
    def test_every_committed_learning_file_is_archivable(self) -> None:
        """The repo's own queue must stay drainable by `learn`.

        This is the ratchet: it is what stops the 37-file backlog from
        re-accumulating between releases.
        """
        assert validate_incoming_learnings()


class TestRenderLearningsIndex:
    """The index replaces reading the directory whole during `orient-agent`.

    Each title states the lesson, so the failure that matters is dropping a
    file: a learning missing from the index is one no agent sees.
    """

    def test_lists_source_title_and_filename(self, tmp_path: Path) -> None:
        root = _repo(tmp_path, **{"20260901-good.md": _GOOD})
        out = render_learnings_index(validate_incoming_learnings(root))
        assert "ISSUE-2762  A thing was learned" in out
        assert "    20260901-good.md" in out
        assert out.startswith("# 1 incoming learnings")

    def test_orders_newest_first(self, tmp_path: Path) -> None:
        older = _GOOD.replace("2026-09-01", "2026-08-01").replace(
            "A thing", "Older thing"
        )
        root = _repo(
            tmp_path,
            **{"20260901-new.md": _GOOD, "20260801-old.md": older},
        )
        out = render_learnings_index(validate_incoming_learnings(root))
        assert out.index("A thing was learned") < out.index("Older thing")

    def test_empty_directory_renders_a_header_only(
        self, tmp_path: Path
    ) -> None:
        (tmp_path / "pyproject.toml").write_text("[project]\nname='x'\n")
        out = render_learnings_index(validate_incoming_learnings(tmp_path))
        assert out.splitlines() == [
            "# 0 incoming learnings, newest first. Titles state the lesson;"
            " read plan/incoming/learnings/<file> for the evidence behind one"
            " that bears on your task."
        ]

    @pytest.mark.spec("BW-02-001")
    def test_real_corpus_index_lists_every_committed_learning(self) -> None:
        entries = validate_incoming_learnings()
        out = render_learnings_index(entries)
        assert entries
        assert [name for name in entries if name not in out] == []


class TestLearningsIndexCli:
    """``learnings-index`` is what orient-agent reads instead of the queue."""

    @pytest.mark.spec("BW-02-006")
    def test_malformed_file_does_not_cost_the_valid_entries(
        self, tmp_path: Path, monkeypatch, capsys
    ) -> None:
        """An unquoted colon in one title used to abort the whole index."""
        root = _repo(
            tmp_path,
            **{
                "20260901-good.md": _GOOD,
                "20260902-bad.md": "---\ntitle: broken: colon\n---\nb\n",
            },
        )
        monkeypatch.setattr(incoming, "_find_repo_root", lambda: root)
        incoming.main()
        out, err = capsys.readouterr()
        assert "A thing was learned" in out
        assert "1 incoming learnings" in out
        assert "20260902-bad.md" in err
        assert "20260901-good.md" not in err

    @pytest.mark.spec("BW-02-006")
    def test_clean_queue_writes_nothing_to_stderr(
        self, tmp_path: Path, monkeypatch, capsys
    ) -> None:
        root = _repo(tmp_path, **{"20260901-good.md": _GOOD})
        monkeypatch.setattr(incoming, "_find_repo_root", lambda: root)
        incoming.main()
        out, err = capsys.readouterr()
        assert "A thing was learned" in out
        assert err == ""
