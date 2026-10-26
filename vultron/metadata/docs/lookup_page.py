"""Generate the cross-tab lookup page of ``page_type: reference`` pages.

Requirements: specs/diataxis-requirements.yaml DF-11-021 (one lookup page,
linked from the home page and every start page, listing the reference pages
by top-level nav section; a subgroup listed once through its index; an
omitted page placed by its own directory's index; generated and check gated),
DF-11-005 (generated listings are never hand-maintained), DF-11-006 (a large
leaf set is reached through one entry), DF-09-009 (an empty target set
fails). Design rationale: ``notes/site-information-architecture.md`` § "Inside
a tab: topics, landing pages, threads" (ADR-0136).

Once Reference stopped being a top-level tab, a returning reader lost the
view by type. The lookup page gives it back, derived from the same two
sources the section landing pages use (:mod:`landing_pages`): the
``mkdocs.yml`` nav and each page's frontmatter.

Placement rules, applied per top-level nav section, in nav order:

* a reference page directly under the top-level section is listed on its own;
* a reference page inside a nav group below the top level is listed once,
  through the ``index.md`` that opens the outermost such group containing
  it, under the group's label and with the index's ``description:``;
* a reference page whose groups below the top level have no opening
  ``index.md`` is listed on its own;
* a reference page the nav omits is placed where the nav carries the
  ``index.md`` of its own directory, as if it sat in the nav right after that
  index, and then follows the rules above. When the nav does not carry that
  index, the page cannot be placed, and that is a fault naming the page,
  never a silent omission.

Only the text between :data:`BEGIN_MARKER` and :data:`END_MARKER` is
generated; the page's framing prose is hand-written and survives
regeneration. Every entry shows its target's ``description:``, so an entry
whose target declares none is a fault too.

:func:`lookup_link_faults` is the other half of the rule: the home page and
every start page must link the lookup page. A missing link is reported, never
written, like a routing page's missing member.
"""

from __future__ import annotations

import posixpath
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from vultron.metadata.base import mkdocs_config, unbuilt_docs_spec, walk_nav
from vultron.metadata.docs.landing_pages import (
    WRITE_COMMAND,
    Entry,
    LandingPage,
    group_landing,
    is_url,
    linked_pages,
    nav_entry,
    render_listing,
    split_nav_item,
    unreadable_nav_item,
)
from vultron.metadata.docs.page_frontmatter import (
    DocsTree,
    classify_docs_tree,
)
from vultron.metadata.docs.page_schema import PageType, is_working_record
from vultron.metadata.file_loading import (
    MetadataLoadError,
    MetadataLoadErrors,
    load_frontmatter,
)
from vultron.metadata.generated_block import splice_between

#: ``docs/``-relative path of the lookup page, beside the home page.
LOOKUP_PATH = "lookup.md"

#: ``docs/``-relative path of the home page, which must link the lookup page.
HOME_PATH = "index.md"

#: Opening marker of the generated listing. Names both inputs and the command.
BEGIN_MARKER = (
    "<!-- BEGIN GENERATED LOOKUP LISTING — do not edit; change the mkdocs.yml "
    "nav or a reference page's page_type: or description: frontmatter, then "
    f"run `{WRITE_COMMAND}` -->"
)

#: Closing marker of the generated listing.
END_MARKER = "<!-- END GENERATED LOOKUP LISTING -->"

_INDEX_NAME = "index.md"


@dataclass(frozen=True, slots=True)
class LookupSection:
    """The entries one top-level nav section contributes, in nav order."""

    label: str
    entries: tuple[Entry, ...]


def _page_type(root: Path, rel: str) -> object:
    return load_frontmatter(root / "docs" / rel, root=root).metadata.get(
        "page_type"
    )


def reference_pages(root: Path, tree: DocsTree) -> tuple[str, ...]:
    """Every built reader-facing page in *tree* declaring ``page_type:
    reference``.

    Fragments, working-record pages (DF-11-003) and pages the build withholds
    (``draft_docs``, ``exclude_docs``) have no reader to look them up.
    """
    unbuilt = unbuilt_docs_spec(mkdocs_config(root))
    return tuple(
        page
        for page in tree.pages
        if not is_working_record(page)
        and not unbuilt.match_file(page)
        and _page_type(root, page) == PageType.REFERENCE.value
    )


def _placements(
    omitted: Iterable[str], navved: frozenset[str]
) -> tuple[dict[str, list[str]], list[MetadataLoadError]]:
    """Map each nav-carried directory index to the omitted pages it places.

    Returns the mapping and one fault per page that cannot be placed because
    the nav does not carry its own directory's ``index.md``.
    """
    placed: dict[str, list[str]] = {}
    faults: list[MetadataLoadError] = []
    for page in omitted:
        index = posixpath.join(posixpath.dirname(page), _INDEX_NAME)
        if index != page and index in navved:
            placed.setdefault(index, []).append(page)
            continue
        faults.append(
            MetadataLoadError(
                "is a page_type: reference page the mkdocs.yml nav omits, "
                f"and the nav does not carry {index}, so the lookup page "
                f"cannot place it; add the page or {index} to the nav "
                "(DF-11-021)",
                path=f"docs/{page}",
            )
        )
    return placed, faults


