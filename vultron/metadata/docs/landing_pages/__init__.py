"""Generate or check the contents of every ``index.md`` that opens a nav group.

Requirements: specs/diataxis-requirements.yaml DF-11-005 (generated, check
gated, never hand-maintained), DF-11-028 (the two exempt shapes), DF-11-029 (a
routing page links every member), DF-09-009 (an empty target set fails),
DF-11-004 (a level is never rendered). Design rationale:
``notes/site-information-architecture.md`` § "Landing pages are generated,
never hand-maintained" and § "An ``index.md`` is a routing surface"
(ADR-0102, #3617).

Every section landing page used to be a hand-written copy of the navigation,
and every one had drifted from it. So the listing is derived from two
machine-readable sources instead:

* **the ``mkdocs.yml`` nav**, which says what a section contains and supplies
  each entry's label and its fallback order;
* **each listed page's frontmatter**, which supplies an optional
  ``description:`` shown beside the link and an optional ``level`` that sorts
  the listing (DF-11-001).

Only the text between :data:`BEGIN_MARKER` and :data:`END_MARKER` is
generated. The prerequisites admonition, the section's framing, and any
cross-section pointers are hand-written prose and survive regeneration.

A section index is the ``index.md`` a nav group opens with, at any depth. Each
one declares in its frontmatter which of three shapes it is (:class:`Contents`),
and the declaration is required: an index that opens a group without one is a
fault, so no sub-section can be left undecided by omission.

* ``contents: generated`` — the page enumerates its group; the listing between
  the markers is generated and ``--check`` fails when it is stale.
* ``contents: routing`` — the page links its group's members inside framing
  prose or a themed grouping that is editorial content. Nothing is generated;
  ``--check`` fails when the page fails to link a member (DF-11-029's
  routing-page exemption). The members it must link are the group's nav
  members plus any reader page in its own directory the nav does not carry
  (DF-11-006's routing-page pattern), so a page added to the directory without
  a link is caught.
* ``contents: rendered`` — the enumeration is rendered at build time from a
  registry (DEMOCI-11-009), so nothing is committed to drift. The generator
  records the page and leaves it alone.

Submodules, by concern: ``model`` (markers, ``contents:`` kinds and the
page models), ``nav`` (reading nav items) and ``sections`` (discovering
section indexes, checking routing indexes and rendering listings).
"""

from vultron.metadata.docs.landing_pages.model import (
    BEGIN_MARKER,
    CONTENTS_KEY,
    END_MARKER,
    WRITE_COMMAND,
    Entry,
    LandingPage,
)
from vultron.metadata.docs.landing_pages.nav import (
    group_landing,
    is_url,
    nav_entry,
    page_title,
    sort_entries,
    split_nav_item,
    unreadable_nav_item,
)
from vultron.metadata.docs.landing_pages.sections import (
    discover_landing_pages,
    discover_section_indexes,
    linked_pages,
    render_listing,
    routing_faults,
    splice_listing,
)

__all__ = [
    "BEGIN_MARKER",
    "CONTENTS_KEY",
    "END_MARKER",
    "Entry",
    "LandingPage",
    "WRITE_COMMAND",
    "discover_landing_pages",
    "discover_section_indexes",
    "group_landing",
    "is_url",
    "linked_pages",
    "nav_entry",
    "page_title",
    "render_listing",
    "routing_faults",
    "sort_entries",
    "splice_listing",
    "split_nav_item",
    "unreadable_nav_item",
]
