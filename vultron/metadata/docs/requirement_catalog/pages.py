"""The Requirements Catalog pages: kinds, landing, per-kind pages and the page table."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

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
        ("VAM", "MSM", "VM", "MV", "SE", "AKM", "CS", "OID", "CSAF"),
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
