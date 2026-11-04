"""Discover each nav group's index, check routing indexes and render generated listings."""

from __future__ import annotations

import posixpath
from pathlib import Path

from vultron.metadata.base import mkdocs_config
from vultron.metadata.docs.landing_pages.model import (
    _INDEX_NAME,
    BEGIN_MARKER,
    CONTENTS_KEY,
    END_MARKER,
    Contents,
    Entry,
    LandingPage,
    RoutingPage,
    SectionIndexes,
    _PageFacts,
)
from vultron.metadata.docs.landing_pages.nav import (
    _contents_of,
    _member_pages,
    _page_facts,
    group_landing,
    is_url,
    nav_entry,
    sort_entries,
    split_nav_item,
)
from vultron.metadata.docs.page_frontmatter import (
    classify_docs_tree,
    include_directives,
)
from vultron.metadata.docs.page_links import link_targets
from vultron.metadata.docs.page_schema import is_working_record
from vultron.metadata.file_loading import MetadataLoadError
from vultron.metadata.generated_block import splice_between


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
            _label, value = split_nav_item(item)
            if isinstance(value, list):
                self._group(value)
            elif (
                isinstance(value, str)
                and not is_url(value)
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
                    "(DF-11-028, DF-11-006)",
                    path=f"docs/{landing}",
                )
            return
        self._decided(landing, facts, [])

    def _group(self, value: list[object]) -> None:
        landing = group_landing(value)
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
                [nav_entry(i, self.docs_dir, self.root) for i in members]
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


def linked_pages(root: Path, page: str) -> set[str]:
    """The ``docs/``-relative pages the page at *page* links.

    A link counts whether the page writes it or a fragment it includes whole
    carries it, so cards shared with another page route both (DF-10-002). A
    fragment's links resolve against the fragment, as include-markdown rewrites
    them; a ``start=`` or ``end=`` include may cut the link, so it is not
    counted.
    """
    docs_dir = root / "docs"
    host = docs_dir / page
    linked = link_targets(page, host.read_text(encoding="utf-8"))
    for _, fragment, whole in include_directives(host, docs_dir, uncut=True):
        if whole:
            text = (docs_dir / fragment).read_text(encoding="utf-8")
            linked |= link_targets(fragment, text)
    return linked


def routing_faults(root: Path, page: RoutingPage) -> list[MetadataLoadError]:
    """Return one fault per member *page* is required to link but does not.

    Links are counted by :func:`linked_pages`. Every missing member is
    reported, not only the first (EH-07-001).
    """
    linked = linked_pages(root, page.path)
    return [
        MetadataLoadError(
            f"declares `{CONTENTS_KEY}: {Contents.ROUTING.value}` but does not "
            f"link {member}; a routing page must link every member of its "
            "section (DF-11-029)",
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
        if is_url(entry.target)
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
