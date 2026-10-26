"""Tests for vultron.metadata.docs.requirement_catalog (issue #4895).

The placement table decides which Requirements Catalog page shows each
requirement file (DF-12-005), and the lookup and linker decide where a
requirement's row is and how a rendered row links it (DF-12-002). The first
tests are gates on the real ``specs/`` corpus; the rest pin each fault, the
lookup's refusals, and every link path, including the single-page edition.
"""

from __future__ import annotations

import os
import re
from collections import Counter
from pathlib import Path

import pytest
import yaml

from vultron.metadata.docs import exec_page
from vultron.metadata.docs.requirement_catalog import (
    CATALOG_KINDS,
    CATALOG_PAGES,
    FULL_PAGE,
    CatalogPage,
    NotInCatalogError,
    catalog_location,
    current_page,
    placement_faults,
    requirement_linker,
    site_href,
)
from vultron.metadata.specs.docs_render import render_catalog_page
from vultron.metadata.specs.registry import SpecRegistry, load_registry
from vultron.metadata.specs.schema import SpecKind

_ANCHOR_RE = re.compile(r'<a id="([^"]+)"></a>')
_SPEC_PAGE = "reference/vultron-spec/considerations.md"


def _rid(file_id: str, n: int) -> str:
    """Return requirement *n* of *file_id*'s one group.

    Built at run time: spec-lint fails a literal ID the real corpus lacks
    anywhere outside ``test/metadata/specs/`` (SR-04-008).
    """
    return f"{file_id}-01-{n:03d}"


def _spec(spec_id: str, kind: str) -> dict:
    return {
        "id": spec_id,
        "priority": "MUST",
        "kind": kind,
        "statement": f"{spec_id} statement",
    }


def _file(file_id: str, *kinds: str) -> dict:
    return {
        "id": file_id,
        "title": f"{file_id} Title",
        "description": f"{file_id} description",
        "scope": ["production"],
        "groups": [
            {
                "id": f"{file_id}-01",
                "title": f"{file_id} Group",
                "specs": [
                    _spec(_rid(file_id, n), kind)
                    for n, kind in enumerate(kinds, start=1)
                ],
            }
        ],
    }


@pytest.fixture
def registry(tmp_path: Path) -> SpecRegistry:
    """AAA holds protocol, BBB both tiers, CCC architecture only."""
    for data in (
        _file("AAA", "protocol", "protocol"),
        _file("BBB", "protocol", "foundation"),
        _file("CCC", "architecture"),
    ):
        (tmp_path / f"{data['id'].lower()}.yaml").write_text(yaml.dump(data))
    return load_registry(tmp_path)


PAGES = (
    CatalogPage("one", "One", SpecKind.PROTOCOL, ("AAA",)),
    CatalogPage("two", "Two", SpecKind.PROTOCOL, ("BBB",)),
    CatalogPage("foundation", "Inherited", SpecKind.FOUNDATION, ("BBB",)),
)


# ---------------------------------------------------------------------------
# Gates on the real corpus
# ---------------------------------------------------------------------------


@pytest.mark.spec("DF-12-005", "DF-12-001")
def test_real_placement_table_is_sound() -> None:
    faults = placement_faults(load_registry())
    assert not faults, "\n".join(faults)


@pytest.mark.spec("DF-12-001", "DF-12-002")
def test_real_catalog_renders_every_requirement_exactly_once() -> None:
    """Every protocol and foundation requirement has one catalog row, and no
    other requirement has any."""
    registry = load_registry()
    counts: Counter[str] = Counter()
    for page in CATALOG_PAGES:
        md = render_catalog_page(
            page.key, registry, page=page.path, published=True
        )
        counts.update(_ANCHOR_RE.findall(md))
    expected = {
        spec_id.lower()
        for spec_id, spec in registry.all_specs.items()
        if spec.kind in CATALOG_KINDS
    }
    assert expected, "no protocol or foundation requirement in the corpus"
    assert set(counts) == expected
    assert [a for a, n in counts.items() if n != 1] == []


# ---------------------------------------------------------------------------
# Placement faults
# ---------------------------------------------------------------------------


def test_sound_table_has_no_faults(registry: SpecRegistry) -> None:
    assert placement_faults(registry, PAGES) == []


def test_unplaced_file_fails(registry: SpecRegistry) -> None:
    pages = PAGES[1:]
    assert placement_faults(registry, pages) == [
        "AAA holds protocol requirements but no protocol catalog page "
        "places it (DF-12-005)"
    ]


