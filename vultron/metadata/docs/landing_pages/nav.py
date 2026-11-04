"""Read nav items: titles, page facts, group landings and listing entries."""

from __future__ import annotations

import posixpath
from pathlib import Path
from urllib.parse import urlsplit

import frontmatter

from vultron.metadata.docs.landing_pages.model import (
    _ATTR_LIST_RE,
    _H1_RE,
    _INDEX_NAME,
    CONTENTS_KEY,
    WRITE_COMMAND,
    Contents,
    Entry,
    _PageFacts,
)
from vultron.metadata.docs.page_schema import LEVELS
from vultron.metadata.file_loading import MetadataLoadError, load_frontmatter
from vultron.metadata.markdown_tables import fenced_lines


def is_url(target: str) -> bool:
    """True for any target with a URI scheme (``https:``, ``mailto:``...)."""
    return bool(urlsplit(target).scheme)


def _body_h1(body: str) -> str | None:
    """The first H1 of a page body, outside fenced code, without attr lists.

    Fenced lines come from :func:`fenced_lines`, the one fence reader
    (CS-22-001): it honours run length and fence character, so a shorter run
    or the other character inside a longer block does not end it, and it
    tracks a fence nested under an admonition, where a ``# comment`` inside a
    shell block would otherwise be taken for the page's heading.
    """
    fenced = fenced_lines(body)
    for number, line in enumerate(body.splitlines(), start=1):
        if number in fenced:
            continue
        match = _H1_RE.match(line)
        if match:
            return _ATTR_LIST_RE.sub("", match.group(1)).strip() or None
    return None


def page_title(post: frontmatter.Post, rel: str) -> str:
    """The title mkdocs shows for the page at *rel*, whitespace-folded.

    Frontmatter ``title:``, else the body's first H1, else the file stem.
    """
    title = post.metadata.get("title")
    if not isinstance(title, str) or not title.strip():
        title = _body_h1(post.content) or Path(rel).stem
    return " ".join(title.split())


def _page_facts(docs_dir: Path, rel: str, root: Path) -> _PageFacts:
    """Read a page's title and the ``description``, ``level`` and ``contents``
    it declares.

    The title follows mkdocs (:func:`page_title`).

    A level off the ladder is treated as undeclared: ``docs-frontmatter``
    already reports it against the page, and failing here too would name one
    fault from two tools.

    Raises:
        MetadataLoadError: If the page is missing, or ``description`` is
            present but not a non-blank string.
    """
    path = docs_dir / rel
    if not path.is_file():
        raise MetadataLoadError(
            "is listed in the mkdocs.yml nav but does not exist",
            path=f"docs/{rel}",
        )
    if (
        posixpath.basename(rel) == _INDEX_NAME
        and not path.read_text(encoding="utf-8").strip()
    ):
        raise MetadataLoadError(
            "is empty; an index page's hand-written prose cannot be "
            f"regenerated. Restore the file, then run '{WRITE_COMMAND}'.",
            path=f"docs/{rel}",
        )
    post = load_frontmatter(path, root=root)
    metadata = post.metadata
    raw = metadata.get("description")
    description: str | None = None
    if raw is not None:
        if not isinstance(raw, str) or not raw.strip():
            raise MetadataLoadError(
                "description: must be a non-blank string when present",
                path=f"docs/{rel}",
            )
        description = " ".join(raw.split())
    level = metadata.get("level")
    contents = metadata.get(CONTENTS_KEY)
    return _PageFacts(
        title=page_title(post, rel),
        description=description,
        level=level if type(level) is int and level in LEVELS else None,
        contents=contents if isinstance(contents, str) else None,
    )


def split_nav_item(item: object) -> tuple[str | None, object]:
    """Return ``(label, value)`` for one nav item; bare paths have no label."""
    if isinstance(item, dict) and len(item) == 1:
        ((label, value),) = item.items()
        return str(label), value
    return None, item


