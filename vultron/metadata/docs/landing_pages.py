"""Generate or check the contents of every ``index.md`` that opens a nav group.

Requirements: specs/diataxis-requirements.yaml DF-11-005 (generated, check
gated, never hand-maintained; the two exempt shapes), DF-09-009 (an empty
target set fails), DF-11-004 (a level is never rendered). Design rationale:
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
  ``--check`` fails when the page fails to link a member (DF-11-005's
  routing-page exemption). The members it must link are the group's nav
  members plus any reader page in its own directory the nav does not carry
  (DF-11-006's routing-page pattern), so a page added to the directory without
  a link is caught.
* ``contents: rendered`` — the enumeration is rendered at build time from a
  registry (DEMOCI-11-009), so nothing is committed to drift. The generator
  records the page and leaves it alone.
"""

from __future__ import annotations

import posixpath
import re
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from urllib.parse import urlsplit

from vultron.metadata.base import mkdocs_config
from vultron.metadata.docs.page_frontmatter import (
    classify_docs_tree,
    include_directives,
)
from vultron.metadata.docs.page_links import link_targets
from vultron.metadata.docs.page_schema import LEVELS, is_working_record
from vultron.metadata.file_loading import MetadataLoadError, load_frontmatter
from vultron.metadata.generated_block import splice_between
from vultron.metadata.markdown_tables import fenced_lines

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

#: Frontmatter key on every ``index.md`` that opens a nav group (DF-11-005).
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


def _is_url(target: str) -> bool:
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


def _page_facts(docs_dir: Path, rel: str, root: Path) -> _PageFacts:
    """Read a page's title and the ``description``, ``level`` and ``contents``
    it declares.

    The title follows mkdocs: frontmatter ``title:``, else the body's first
    H1, else the file stem.

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
    title = metadata.get("title")
    if not isinstance(title, str) or not title.strip():
        title = _body_h1(post.content) or Path(rel).stem
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
        title=" ".join(title.split()),
        description=description,
        level=level if type(level) is int and level in LEVELS else None,
        contents=contents if isinstance(contents, str) else None,
    )


def _split_item(item: object) -> tuple[str | None, object]:
    """Return ``(label, value)`` for one nav item; bare paths have no label."""
    if isinstance(item, dict) and len(item) == 1:
        ((label, value),) = item.items()
        return str(label), value
    return None, item


def _group_landing(items: list[object]) -> str | None:
    """The ``index.md`` a nav group opens with, which becomes its link."""
    if not items:
        return None
    _label, value = _split_item(items[0])
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


def _entry(item: object, docs_dir: Path, root: Path) -> Entry:
    label, value = _split_item(item)
    if isinstance(value, str):
        if _is_url(value):
            return Entry(label=label or value, target=value)
        facts = _page_facts(docs_dir, value, root)
        return Entry(
            label=label or facts.title,
            target=value,
            description=facts.description,
            level=facts.level,
        )
    if not isinstance(value, list) or label is None:
        raise MetadataLoadError(
            f"has a nav item this generator cannot read: {item!r}",
            path="mkdocs.yml",
        )
    landing = _group_landing(value)
    if landing is not None:
        facts = _page_facts(docs_dir, landing, root)
        return Entry(
            label=label,
            target=landing,
            description=facts.description,
            level=facts.level,
        )
    children = sort_entries([_entry(i, docs_dir, root) for i in value])
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
        _label, value = _split_item(item)
        if isinstance(value, str):
            if not _is_url(value):
                pages.append(value)
        elif isinstance(value, list):
            landing = _group_landing(value)
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
            "(DF-11-005, #3617)",
            path=f"docs/{landing}",
        )
    try:
        return Contents(facts.contents)
    except ValueError:
        raise MetadataLoadError(
            f"declares `{CONTENTS_KEY}: {facts.contents}`; permitted values "
            f"are {permitted} (DF-11-005)",
            path=f"docs/{landing}",
        ) from None


class _Walk:
    """One pass over the nav, collecting each group-opening index by shape."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.docs_dir = root / "docs"
        self.generated: list[LandingPage] = []
        self.routing: list[RoutingPage] = []
        self.rendered: list[str] = []
        self._orphans: dict[str, list[str]] | None = None

    def _orphan_siblings(self, landing: str) -> list[str]:
        """Reader pages beside *landing* that the nav does not carry.

        These are the leaves a routing page exists to reach (DF-11-006).
        Fragments are not pages and the working record is routed from its own
        door (DF-11-003), so neither is required.
        """
        if self._orphans is None:
            tree = classify_docs_tree(self.root)
            by_dir: dict[str, list[str]] = {}
            for page in tree.pages:
                if page in tree.navved or is_working_record(page):
                    continue
                if posixpath.basename(page) == _INDEX_NAME:
                    continue
                by_dir.setdefault(posixpath.dirname(page), []).append(page)
            self._orphans = by_dir
        return self._orphans.get(posixpath.dirname(landing), [])

    def visit(self, items: list[object]) -> None:
        for item in items:
            _label, value = _split_item(item)
            if isinstance(value, list):
                self._group(value)
            elif (
                isinstance(value, str)
                and not _is_url(value)
                and posixpath.basename(value) == _INDEX_NAME
            ):
                self._leaf_index(value)

    def _leaf_index(self, landing: str) -> None:
        """An ``index.md`` the nav carries as a leaf, not as a group opener.

        It is a section index only if it says so, or if its directory holds
        reader pages the nav omits: then it is the routing page those pages
        are reached through (DF-11-006) and must declare that, so a leaf set
        cannot be left with an unaccountable door.
        """
        facts = _page_facts(self.docs_dir, landing, self.root)
        orphans = self._orphan_siblings(landing)
        if facts.contents is None:
            if orphans:
                raise MetadataLoadError(
                    f"is the only nav entry for its directory, which holds "
                    f"{len(orphans)} reader page(s) the nav omits "
                    f"({', '.join(orphans)}), but declares no "
                    f"`{CONTENTS_KEY}:`; declare `{CONTENTS_KEY}: "
                    f"{Contents.ROUTING.value}` and link each of them "
                    "(DF-11-005, DF-11-006)",
                    path=f"docs/{landing}",
                )
            return
        self._decided(landing, facts, [])

    def _group(self, value: list[object]) -> None:
        landing = _group_landing(value)
        if landing is None:
            self.visit(value)
            return
        facts = _page_facts(self.docs_dir, landing, self.root)
        self._decided(landing, facts, value[1:])
        self.visit(value[1:])

    def _decided(
        self, landing: str, facts: _PageFacts, members: list[object]
    ) -> None:
        """File *landing* under its declared shape, given its nav *members*."""
        shape = _contents_of(facts, landing)
        if shape is Contents.GENERATED:
            if not members:
                raise MetadataLoadError(
                    f"the nav group opening with {landing} lists nothing "
                    "else, so its landing page would enumerate an empty "
                    "section",
                    path="mkdocs.yml",
                )
            entries = sort_entries(
                [_entry(i, self.docs_dir, self.root) for i in members]
            )
            self.generated.append(LandingPage(path=landing, entries=entries))
        elif shape is Contents.ROUTING:
            required = dict.fromkeys(
                [*_member_pages(members), *self._orphan_siblings(landing)]
            )
            self.routing.append(
                RoutingPage(path=landing, required=tuple(required))
            )
        else:
            self.rendered.append(landing)


