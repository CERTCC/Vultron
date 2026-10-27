"""The lookup-page files every throwaway ``docs-site`` checkout needs (DF-11-021).

``uv run docs-site`` refuses a tree with no lookup page, no reference page to
list on it, or a home page or start page that does not link it, just as it
refuses one with no generated landing page. A test tree built for another
artifact adds :data:`LOOKUP_FILES` and :data:`LOOKUP_NAV` through
:func:`with_lookup`, and a start page carries :data:`LOOKUP_LINK`.
"""

from __future__ import annotations

from vultron.metadata.docs.lookup_page import (
    BEGIN_MARKER,
    END_MARKER,
    HOME_PATH,
    LOOKUP_PATH,
)

#: The link a start page (one directory down) writes to the lookup page.
LOOKUP_LINK = f"[Look Something Up](../{LOOKUP_PATH})"

#: The one reference page the lookup page lists. It sits in a directory of its
#: own, so it shares no directory with the test's pages.
REF_PAGE = "lookup-ref/ref.md"

#: ``docs/``-relative files: the home page, the lookup page, one reference page.
#: Only the reference page is in the nav: a home page carried by the nav would
#: become the routing door to every page beside it the test leaves out of the
#: nav (DF-11-006), and ``docs-site`` reads neither page through the nav.
LOOKUP_FILES: dict[str, str] = {
    HOME_PATH: f"# Home\n\n[Look Something Up]({LOOKUP_PATH})\n",
    LOOKUP_PATH: f"# Look Something Up\n\n{BEGIN_MARKER}\n\n{END_MARKER}\n",
    REF_PAGE: (
        "---\npage_type: reference\ndescription: A table.\n---\n\n# Ref\n"
    ),
}

#: The nav entry carrying :data:`REF_PAGE`.
LOOKUP_NAV: list[object] = [{"Ref": REF_PAGE}]


def with_lookup(
    files: dict[str, str], nav: list[object]
) -> tuple[dict[str, str], list[object]]:
    """*files* and *nav* with the lookup files added; *files* wins a clash."""
    return {**LOOKUP_FILES, **files}, [*nav, *LOOKUP_NAV]