def test_file_unplaced_for_one_of_its_tiers_fails(
    registry: SpecRegistry,
) -> None:
    pages = (
        *PAGES[:2],
        CatalogPage("foundation", "I", SpecKind.FOUNDATION, ()),
    )
    assert placement_faults(registry, pages) == [
        "BBB holds foundation requirements but no foundation catalog page "
        "places it (DF-12-005)"
    ]


def test_file_placed_twice_for_one_tier_fails(registry: SpecRegistry) -> None:
    pages = (
        CatalogPage("one", "One", SpecKind.PROTOCOL, ("AAA", "BBB")),
        *PAGES[1:],
    )
    assert placement_faults(registry, pages) == [
        "BBB is placed 2 times for the protocol tier (DF-12-005)"
    ]


def test_file_placed_twice_on_one_page_fails(registry: SpecRegistry) -> None:
    pages = (
        CatalogPage("one", "One", SpecKind.PROTOCOL, ("AAA", "AAA")),
        *PAGES[1:],
    )
    assert placement_faults(registry, pages) == [
        "AAA is placed 2 times for the protocol tier (DF-12-005)"
    ]


def test_placed_file_without_that_tier_fails(registry: SpecRegistry) -> None:
    pages = (
        *PAGES[:2],
        CatalogPage("foundation", "I", SpecKind.FOUNDATION, ("AAA", "BBB")),
    )
    assert placement_faults(registry, pages) == [
        "AAA is placed on a foundation catalog page but holds no "
        "foundation requirement"
    ]


def test_placed_unknown_file_fails(registry: SpecRegistry) -> None:
    pages = (*PAGES, CatalogPage("x", "X", SpecKind.PROTOCOL, ("ZZZ",)))
    assert placement_faults(registry, pages) == [
        "ZZZ is placed but names no requirement file"
    ]


def test_duplicate_page_key_fails(registry: SpecRegistry) -> None:
    pages = (*PAGES, CatalogPage("one", "Again", SpecKind.PROTOCOL, ()))
    assert placement_faults(registry, pages) == [
        "catalog page key 'one' is declared 2 times"
    ]


def test_page_of_another_tier_fails(registry: SpecRegistry) -> None:
    pages = (*PAGES, CatalogPage("arch", "A", SpecKind.ARCHITECTURE, ()))
    assert placement_faults(registry, pages) == [
        "catalog page 'arch' has tier architecture; the catalog holds only "
        "protocol and foundation requirements"
    ]


@pytest.mark.parametrize("count", [0, 2])
def test_foundation_needs_exactly_one_page(
    registry: SpecRegistry, count: int
) -> None:
    pages = PAGES[:2] + tuple(
        CatalogPage(
            f"f{n}", "F", SpecKind.FOUNDATION, ("BBB",) if n == 0 else ()
        )
        for n in range(count)
    )
    faults = placement_faults(registry, pages)
    assert any("exactly one catalog page" in f for f in faults)


# ---------------------------------------------------------------------------
# Lookup
# ---------------------------------------------------------------------------


@pytest.mark.spec("DF-12-002")
def test_catalog_location_of_protocol_requirement(
    registry: SpecRegistry,
) -> None:
    location = catalog_location(_rid("BBB", 1), registry, PAGES)
    assert location.page.key == "two"
    assert location.page.path == "reference/vultron-spec/requirements-two.md"
    assert location.anchor == "bbb-01-001"


def test_catalog_location_of_foundation_requirement(
    registry: SpecRegistry,
) -> None:
    location = catalog_location(_rid("BBB", 2), registry, PAGES)
    assert location.page.key == "foundation"


@pytest.mark.spec("DF-12-003")
def test_catalog_location_refuses_another_kind(registry: SpecRegistry) -> None:
    with pytest.raises(NotInCatalogError, match="architecture requirement"):
        catalog_location(_rid("CCC", 1), registry, PAGES)


def test_catalog_location_refuses_unknown_id(registry: SpecRegistry) -> None:
    with pytest.raises(NotInCatalogError, match="names no requirement"):
        catalog_location(_rid("ZZZ", 1), registry, PAGES)


def test_catalog_location_refuses_unplaced_file(
    registry: SpecRegistry,
) -> None:
    with pytest.raises(NotInCatalogError, match="places file AAA"):
        catalog_location(_rid("AAA", 1), registry, PAGES[1:])


# ---------------------------------------------------------------------------
# Links
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("from_page", "to_page", "expected"),
    [
        ("a/b.md", "a/b.md", "#x"),
        (
            "reference/specs/protocol.md",
            "reference/specs/project.md",
            "../project/#x",
        ),
        (FULL_PAGE, "reference/specs/protocol.md", "../../specs/protocol/#x"),
        ("reference/specs/protocol.md", "reference/specs/index.md", "../#x"),
        (
            "index.md",
            "reference/specs/protocol.md",
            "reference/specs/protocol/#x",
        ),
    ],
)
def test_site_href(from_page: str, to_page: str, expected: str) -> None:
    assert site_href(from_page, to_page, "x") == expected


