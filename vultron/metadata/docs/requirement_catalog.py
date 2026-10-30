#  Copyright (c) 2026 Carnegie Mellon University and Contributors.
#  - see Contributors.md for a full list of Contributors
#  - see ContributionInstructions.md for information on how you can Contribute to this project
#  Vultron Multiparty Coordinated Vulnerability Disclosure Protocol Prototype is
#  licensed under a MIT (SEI)-style license, please see LICENSE.md distributed
#  with this Software or contact permission@sei.cmu.edu for full terms.
#  Created, in part, with funding and support from the United States Government
#  (see Acknowledgments file). This program may include and/or can make use of
#  certain third party source code, object code, documentation and other files
#  ("Third Party Software"). See LICENSE.md for more details.
#  Carnegie Mellon®, CERT® and CERT Coordination Center® are registered in the
#  U.S. Patent and Trademark Office by Carnegie Mellon University
"""Where each requirement is shown: the Requirements Catalog placement table.

The Protocol Specification renders its normative text from the ``protocol``
and ``foundation`` requirement tiers (ADR-0147). Every requirement of the two
tiers is shown once, in a Requirements Catalog row, and every other page that
shows or links it links that row (DF-12-001, DF-12-010). This module is the
one place that decides where a row lives:

* :data:`CATALOG_PAGES` is the placement table. It maps each catalog page key
  to the requirement files, by file ID, whose items of one tier the page
  holds. Placement is declared here, on the documentation side, and never as
  a field in a requirement file (DF-12-005). :func:`placement_faults` fails a
  file holding either tier that no page of that tier places, or that two
  places of that tier name (DF-12-015).
* :func:`catalog_location` returns the catalog page and anchor of a
  requirement of either tier, and refuses an ID of any other kind.
* :func:`requirement_linker` turns a requirement ID into the link target a
  rendered row shows on a given page. The renderers in
  :mod:`vultron.metadata.specs.docs_render` print their output from a
  ``markdown-exec`` block, where MkDocs neither rewrites nor validates a link,
  so the target is a built-site URL relative to the page, never a ``.md``
  path (``vultron/metadata/AGENTS.md``). On the single-page edition
  (``full.md``) a catalog row is in the page, so the link is a bare
  ``#anchor``: the ``full.md`` link hook skips fenced code and never sees an
  exec block's output (``full_page_links.py``).

* :func:`anchor_homes` maps each requirement, group and file ID to the
  pages whose rendered rows or headings define its anchor, so a tool that
  rewrites links (``scripts/relink_requirement_anchors.py``) and the gate
  that holds ``docs/`` to them agree with the renderers.

The two tiers have no per-kind requirements page: the catalog is where their
rows are (SR-09-004), and the retired ``reference/specs/protocol.md`` and
``foundation.md`` redirect to :data:`CATALOG_LANDING` (#4901).
"""

from __future__ import annotations

import os
from collections import Counter
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from types import MappingProxyType

from vultron.metadata.docs.exec_page import EXEC_PAGE_ENV
from vultron.metadata.docs.site_urls import relative_url
from vultron.metadata.specs.registry import SpecRegistry
from vultron.metadata.specs.schema import SpecKind

CATALOG_KINDS: frozenset[SpecKind] = frozenset(
    {SpecKind.PROTOCOL, SpecKind.FOUNDATION}
)
"""The requirement tiers the Requirements Catalog holds (DF-12-001)."""

FULL_PAGE = "reference/vultron-spec/full.md"
"""The single-page edition, which includes the catalog in document order."""

CATALOG_DIR = "reference/vultron-spec/requirements"
"""``docs/``-relative directory holding the Requirements Catalog pages."""

CATALOG_LANDING = f"{CATALOG_DIR}/index.md"
"""The catalog's routing landing page, which holds the §14 heading."""

CATALOG_INTRO = "reference/vultron-spec/_catalog/_intro.md"
"""The fragment holding the §14 heading and the catalog's framing."""

_CATALOG_PAGE = CATALOG_DIR + "/{key}.md"
_CATALOG_FRAGMENT = "reference/vultron-spec/_catalog/_{key}.md"
_KIND_PAGE = "reference/specs/{kind}.md"

RETIRED_KIND_PAGES: Mapping[str, SpecKind] = MappingProxyType(
    {_KIND_PAGE.format(kind=kind.value): kind for kind in CATALOG_KINDS}
)
"""The per-kind pages of the two catalog tiers, retired into the catalog
(#4901), each mapped to its tier. They redirect to :data:`CATALOG_LANDING`."""


