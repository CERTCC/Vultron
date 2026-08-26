"""Tests for vultron.metadata.adr.index_gen (MS-14-003, ADR-0043)."""

import pytest

from vultron.metadata.adr.index_gen import (
    duplicate_numbers,
    generate_index,
    main,
    missing_nav_entries,
)


def _write_adr(adr_dir, num, status, title, superseded_by=None):
    fm = f"---\nstatus: {status}\n"
    if superseded_by:
        fm += f"superseded_by: {superseded_by}\n"
    fm += "---\n"
    (adr_dir / f"{num}-stub.md").write_text(f"{fm}# {title}\n")


def _scaffold(tmp_path):
    """Create a minimal repo with pyproject.toml + docs/adr/ + mkdocs.yml."""
    (tmp_path / "pyproject.toml").write_text("[project]\nname='x'\n")
    adr_dir = tmp_path / "docs" / "adr"
    adr_dir.mkdir(parents=True)
    (adr_dir / "index.md").write_text(
        "# Decisions\n\nPreamble prose.\n\n## Accepted ADRs\n\n- old\n"
    )
    return adr_dir


class TestGenerateIndex:
    def test_sections_by_status(self, tmp_path):
        adr_dir = _scaffold(tmp_path)
        _write_adr(adr_dir, "0001", "accepted", "First")
        _write_adr(adr_dir, "0002", "proposed", "Second")
        _write_adr(adr_dir, "0003", "rejected", "Third")
        _write_adr(
            adr_dir,
            "0004",
            "superseded",
            "Fourth",
            superseded_by="0001-stub.md",
        )

        out = generate_index(tmp_path)

        assert "Preamble prose." in out  # preamble preserved
        assert "## Accepted ADRs" in out
        # ADR-0001 under Accepted, ADR-0002 under Proposed, etc.
        accepted = out.split("## Accepted ADRs")[1].split("## Proposed")[0]
        assert "ADR-0001 First" in accepted
        assert "ADR-0002" not in accepted
        proposed = out.split("## Proposed ADRs")[1].split("## Rejected")[0]
        assert "ADR-0002 Second" in proposed
        retired = out.split("## Superseded / Archived ADRs")[1]
        assert "ADR-0004 Fourth" in retired
        assert "superseded by 0001-stub.md" in retired

    def test_accepted_provisional_annotated(self, tmp_path):
        adr_dir = _scaffold(tmp_path)
        _write_adr(adr_dir, "0001", "accepted-provisional", "Shaky")
        out = generate_index(tmp_path)
        assert "[ADR-0001 Shaky](0001-stub.md) *(provisional)*" in out

    def test_partially_superseded_is_annotated_but_stays_accepted(
        self, tmp_path
    ):
        """ADR-0012's case: one decision replaced, the rest still in force.

        Retiring the whole ADR would discard the decisions that still hold, so
        the status stays ``accepted``. But an unannotated accepted entry reads as
        wholly current, and the index is where a reader chooses what to open —
        which is how ADR-0012 kept being cited for a DataLayer layout ADR-0073
        had replaced.
        """
        adr_dir = _scaffold(tmp_path)
        _write_adr(adr_dir, "0001", "accepted", "Replacement")
        (adr_dir / "0002-stub.md").write_text(
            "---\nstatus: accepted\n"
            "partially_superseded_by: 0001-stub.md\n---\n# Older\n"
        )

        out = generate_index(tmp_path)

        accepted = out.split("## Accepted ADRs")[1].split("## Proposed")[0]
        assert (
            "[ADR-0002 Older](0002-stub.md) — partially superseded by"
            " 0001-stub.md" in accepted
        )
        # Not retired: it is not in the archived section and keeps its status.
        assert "ADR-0002" not in out.split("## Superseded / Archived ADRs")[1]

    def test_numeric_ordering(self, tmp_path):
        adr_dir = _scaffold(tmp_path)
        _write_adr(adr_dir, "0010", "accepted", "Ten")
        _write_adr(adr_dir, "0002", "accepted", "Two")
        out = generate_index(tmp_path)
        assert out.index("ADR-0002") < out.index("ADR-0010")

    def test_redundant_adr_prefix_stripped(self, tmp_path):
        adr_dir = _scaffold(tmp_path)
        _write_adr(adr_dir, "0001", "accepted", "ADR-0001: Real Title")
        out = generate_index(tmp_path)
        assert "ADR-0001 Real Title" in out
        assert "ADR-0001 ADR-0001" not in out

    def test_generate_is_idempotent(self, tmp_path):
        adr_dir = _scaffold(tmp_path)
        _write_adr(adr_dir, "0001", "accepted", "First")
        first = generate_index(tmp_path)
        (adr_dir / "index.md").write_text(first)
        assert generate_index(tmp_path) == first


