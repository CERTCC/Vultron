"""Tests for the shared nav-exclusion helpers in vultron.metadata.base.

Both ``docs-frontmatter`` (DF-11-003) and ``adr-index --check`` (MS-14-006)
use them, so they are tested here, where they live.
"""

from pathlib import Path

import pytest
from mkdocs.config.config_options import PathSpec

from vultron.metadata.base import (
    mkdocs_config,
    nav_exclusion_fault,
    nav_paths,
    not_in_nav_spec,
    repo_root,
)

pytestmark = pytest.mark.spec("DF-11-003")


def _write(tmp_path: Path, text: str) -> Path:
    (tmp_path / "mkdocs.yml").write_text(text, encoding="utf-8")
    return tmp_path


def test_matches_what_mkdocs_matches_on_the_committed_tree():
    """A hand-rolled glob would drift from the build; this one must not."""
    root = repo_root()
    ours = not_in_nav_spec(root)
    theirs = PathSpec().run_validation(mkdocs_config(root)["not_in_nav"])
    pages = [
        p.relative_to(root / "docs").as_posix()
        for p in (root / "docs").rglob("*.md")
    ]
    assert pages
    disagree = [p for p in pages if ours.match_file(p) != theirs.match_file(p)]
    assert disagree == []


def test_absent_key_matches_nothing(tmp_path):
    root = _write(tmp_path, "nav:\n  - index.md\n")
    assert not not_in_nav_spec(root).match_file("adr/0001-x.md")


def test_comment_lines_are_not_patterns(tmp_path):
    root = _write(tmp_path, "not_in_nav: |\n  # adr/*.md\n")
    assert not not_in_nav_spec(root).match_file("adr/0001-x.md")


class TestNavExclusionFault:
    def test_unnavved_and_matched_is_placed_correctly(self, tmp_path):
        root = _write(
            tmp_path, "nav:\n  - index.md\nnot_in_nav: |\n  adr/*.md\n"
        )
        fault = nav_exclusion_fault(
            "adr/0001-x.md", nav_paths(root), not_in_nav_spec(root)
        )
        assert fault is None

    def test_navved_page_is_reported_even_when_matched(self, tmp_path):
        """A nav entry wins over ``not_in_nav``, so the page is still navved."""
        root = _write(
            tmp_path,
            "nav:\n  - adr/0001-x.md\nnot_in_nav: |\n  adr/*.md\n",
        )
        fault = nav_exclusion_fault(
            "adr/0001-x.md", nav_paths(root), not_in_nav_spec(root)
        )
        assert fault is not None and "listed in the mkdocs.yml nav" in fault

    def test_unmatched_page_is_reported(self, tmp_path):
        root = _write(tmp_path, "nav:\n  - index.md\n")
        fault = nav_exclusion_fault(
            "adr/0001-x.md", nav_paths(root), not_in_nav_spec(root)
        )
        assert fault is not None and "not matched by not_in_nav" in fault