def kind_page(kind: SpecKind) -> str:
    """Return the ``docs/``-relative source of *kind*'s requirements page.

    Raises:
        ValueError: If *kind* is ``protocol`` or ``foundation``, whose rows are
            in the Requirements Catalog instead (SR-09-004).
    """
    if kind in CATALOG_KINDS:
        raise ValueError(
            f"{kind.value} requirements have no per-kind page; they are in "
            "the Requirements Catalog (SR-09-004, DF-12-001)"
        )
    return _KIND_PAGE.format(kind=kind.value)


@dataclass(frozen=True)
class CatalogPage:
    """One Requirements Catalog page and the requirement files it holds.

    Attributes:
        key: The page's key; its source is ``<key>.md`` in :data:`CATALOG_DIR`.
        title: The page's title.
        tier: The one requirement tier the page shows.
        files: The IDs of the requirement files whose ``tier`` items the page
            shows, one subsection each, in this order.
    """

    key: str
    title: str
    tier: SpecKind
    files: tuple[str, ...]

    @property
    def path(self) -> str:
        """The page's ``docs/``-relative source path."""
        return _CATALOG_PAGE.format(key=self.key)

    @property
    def fragment(self) -> str:
        """The ``docs/``-relative fragment holding the page's subsection.

        The page and ``full.md`` include it, and it alone calls
        :func:`~vultron.metadata.specs.docs_render.render_catalog_page` for
        this key, so the rows render on exactly those two pages (DF-12-002).
        """
        return _CATALOG_FRAGMENT.format(key=self.key)


CATALOG_PAGES: tuple[CatalogPage, ...] = (
    CatalogPage(
        "vultron-protocol",
        "Vultron Protocol",
        SpecKind.PROTOCOL,
        ("VP",),
    ),
    CatalogPage(
        "messages",
        "Messages and Vocabulary",
        SpecKind.PROTOCOL,
        ("VAM", "MSM", "VM", "MV", "SE", "AKM", "CS"),
    ),
    CatalogPage(
        "state-behavior",
        "Report, Embargo and Case State Behavior",
        SpecKind.PROTOCOL,
        ("SM", "RMB", "EMB", "EP", "DUR", "CSB"),
    ),
    CatalogPage(
        "case-management",
        "Case Management",
        SpecKind.PROTOCOL,
        ("CM", "CP", "PRM", "ASK"),
    ),
    CatalogPage(
        "ledger-replication",
        "Case Ledger and Replication",
        SpecKind.PROTOCOL,
        ("CLP", "SYNC", "PCR", "CBT"),
    ),
    CatalogPage(
        "message-processing",
        "Message Processing",
        SpecKind.PROTOCOL,
        ("HP", "RSH", "RF", "BT", "EDF"),
    ),
    CatalogPage(
        "transport-security",
        "Transport and Security",
        SpecKind.PROTOCOL,
        ("HTTP", "IE", "OX", "SIG", "ENC"),
    ),
    CatalogPage(
        "foundation",
        "Inherited Requirements",
        SpecKind.FOUNDATION,
        (
            "VM",
            "MV",
            "SE",
            "AKM",
            "CS",
            "ID",
            "OID",
            "RF",
            "HTTP",
            "IE",
            "OX",
            "AR",
        ),
    ),
)
"""The placement table: every catalog page, in catalog order (DF-12-005)."""


class NotInCatalogError(ValueError):
    """Raised for an ID that names no requirement the catalog shows."""


@dataclass(frozen=True)
class CatalogLocation:
    """Where a requirement's catalog row is.

    Attributes:
        page: The catalog page holding the row.
        anchor: The row's anchor, without ``#``.
    """

    page: CatalogPage
    anchor: str


def requirement_anchor(spec_id: str) -> str:
    """Return the anchor a requirement row defines (lower-cased, dashes)."""
    return spec_id.lower().replace("_", "-")


def _file_of(registry: SpecRegistry) -> dict[str, str]:
    return {
        spec.id: spec_file.id
        for spec_file in registry.files
        for group in spec_file.groups
        for spec in group.specs
    }


def _page_for(
    file_id: str, tier: SpecKind, pages: Iterable[CatalogPage]
) -> CatalogPage | None:
    return next(
        (p for p in pages if p.tier == tier and file_id in p.files), None
    )