def test_unpublished_catalog_links_the_per_kind_row(
    registry: SpecRegistry,
) -> None:
    href = requirement_linker(
        registry, _SPEC_PAGE, pages=PAGES, published=False
    )
    assert href(_rid("AAA", 1)) == "../../specs/protocol/#aaa-01-001"
    assert href(_rid("BBB", 2)) == "../../specs/foundation/#bbb-01-002"


@pytest.mark.spec("DF-12-002")
def test_published_catalog_links_the_catalog_row(
    registry: SpecRegistry,
) -> None:
    href = requirement_linker(
        registry, _SPEC_PAGE, pages=PAGES, published=True
    )
    assert href(_rid("AAA", 1)) == "../requirements-one/#aaa-01-001"
    assert href(_rid("BBB", 2)) == "../requirements-foundation/#bbb-01-002"


def test_published_catalog_row_on_its_own_page_is_in_page(
    registry: SpecRegistry,
) -> None:
    href = requirement_linker(
        registry, PAGES[0].path, pages=PAGES, published=True
    )
    assert href(_rid("AAA", 1)) == "#aaa-01-001"


@pytest.mark.spec("DF-12-002")
def test_full_page_links_the_in_page_catalog_copy(
    registry: SpecRegistry,
) -> None:
    href = requirement_linker(registry, FULL_PAGE, pages=PAGES, published=True)
    assert href(_rid("AAA", 1)) == "#aaa-01-001"
    assert href(_rid("BBB", 2)) == "#bbb-01-002"


def test_full_page_before_publishing_links_the_per_kind_row(
    registry: SpecRegistry,
) -> None:
    href = requirement_linker(
        registry, FULL_PAGE, pages=PAGES, published=False
    )
    assert href(_rid("AAA", 1)) == "../../specs/protocol/#aaa-01-001"


def test_other_kinds_link_their_per_kind_row(registry: SpecRegistry) -> None:
    for published in (False, True):
        href = requirement_linker(
            registry, FULL_PAGE, pages=PAGES, published=published
        )
        assert href(_rid("CCC", 1)) == "../../specs/architecture/#ccc-01-001"


def test_unknown_id_has_no_link(registry: SpecRegistry) -> None:
    href = requirement_linker(registry, _SPEC_PAGE, pages=PAGES)
    assert href(_rid("ZZZ", 1)) is None


# ---------------------------------------------------------------------------
# The page being rendered
# ---------------------------------------------------------------------------


def test_current_page_reads_the_hook_variable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(exec_page.EXEC_PAGE_ENV, FULL_PAGE)
    assert current_page() == FULL_PAGE


def test_current_page_outside_a_build_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(exec_page.EXEC_PAGE_ENV, raising=False)
    with pytest.raises(RuntimeError, match=r"exec_page\.py"):
        current_page()


class _File:
    src_uri = FULL_PAGE


class _Page:
    file = _File()


def test_exec_page_hook_records_and_forgets_the_page(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(exec_page.EXEC_PAGE_ENV, raising=False)
    page = _Page()
    assert exec_page.on_pre_page(page, config=None, files=None) is page  # type: ignore[arg-type]
    assert os.environ[exec_page.EXEC_PAGE_ENV] == FULL_PAGE
    exec_page.on_post_build(config=None)  # type: ignore[arg-type]
    assert exec_page.EXEC_PAGE_ENV not in os.environ


def test_exec_page_hook_is_registered() -> None:
    mkdocs_yml = Path(__file__).resolve().parents[3] / "mkdocs.yml"
    assert "vultron/metadata/docs/exec_page.py" in mkdocs_yml.read_text()


def test_published_tier_file_without_a_page_links_its_per_kind_row(
    registry: SpecRegistry,
) -> None:
    """An unplaced file is a placement fault; its rows still get a live link
    rather than none while the fault stands."""
    href = requirement_linker(
        registry, _SPEC_PAGE, pages=PAGES[1:], published=True
    )
    assert href(_rid("AAA", 1)) == "../../specs/protocol/#aaa-01-001"


def test_exec_page_hook_forgets_the_page_after_a_failed_build(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(exec_page.EXEC_PAGE_ENV, FULL_PAGE)
    exec_page.on_build_error(error=RuntimeError("build failed"))
    assert exec_page.EXEC_PAGE_ENV not in os.environ