def discover_section_indexes(root: Path) -> SectionIndexes:
    """Return every section index in the nav, at any depth, by declared shape.

    A section index is an ``index.md`` that opens a nav group, or one the nav
    carries as a leaf that declares a shape or is the door to reader pages
    the nav omits.

    Raises:
        MetadataLoadError: If a section index declares no ``contents:`` or an
            unknown one, no generated page resolves (DF-09-009), a generated
            section lists nothing but its landing page, or a listed page is
            unreadable or empty.
    """
    nav = mkdocs_config(root).get("nav")
    walk = _Walk(root)
    walk.visit(nav if isinstance(nav, list) else [])
    if not walk.generated:
        raise MetadataLoadError(
            "resolved no section landing pages from the nav; an empty target "
            "set is a failure, not a pass (DF-09-009)",
            path="mkdocs.yml",
        )
    return SectionIndexes(
        generated=tuple(walk.generated),
        routing=tuple(walk.routing),
        rendered=tuple(walk.rendered),
    )


def discover_landing_pages(root: Path) -> tuple[LandingPage, ...]:
    """Return every nav group index that declares ``contents: generated``.

    Raises:
        MetadataLoadError: As :func:`discover_section_indexes`.
    """
    return discover_section_indexes(root).generated


def routing_faults(root: Path, page: RoutingPage) -> list[MetadataLoadError]:
    """Return one fault per member *page* is required to link but does not.

    A link counts whether the page writes it or a fragment it includes whole
    carries it, so cards shared with another page route both (DF-10-002). A
    fragment's links resolve against the fragment, as include-markdown rewrites
    them; a ``start=`` include may cut the link, so it is not counted. Every
    missing member is reported, not only the first (EH-07-001).
    """
    docs_dir = root / "docs"
    host = docs_dir / page.path
    linked = link_targets(page.path, host.read_text(encoding="utf-8"))
    for _, fragment, whole in include_directives(host, docs_dir):
        if whole:
            text = (docs_dir / fragment).read_text(encoding="utf-8")
            linked |= link_targets(fragment, text)
    return [
        MetadataLoadError(
            f"declares `{CONTENTS_KEY}: {Contents.ROUTING.value}` but does not "
            f"link {member}; a routing page must link every member of its "
            "section (DF-11-005)",
            path=f"docs/{page.path}",
        )
        for member in page.required
        if member not in linked
    ]


def _render_entry(entry: Entry, landing: str, depth: int) -> list[str]:
    indent = "    " * depth
    if entry.target is None:
        lines = [f"{indent}- **{entry.label}**"]
        for child in entry.children:
            lines.extend(_render_entry(child, landing, depth + 1))
        return lines
    href = (
        entry.target
        if _is_url(entry.target)
        else posixpath.relpath(entry.target, posixpath.dirname(landing))
    )
    line = f"{indent}- [{entry.label}]({href})"
    if entry.description:
        line += f" — {entry.description}"
    return [line]


#: Python-Markdown nests a list item only at a 4-space indent, but markdownlint's
#: MD007 wants 2 and its auto-fix would flatten every group, so a listing that
#: nests switches MD007 off for exactly its own span.
_MD007_OFF = "<!-- markdownlint-disable MD007 -->"
_MD007_ON = "<!-- markdownlint-enable MD007 -->"


def render_listing(page: LandingPage) -> str:
    """Render a landing page's generated contents listing as a markdown list.

    Levels are used only to sort; none is printed (DF-11-004).
    """
    lines: list[str] = []
    for entry in page.entries:
        lines.extend(_render_entry(entry, page.path, 0))
    if any(entry.children for entry in page.entries):
        lines = [_MD007_OFF, *lines, _MD007_ON]
    return "\n".join(lines)


def splice_listing(current: str, page: LandingPage) -> str:
    """Return *current* with its generated listing replaced from *page*."""
    return splice_between(
        current,
        render_listing(page),
        f"docs/{page.path}",
        BEGIN_MARKER,
        END_MARKER,
    )