def catalog_location(
    spec_id: str,
    registry: SpecRegistry,
    pages: tuple[CatalogPage, ...] = CATALOG_PAGES,
) -> CatalogLocation:
    """Return the catalog page and anchor of *spec_id*'s row.

    Raises:
        NotInCatalogError: If *spec_id* names no requirement, names one whose
            kind is not ``protocol`` or ``foundation`` (DF-12-012), or names
            one whose file no catalog page of its tier places (DF-12-015).
    """
    try:
        kind = registry.get_effective_kind(spec_id)
    except KeyError:
        raise NotInCatalogError(f"{spec_id} names no requirement") from None
    if kind not in CATALOG_KINDS:
        raise NotInCatalogError(
            f"{spec_id} is a {kind.value} requirement; only protocol and "
            "foundation requirements are in the Requirements Catalog "
            "(DF-12-012)"
        )
    file_id = _file_of(registry)[spec_id]
    page = _page_for(file_id, kind, pages)
    if page is None:
        raise NotInCatalogError(
            f"{spec_id}: no {kind.value} catalog page places file {file_id} "
            "(add it to CATALOG_PAGES, DF-12-015)"
        )
    return CatalogLocation(page, requirement_anchor(spec_id))


def _page_faults(pages: tuple[CatalogPage, ...]) -> list[str]:
    """Return the faults in the table's pages, without reading any file."""
    faults = [
        f"catalog page key {key!r} is declared {count} times"
        for key, count in Counter(p.key for p in pages).items()
        if count > 1
    ]
    faults.extend(
        f"catalog page {page.key!r} has tier {page.tier.value}; the "
        "catalog holds only protocol and foundation requirements"
        for page in pages
        if page.tier not in CATALOG_KINDS
    )
    faults.extend(
        f"catalog page key {page.key!r} would be the catalog landing page"
        for page in pages
        if page.path == CATALOG_LANDING
    )
    foundation_pages = [p.key for p in pages if p.tier is SpecKind.FOUNDATION]
    if len(foundation_pages) != 1:
        faults.append(
            "foundation requirements need exactly one catalog page of their "
            f"own (DF-12-009); found {foundation_pages or 'none'}"
        )
    return faults


def _file_faults(
    registry: SpecRegistry, pages: tuple[CatalogPage, ...]
) -> list[str]:
    """Return the faults in where the table places each requirement file."""
    tiers: dict[str, set[SpecKind]] = {
        spec_file.id: {
            spec.kind
            for group in spec_file.groups
            for spec in group.specs
            if spec.kind in CATALOG_KINDS
        }
        for spec_file in registry.files
    }
    placed: Counter[tuple[str, SpecKind]] = Counter(
        (file_id, page.tier) for page in pages for file_id in page.files
    )
    faults: list[str] = []
    for (file_id, tier), count in sorted(placed.items()):
        if file_id not in tiers:
            faults.append(f"{file_id} is placed but names no requirement file")
        elif tier not in tiers[file_id]:
            faults.append(
                f"{file_id} is placed on a {tier.value} catalog page but "
                f"holds no {tier.value} requirement"
            )
        if count > 1:
            faults.append(
                f"{file_id} is placed {count} times for the {tier.value} tier "
                "(DF-12-015)"
            )
    faults.extend(
        f"{file_id} holds {tier.value} requirements but no "
        f"{tier.value} catalog page places it (DF-12-015)"
        for file_id, file_tiers in sorted(tiers.items())
        for tier in sorted(file_tiers, key=lambda k: k.value)
        if (file_id, tier) not in placed
    )
    return faults


def placement_faults(
    registry: SpecRegistry,
    pages: tuple[CatalogPage, ...] = CATALOG_PAGES,
) -> list[str]:
    """Return every fault in the placement table *pages* against *registry*.

    A fault is a duplicate page key, a page of a tier the catalog does not
    hold, other than one ``foundation`` page (DF-12-009), a placed file that
    does not exist or holds no item of the page's tier, or a file holding a
    tier that no page of that tier places, or that two places of that tier
    name (DF-12-015). An empty list means the table is sound.
    """
    return _page_faults(pages) + _file_faults(registry, pages)


def current_page() -> str:
    """Return the ``docs/``-relative source path of the page being rendered.

    The ``exec_page`` MkDocs hook records it before each page renders, so a
    renderer called from a ``markdown-exec`` block can tell which page it is
    printing for.

    Raises:
        RuntimeError: If no page is recorded: the renderer is running outside
            a MkDocs build, or the ``exec_page`` hook is not registered.
    """
    page = os.environ.get(EXEC_PAGE_ENV)
    if not page:
        raise RuntimeError(
            f"{EXEC_PAGE_ENV} is not set: pass page= explicitly, or register "
            "vultron/metadata/docs/exec_page.py under hooks: in mkdocs.yml"
        )
    return page