class TestMissingNavEntries:
    def test_detects_missing(self, tmp_path):
        adr_dir = _scaffold(tmp_path)
        _write_adr(adr_dir, "0001", "accepted", "First")
        _write_adr(adr_dir, "0002", "accepted", "Second")
        (tmp_path / "mkdocs.yml").write_text(
            "nav:\n  - x: 'adr/0001-stub.md'\n"
        )
        missing = missing_nav_entries(tmp_path)
        assert missing == ["adr/0002-stub.md"]

    def test_archived_excluded_from_nav_check(self, tmp_path):
        adr_dir = _scaffold(tmp_path)
        archived = adr_dir / "archived"
        archived.mkdir()
        _write_adr(
            archived, "0001", "superseded", "Old", superseded_by="0002-x.md"
        )
        _write_adr(adr_dir, "0002", "accepted", "New")
        (tmp_path / "mkdocs.yml").write_text(
            "nav:\n  - x: 'adr/0002-stub.md'\n"
        )
        # 0001 is archived → not required in nav
        assert missing_nav_entries(tmp_path) == []

    def test_substring_in_comment_does_not_false_pass(self, tmp_path):
        """A path present only in a comment is NOT a real nav entry.

        Guards the structural (YAML-tree) nav walk against the old raw
        substring match, which would false-pass here and then break
        ``mkdocs build --strict`` (MS-14-006).
        """
        adr_dir = _scaffold(tmp_path)
        _write_adr(adr_dir, "0001", "accepted", "First")
        (tmp_path / "mkdocs.yml").write_text(
            "nav:\n"
            "  - Home: 'index.md'\n"
            "# see also adr/0001-stub.md for context\n"
        )
        assert missing_nav_entries(tmp_path) == ["adr/0001-stub.md"]

    def test_tolerates_mkdocs_custom_tags(self, tmp_path):
        """`!ENV` / `!!python/name:` tags must not crash the nav parse."""
        adr_dir = _scaffold(tmp_path)
        _write_adr(adr_dir, "0001", "accepted", "First")
        (tmp_path / "mkdocs.yml").write_text(
            "plugins:\n"
            "  - search\n"
            "  - mkdocstrings:\n"
            "      enabled: !ENV [ENABLE_MKDOCSTRINGS, true]\n"
            "markdown_extensions:\n"
            "  - pymdownx.emoji:\n"
            "      emoji_generator: !!python/name:material.extensions"
            ".emoji.to_svg\n"
            "nav:\n"
            "  - First: 'adr/0001-stub.md'\n"
        )
        assert missing_nav_entries(tmp_path) == []


class TestMainCLI:
    def _scaffold_synced(self, tmp_path):
        adr_dir = _scaffold(tmp_path)
        _write_adr(adr_dir, "0001", "accepted", "First")
        (tmp_path / "mkdocs.yml").write_text(
            "nav:\n  - First: 'adr/0001-stub.md'\n"
        )
        return adr_dir

    def test_write_makes_index_current(self, tmp_path, monkeypatch):
        adr_dir = self._scaffold_synced(tmp_path)
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr("sys.argv", ["adr-index", "--write"])
        main()
        # index.md now equals generate_index → --check passes
        assert generate_index(tmp_path) == (adr_dir / "index.md").read_text(
            encoding="utf-8"
        )

    def test_check_passes_when_in_sync(self, tmp_path, monkeypatch):
        self._scaffold_synced(tmp_path)
        monkeypatch.chdir(tmp_path)
        # sync the index first
        monkeypatch.setattr("sys.argv", ["adr-index", "--write"])
        main()
        monkeypatch.setattr("sys.argv", ["adr-index", "--check"])
        main()  # exit 0 → no SystemExit

    def test_check_exits_1_when_stale(self, tmp_path, monkeypatch):
        self._scaffold_synced(tmp_path)
        monkeypatch.chdir(tmp_path)
        # index.md is the stub scaffold, not the generated content → stale
        monkeypatch.setattr("sys.argv", ["adr-index", "--check"])
        with pytest.raises(SystemExit) as exc:
            main()
        assert exc.value.code == 1

    def test_check_exits_1_when_nav_missing(self, tmp_path, monkeypatch):
        adr_dir = _scaffold(tmp_path)
        _write_adr(adr_dir, "0001", "accepted", "First")
        # sync index but leave the ADR out of nav
        (tmp_path / "mkdocs.yml").write_text("nav:\n  - Home: 'index.md'\n")
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr("sys.argv", ["adr-index", "--write"])
        main()
        monkeypatch.setattr("sys.argv", ["adr-index", "--check"])
        with pytest.raises(SystemExit) as exc:
            main()
        assert exc.value.code == 1


