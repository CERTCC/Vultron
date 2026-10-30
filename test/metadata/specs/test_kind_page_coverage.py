"""Assert that every SpecKind has exactly one place its rows render (AC-5).

A kind outside the Requirements Catalog has a matching
``docs/reference/specs/<kind-slug>.md`` page, so a new kind fails here until
its page exists ("new kind → new page"). The ``protocol`` and ``foundation``
tiers render only in the Protocol Specification's Requirements Catalog
(SR-09-004, DF-12-001), so they have no per-kind page; their old pages were
retired behind redirects (#4901).
"""

from pathlib import Path

import pytest

from vultron.metadata.docs.requirement_catalog import (
    CATALOG_KINDS,
    CATALOG_PAGES,
)
from vultron.metadata.specs.schema import SpecKind

_ROOT = Path(__file__).parents[3]
_DOCS = _ROOT / "docs"
_DOCS_SPECS_DIR = _DOCS / "reference" / "specs"


@pytest.mark.parametrize(
    "kind", [k for k in SpecKind if k not in CATALOG_KINDS]
)
def test_kind_has_docs_page(kind: SpecKind) -> None:
    """Every other SpecKind must have a matching docs/reference/specs/<slug>.md."""
    page = _DOCS_SPECS_DIR / f"{kind.value}.md"
    assert page.exists(), (
        f"Missing docs page for SpecKind.{kind.name}: "
        f"expected {page.relative_to(_ROOT)}"
    )


@pytest.mark.spec("SR-09-004", "DF-12-001")
@pytest.mark.parametrize("kind", sorted(CATALOG_KINDS))
def test_catalog_tier_has_catalog_pages_and_no_kind_page(
    kind: SpecKind,
) -> None:
    assert not (_DOCS_SPECS_DIR / f"{kind.value}.md").exists()
    pages = [p for p in CATALOG_PAGES if p.tier is kind]
    assert pages
    missing = [p.path for p in pages if not (_DOCS / p.path).is_file()]
    assert not missing, f"catalog pages missing: {missing}"
