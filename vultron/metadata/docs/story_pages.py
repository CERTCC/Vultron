#  Copyright (c) 2026 Carnegie Mellon University and Contributors.
#  - see Contributors.md for a full list of Contributors
#  - see ContributionInstructions.md for information on how you can Contribute to this project
#  Vultron Multiparty Coordinated Vulnerability Disclosure Protocol Prototype is
#  licensed under a MIT (SEI)-style license, please see LICENSE.md distributed
#  with this Software or contact permission@sei.cmu.edu for full terms.
#  Created, in part, with funding and support from the United States Government
#  (see Acknowledgments file). This program may include and/or can make use of
#  certain third party source code, object code, documentation and other files
#  ("Third Party Software"). See LICENSE.md for more details.
#  Carnegie Mellon®, CERT® and CERT Coordination Center® are registered in the
#  U.S. Patent and Trademark Office by Carnegie Mellon University
"""The user-story page catalog: which story IDs have a page (TRACE-03-001).

A requirement names the stories that motivated it in its ``stories:`` field
(SR-11-001, ADR-0072). The field holds IDs, not paths, so nothing in the
registry can tell whether a cited story exists; only the page set under
``docs/reference/user_stories/`` can. This module is that page set, and it is
read by both sides of the story graph:

* ``spec-lint`` hard-errors on a ``stories:`` entry whose page is absent
  (TRACE-03-001), which until #4506 was pattern-checked only (SR-11-002), so a
  typo was a silent broken edge;
* the generated index table and traceability matrix
  (:mod:`~vultron.metadata.docs.story_coverage`) enumerate the catalog, so a
  page no requirement cites is still listed, flagged (TRACE-01-002).

It holds no registry import on purpose: a page is a page whether or not any
requirement cites it, and the linter reaches the catalog without reaching the
docs renderers.
"""

from __future__ import annotations

import re
from pathlib import Path

from vultron.metadata.file_loading import MetadataLoadError
from vultron.metadata.specs.schema import STORY_ID_PATTERN

#: ``docs/``-relative directory holding the story pages and their index.
STORY_DIR = "reference/user_stories"

#: Repository-relative directory holding the story pages.
STORY_ROOT = f"docs/{STORY_DIR}"

#: A story page's file stem is its ID. Compiled from the one definition of
#: that shape, so this scanner cannot disagree with ``StoryIdStr`` about which
#: filenames are stories (SR-11-002).
STORY_ID_RE = re.compile(STORY_ID_PATTERN)

#: The markers around a story page's text. The generated table and matrix
#: quote what lies between them, so every page carries each exactly once.
STORY_START = "<!-- story-start -->"
STORY_END = "<!-- story-end -->"


def story_page(story_id: str) -> str:
    """Return the ``STORY_DIR``-relative page name of *story_id*."""
    return f"{story_id}.md"


def story_ids(root: Path) -> tuple[str, ...]:
    """Return every story ID with a page under *root*, sorted.

    A file in the directory whose stem is not a story ID — the ``index.md``,
    the generated ``table.md`` and ``traceability.md`` — is not a story.

    Raises:
        MetadataLoadError: If the directory is absent or holds no story page.
            An empty target set is a failure, not a pass (DF-09-009): a
            catalog that resolved nothing would silently excuse every
            ``stories:`` entry in the corpus.
    """
    directory = root / STORY_ROOT
    if not directory.is_dir():
        raise MetadataLoadError(
            "the user-story catalog directory is missing; every `stories:` "
            "entry in specs/ names a page in it (TRACE-03-001)",
            path=STORY_ROOT,
        )
    found = tuple(
        sorted(
            path.stem
            for path in directory.glob("*.md")
            if STORY_ID_RE.fullmatch(path.stem)
        )
    )
    if not found:
        raise MetadataLoadError(
            "resolved no story pages; an empty catalog is a failure, not a "
            "pass (DF-09-009)",
            path=STORY_ROOT,
        )
    return found


def story_catalog(root: Path) -> frozenset[str]:
    """The catalog as a set, for a reader that compares two trees.

    Raises:
        MetadataLoadError: As :func:`story_ids` documents.
    """
    return frozenset(story_ids(root))


__all__ = [
    "STORY_DIR",
    "STORY_END",
    "STORY_ID_RE",
    "STORY_ROOT",
    "STORY_START",
    "story_catalog",
    "story_ids",
    "story_page",
]
