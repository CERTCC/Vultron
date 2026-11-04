"""The landing-page model: markers, ``contents:`` kinds, entries and section indexes."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum

#: Command that regenerates every artifact, quoted in markers and errors.
WRITE_COMMAND = "uv run docs-site --write"


#: Opening marker of a generated listing. Names both inputs and the command, so
#: a reader who found the listing by grep learns where to make a change.
BEGIN_MARKER = (
    "<!-- BEGIN GENERATED SECTION CONTENTS — do not edit; change the mkdocs.yml "
    "nav or a listed page's description: frontmatter, then run "
    f"`{WRITE_COMMAND}` -->"
)


#: Closing marker of a generated listing.
END_MARKER = "<!-- END GENERATED SECTION CONTENTS -->"


#: Frontmatter key on every ``index.md`` that opens a nav group (DF-11-028).
CONTENTS_KEY = "contents"


_INDEX_NAME = "index.md"


_H1_RE = re.compile(r"^#\s+(.*?)\s*#*\s*$")


_ATTR_LIST_RE = re.compile(r"\s*\{[^}]*\}\s*$")


class Contents(StrEnum):
    """How an ``index.md`` that opens a nav group carries its contents."""

    GENERATED = "generated"
    ROUTING = "routing"
    RENDERED = "rendered"


@dataclass(frozen=True, slots=True)
class Entry:
    """One item in a landing page's contents listing.

    Attributes:
        label: The nav label; for an unlabelled nav path, the page's
            ``title:`` frontmatter, else its H1, as mkdocs would show it.
        target: ``docs/``-relative path, an external URL, or ``None`` for a
            group that has no landing page of its own.
        description: The target page's ``description:``, whitespace-folded.
        level: The level the entry sorts by, or ``None`` when undeclared.
        children: A group's members; empty when the entry links to a page.
    """

    label: str
    target: str | None
    description: str | None = None
    level: int | None = None
    children: tuple[Entry, ...] = ()


@dataclass(frozen=True, slots=True)
class LandingPage:
    """A nav group whose index declares ``contents: generated``."""

    path: str
    entries: tuple[Entry, ...]


@dataclass(frozen=True, slots=True)
class RoutingPage:
    """A nav group whose index declares ``contents: routing``.

    Attributes:
        path: ``docs/``-relative path of the index.
        required: Every ``docs/``-relative page the index must link: the
            group's nav members, and the reader pages in the index's own
            directory that the nav does not carry.
    """

    path: str
    required: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class SectionIndexes:
    """Every ``index.md`` that opens a nav group, by declared shape."""

    generated: tuple[LandingPage, ...]
    routing: tuple[RoutingPage, ...]
    rendered: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class _PageFacts:
    title: str
    description: str | None
    level: int | None
    contents: str | None
