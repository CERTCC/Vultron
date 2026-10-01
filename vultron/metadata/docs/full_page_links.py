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
"""MkDocs hook: keep cross-references on the single-page spec edition in-page.

The Protocol Specification under ``docs/reference/vultron-spec/`` is assembled
from single-sourced ``_*.md`` fragments. Each body page, each annex page and
``open-questions.md`` includes a run of them, and ``full.md`` includes them
all. A cross-reference inside a fragment targets the page that owns the
section, with the heading anchor
(``tracking-models.md#6-report-management-rm-state-machine-n``), so it is valid
on every page that renders the fragment (#4062). On ``full.md`` that link left
the page, although the section it names is further up or down the same page
(#4089).

This ``on_page_markdown`` hook rewrites those links on ``full.md`` only. A
Markdown link whose target is another page of the section, *with* a fragment,
becomes a bare ``#fragment`` link. Left unchanged:

- a link to a section page without a fragment: it names a page, not a
  section, and the page has no in-page counterpart;
- a link to ``index.md``, the routing page, which ``full.md`` does not include;
- a link to any page outside the section (its target holds a ``/``);
- every page other than ``full.md``, so no part page renders differently.

The hook runs after ``include-markdown`` has assembled the page:
``include-markdown`` registers its ``on_page_markdown`` at priority 100 and
this hook at :data:`_PRIORITY`, below it. By then ``include-markdown`` has
rewritten each fragment's relative link against ``full.md``, so a link written
``../conformance.md#…`` in ``_conformance/`` arrives as ``conformance.md#…``.
No fragment is edited.

The rewrite is correct only because every heading id is the same on ``full.md``
as on the page that owns the heading. ``heading-offset`` changes an annex
heading's level and not its text, so not its id, and the assembled page has no
duplicate heading (a duplicate would gain a ``_1`` suffix and the bare link
would land on the first copy). A rewritten link to an id ``full.md`` lacks is a
dead in-page anchor, which ``mkdocs build --strict`` fails on
(``validation.links.anchors: warn``, DOCBW-03-011);
``test/metadata/docs/test_full_page_links.py`` also checks the built page.

Registered under ``hooks:`` in ``mkdocs.yml``. MkDocs loads a hook by file
path, so this module imports only the standard library and MkDocs itself.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from mkdocs.plugins import event_priority

if TYPE_CHECKING:
    from mkdocs.config.defaults import MkDocsConfig
    from mkdocs.structure.files import Files
    from mkdocs.structure.pages import Page

FULL_PAGE_SRC_URI = "reference/vultron-spec/full.md"
"""The single-page edition, the only page this hook changes."""

_INDEX_PAGE = "index.md"

_PRIORITY = -50
"""Below ``include-markdown``'s 100, so the page is already assembled."""

# An inline link target: ``](page.md#fragment)``, optionally ``./``-prefixed
# and optionally followed by a title. The page name has no ``/``, so only a
# page in the same directory as ``full.md`` matches.
_SECTION_LINK = re.compile(
    r"\]\((?:\./)?(?P<page>[A-Za-z0-9_.-]+\.md)#(?P<fragment>[^)\s]+)"
    r"(?P<rest>(?:\s+\"[^\"]*\")?\))"
)


def _in_page(match: re.Match[str]) -> str:
    if match["page"] == _INDEX_PAGE:
        return match[0]
    return f"](#{match['fragment']}{match['rest']}"


def rewrite_section_links(markdown: str) -> str:
    """Return *markdown* with each same-section ``page.md#fragment`` link
    rewritten to ``#fragment``.

    Links to ``index.md``, links without a fragment and links into another
    directory are returned unchanged.
    """
    return _SECTION_LINK.sub(_in_page, markdown)


@event_priority(_PRIORITY)
def on_page_markdown(
    markdown: str, *, page: Page, config: MkDocsConfig, files: Files
) -> str:
    """Rewrite same-section cross-references on ``full.md``; leave every
    other page unchanged."""
    if page.file.src_uri != FULL_PAGE_SRC_URI:
        return markdown
    return rewrite_section_links(markdown)


__all__ = ["FULL_PAGE_SRC_URI", "on_page_markdown", "rewrite_section_links"]
