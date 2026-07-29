"""Tests for vultron.metadata.adr.index_gen (MS-14-003, ADR-0043)."""

import pytest

from vultron.metadata.adr.index_gen import (
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
