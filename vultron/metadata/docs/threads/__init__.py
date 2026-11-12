"""Reading-path threads: load, check, and render them at both ends.

Requirements: specs/diataxis-requirements.yaml DF-11-013 (a thread is staged
data on its start page), DF-11-014 (the start page's listing is generated and
check gated), DF-11-015 (each member page shows a box per thread: a link
back to the start page and previous and next tiles), DF-11-016
(the thread check), DF-11-022 (a section member's box names the section),
DF-11-023 (each box is a committed fragment), DF-11-044 (placed by hand),
DF-11-034 (the link and the tiles), DF-11-009 (titled by situation, never by
``stakeholder_type``), DF-09-009 (an empty target set fails). Design rationale:
``notes/site-information-architecture.md`` § "Threads: staged data, rendered at
both ends" (ADR-0150).

A thread is a partial order, not a sequence. It lives in one place, the
``thread:`` frontmatter of the start page that opens it
(:class:`~vultron.metadata.docs.page_schema.ThreadDeclaration`), and is shown
in two:

* on the **start page**, as the listing between :data:`LISTING_BEGIN` and
  :data:`LISTING_END`, which ``uv run docs-site --write`` splices in
  (:mod:`~vultron.metadata.docs.site_sync`) — a stage is a section, a chain a
  numbered list, a set a bulleted one;
* on each **member page**, as a box per thread: a committed fragment under
  :data:`BOX_DIR` that ``docs-site --write`` generates (:func:`render_boxes`)
  and the page's author places with an ``include-markdown`` line. It links
  back to the start page and holds a tile of the pages before the page and a
  tile of the pages after it, both sets (:func:`position`).
  That every page renders its boxes is the built-site check
  (:mod:`~vultron.metadata.docs.path_boxes`).

``uv run docs-threads`` is the thread check (DF-11-016), a pre-commit hook
with ``test_the_committed_threads_pass`` as its CI backstop. That no member
runs ahead of its thread is ``docs-thread-order``'s check
(:mod:`~vultron.metadata.docs.thread_order`, DF-11-024).

Submodules, by concern: ``check`` (loading and checking the threads, and
the CLI), ``listing`` (the start-page listing) and ``boxes`` (the
reading-path box fragments).
"""

from vultron.metadata.docs.threads.boxes import (
    BOX_CLASS,
    BOX_DIR,
    BOX_TILES,
    CHOOSE_SUFFIX,
    MEMBER_ATTR,
    START_LINK_TEXT,
    THREAD_ATTR,
    box_fragment_path,
    box_targets,
    include_line,
    render_box,
    render_boxes,
    thread_name,
)
from vultron.metadata.docs.threads.check import (
    StartThread,
    check_threads,
    load_threads,
    main,
    position,
)
from vultron.metadata.docs.threads.listing import (
    LISTING_BEGIN,
    LISTING_END,
    STOPPING_POINT,
    page_titles,
    render_listing,
    splice_thread_listing,
)

__all__ = [
    "BOX_CLASS",
    "BOX_DIR",
    "BOX_TILES",
    "CHOOSE_SUFFIX",
    "START_LINK_TEXT",
    "LISTING_BEGIN",
    "LISTING_END",
    "MEMBER_ATTR",
    "STOPPING_POINT",
    "StartThread",
    "THREAD_ATTR",
    "box_fragment_path",
    "box_targets",
    "check_threads",
    "include_line",
    "load_threads",
    "main",
    "page_titles",
    "position",
    "render_box",
    "render_boxes",
    "render_listing",
    "splice_thread_listing",
    "thread_name",
]