def site_href(from_page: str, to_page: str, anchor: str) -> str:
    """Return a link from *from_page* to *anchor* on *to_page*.

    Both pages are ``docs/``-relative source paths. The link is the built-site
    URL relative to *from_page*, or a bare ``#anchor`` when the two are the
    same page.
    """
    if from_page == to_page:
        return f"#{anchor}"
    return f"{relative_url(to_page, page_path=from_page)}#{anchor}"


def requirement_linker(
    registry: SpecRegistry,
    page: str,
    *,
    pages: tuple[CatalogPage, ...] = CATALOG_PAGES,
) -> Callable[[str], str | None]:
    """Return a function giving the link target for a requirement ID on *page*.

    The returned function maps an ID to the URL of its row, relative to
    *page*, or to ``None`` when the ID names no requirement or names one of
    the two tiers whose file no catalog page places (a fault
    :func:`placement_faults` reports). A ``protocol`` or ``foundation``
    requirement links its catalog row, in-page on ``full.md`` (DF-12-011);
    any other kind links its row on its per-kind requirements page.

    Args:
        registry: The loaded requirement registry.
        page: ``docs/``-relative source path of the page the link is on.
        pages: The placement table.
    """
    file_of = _file_of(registry)

    def href(spec_id: str) -> str | None:
        try:
            kind = registry.get_effective_kind(spec_id)
        except KeyError:
            return None
        anchor = requirement_anchor(spec_id)
        if kind not in CATALOG_KINDS:
            return site_href(page, kind_page(kind), anchor)
        target = _page_for(file_of[spec_id], kind, pages)
        if target is None:
            return None
        if page == FULL_PAGE:
            return f"#{anchor}"
        return site_href(page, target.path, anchor)

    return href


@dataclass(frozen=True)
class AnchorHome:
    """A page whose rendered requirements define an anchor.

    Attributes:
        page: The page's ``docs/``-relative source path.
        fragment: The anchor's id on that page, without ``#``.
        tier: The kind of the items the anchor stands for on that page.
        items: How many of the ID's requirements the page shows there: one
            for a requirement, the matching items for a group or file.
    """

    page: str
    fragment: str
    tier: SpecKind
    items: int


def anchor_homes(
    registry: SpecRegistry,
    pages: tuple[CatalogPage, ...] = CATALOG_PAGES,
) -> dict[str, tuple[AnchorHome, ...]]:
    """Map each requirement, group and file ID to the pages defining its anchor.

    Keys are the lower-cased IDs (``vm-10-001``, ``vm-10``, ``vm``). A
    requirement has one home. A group or file has one per page that shows
    any of its items: its per-kind page, with the bare ID as the fragment,
    or a catalog page, where the fragment carries the tier
    (``protocol-vm-10``) so that ``full.md``, which holds both tiers, defines
    no id twice. A requirement of the two tiers whose file no catalog page
    places has no home. Homes are listed in :class:`SpecKind` order.
    """
    counts: Counter[tuple[str, str, str, SpecKind]] = Counter()
    for spec_file in registry.files:
        for group in spec_file.groups:
            for spec in group.specs:
                if spec.kind in CATALOG_KINDS:
                    catalog = _page_for(spec_file.id, spec.kind, pages)
                    if catalog is None:
                        continue
                    target, prefix = catalog.path, f"{spec.kind.value}-"
                else:
                    target, prefix = kind_page(spec.kind), ""
                for key, fragment in (
                    (spec_file.id, prefix + requirement_anchor(spec_file.id)),
                    (group.id, prefix + requirement_anchor(group.id)),
                    (spec.id, requirement_anchor(spec.id)),
                ):
                    counts[
                        (requirement_anchor(key), target, fragment, spec.kind)
                    ] += 1
    order = list(SpecKind)
    homes: dict[str, list[AnchorHome]] = {}
    for (key, target, fragment, tier), items in counts.items():
        homes.setdefault(key, []).append(
            AnchorHome(target, fragment, tier, items)
        )
    return {
        key: tuple(sorted(found, key=lambda h: order.index(h.tier)))
        for key, found in homes.items()
    }


__all__ = [
    "CATALOG_DIR",
    "CATALOG_INTRO",
    "CATALOG_KINDS",
    "CATALOG_LANDING",
    "CATALOG_PAGES",
    "FULL_PAGE",
    "AnchorHome",
    "CatalogLocation",
    "CatalogPage",
    "RETIRED_KIND_PAGES",
    "NotInCatalogError",
    "anchor_homes",
    "catalog_location",
    "current_page",
    "kind_page",
    "placement_faults",
    "requirement_anchor",
    "requirement_linker",
    "site_href",
]
