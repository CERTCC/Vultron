"""The Protocol Specification's pages carry the register's draft status (#5914).

The status block (``docs/reference/vultron-spec/_status.md``) and the Revision
Log's status tables are generated from the drafts register
(``docs/reference/vultron-spec/drafts.yaml``, DOCBW-08-004), so they cannot
disagree with each other; ``test/ci/test_drafts_register.py`` tests the
generation, and ``docs-site --check`` the committed copies. These tests hold
what the generation does not decide: that the specification's pages show the
status block and link the Revision Log, and that the register's dates follow
its drafts.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from vultron.metadata.base import repo_root
from vultron.metadata.docs.drafts_register import load_register

SPEC_DIR = repo_root() / "docs" / "reference" / "vultron-spec"
SPEC_INDEX = SPEC_DIR / "index.md"
FULL_PAGE = SPEC_DIR / "full.md"


def test_entry_dates_do_not_decrease() -> None:
    """A draft's date is the day its entry was added: a later one is no earlier."""
    dates = [entry.date for entry in load_register(repo_root()).drafts]
    assert dates == sorted(dates)


@pytest.mark.parametrize("page", [SPEC_INDEX, FULL_PAGE], ids=lambda p: p.name)
def test_page_includes_status_block(page: Path) -> None:
    text = page.read_text(encoding="utf-8")
    assert '{% include-markdown "./_status.md" %}' in text


def test_spec_index_links_revision_log() -> None:
    assert "](revision-log.md)" in SPEC_INDEX.read_text(encoding="utf-8")
