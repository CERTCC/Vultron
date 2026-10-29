"""Tests for vultron.metadata.docs.requirement_links (#4901).

A requirement's anchor is defined only where its row renders: a ``protocol``
or ``foundation`` requirement on its Requirements Catalog page (and that
page's copy on ``full.md``), any other kind on its per-kind page (SR-09-001,
DF-12-002). The first tests are gates on the real ``docs/`` tree: every link
to a requirement targets the page defining its anchor, no link names a
retired tier page, and no page but the catalog and ``full.md`` defines a
catalog anchor. The rest pin the rewrite rules and each fault on small trees.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from vultron.metadata.docs.requirement_catalog import CatalogPage
from vultron.metadata.docs.requirement_links import (
    RequirementLinker,
    anchor_definition_faults,
    retired_page_links,
)
from vultron.metadata.specs.registry import SpecRegistry, load_registry
from vultron.metadata.specs.schema import SpecKind

_DOCS = Path(__file__).resolve().parents[3] / "docs"


# ---------------------------------------------------------------------------
# Gates on the real tree
# ---------------------------------------------------------------------------


def _docs_files() -> list[tuple[str, str]]:
    files = [
        (path.relative_to(_DOCS).as_posix(), path.read_text(encoding="utf-8"))
        for path in sorted(_DOCS.rglob("*.md"))
    ]
    assert files, "no docs/ file found"
    return files


@pytest.mark.spec("DF-12-002", "SR-09-001", "SR-09-002")
def test_every_requirement_link_targets_the_page_defining_it() -> None:
    """Run ``scripts/relink_requirement_anchors.py`` when this fails."""
    linker = RequirementLinker(load_registry())
    stale = [
        rel
        for rel, text in _docs_files()
        if linker.relink(text, rel)[0] != text
    ]
    assert not stale, "\n".join(stale)


@pytest.mark.spec("DF-12-001")
def test_no_link_names_a_retired_tier_page() -> None:
    found = [
        link
        for rel, text in _docs_files()
        for link in retired_page_links(text, rel)
    ]
    assert not found, "\n".join(found)


@pytest.mark.spec("DF-12-002")
def test_only_the_catalog_defines_catalog_anchors() -> None:
    faults = anchor_definition_faults(_DOCS, load_registry())
    assert not faults, "\n".join(faults)


# ---------------------------------------------------------------------------
# A small corpus
# ---------------------------------------------------------------------------


#: Built at run time: spec-lint fails a literal ID the real corpus lacks
#: anywhere outside ``test/metadata/specs/`` (SR-04-008).
T = "TST"


def _item(spec_id: str, kind: str) -> dict:
    return {
        "id": spec_id,
        "priority": "MUST",
        "kind": kind,
        "statement": f"{spec_id} statement",
        "rationale": "Because testing.",
    }


_SPECS = {
    "id": "TST",
    "title": "Test",
    "description": "Test spec file",
    "scope": ["production"],
    "groups": [
        {
            # straddles the catalog and the project page
            "id": "TST-01",
            "title": "Straddling group",
            "specs": [
                _item(f"{T}-01-001", "project"),
                _item(f"{T}-01-002", "project"),
                _item(f"{T}-01-003", "protocol"),
            ],
        },
        {
            "id": "TST-02",
            "title": "Both tiers",
            "specs": [
                _item(f"{T}-02-001", "protocol"),
                _item(f"{T}-02-002", "foundation"),
            ],
        },
        {
            # an even split: SpecKind order breaks the tie toward project
            "id": "TST-03",
            "title": "Tied group",
            "specs": [
                _item(f"{T}-03-001", "process"),
                _item(f"{T}-03-002", "project"),
            ],
        },
        {
            # a letter-suffixed ID is a requirement ID too
            "id": "TST-04",
            "title": "Suffixed group",
            "specs": [
                _item(f"{T}-04-001", "protocol"),
                _item(f"{T}-04-001b", "project"),
            ],
        },
    ],
}

_PAGES = (
    CatalogPage("one", "One", SpecKind.PROTOCOL, ("TST",)),
    CatalogPage("foundation", "Inherited", SpecKind.FOUNDATION, ("TST",)),
)


@pytest.fixture
def registry(tmp_path: Path) -> SpecRegistry:
    specs = tmp_path / "specs"
    specs.mkdir()
    (specs / "tst.yaml").write_text(yaml.dump(_SPECS), encoding="utf-8")
    return load_registry(specs)


@pytest.fixture
def linker(registry: SpecRegistry) -> RequirementLinker:
    return RequirementLinker(registry, _PAGES)


_PAGE = "topics/page.md"
_ONE = "../reference/vultron-spec/requirements/one.md"
_FOUNDATION = "../reference/vultron-spec/requirements/foundation.md"
_PROJECT = "../reference/specs/project.md"


def _relink(linker: RequirementLinker, text: str, path: str = _PAGE) -> str:
    return linker.relink(text, path)[0]


# ---------------------------------------------------------------------------
# Rewrites
# ---------------------------------------------------------------------------


@pytest.mark.spec("DF-12-002")
def test_retired_page_link_moves_to_the_catalog_row(linker) -> None:
    text = f"[{T}-01-003](../reference/specs/protocol.md#tst-01-003)"
    assert _relink(linker, text) == f"[{T}-01-003]({_ONE}#tst-01-003)"


def test_foundation_link_moves_to_the_inherited_page(linker) -> None:
    text = f"[{T}-02-002](../reference/specs/foundation.md#tst-02-002)"
    assert _relink(linker, text) == f"[{T}-02-002]({_FOUNDATION}#tst-02-002)"


def test_group_link_keeps_the_tier_it_named(linker) -> None:
    protocol = "[TST-02](../reference/specs/protocol.md#tst-02)"
    foundation = "[TST-02](../reference/specs/foundation.md#tst-02)"
    assert _relink(linker, protocol) == f"[TST-02]({_ONE}#protocol-tst-02)"
    assert _relink(linker, foundation) == (
        f"[TST-02]({_FOUNDATION}#foundation-tst-02)"
    )


def test_relabeled_requirement_leaves_the_catalog(linker) -> None:
    text = f"[{T}-01-001]({_ONE}#tst-01-001)"
    assert _relink(linker, text) == f"[{T}-01-001]({_PROJECT}#tst-01-001)"


def test_group_without_items_of_the_named_tier_goes_to_the_majority(
    linker,
) -> None:
    text = "[TST-03](../reference/specs/protocol.md#tst-03)"
    assert _relink(linker, text) == f"[TST-03]({_PROJECT}#tst-03)"


def test_file_link_named_on_a_catalog_page_stays_there(linker) -> None:
    text = "[TST](../reference/specs/protocol.md#tst)"
    assert _relink(linker, text) == f"[TST]({_ONE}#protocol-tst)"


def test_link_already_right_is_unchanged(linker) -> None:
    text = (
        f"[{T}-01-003]({_ONE}#tst-01-003) [TST-01]({_PROJECT}#tst-01) "
        f"[TST-01]({_ONE}#protocol-tst-01)"
    )
    assert _relink(linker, text) == text


def test_requirement_cited_by_its_group_is_repointed(linker) -> None:
    text = f"[{T}-01-003](../reference/specs/protocol.md#tst-01)"
    out, stats = linker.relink(text, _PAGE)
    assert out == f"[{T}-01-003]({_ONE}#tst-01-003)"
    assert stats.repointed == 1


def test_id_list_is_split_one_link_per_page(linker) -> None:
    text = f"[{T}-01-001, {T}-01-003](../reference/specs/protocol.md#tst-01)"
    assert _relink(linker, text) == (
        f"[{T}-01-001]({_PROJECT}#tst-01-001), [{T}-01-003]({_ONE}#tst-01-003)"
    )


def test_suffixed_id_is_a_requirement_id(linker) -> None:
    text = f"[{T}-04-001, {T}-04-001b](../reference/specs/protocol.md#tst-04)"
    assert _relink(linker, text) == (
        f"[{T}-04-001]({_ONE}#tst-04-001), "
        f"[{T}-04-001b]({_PROJECT}#tst-04-001b)"
    )


def test_list_naming_another_group_is_not_split(linker) -> None:
    text = f"[{T}-01-003, {T}-02-001]({_ONE}#protocol-tst-01)"
    assert _relink(linker, text) == text


def test_unknown_ids_are_reported_and_left(linker) -> None:
    text = f"[{T}-01-001, {T}-01-008, {T}-01-009](../reference/specs/protocol.md#tst-01)"
    out, stats = linker.relink(text, _PAGE)
    # the group anchor still moves; the list is not split
    assert out == (
        f"[{T}-01-001, {T}-01-008, {T}-01-009]({_ONE}#protocol-tst-01)"
    )
    assert stats.unknown == {f"{T}-01-008": 1, f"{T}-01-009": 1}


def test_unknown_anchor_is_reported_and_left(linker) -> None:
    text = "[Overview](../reference/specs/project.md#overview)"
    out, stats = linker.relink(text, _PAGE)
    assert out == text
    assert stats.unknown == {"#overview": 1}


def test_links_resolve_against_the_file_holding_them(linker) -> None:
    """A fragment's links stay relative to the fragment's own directory."""
    text = f"[{T}-01-003](../../specs/protocol.md#tst-01-003)"
    path = "reference/vultron-spec/_conformance/_x.md"
    assert _relink(linker, text, path) == (
        f"[{T}-01-003](../requirements/one.md#tst-01-003)"
    )


def test_other_pages_and_fenced_code_are_left_alone(linker) -> None:
    text = "\n".join(
        [
            f"[{T}-01-003](../topics/other.md#tst-01-003)",
            "```markdown",
            f"[{T}-01-003](../reference/specs/protocol.md#tst-01-003)",
            "```",
        ]
    )
    assert _relink(linker, text) == text


def test_retired_page_links_finds_links_with_and_without_a_fragment() -> None:
    text = (
        "[a](../reference/specs/protocol.md) "
        "[b](../reference/specs/foundation.md#x) "
        "[c](../reference/specs/project.md)"
    )
    assert retired_page_links(text, _PAGE) == [
        "docs/topics/page.md:1: ../reference/specs/protocol.md",
        "docs/topics/page.md:1: ../reference/specs/foundation.md#x",
    ]


# ---------------------------------------------------------------------------
# Anchor definitions
# ---------------------------------------------------------------------------

_EXEC = '```python exec="true"\n{code}\n```\n'


def _tree(tmp_path: Path, files: dict[str, str]) -> Path:
    docs = tmp_path / "docs"
    for rel, text in files.items():
        path = docs / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return docs


def _sound_catalog() -> dict[str, str]:
    spec = "reference/vultron-spec"
    files: dict[str, str] = {}
    full = ""
    for page in _PAGES:
        frag = page.fragment.removeprefix(f"{spec}/")
        files[page.fragment] = _EXEC.format(
            code=f'print(render_catalog_page("{page.key}"))'
        )
        files[page.path] = f'{{% include-markdown "../{frag}" %}}\n'
        full += f'{{% include-markdown "./{frag}" %}}\n'
    files[f"{spec}/full.md"] = full
    return files


def test_sound_catalog_has_no_anchor_faults(tmp_path, registry) -> None:
    docs = _tree(tmp_path, _sound_catalog())
    assert anchor_definition_faults(docs, registry, _PAGES) == []


@pytest.mark.spec("DF-12-002")
def test_catalog_render_outside_its_fragment_fails(tmp_path, registry) -> None:
    files = _sound_catalog()
    files["topics/x.md"] = _EXEC.format(
        code='print(render_catalog_page("one"))'
    )
    faults = anchor_definition_faults(_tree(tmp_path, files), registry, _PAGES)
    assert faults == [
        "docs/topics/x.md:2: render_catalog_page('one') belongs only in "
        "reference/vultron-spec/_catalog/_one.md"
    ]


@pytest.mark.spec("SR-09-001")
def test_per_kind_render_of_a_catalog_tier_fails(tmp_path, registry) -> None:
    files = _sound_catalog()
    files["reference/specs/protocol.md"] = _EXEC.format(
        code='print(render_for_kind("protocol", registry))'
    )
    faults = anchor_definition_faults(_tree(tmp_path, files), registry, _PAGES)
    assert len(faults) == 1
    assert "render_for_kind('protocol')" in faults[0]


@pytest.mark.parametrize(
    "definition",
    [
        '<a id="tst-01-003"></a>',
        '<a name="tst-01-003"></a>',
        "## Heading {#protocol-tst-01}",
    ],
)
def test_hand_written_catalog_anchor_fails(
    tmp_path, registry, definition
) -> None:
    files = _sound_catalog()
    files["topics/x.md"] = f"{definition}\n"
    faults = anchor_definition_faults(_tree(tmp_path, files), registry, _PAGES)
    assert len(faults) == 1
    assert faults[0].startswith("docs/topics/x.md:1: defines #")


def test_hand_written_anchor_of_another_kind_is_allowed(
    tmp_path, registry
) -> None:
    files = _sound_catalog()
    files["topics/x.md"] = '<a id="tst-01-001"></a>\n'
    docs = _tree(tmp_path, files)
    assert anchor_definition_faults(docs, registry, _PAGES) == []


def test_catalog_fragment_on_another_page_fails(tmp_path, registry) -> None:
    files = _sound_catalog()
    files["topics/x.md"] = (
        '{% include-markdown "../reference/vultron-spec/_catalog/_one.md" %}\n'
    )
    faults = anchor_definition_faults(_tree(tmp_path, files), registry, _PAGES)
    assert len(faults) == 1
    assert "_catalog/_one.md: renders on" in faults[0]
    assert "topics/x.md" in faults[0]


def test_missing_catalog_fragment_fails(tmp_path, registry) -> None:
    files = _sound_catalog()
    del files[_PAGES[0].fragment]
    faults = anchor_definition_faults(_tree(tmp_path, files), registry, _PAGES)
    assert faults == [
        "docs/reference/vultron-spec/_catalog/_one.md: missing catalog fragment"
    ]