def group_landing(items: list[object]) -> str | None:
    """The ``index.md`` a nav group opens with, which becomes its link."""
    if not items:
        return None
    _label, value = split_nav_item(items[0])
    if isinstance(value, str) and posixpath.basename(value) == _INDEX_NAME:
        return value
    return None


def sort_entries(entries: list[Entry]) -> tuple[Entry, ...]:
    """Order entries by level, keeping nav order wherever levels are absent.

    Each entry without a level stays attached to the nearest declared entry
    before it in nav order; entries before any declared one lead. The runs so
    formed are sorted stably by their leader's level. So a listing in which no
    page declares a level keeps nav order exactly, one in which every page does
    is sorted by level, and a partly declared listing moves only as far as its
    declarations say (#3527 AC-1).
    """
    runs: list[tuple[int, list[Entry]]] = [(0, [])]
    for entry in entries:
        if entry.level is None:
            runs[-1][1].append(entry)
        else:
            runs.append((entry.level, [entry]))
    ordered = sorted(runs, key=lambda run: run[0])
    return tuple(entry for _level, run in ordered for entry in run)


def unreadable_nav_item(item: object) -> MetadataLoadError:
    """The error for a nav *item* of a shape mkdocs cannot read.

    One builder, so every nav reader names the fault the same way
    (CS-22-001).
    """
    return MetadataLoadError(
        f"has a nav item this generator cannot read: {item!r}",
        path="mkdocs.yml",
    )


def nav_entry(item: object, docs_dir: Path, root: Path) -> Entry:
    """The listing entry for one nav *item*.

    A page links itself; a group that opens with an ``index.md`` links that
    index, under the group's label and with the index's description; a group
    without one becomes an unlinked entry holding its members.

    Raises:
        MetadataLoadError: If a listed page is missing or unreadable, or the
            item is a shape this generator cannot read.
    """
    label, value = split_nav_item(item)
    if isinstance(value, str):
        if is_url(value):
            return Entry(label=label or value, target=value)
        facts = _page_facts(docs_dir, value, root)
        return Entry(
            label=label or facts.title,
            target=value,
            description=facts.description,
            level=facts.level,
        )
    if not isinstance(value, list) or label is None:
        raise unreadable_nav_item(item)
    landing = group_landing(value)
    if landing is not None:
        facts = _page_facts(docs_dir, landing, root)
        return Entry(
            label=label,
            target=landing,
            description=facts.description,
            level=facts.level,
        )
    children = sort_entries([nav_entry(i, docs_dir, root) for i in value])
    levels = [c.level for c in children if c.level is not None]
    return Entry(
        label=label,
        target=None,
        level=min(levels) if levels else None,
        children=children,
    )


def _member_pages(items: list[object]) -> list[str]:
    """The pages a routing index must link for the nav members *items*.

    A member page is itself; a member group that opens with an index is that
    index; a member group without one contributes each of its leaves. External
    URLs are not pages and are skipped.
    """
    pages: list[str] = []
    for item in items:
        _label, value = split_nav_item(item)
        if isinstance(value, str):
            if not is_url(value):
                pages.append(value)
        elif isinstance(value, list):
            landing = group_landing(value)
            if landing is not None:
                pages.append(landing)
            else:
                pages.extend(_member_pages(value))
    return pages


def _contents_of(facts: _PageFacts, landing: str) -> Contents:
    """The declared shape of a group-opening index, or a fault naming it."""
    permitted = ", ".join(member.value for member in Contents)
    if facts.contents is None:
        raise MetadataLoadError(
            f"opens a mkdocs.yml nav group but declares no `{CONTENTS_KEY}:`; "
            f"declare one of {permitted} so the decision is recorded "
            "(DF-11-028, #3617)",
            path=f"docs/{landing}",
        )
    try:
        return Contents(facts.contents)
    except ValueError:
        raise MetadataLoadError(
            f"declares `{CONTENTS_KEY}: {facts.contents}`; permitted values "
            f"are {permitted} (DF-11-028)",
            path=f"docs/{landing}",
        ) from None
