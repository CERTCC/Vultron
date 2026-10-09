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
becomes a bare ``#fragment`` link, whether it is an inline link, an image or
a reference definition, at any indent (an admonition body is indented). Left
unchanged:

- a link to a section page without a fragment: it names a page, not a
  section, and the page has no in-page counterpart;
- a link to ``index.md``, the routing page, which ``full.md`` does not include;
- a link to any page outside the section (its target holds a ``/``);
- a link shown inside a fenced code block or an inline code span (an
  escaped backtick, ``\\` ``, opens no code span);
- a raw-HTML ``<a href>``, which is not a Markdown link;
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


# A same-directory page with a fragment: ``page.md#fragment``, optionally
# ``./``-prefixed. The page name has no ``/``, so only a page in the same
# directory as ``full.md`` matches. Each link form names its own groups.
def _target(form: str) -> str:
    return (
        rf"(?:\./)?(?P<{form}_page>[A-Za-z0-9_.-]+\.md)"
        rf"#(?P<{form}_fragment>[^)>\s\"']+)"
    )


_TITLE = r"""(?:\s+(?:"[^"\n]*"|'[^'\n]*'|\([^)\n]*\)))?"""

# One pass over the page. Code is matched first and kept verbatim, so a link
# shown inside a fenced block or an inline code span is never rewritten. An
# escaped backtick is kept verbatim too, so it cannot open a code span. A code
# span opens on a whole run of backticks (no backtick before or after it), so
# an unclosed run is tried once and cannot backtrack tick by tick. A link
# is either inline, ``](target "title")`` with the target optionally in angle
# brackets, or a reference definition, ``[label]: target "title"``.
_TOKEN = re.compile(
    r"(?P<code>"
    r"^[ \t]*(?P<fence>`{3,}|~{3,})[^\n]*\n[\s\S]*?^[ \t]*(?P=fence)[ \t]*$"
    r"|\\`"
    r"|(?<!`)(?P<ticks>`+)(?!`)(?:(?!(?P=ticks)).)+?(?P=ticks)"
    r")"
    rf"|\]\(<?{_target('inline')}(?P<inline_rest>>?{_TITLE}\))"
    rf"|(?P<definition_head>^[ \t]*\[[^\]\n]+\]:[ \t]*)<?"
    rf"{_target('definition')}(?P<definition_rest>>?{_TITLE}[ \t]*$)",
    re.MULTILINE,
)


def _in_page(match: re.Match[str]) -> str:
    if match["code"] is not None:
        return match[0]
    form = "inline" if match["inline_page"] is not None else "definition"
    if match[f"{form}_page"] == _INDEX_PAGE:
        return match[0]
    # Angle brackets go with the page: ``<layers.md#x>`` becomes ``#x``.
    fragment = "#" + match[f"{form}_fragment"]
    rest = match[f"{form}_rest"].removeprefix(">")
    if form == "inline":
        return f"]({fragment}{rest}"
    return f"{match['definition_head']}{fragment}{rest}"


def rewrite_section_links(markdown: str) -> str:
    """Return *markdown* with each same-section ``page.md#fragment`` link
    rewritten to ``#fragment``.

    Inline links, images and reference definitions are rewritten. Links to
    ``index.md``, links without a fragment, links into another directory and
    anything inside a fenced code block or an inline code span are returned
    unchanged. A raw-HTML ``<a href>`` is not a Markdown link and is not
    rewritten.
    """
    return _TOKEN.sub(_in_page, markdown)


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
