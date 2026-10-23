"""Assert that every SpecKind value has a corresponding docs page (AC-5).

Fails when a new kind is added to the SpecKind enum without a matching
``docs/reference/specs/<kind-slug>.md`` file, enforcing the
"new kind → new page" rule.
"""

from pathlib import Path

import pytest

from vultron.metadata.specs.schema import SpecKind

_DOCS_SPECS_DIR = Path(__file__).parents[3] / "docs" / "reference" / "specs"


@pytest.mark.parametrize("kind", list(SpecKind))
def test_kind_has_docs_page(kind: SpecKind) -> None:
    """Every SpecKind must have a matching docs/reference/specs/<slug>.md."""
    slug = kind.value  # StrEnum value is the slug (e.g. "dev-process")
    page = _DOCS_SPECS_DIR / f"{slug}.md"
    assert page.exists(), (
        f"Missing docs page for SpecKind.{kind.name}: "
        f"expected {page.relative_to(Path(__file__).parents[3])}"
    )
