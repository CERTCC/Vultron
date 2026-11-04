"""Link targets for a requirement: site and source hrefs, the linker and anchor homes."""

from __future__ import annotations

import os
import posixpath
from collections import Counter
from collections.abc import Callable, Mapping
from dataclasses import dataclass

from vultron.metadata.docs.exec_page import EXEC_PAGE_ENV
from vultron.metadata.docs.requirement_catalog.pages import (
    CATALOG_KINDS,
    CATALOG_PAGES,
    FULL_PAGE,
    CatalogPage,
    kind_page,
)
from vultron.metadata.docs.requirement_catalog.placement import (
    _file_of,
    _page_for,
    requirement_anchor,
)
from vultron.metadata.docs.site_urls import relative_url
from vultron.metadata.specs.registry import SpecRegistry
from vultron.metadata.specs.schema import SpecKind


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


def source_href(to_page: str, anchor: str, *, from_page: str) -> str:
    """Return a source-relative link from *from_page* to *anchor* on *to_page*.

    Both pages are ``docs/``-relative source paths, and so is the result: the
    ``.md`` path MkDocs rewrites and validates. Use this for a link committed
    in a ``docs/`` file, and :func:`site_href` for one a renderer prints from
    an exec block, where MkDocs never sees the link and a ``.md`` target 404s.
    """
    start = posixpath.dirname(from_page) or "."
    return f"{posixpath.relpath(to_page, start)}#{anchor}"


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


def anchor_home_of(
    homes: Mapping[str, tuple[AnchorHome, ...]], spec_id: str
) -> AnchorHome | None:
    """The page defining *spec_id*'s anchor in *homes*, or ``None``.

    Keys the lookup with :func:`requirement_anchor`, which is what
    :func:`anchor_homes` built them with. A caller that lower-cases the ID
    itself agrees only because ``SpecIdStr`` forbids an underscore — an
    undeclared coupling that this function removes.
    """
    found = homes.get(requirement_anchor(spec_id))
    return found[0] if found else None
