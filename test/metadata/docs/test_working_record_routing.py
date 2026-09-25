"""Every working-record page is reachable from the working-record door.

Requirements: DF-11-003 (working record stays out of the nav, behind one
labeled door) and DF-11-006 (each group is reached through a routing page that
links every member). ``docs-frontmatter`` checks that a working-record page is
out of the nav; this checks that taking it out did not orphan it (#3528).
"""

from __future__ import annotations

import posixpath
import re

import pytest

from vultron.metadata.base import repo_root
from vultron.metadata.docs.page_frontmatter import classify_docs_tree
from vultron.metadata.docs.page_schema import is_working_record

#: The working record's one nav entry.
DOOR = "about/project_record.md"

#: Working record that no routing page is meant to reach: agent- and
#: maintainer-facing trees, and the page ``mkdocs.yml`` records as linked from
#: nowhere (the ontology tombstone, #3551).
UNROUTED = re.compile(
    r"(agents|developer|reference/codebase)/.*|reference/ontology/index\.md"
)

_LINK_RE = re.compile(
    r"\]\((?!https?:|mailto:|#)([^)\s#]+\.md)(?:#[^)\s]*)?(?:\s+\"[^\"]*\")?\)"
)


def _links(docs_path: str, text: str) -> set[str]:
    """``docs/``-relative targets of the relative ``.md`` links in *text*."""
    base = posixpath.dirname(docs_path)
    return {
        posixpath.normpath(posixpath.join(base, target))
        for target in _LINK_RE.findall(text)
    }


def _reachable_from_door() -> set[str]:
    """Pages reached from the door, following links through working record."""
    docs = repo_root() / "docs"
    seen = {DOOR}
    queue = [DOOR]
    while queue:
        rel = queue.pop()
        text = (docs / rel).read_text(encoding="utf-8")
        for target in _links(rel, text) - seen:
            if (docs / target).is_file():
                seen.add(target)
                if is_working_record(target):
                    queue.append(target)
    return seen


def test_links_resolve_relative_to_the_linking_page():
    assert _links(
        "adr/index.md", "[a](0001-x.md) [b](archived/README.md)"
    ) == {
        "adr/0001-x.md",
        "adr/archived/README.md",
    }
    assert _links(
        "about/x.md", "[a](../adr/index.md#top) [b](https://e.org/c.md)"
    ) == {"adr/index.md"}


def test_links_with_a_title_are_followed():
    assert _links(
        "about/x.md", '[a](../adr/index.md "ADRs") [b](y.md#s "t")'
    ) == {"adr/index.md", "about/y.md"}


@pytest.mark.spec("DF-11-003")
@pytest.mark.spec("DF-11-006")
def test_every_working_record_page_is_reached_from_the_door():
    tree = classify_docs_tree(repo_root())
    working = {
        rel
        for rel in tree.pages
        if is_working_record(rel) and not UNROUTED.fullmatch(rel)
    }

    assert working, "no working-record pages classified; check is vacuous"
    orphaned = sorted(working - _reachable_from_door())

    assert orphaned == [], (
        f"working-record page(s) not reached from docs/{DOOR}; link each "
        f"from the routing page for its group (DF-11-006): {orphaned}"
    )
