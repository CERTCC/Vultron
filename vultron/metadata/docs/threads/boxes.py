"""Render the reading-path box fragments under ``docs/start/_paths/``."""

from __future__ import annotations

import html
import posixpath
from collections.abc import Mapping

from vultron.metadata.docs.landing_pages import WRITE_COMMAND
from vultron.metadata.docs.page_schema import (
    START_DIR,
    THREAD_KEY,
)
from vultron.metadata.docs.threads.check import StartThread, _entry, position
from vultron.metadata.docs.threads.listing import _link

#: ``docs/``-relative directory of the committed box fragments, one
#: subdirectory per thread (DF-11-023). Listed in ``exclude_docs``: a fragment
#: reaches a reader only through the ``include-markdown`` line its page's
#: author places.
BOX_DIR = f"{START_DIR}/_paths"


#: The tiles a box may hold, each with its direction label: a member's box
#: holds the pages before it and the pages after it (DF-11-034); a start
#: page's box holds only where the thread begins (DF-11-053).
BOX_TILES = {"previous": "Previous", "next": "Next", "begin": "Begin"}


#: Added to a tile's direction label when its set holds more than one page,
#: so the reader knows the pages are alternatives, not a sequence.
CHOOSE_SUFFIX = " — pick one"


#: The text of the link back to the thread's start page (DF-11-034).
START_LINK_TEXT = "Path overview"


#: The class every rendered box carries, beside Material's admonition
#: classes, so the built-site check can find it (DF-11-045).
BOX_CLASS = "reading-path"


#: The attributes naming the thread and the target a rendered box was made
#: for: the start page's stem, and the member's ``page`` (anchor included) or
#: the start page's path (DF-11-023).
THREAD_ATTR = "data-thread"


MEMBER_ATTR = "data-member"


#: Separators of a fragment's file name: a ``/`` of the page path, and the
#: ``#`` before a section member's anchor.
_DIR_SEP = "__"


_ANCHOR_SEP = "--"


def thread_name(thread: StartThread) -> str:
    """The thread's name: its start page's file stem (``coordinate-cases``)."""
    return posixpath.splitext(posixpath.basename(thread.path))[0]


def box_targets(thread: StartThread) -> list[str]:
    """Every page string that carries a box of *thread*, in reading order.

    The start page's path first, then each member's ``page``, with a section
    member's anchor kept: a section's box is not its page's box (DF-11-022).
    """
    return [thread.path, *(member.page for member in thread.members())]


def box_fragment_path(thread: StartThread, target: str) -> str:
    """Return the ``docs/``-relative fragment holding *target*'s box.

    ``topics/a/b.md`` gives ``start/_paths/<thread>/topics__a__b.md``, and
    ``reference/glossary.md#roles`` gives ``…/reference__glossary--roles.md``,
    so two sections of one page do not collide (DF-11-023).
    """
    path, _hash, anchor = target.partition("#")
    stem = path.removesuffix(".md").replace("/", _DIR_SEP)
    if anchor:
        stem = f"{stem}{_ANCHOR_SEP}{anchor}"
    return f"{BOX_DIR}/{thread_name(thread)}/{stem}.md"


def include_line(host: str, fragment: str) -> str:
    """The ``include-markdown`` line that places *fragment* on page *host*.

    Both are ``docs/``-relative; the included path is relative to the host
    page and starts with ``./`` or ``../``, the form ``include-markdown``
    resolves against the host page rather than the working directory.
    """
    rel = posixpath.relpath(fragment, posixpath.dirname(host) or ".")
    if not rel.startswith("../"):
        rel = f"./{rel}"
    return f'{{% include-markdown "{rel}" %}}'


def _box_marker(thread: StartThread) -> str:
    """The comment opening a fragment: where it comes from, and how to change it."""
    return (
        "<!-- GENERATED READING PATH BOX — do not edit; change "
        f"docs/{thread.path}'s {THREAD_KEY}: frontmatter, then run "
        f"`{WRITE_COMMAND}` -->"
    )


def _tile(side: str, links: list[str]) -> list[str]:
    """One tile: a direction label over its list of links (DF-11-034).

    An empty set gives an empty tile, kept so the next tile stays on the right.
    The tile is a ``md_in_html`` block, so MkDocs rewrites and validates each
    link, and the stylesheet makes a one-link tile clickable as a whole.
    """
    classes = f"{BOX_CLASS}-tile {BOX_CLASS}-{side}"
    if not links:
        return [
            f'<div class="{classes} {BOX_CLASS}-empty" aria-hidden="true"></div>'
        ]
    label = BOX_TILES[side] + (CHOOSE_SUFFIX if len(links) > 1 else "")
    return [
        f'<div class="{classes}" markdown>',
        f'<p class="{BOX_CLASS}-direction">{label}</p>',
        "",
        *(f"- {link}" for link in links),
        "",
        "</div>",
    ]


