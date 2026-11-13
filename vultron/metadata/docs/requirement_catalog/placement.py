"""Place a requirement on its catalog page, and check the placement table (DF-12-001/002)."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass

from vultron.metadata.docs.requirement_catalog.pages import (
    CATALOG_KINDS,
    CATALOG_LANDING,
    CATALOG_PAGES,
    CatalogPage,
)
from vultron.metadata.specs.registry import SpecRegistry
from vultron.metadata.specs.schema import SpecKind


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
    file_id = registry.get_file_id(spec_id)
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
