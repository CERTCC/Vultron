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
from vultron.metadata.docs.threads.listing import _link, _link_text

#: ``docs/``-relative directory of the committed box fragments, one
#: subdirectory per thread (DF-11-023). Listed in ``exclude_docs``: a fragment
#: reaches a reader only through the ``include-markdown`` line its page's
#: author places.
BOX_DIR = f"{START_DIR}/_paths"


#: Shown in a box cell whose set is empty: the first page has no previous
#: set, the last no next set, and a start page no previous set (DF-11-034).
EMPTY_CELL = "---"


#: The box's column headings, in order (DF-11-015).
BOX_COLUMNS = ("Start", "Previous", "Current", "Next")


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


def _text_cell(text: str) -> list[str]:
    return ["", f"- {_link_text(text)}", ""]


def _link_cell(links: list[str]) -> list[str]:
    return ["", *(f"- {link}" for link in links), ""]


def _cell(body: list[str] | None) -> str:
    """One ``<td>``: Markdown-processed when it holds a list (``md_in_html``)."""
    if body is None:
        return f"<td>{EMPTY_CELL}</td>"
    return "\n".join(['<td markdown="block">', *body, "</td>"])


def render_box(
    thread: StartThread, target: str, titles: Mapping[str, str]
) -> str:
    """Render *thread*'s box for *target*: its start page or a member's ``page``.

    The box is an admonition titled by the start page's situation, the same
    for every reader: no ``stakeholder_type``, no level, no script, no query
    string (DF-11-009, DF-11-035). A member's box names its stage, as a page
    or, for a ``page.md#anchor`` member, a section (DF-11-022); a start page's
    names none. The table is HTML whose cells ``md_in_html`` processes as
    Markdown, so MkDocs rewrites and validates every link in it; links are
    relative to the fragment, and ``include-markdown`` rewrites them for the
    page that includes it.

    Raises:
        ValueError: If *target* is neither the start page nor a member.
    """
    fragment = box_fragment_path(thread, target)
    start_href = posixpath.relpath(thread.path, posixpath.dirname(fragment))
    start_link = f"[{_link_text(thread.title)}]({start_href})"
    if target == thread.path:
        stage_line: list[str] = []
        start = _text_cell(thread.title)
        before: list[str] | None = None
        current = _text_cell(thread.title)
        after_members = _entry(thread.stages[0]) if thread.stages else ()
    else:
        member = next((m for m in thread.members() if m.page == target), None)
        where = position(thread, member.path) if member else None
        if member is None or where is None:
            raise ValueError(
                f"{target} is not on the thread of docs/{thread.path}"
            )
        unit = "section" if "#" in member.page else "page"
        stage_line = [f"This {unit} is part of *{where.stage.title}*.", ""]
        start = _link_cell([start_link])
        before = (
            _link_cell([_link(m, fragment, titles) for m in where.before])
            if where.before
            else None
        )
        current = _text_cell(member.label or titles[member.path])
        after_members = where.after
    after = (
        _link_cell([_link(m, fragment, titles) for m in after_members])
        if after_members
        else None
    )
    headings = "".join(f"<th>{name}</th>" for name in BOX_COLUMNS)
    lines = [
        _box_marker(thread),
        "",
        f'<div class="admonition abstract {BOX_CLASS}" '
        f'{THREAD_ATTR}="{html.escape(thread_name(thread))}" '
        f'{MEMBER_ATTR}="{html.escape(target)}" markdown>',
        '<p class="admonition-title">Reading path: '
        f"{html.escape(thread.title)}</p>",
        "",
        *stage_line,
        f'<table class="{BOX_CLASS}-table" markdown>',
        f"<thead><tr>{headings}</tr></thead>",
        "<tbody markdown>",
        "<tr markdown>",
        *(_cell(body) for body in (start, before, current, after)),
        "</tr>",
        "</tbody>",
        "</table>",
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