def _open_box(thread: StartThread, target: str, classes: str) -> list[str]:
    """The marker comment and the box's opening tag, naming thread and target."""
    return [
        _box_marker(thread),
        "",
        f'<div class="{classes}" '
        f'{THREAD_ATTR}="{html.escape(thread_name(thread))}" '
        f'{MEMBER_ATTR}="{html.escape(target)}" markdown>',
    ]


def _begin_box(
    thread: StartThread, fragment: str, titles: Mapping[str, str]
) -> str:
    """A start page's box: one tile, where the thread begins (DF-11-053).

    It has no title or stage line: the start page is the thread, and its own
    title already names the reader's situation. The tile links the first
    stage's entry pages: a chain's first member, or every member of a set.
    """
    first = _entry(thread.stages[0])
    lines = [
        *_open_box(thread, thread.path, f"{BOX_CLASS} {BOX_CLASS}-begin-box"),
        f'<div class="{BOX_CLASS}-tiles" markdown>',
        *_tile("begin", [_link(m, fragment, titles) for m in first]),
        "</div>",
        "",
        "</div>",
    ]
    return "\n".join(lines) + "\n"


def render_box(
    thread: StartThread, target: str, titles: Mapping[str, str]
) -> str:
    """Render *thread*'s box for *target*: its start page or a member's ``page``.

    The box is an admonition titled by the start page's situation, the same
    for every reader: no ``stakeholder_type``, no level, no script, no query
    string (DF-11-009, DF-11-035). It names the member's stage, as a page or,
    for a ``page.md#anchor`` member, a section (DF-11-022), and links back to
    the start page. Two tiles follow, the pages before and
    the pages after (DF-11-034). The tiles are HTML blocks that ``md_in_html``
    processes as Markdown, so MkDocs rewrites and validates every link in
    them; links are relative to the fragment, and ``include-markdown``
    rewrites them for the page that includes it. A start page's box is
    :func:`_begin_box` instead.

    Raises:
        ValueError: If *target* is neither the start page nor a member.
    """
    fragment = box_fragment_path(thread, target)
    if target == thread.path:
        return _begin_box(thread, fragment, titles)
    member = next((m for m in thread.members() if m.page == target), None)
    where = position(thread, member.path) if member else None
    if member is None or where is None:
        raise ValueError(
            f"{target} is not on the thread of docs/{thread.path}"
        )
    unit = "section" if "#" in member.page else "page"
    start_href = posixpath.relpath(thread.path, posixpath.dirname(fragment))
    where_line = [
        f'<div class="{BOX_CLASS}-where" markdown>',
        f"This {unit} is part of *{where.stage.title}*.",
        "",
        f'<p class="{BOX_CLASS}-start" markdown>'
        f"[{START_LINK_TEXT}]({start_href})</p>",
        "</div>",
        "",
    ]
    before = [_link(m, fragment, titles) for m in where.before]
    after = [_link(m, fragment, titles) for m in where.after]
    lines = [
        *_open_box(thread, target, f"admonition abstract {BOX_CLASS}"),
        '<p class="admonition-title">Reading path: '
        f"{html.escape(thread.title)}</p>",
        "",
        *where_line,
        f'<div class="{BOX_CLASS}-tiles" markdown>',
        *_tile("previous", before),
        *_tile("next", after),
        "</div>",
        "",
        "</div>",
    ]
    return "\n".join(lines) + "\n"


def render_boxes(
    threads: tuple[StartThread, ...], titles: Mapping[str, str]
) -> dict[str, str]:
    """Return ``{docs/-relative fragment path: box}`` for every thread target.

    Raises:
        ValueError: If two targets of one thread would share a fragment name.
    """
    boxes: dict[str, str] = {}
    owner: dict[str, str] = {}
    for thread in threads:
        for target in box_targets(thread):
            fragment = box_fragment_path(thread, target)
            if fragment in owner:
                raise ValueError(
                    f"docs/{thread.path}: {owner[fragment]} and {target} "
                    f"would share the box fragment docs/{fragment}"
                )
            owner[fragment] = target
            boxes[fragment] = render_box(thread, target, titles)
    return boxes
