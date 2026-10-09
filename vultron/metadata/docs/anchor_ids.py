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
"""MkDocs hook: register every ``id`` in a page's rendered HTML as an anchor.

MkDocs validates a ``page.md#fragment`` link against the target page's
``present_anchor_ids``, which it fills from two places while rendering: a
treeprocessor that reads ``id`` attributes off the parent Markdown element
tree, and a preprocessor that scans the page's *source* for raw-HTML
``id=``/``<a name=>``. Neither sees inside a ``markdown-exec`` block. The
block's output reaches the parent as a stashed HTML placeholder, and
``markdown-exec`` reports only its *headings* back (its ``InsertHeadings``
treeprocessor), so a heading printed from an exec block is a valid target and
an ``<a id="mv-03-002">`` printed beside it is not — even though the built
HTML carries it and a browser scrolls to it. Under ``validation.links.anchors:
warn`` (DOCBW-03-011) a strict build then fails on a link that works, which is
how every requirement citation in ``docs/`` came to point at its group heading
instead of the requirement (#3243, #3735).

The fix is an ``on_page_content`` hook. It runs as each page renders, after
``markdown-exec`` has spliced its output into the page HTML, and adds every id
it finds to ``page.present_anchor_ids``. MkDocs populates every page before it
validates any anchor (``mkdocs.commands.build``: the ``_populate_page`` loop
finishes before the ``validate_anchor_links`` loop starts), so the ids are in
place in time. A fabricated anchor still fails: the id has to be in the HTML.

The collection rule matches MkDocs' own raw-HTML collector
(``mkdocs.structure.pages._HTMLHandler``): an ``id`` attribute on any tag, a
``name`` attribute on ``<a>`` only. Keeping the two rules identical is what
lets this hook widen the set without ever disagreeing with the collector it
extends.

What this hook does **not** do: validate links that an exec block *prints*.
MkDocs never parses those as Markdown links, so they are neither rewritten nor
checked, and the DOCBW-03-007 ``docs-links`` gate strips fragments by design
(#3634). A generator that emits ``#fragment`` links needs its own test that
each fragment exists on its target page; for the spec pages that is
``test_render_for_kind_cross_links_resolve`` over the ``_cross_link`` "Related"
column (``test/metadata/specs/test_docs_render.py``).

Registered under ``hooks:`` in ``mkdocs.yml``. MkDocs loads a hook by file
path, so this module imports only the standard library and MkDocs itself.
"""

from __future__ import annotations

from html.parser import HTMLParser
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mkdocs.config.defaults import MkDocsConfig
    from mkdocs.structure.files import Files
    from mkdocs.structure.pages import Page


class _AnchorIdCollector(HTMLParser):
    """Collect anchor targets the way ``mkdocs.structure.pages._HTMLHandler`` does.

    An ``id`` counts on any tag; a ``name`` counts on ``<a>`` only, because a
    browser scrolls to ``<a name="x">`` but not to ``<div name="x">``. Empty
    values are dropped: ``id=""`` is not a target a link can name.
    """

    def __init__(self) -> None:
        super().__init__()
        self.anchor_ids: set[str] = set()

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        for key, value in attrs:
            if not value:
                continue
            if key == "id" or (key == "name" and tag == "a"):
                self.anchor_ids.add(value)


def anchor_ids_in(html: str) -> frozenset[str]:
    """Return every anchor target in *html*: any ``id``, plus ``<a name>``."""
    collector = _AnchorIdCollector()
    collector.feed(html)
    collector.close()
    return frozenset(collector.anchor_ids)


def on_page_content(
    html: str, *, page: Page, config: MkDocsConfig, files: Files
) -> str:
    """Add every anchor target in the rendered *html* to the page.

    ``present_anchor_ids`` is ``None`` when anchor validation is off (or the
    page was not rendered); the page is then left alone. Otherwise the ids are
    *added* to the set MkDocs already collected, never substituted for it. The
    HTML is returned unchanged: this hook registers targets, it does not
    rewrite content.
    """
    present = page.present_anchor_ids
    if present is None:
        return html
    present.update(anchor_ids_in(html))
    return html


__all__ = ["anchor_ids_in", "on_page_content"]
