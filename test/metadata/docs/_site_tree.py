"""The one builder of a throwaway ``docs-site`` checkout (#5693).

``uv run docs-site`` refuses a tree that lacks any input one of its generated
artifacts reads: the lookup page and its hosts (DF-11-021), a story page
(TRACE-03-003), a ``protocol`` or ``foundation`` requirement for the known-gaps
fragment (DF-12-019), and the drafts register with the Revision Log that
includes its status tables (DOCBW-08-004). :func:`site_tree` seeds each group,
so a test built for one artifact gets a tree the others accept, and a new
artifact's seed is added here once, not in every module that builds a tree.

Each seed group can be suppressed, for a test that must resolve no pages at
all (DF-09-009). The seeds themselves live in ``_lookup_tree.py``,
``_story_tree.py``, ``_spec_tree.py`` and ``_drafts_tree.py``.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from ._drafts_tree import with_drafts
from ._lookup_tree import with_lookup
from ._spec_tree import write_seed_specs
from ._story_tree import with_stories


def site_tree(
    tmp_path: Path,
    files: dict[str, str] | None = None,
    nav: list[object] | None = None,
    *,
    lookup: bool = True,
    stories: bool = True,
    specs: bool = True,
    drafts: bool = True,
    config: dict[str, object] | None = None,
) -> Path:
    """Write a checkout under *tmp_path* and return it.

    Args:
        tmp_path: The checkout's root.
        files: ``docs/``-relative files; each wins a clash with a seed.
        nav: The ``mkdocs.yml`` nav; the lookup seed's entry is appended.
        lookup: Seed the lookup page, its hosts and its reference page.
        stories: Seed one user-story page.
        specs: Seed one requirement file, unless the tree already has one.
        drafts: Seed the drafts register and the Revision Log.
        config: Other ``mkdocs.yml`` keys, such as ``not_in_nav``.
    """
    files = dict(files or {})
    nav = list(nav or [])
    if stories:
        files = with_stories(files)
    if lookup:
        files, nav = with_lookup(files, nav)
    if drafts:
        files = with_drafts(files)
    (tmp_path / "mkdocs.yml").write_text(
        yaml.safe_dump({"nav": nav, **(config or {})})
    )
    for rel, text in files.items():
        path = tmp_path / "docs" / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    if specs:
        write_seed_specs(tmp_path)
    return tmp_path