def _with_placed(
    items: list[object], placed: dict[str, list[str]]
) -> list[object]:
    """*items* with each omitted page inserted right after its index.

    Inserted beside the index, the page shares the index's groups, so the
    placement rules for nav pages apply to it unchanged.
    """
    out: list[object] = []
    for item in items:
        label, value = split_nav_item(item)
        if isinstance(value, list) and label is not None:
            out.append({label: _with_placed(value, placed)})
            continue
        out.append(item)
        if isinstance(value, str):
            out.extend(placed.get(value, []))
    return out


class _Lookup:
    """One pass over the nav, collecting each section's reference entries."""

    def __init__(self, root: Path, reference: frozenset[str]) -> None:
        self.root = root
        self.docs_dir = root / "docs"
        self.reference = reference

    def _holds_reference(self, items: list[object]) -> bool:
        return any(path in self.reference for path in walk_nav(items))

    def entries(self, items: list[object]) -> list[Entry]:
        """The entries for the members *items* of a section or a group
        without an opening index."""
        found: list[Entry] = []
        for item in items:
            label, value = split_nav_item(item)
            if isinstance(value, str):
                if value in self.reference:
                    found.append(nav_entry(item, self.docs_dir, self.root))
            elif isinstance(value, list) and label is not None:
                if not self._holds_reference(value):
                    continue
                if group_landing(value) is not None:
                    found.append(nav_entry(item, self.docs_dir, self.root))
                else:
                    found.extend(self.entries(value))
            else:
                raise unreadable_nav_item(item)
        return found

    def section(
        self, item: object, placed: dict[str, list[str]]
    ) -> LookupSection | None:
        """The section one top-level nav *item* contributes, if any.

        A top-level page is a section of its own, holding the omitted pages
        its index places, so they stay in its section rather than becoming
        sections of their own.

        Raises:
            MetadataLoadError: If the item is a shape mkdocs cannot read.
        """
        label, value = split_nav_item(item)
        if isinstance(value, list) and label is not None:
            members = _with_placed(value, placed)
        elif isinstance(value, str):
            if is_url(value):
                return None
            members = [item, *placed.get(value, [])]
        else:
            raise unreadable_nav_item(item)
        entries = self.entries(members)
        if not entries:
            return None
        return LookupSection(
            label=label if label is not None else entries[0].label,
            entries=tuple(entries),
        )


def _description_faults(
    sections: Iterable[LookupSection],
) -> list[MetadataLoadError]:
    return [
        MetadataLoadError(
            "is listed on the lookup page but declares no description:; "
            "every lookup entry shows its page's description (DF-11-021)",
            path=f"docs/{entry.target}",
        )
        for section in sections
        for entry in section.entries
        if entry.description is None
    ]


def lookup_sections(root: Path) -> tuple[LookupSection, ...]:
    """Return the lookup page's listing, one section per top-level nav item.

    Raises:
        MetadataLoadError: If a listed page is missing or unreadable, the
            nav holds an item of a shape mkdocs cannot read, or no reference
            page resolves (DF-09-009).
        MetadataLoadErrors: Carrying every omitted reference page that cannot
            be placed and every entry whose target declares no
            ``description:``.
    """
    tree = classify_docs_tree(root)
    reference = reference_pages(root, tree)
    if not reference:
        raise MetadataLoadError(
            "resolved no page_type: reference pages for the lookup page; an "
            "empty target set is a failure, not a pass (DF-09-009)",
            path="docs/",
        )
    placed, faults = _placements(
        (page for page in reference if page not in tree.navved), tree.navved
    )
    nav = mkdocs_config(root).get("nav")
    walk = _Lookup(root, frozenset(reference))
    sections = tuple(
        section
        for section in (
            walk.section(item, placed)
            for item in (nav if isinstance(nav, list) else [])
        )
        if section is not None
    )
    faults.extend(_description_faults(sections))
    if faults:
        raise MetadataLoadErrors(
            faults,
            summary=f"{len(faults)} lookup-page finding(s) (DF-11-021):",
        )
    return sections


def render_lookup(sections: Iterable[LookupSection]) -> str:
    """Render the listing: a heading per section, then its entries."""
    blocks = [
        f"## {section.label}\n\n"
        + render_listing(
            LandingPage(path=LOOKUP_PATH, entries=section.entries)
        )
        for section in sections
    ]
    return "\n\n".join(blocks)


def splice_lookup(current: str, sections: Iterable[LookupSection]) -> str:
    """Return *current* with its generated listing replaced from *sections*."""
    return splice_between(
        current,
        render_lookup(sections),
        f"docs/{LOOKUP_PATH}",
        BEGIN_MARKER,
        END_MARKER,
    )


def lookup_link_faults(
    root: Path, hosts: Iterable[str]
) -> list[MetadataLoadError]:
    """One fault per page in *hosts* that does not link the lookup page.

    *hosts* are ``docs/``-relative: the home page and every start page.
    Links are counted by :func:`landing_pages.linked_pages`.
    """
    return [
        MetadataLoadError(
            f"does not link the lookup page, {LOOKUP_PATH}; the home page and "
            "every start page link it in their framing (DF-11-021)",
            path=f"docs/{host}",
        )
        for host in hosts
        if LOOKUP_PATH not in linked_pages(root, host)
    ]