def _write_adr_named(adr_dir, filename, status, title):
    """Write an ADR at an explicit filename, so two can share a number."""
    (adr_dir / filename).write_text(f"---\nstatus: {status}\n---\n# {title}\n")


class TestDuplicateNumbers:
    """Two ADRs must not share a number (#1872's branch hit this four times)."""

    def test_no_duplicates_returns_empty(self, tmp_path):
        adr_dir = _scaffold(tmp_path)
        _write_adr(adr_dir, "0001", "accepted", "First")
        _write_adr(adr_dir, "0002", "accepted", "Second")

        assert duplicate_numbers(tmp_path) == {}

    def test_two_files_claiming_one_number_are_reported(self, tmp_path):
        """The exact collision an unlanded ADR hits when main allocates first.

        An ADR number is `max(existing) + 1` at authoring time and is not
        *reserved* until the PR merges, so a long-lived branch's claim is
        invalidated by any ADR that lands ahead of it.
        """
        adr_dir = _scaffold(tmp_path)
        _write_adr_named(
            adr_dir, "0070-outbox-terminal-state.md", "accepted", "Theirs"
        )
        _write_adr_named(
            adr_dir, "0070-per-actor-storage.md", "accepted", "Ours"
        )

        dupes = duplicate_numbers(tmp_path)
        assert set(dupes) == {"0070"}
        assert sorted(dupes["0070"]) == [
            "0070-outbox-terminal-state.md",
            "0070-per-actor-storage.md",
        ]

    def test_check_fails_and_names_both_claimants(
        self, tmp_path, monkeypatch, capsys
    ):
        """``--check`` must fail: rendering both entries silently is the bug."""
        adr_dir = _scaffold(tmp_path)
        _write_adr_named(adr_dir, "0070-a.md", "accepted", "A")
        _write_adr_named(adr_dir, "0070-b.md", "accepted", "B")
        (tmp_path / "mkdocs.yml").write_text(
            "nav:\n  - A: 'adr/0070-a.md'\n  - B: 'adr/0070-b.md'\n"
        )
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr("sys.argv", ["adr-index", "--check"])

        with pytest.raises(SystemExit) as exc:
            main()
        assert exc.value.code == 1
        err = capsys.readouterr().err
        assert "ADR-0070 is claimed by 2 files" in err
        assert "0070-a.md" in err and "0070-b.md" in err

    def test_write_refuses_rather_than_rendering_a_duplicate(
        self, tmp_path, monkeypatch, capsys
    ):
        """``--write`` must not produce an index with two ADR-0070 lines.

        Regenerating happily rendered both, which is how four successive
        collisions went unnoticed until merge time.
        """
        adr_dir = _scaffold(tmp_path)
        _write_adr_named(adr_dir, "0070-a.md", "accepted", "A")
        _write_adr_named(adr_dir, "0070-b.md", "accepted", "B")
        before = (adr_dir / "index.md").read_text()
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr("sys.argv", ["adr-index", "--write"])

        with pytest.raises(SystemExit) as exc:
            main()
        assert exc.value.code == 1
        assert (adr_dir / "index.md").read_text() == before, (
            "the index must be left untouched rather than rewritten with a"
            " duplicate number"
        )
        assert "Refusing to write" in capsys.readouterr().err
