"""Tests for vultron.metadata.specs.docs_render.render_for_kind (AC-1).

Covers: priority badges, group/file headers, behavioral ECA blocks,
cross-kind relationship links, ValueError for an unknown kind, the notice
for a kind no spec carries yet,
and SpecTag.BEHAVIORAL detection.
"""

import ast
import posixpath
import re
from pathlib import Path

import pytest
import yaml

from vultron.metadata.docs.anchor_ids import anchor_ids_in
from vultron.metadata.docs.exec_page import EXEC_PAGE_ENV
from vultron.metadata.docs.requirement_catalog import (
    CATALOG_PAGES,
    FULL_PAGE,
    CatalogPage,
    NotInCatalogError,
    kind_page,
)
from vultron.metadata.docs.site_urls import url_path
from vultron.metadata.specs.docs_render import (
    _REL_LABEL,
    render_catalog_page,
    render_for_kind,
    render_requirement_row,
    requirement_callout,
)
from vultron.metadata.specs.registry import load_registry
from vultron.metadata.specs.schema import RelationType, SpecKind, SpecTag

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

GENERAL_YAML = {
    "id": "GEN",
    "title": "General Test Specs",
    "description": "A general kind spec for testing docs_render",
    "scope": ["production"],
    "groups": [
        {
            "id": "GEN-01",
            "title": "General Group",
            "description": "Tests the general kind page renderer",
            "specs": [
                {
                    "id": "GEN-01-001",
                    "priority": "MUST",
                    "kind": "protocol",
                    "statement": "GEN-01-001 MUST render correctly",
                    "rationale": "Required for docs coverage",
                },
                {
                    "id": "GEN-01-002",
                    "priority": "SHOULD",
                    "kind": "protocol",
                    "statement": "GEN-01-002 SHOULD appear with a badge",
                    "rationale": "Because testing.",
                    "relationships": [
                        {
                            "rel_type": "satisfies",
                            "spec_id": "GEN-01-001",
                        }
                    ],
                },
                {
                    "id": "GEN-01-003",
                    "priority": "MAY",
                    "kind": "protocol",
                    "statement": "GEN-01-003 MAY be optional",
                    "rationale": "Because testing.",
                },
                {
                    "id": "GEN-01-004",
                    "priority": "MUST_NOT",
                    "kind": "protocol",
                    "statement": "GEN-01-004 MUST NOT do the bad thing",
                    "rationale": "Because testing.",
                },
                {
                    "id": "GEN-01-005",
                    "priority": "SHOULD_NOT",
                    "kind": "protocol",
                    "statement": "GEN-01-005 SHOULD NOT be used",
                    "rationale": "Because testing.",
                },
            ],
        }
    ],
}

DOMAIN_YAML = {
    "id": "DOM",
    "title": "Domain Test Specs",
    "description": "A domain kind spec with relationships",
    "scope": ["production"],
    "groups": [
        {
            "id": "DOM-01",
            "title": "Domain Group",
            "specs": [
                {
                    "id": "DOM-01-001",
                    "priority": "MUST",
                    "kind": "architecture",
                    "statement": "DOM-01-001 MUST cross-reference GEN-01-001",
                    "rationale": "Because testing.",
                    "relationships": [
                        {
                            "rel_type": "satisfies",
                            "spec_id": "GEN-01-001",
                            "note": "fulfills the general rule",
                        }
                    ],
                }
            ],
        }
    ],
}

BEHAVIORAL_YAML = {
    "id": "BHV",
    "title": "Behavioral Test Specs",
    "description": "A domain spec with BehavioralSpec items",
    "tags": ["behavioral"],
    "scope": ["production"],
    "groups": [
        {
            "id": "BHV-01",
            "title": "Behavioral Group",
            "trigger": {"type": "message_received", "value": "EP"},
            "specs": [
                {
                    "id": "BHV-01-001",
                    "priority": "MUST",
                    "kind": "protocol",
                    "statement": "BHV-01-001 MUST fire on EP",
                    "rationale": "Because testing.",
                    "preconditions": [
                        {
                            "rm_state": ["ACCEPTED"],
                            "em_state": ["NONE"],
                            "cs_pattern": "vfd...",
                            "description": "Actor is in RM Accepted, EM None, CS matches vfd...",
                        }
                    ],
                    "steps": [
                        {
                            "order": 1,
                            "actor": "Participant",
                            "action": "Propose embargo",
                            "expected": "EM transitions to PROPOSED",
                        }
                    ],
                    "postconditions": [
                        {"description": "EM state is PROPOSED"}
                    ],
                }
            ],
        }
    ],
}


@pytest.fixture
def general_registry(tmp_path):
    (tmp_path / "gen.yaml").write_text(yaml.dump(GENERAL_YAML))
    return load_registry(tmp_path)


@pytest.fixture
def cross_kind_registry(tmp_path):
    (tmp_path / "gen.yaml").write_text(yaml.dump(GENERAL_YAML))
    (tmp_path / "dom.yaml").write_text(yaml.dump(DOMAIN_YAML))
    return load_registry(tmp_path)


@pytest.fixture
def behavioral_registry(tmp_path):
    (tmp_path / "dom.yaml").write_text(yaml.dump(DOMAIN_YAML))
    (tmp_path / "bhv.yaml").write_text(yaml.dump(BEHAVIORAL_YAML))
    return load_registry(tmp_path)


# ---------------------------------------------------------------------------
# ValueError for an unknown kind; a notice for an empty one
# ---------------------------------------------------------------------------


def test_render_for_kind_unknown_raises(general_registry):
    with pytest.raises(ValueError, match="Unknown SpecKind"):
        render_for_kind("nonexistent-kind", general_registry)


def test_render_for_kind_with_no_specs_renders_a_notice(general_registry):
    """A valid kind no spec carries renders a notice, not an error.

    Every kind has a page (test_kind_page_coverage.py), and a new kind such as
    ``foundation`` has no specs until the corpus is swept (ADR-0134), so the
    docs build must not fail on it.
    """
    output = render_for_kind("process", general_registry)
    assert "No requirements yet" in output
    assert "`kind: process`" in output
    assert "<h2" not in output and "##" not in output


# ---------------------------------------------------------------------------
# Priority badges
# ---------------------------------------------------------------------------


def test_render_for_kind_must_badge(general_registry):
    md = render_for_kind("protocol", general_registry)
    assert "**MUST**" in md


def test_render_for_kind_should_badge(general_registry):
    md = render_for_kind("protocol", general_registry)
    assert "**SHOULD**" in md


def test_render_for_kind_may_badge(general_registry):
    md = render_for_kind("protocol", general_registry)
    assert "**MAY**" in md


def test_render_for_kind_must_not_badge(general_registry):
    md = render_for_kind("protocol", general_registry)
    assert "**MUST NOT**" in md


def test_render_for_kind_should_not_badge(general_registry):
    md = render_for_kind("protocol", general_registry)
    assert "**SHOULD NOT**" in md


# ---------------------------------------------------------------------------
# Structure: file H2, group H3, spec IDs, statements
# ---------------------------------------------------------------------------


def test_render_for_kind_file_title_h2(general_registry):
    md = render_for_kind("protocol", general_registry)
    assert "## General Test Specs" in md


@pytest.mark.spec("SR-01-003")
def test_render_for_kind_prints_file_id_without_version(general_registry):
    md = render_for_kind("protocol", general_registry)
    assert "*File ID*: `GEN`" in md
    assert "Version" not in md


def test_render_for_kind_group_title_h3(general_registry):
    md = render_for_kind("protocol", general_registry)
    assert "### General Group" in md


def test_render_for_kind_spec_id_in_output(general_registry):
    md = render_for_kind("protocol", general_registry)
    assert "GEN-01-001" in md


def test_render_for_kind_statement_in_output(general_registry):
    md = render_for_kind("protocol", general_registry)
    assert "MUST render correctly" in md


def test_render_for_kind_rationale_in_output(general_registry):
    md = render_for_kind("protocol", general_registry)
    assert "Required for docs coverage" in md


def test_render_for_kind_anchors_present(general_registry):
    md = render_for_kind("protocol", general_registry)
    assert 'id="gen-01-001"' in md


# ---------------------------------------------------------------------------
# Cross-kind relationship links
# ---------------------------------------------------------------------------

#: A Related-cell link as rendered: ``[ID](#id)`` on the same kind page or
#: ``[ID](../<slug>/#id)`` on another. Requirement IDs are upper-case with
#: two-digit group and three-digit item parts.
_CROSS_LINK_RE = re.compile(
    r"\[(?P<id>[A-Z][A-Z0-9]{1,7}-\d{2}-\d{3})\]"
    r"\((?:\.\./(?P<slug>[a-z]+)/)?#(?P<fragment>[a-z0-9-]+)\)"
)


def test_render_for_kind_cross_links_resolve():
    """Every ``#fragment`` the Related column prints exists on its target page.

    The ``anchor_ids`` hook makes exec-emitted ids *linkable*, but MkDocs
    never sees a link an exec block prints, so nothing in the build validates
    the Related column (``notes/documentation-strategy.md`` § "Exec-Block
    Anchors Are Invisible to --strict, Too"). This test is that check, over
    the real ``specs/`` registry and every kind page. SR-09-002 routes a
    requirement to its own kind's page only, so a same-page ``#x`` must be an
    id on this page and a ``../slug/#x`` an id on that slug's page. Zero
    collected links is a failure, not a pass (DF-09-009).
    """
    registry = load_registry()
    pages = {
        kind.value: render_for_kind(kind.value, registry) for kind in SpecKind
    }
    # The hook's own collector, so the test and the build agree on what an
    # id is; ids here are raw HTML in the markdown the exec block prints.
    ids = {slug: anchor_ids_in(md) for slug, md in pages.items()}

    links = 0
    dangling: list[str] = []
    for slug, md in pages.items():
        for match in _CROSS_LINK_RE.finditer(md):
            links += 1
            target = match.group("slug") or slug
            fragment = match.group("fragment")
            if target not in ids:
                dangling.append(f"{slug}: {match.group(0)} -> unknown page")
            elif fragment not in ids[target]:
                dangling.append(
                    f"{slug}: {match.group(0)} -> no id on {target}"
                )

    assert links > 0, "no Related-cell links collected; the pattern is stale"
    assert not dangling, "\n".join(dangling)


def test_cross_link_pattern_matches_both_forms(cross_kind_registry):
    """Guard the regex above against drift in the Related-cell link output."""
    same = render_for_kind("protocol", cross_kind_registry)
    other = render_for_kind("architecture", cross_kind_registry)
    same_hits = [m.groupdict() for m in _CROSS_LINK_RE.finditer(same)]
    other_hits = [m.groupdict() for m in _CROSS_LINK_RE.finditer(other)]
    assert {"id": "GEN-01-001", "slug": None, "fragment": "gen-01-001"} in (
        same_hits
    )
    assert {
        "id": "GEN-01-001",
        "slug": "protocol",
        "fragment": "gen-01-001",
    } in other_hits


def test_render_for_kind_same_kind_link(cross_kind_registry):
    """Relationship to a spec on the same kind page uses a bare anchor."""
    md = render_for_kind("protocol", cross_kind_registry)
    assert "#gen-01-001" in md


def test_render_for_kind_cross_kind_link(cross_kind_registry):
    """Relationship to a spec on a different kind page uses a relative URL."""
    md = render_for_kind("architecture", cross_kind_registry)
    assert "../protocol/#gen-01-001" in md


def test_render_for_kind_relationship_label(cross_kind_registry):
    md = render_for_kind("architecture", cross_kind_registry)
    assert "Satisfies" in md


def test_every_relation_type_has_a_label():
    """A new RelationType member must not render as its raw value."""
    assert set(_REL_LABEL) == set(RelationType)


def test_render_for_kind_relationship_note(cross_kind_registry):
    md = render_for_kind("architecture", cross_kind_registry)
    assert "fulfills the general rule" in md


# ---------------------------------------------------------------------------
# Behavioral ECA block
# ---------------------------------------------------------------------------


def test_render_for_kind_behavioral_section_header(behavioral_registry):
    md = render_for_kind("protocol", behavioral_registry)
    assert "## Behavioral Specifications" in md


def test_render_for_kind_eca_details_block(behavioral_registry):
    md = render_for_kind("protocol", behavioral_registry)
    assert "<details><summary>ECA Details</summary>" in md


def test_render_for_kind_precondition_text(behavioral_registry):
    md = render_for_kind("protocol", behavioral_registry)
    assert "Actor is in RM Accepted" in md


def test_render_for_kind_precondition_rm_state(behavioral_registry):
    md = render_for_kind("protocol", behavioral_registry)
    assert "RM state: `ACCEPTED`" in md


def test_render_for_kind_precondition_cs_pattern(behavioral_registry):
    md = render_for_kind("protocol", behavioral_registry)
    assert "CS pattern: `vfd...`" in md


def test_render_for_kind_step_text(behavioral_registry):
    md = render_for_kind("protocol", behavioral_registry)
    assert "Propose embargo" in md


def test_render_for_kind_step_expected(behavioral_registry):
    md = render_for_kind("protocol", behavioral_registry)
    assert "EM transitions to PROPOSED" in md


def test_render_for_kind_postcondition_text(behavioral_registry):
    md = render_for_kind("protocol", behavioral_registry)
    assert "EM state is PROPOSED" in md


def test_render_for_kind_trigger_line(behavioral_registry):
    md = render_for_kind("protocol", behavioral_registry)
    assert "Message Received" in md
    assert "`EP`" in md


# ---------------------------------------------------------------------------
# SpecTag.BEHAVIORAL enum value
# ---------------------------------------------------------------------------


def test_spec_tag_behavioral_value():
    assert SpecTag.BEHAVIORAL == "behavioral"


def test_spec_tag_behavioral_in_enum():
    assert SpecTag.BEHAVIORAL in list(SpecTag)


# ---------------------------------------------------------------------------
# SpecFile.tags field acceptance
# ---------------------------------------------------------------------------


def test_spec_file_tags_field_accepted(behavioral_registry):
    bhv_file = next(f for f in behavioral_registry.files if f.id == "BHV")
    assert bhv_file.tags is not None
    assert SpecTag.BEHAVIORAL in bhv_file.tags


def test_spec_file_tags_none_by_default(general_registry):
    gen_file = general_registry.files[0]
    assert gen_file.tags is None


# ---------------------------------------------------------------------------
# BehavioralSpec validator does not shadow StatementSpec validator
# ---------------------------------------------------------------------------


def test_behavioral_spec_empty_scope_raises():
    """BehavioralSpec must still reject scope=[] (parent validator not shadowed)."""
    from vultron.metadata.specs.schema import BehavioralSpec, RFC2119Priority

    with pytest.raises(Exception):  # noqa: B017  # ruff-baseline #3353
        BehavioralSpec(
            id="BHV-01-001",
            priority=RFC2119Priority.MUST,
            kind=SpecKind.PROTOCOL,
            statement="test",
            rationale="Because testing.",
            scope=[],
        )


def test_behavioral_spec_empty_preconditions_raises():
    """BehavioralSpec rejects preconditions=[] via its own validator."""
    from vultron.metadata.specs.schema import (
        BehavioralSpec,
        RFC2119Priority,
        Scope,
    )

    with pytest.raises(Exception):  # noqa: B017  # ruff-baseline #3353
        BehavioralSpec(
            id="BHV-01-001",
            priority=RFC2119Priority.MUST,
            kind=SpecKind.PROTOCOL,
            statement="test",
            rationale="Because testing.",
            scope=[Scope.PRODUCTION],
            preconditions=[],
        )


# ---------------------------------------------------------------------------
# Table structure: header row and separator
# ---------------------------------------------------------------------------


def test_render_for_kind_table_header_present(general_registry):
    md = render_for_kind("protocol", general_registry)
    assert "| ID | Priority | Requirement | Related |" in md


def test_render_for_kind_table_separator_present(general_registry):
    md = render_for_kind("protocol", general_registry)
    assert "|---|---|---|---|" in md


# ---------------------------------------------------------------------------
# Pipe-char escaping in cell content
# ---------------------------------------------------------------------------

PIPE_YAML = {
    "id": "PIP",
    "title": "Pipe Test Specs",
    "description": "Spec with a pipe char in the statement",
    "scope": ["production"],
    "groups": [
        {
            "id": "PIP-01",
            "title": "Pipe Group",
            "specs": [
                {
                    "id": "PIP-01-001",
                    "priority": "MUST",
                    "kind": "protocol",
                    "statement": "Do A | B",
                    "rationale": "Because testing.",
                }
            ],
        }
    ],
}


@pytest.fixture
def pipe_registry(tmp_path):
    (tmp_path / "pip.yaml").write_text(__import__("yaml").dump(PIPE_YAML))
    return load_registry(tmp_path)


def test_render_for_kind_pipe_char_escaped(pipe_registry):
    md = render_for_kind("protocol", pipe_registry)
    assert "&#124;" in md
    assert "Do A | B" not in md


# ---------------------------------------------------------------------------
# Multi-relationship Related cell uses <br> separator
# ---------------------------------------------------------------------------

MULTI_REL_YAML = {
    "id": "MRL",
    "title": "Multi-Rel Specs",
    "description": "Spec with two relationships",
    "scope": ["production"],
    "groups": [
        {
            "id": "MRL-01",
            "title": "Multi-Rel Group",
            "specs": [
                {
                    "id": "MRL-01-001",
                    "priority": "MUST",
                    "kind": "protocol",
                    "statement": "MRL base requirement",
                    "rationale": "Because testing.",
                },
                {
                    "id": "MRL-01-002",
                    "priority": "SHOULD",
                    "kind": "protocol",
                    "statement": "MRL multi-rel spec",
                    "rationale": "Because testing.",
                    "relationships": [
                        {"rel_type": "satisfies", "spec_id": "MRL-01-001"},
                        {"rel_type": "implements", "spec_id": "MRL-01-001"},
                    ],
                },
            ],
        }
    ],
}


@pytest.fixture
def multi_rel_registry(tmp_path):
    (tmp_path / "mrl.yaml").write_text(__import__("yaml").dump(MULTI_REL_YAML))
    return load_registry(tmp_path)


def test_render_for_kind_multi_relationship_br_separator(multi_rel_registry):
    md = render_for_kind("protocol", multi_rel_registry)
    # Two relationships in one cell must be joined with <br>
    assert "<br>" in md


# ---------------------------------------------------------------------------
# Material icon badges (distinct per RFC 2119 level)
# ---------------------------------------------------------------------------


def test_render_for_kind_must_material_icon(general_registry):
    md = render_for_kind("protocol", general_registry)
    assert ":material-check-all:" in md


def test_render_for_kind_must_not_material_icon(general_registry):
    md = render_for_kind("protocol", general_registry)
    assert ":material-cancel:" in md


def test_render_for_kind_should_material_icon(general_registry):
    md = render_for_kind("protocol", general_registry)
    assert ":material-check:" in md


def test_render_for_kind_should_not_material_icon(general_registry):
    md = render_for_kind("protocol", general_registry)
    assert ":material-alert-outline:" in md


def test_render_for_kind_may_material_icon(general_registry):
    md = render_for_kind("protocol", general_registry)
    assert ":material-information-outline:" in md


# ---------------------------------------------------------------------------
# All SpecKind values produce output via real registry
# ---------------------------------------------------------------------------


def _carried_kinds(registry) -> set[SpecKind]:
    return {spec.kind for spec in registry.all_specs.values()}


@pytest.mark.spec_corpus
@pytest.mark.parametrize("kind", list(SpecKind))
def test_render_for_kind_real_registry_produces_output(
    kind: SpecKind, real_registry
):
    """Every SpecKind some spec carries renders its spec IDs."""
    if kind not in _carried_kinds(real_registry):
        pytest.skip(f"no spec carries kind {kind.value!r} yet")
    md = render_for_kind(kind.value, real_registry)
    assert re.search(r"[A-Z]{2,8}-\d{2}-\d{3}", md), (
        f"No spec IDs found in rendered output for kind={kind.value!r}"
    )


@pytest.mark.spec_corpus
@pytest.mark.parametrize("kind", list(SpecKind))
def test_render_for_kind_real_registry_empty_kind_shows_notice(
    kind: SpecKind, real_registry
):
    """A SpecKind no spec carries yet renders the notice, so its page builds.

    ``foundation`` carries no spec until the corpus sweep relabels the
    inherited-standard rules (ADR-0134).
    """
    if kind in _carried_kinds(real_registry):
        pytest.skip(f"kind {kind.value!r} has specs")
    assert "No requirements yet" in render_for_kind(kind.value, real_registry)


# ---------------------------------------------------------------------------
# SR-09-001 / SR-09-002: effective-kind routing for mixed-kind files/groups
# ---------------------------------------------------------------------------

# A file-level kind=general file where one group has kind=project
# and another inherits general.  The project page should show the
# overriding group; the general page should show the inherited-kind group
# but suppress the implementation item.
MIXED_KIND_FILE_YAML = {
    "id": "MIX",
    "title": "Mixed Kind Specs",
    "description": "File with general and implementation items",
    "scope": ["production"],
    "groups": [
        {
            "id": "MIX-01",
            "title": "General Group",
            "specs": [
                {
                    "id": "MIX-01-001",
                    "priority": "MUST",
                    "kind": "protocol",
                    "statement": "MIX-01-001 is general",
                    "rationale": "Because testing.",
                },
            ],
        },
        {
            "id": "MIX-02",
            "title": "Implementation Group",
            "specs": [
                {
                    "id": "MIX-02-001",
                    "priority": "MUST",
                    "kind": "project",
                    "statement": "MIX-02-001 is implementation-specific",
                    "rationale": "Because testing.",
                },
            ],
        },
    ],
}

# File kind=general with one group that has mixed-kind items.
MIXED_KIND_GROUP_YAML = {
    "id": "MGR",
    "title": "Mixed Group Items",
    "description": "File with a group containing items of mixed kinds",
    "scope": ["production"],
    "groups": [
        {
            "id": "MGR-01",
            "title": "Mixed Item Group",
            "specs": [
                {
                    "id": "MGR-01-001",
                    "priority": "MUST",
                    "kind": "protocol",
                    "statement": "MGR-01-001 is general",
                    "rationale": "Because testing.",
                },
                {
                    "id": "MGR-01-002",
                    "priority": "SHOULD",
                    "kind": "project",
                    "statement": "MGR-01-002 is implementation",
                    "rationale": "Because testing.",
                },
            ],
        },
    ],
}

# A second file that provides the implementation kind so render_for_kind
# doesn't raise "No spec files with kind=project".
IMPL_ANCHOR_YAML = {
    "id": "IMP",
    "title": "Implementation Anchor",
    "description": "Provides implementation-kind items for the test registry",
    "scope": ["production"],
    "groups": [
        {
            "id": "IMP-01",
            "title": "Implementation Group",
            "specs": [
                {
                    "id": "IMP-01-001",
                    "priority": "MUST",
                    "kind": "project",
                    "statement": "IMP-01-001 is implementation",
                    "rationale": "Because testing.",
                },
            ],
        },
    ],
}


@pytest.fixture
def mixed_kind_file_registry(tmp_path):
    (tmp_path / "mix.yaml").write_text(yaml.dump(MIXED_KIND_FILE_YAML))
    (tmp_path / "imp.yaml").write_text(yaml.dump(IMPL_ANCHOR_YAML))
    return load_registry(tmp_path)


@pytest.fixture
def mixed_kind_group_registry(tmp_path):
    (tmp_path / "mgr.yaml").write_text(yaml.dump(MIXED_KIND_GROUP_YAML))
    (tmp_path / "imp.yaml").write_text(yaml.dump(IMPL_ANCHOR_YAML))
    return load_registry(tmp_path)


def test_group_kind_override_appears_on_overridden_kind_page(
    mixed_kind_file_registry,
):
    """SR-09-001: a group with kind=project must appear on the
    project page even though its file has kind=general."""
    md = render_for_kind("project", mixed_kind_file_registry)
    assert "MIX-02-001" in md, (
        "Item from group with kind=project should appear on project page"
    )


def test_group_kind_override_absent_from_wrong_kind_page(
    mixed_kind_file_registry,
):
    """SR-09-002: a group with kind=project must NOT appear on the
    general page."""
    md = render_for_kind("protocol", mixed_kind_file_registry)
    assert "MIX-02-001" not in md, (
        "Item from group with kind=project should NOT appear on general page"
    )


def test_inherited_kind_group_appears_on_file_kind_page(
    mixed_kind_file_registry,
):
    """SR-09-001: a group that inherits file kind=general appears on the
    general page."""
    md = render_for_kind("protocol", mixed_kind_file_registry)
    assert "MIX-01-001" in md, (
        "Item inheriting file kind=general should appear on general page"
    )


def test_item_kind_override_appears_on_overridden_page(
    mixed_kind_group_registry,
):
    """SR-09-001: an item with kind=project appears on the
    project page even though its group and file have kind=general."""
    md = render_for_kind("project", mixed_kind_group_registry)
    assert "MGR-01-002" in md, (
        "Item with kind=project should appear on project page"
    )


def test_item_kind_override_suppressed_on_wrong_page(
    mixed_kind_group_registry,
):
    """SR-09-002: an item with kind=project is suppressed on the
    general page while the rest of the group still renders."""
    md = render_for_kind("protocol", mixed_kind_group_registry)
    assert "MGR-01-001" in md, (
        "General item should still appear on general page"
    )
    assert "MGR-01-002" not in md, (
        "Implementation item must be suppressed on the general page"
    )


def test_mixed_group_appears_on_both_kind_pages(mixed_kind_group_registry):
    """SR-09-002: a group with mixed-kind items appears on both the general
    and project pages (with different items visible on each)."""
    gen_md = render_for_kind("protocol", mixed_kind_group_registry)
    impl_md = render_for_kind("project", mixed_kind_group_registry)
    # The group heading must appear on both pages
    assert "MGR-01" in gen_md
    assert "MGR-01" in impl_md


# ---------------------------------------------------------------------------
# Shared row renderer, catalog pages and callouts (#4895)
# ---------------------------------------------------------------------------

_CATALOG_PAGES = (
    CatalogPage("general", "General", SpecKind.PROTOCOL, ("GEN", "BHV")),
    CatalogPage("foundation", "Inherited", SpecKind.FOUNDATION, ()),
)
_CALLOUT_PAGE = "reference/vultron-spec/considerations.md"


@pytest.fixture
def catalog_registry(tmp_path):
    for name, data in (
        ("gen", GENERAL_YAML),
        ("dom", DOMAIN_YAML),
        ("bhv", BEHAVIORAL_YAML),
    ):
        (tmp_path / f"{name}.yaml").write_text(yaml.dump(data))
    return load_registry(tmp_path)


def test_row_defining_anchor(cross_kind_registry):
    spec = cross_kind_registry.get("GEN-01-002")
    row = render_requirement_row(
        spec, lambda i: f"#{i.lower()}", define_anchor=True
    )
    assert row.startswith('| <a id="gen-01-002"></a>`GEN-01-002` |')
    assert "[GEN-01-001](#gen-01-001)" in row


@pytest.mark.spec("DF-12-002")
def test_row_linking_anchor_defines_none(cross_kind_registry):
    spec = cross_kind_registry.get("GEN-01-002")
    row = render_requirement_row(
        spec, lambda i: f"x/#{i.lower()}", define_anchor=False
    )
    assert row.startswith("| [`GEN-01-002`](x/#gen-01-002) |")
    assert "<a id=" not in row


def test_row_without_link_target_shows_plain_id(cross_kind_registry):
    spec = cross_kind_registry.get("GEN-01-002")
    row = render_requirement_row(spec, lambda i: None, define_anchor=False)
    assert row.startswith("| `GEN-01-002` |")
    assert "*Satisfies*: GEN-01-001" in row


def test_per_kind_and_catalog_rows_are_one_format(catalog_registry):
    """The per-kind page and the catalog print the same row (AC-1)."""
    kind_md = render_for_kind("protocol", catalog_registry)
    catalog_md = render_catalog_page(
        "general",
        catalog_registry,
        page="reference/specs/protocol.md",
        pages=_CATALOG_PAGES,
    )
    kind_rows = {
        line for line in kind_md.splitlines() if line.startswith("| <a")
    }
    catalog_rows = {
        line for line in catalog_md.splitlines() if line.startswith("| <a")
    }
    assert kind_rows and kind_rows == catalog_rows


@pytest.mark.spec("DF-12-008")
def test_catalog_page_has_one_subsection_per_file(catalog_registry):
    md = render_catalog_page(
        "general",
        catalog_registry,
        page="reference/vultron-spec/requirements-general.md",
        pages=_CATALOG_PAGES,
        published=True,
    )
    assert "### General Test Specs {#protocol-gen}" in md
    assert "#### General Group {#protocol-gen-01}" in md
    assert "### Behavioral Test Specs {#protocol-bhv}" in md
    assert md.index("{#protocol-gen}") < md.index("{#protocol-bhv}")
    assert '<a id="gen-01-001"></a>' in md
    assert "*Trigger*: Message Received — `EP`" in md
    assert "ECA Details" in md
    # A same-page relationship is in-page once the catalog is published.
    assert "[GEN-01-001](#gen-01-001)" in md
    # The architecture file is placed on no catalog page.
    assert "DOM-01-001" not in md


def test_catalog_page_shows_only_its_tier(tmp_path):
    mixed = {
        **GENERAL_YAML,
        "groups": [
            {
                **GENERAL_YAML["groups"][0],
                "specs": [
                    GENERAL_YAML["groups"][0]["specs"][0],
                    {
                        **GENERAL_YAML["groups"][0]["specs"][1],
                        "kind": "foundation",
                    },
                ],
            }
        ],
    }
    (tmp_path / "gen.yaml").write_text(yaml.dump(mixed))
    registry = load_registry(tmp_path)
    pages = (
        CatalogPage("general", "General", SpecKind.PROTOCOL, ("GEN",)),
        CatalogPage("foundation", "Inherited", SpecKind.FOUNDATION, ("GEN",)),
    )
    protocol_md = render_catalog_page(
        "general", registry, page="x.md", pages=pages
    )
    foundation_md = render_catalog_page(
        "foundation", registry, page="x.md", pages=pages
    )
    assert '<a id="gen-01-001"></a>' in protocol_md
    assert "GEN-01-002" not in protocol_md
    assert '<a id="gen-01-002"></a>' in foundation_md
    assert '<a id="gen-01-001"></a>' not in foundation_md
    # Distinct heading ids, so full.md (which includes both) has no duplicate.
    assert "{#protocol-gen-01}" in protocol_md
    assert "{#foundation-gen-01}" in foundation_md


def test_catalog_page_unknown_key_raises(catalog_registry):
    with pytest.raises(KeyError, match="no catalog page 'nope'"):
        render_catalog_page(
            "nope", catalog_registry, page="x.md", pages=_CATALOG_PAGES
        )


def test_catalog_page_with_missing_file_raises(catalog_registry):
    pages = (CatalogPage("general", "G", SpecKind.PROTOCOL, ("ZZZ",)),)
    with pytest.raises(ValueError, match="places ZZZ"):
        render_catalog_page(
            "general", catalog_registry, page="x.md", pages=pages
        )


@pytest.mark.spec("DF-12-011")
def test_catalog_page_on_full_page_links_in_page(catalog_registry):
    md = render_catalog_page(
        "general",
        catalog_registry,
        page=FULL_PAGE,
        pages=_CATALOG_PAGES,
        published=True,
    )
    assert "[GEN-01-001](#gen-01-001)" in md


def test_catalog_page_defaults_to_the_page_being_built(
    catalog_registry, monkeypatch
):
    monkeypatch.setenv(EXEC_PAGE_ENV, FULL_PAGE)
    md = render_catalog_page(
        "general", catalog_registry, pages=_CATALOG_PAGES, published=True
    )
    assert "[GEN-01-001](#gen-01-001)" in md


@pytest.mark.spec("DF-12-003", "DF-12-010")
def test_callout_is_an_info_admonition_linking_rows(catalog_registry):
    md = requirement_callout(
        "GEN-01-002",
        "GEN-01-001",
        registry=catalog_registry,
        page=_CALLOUT_PAGE,
        pages=_CATALOG_PAGES,
        published=True,
    )
    lines = md.splitlines()
    assert lines[0] == '!!! info "Requirements"'
    assert lines[1] == ""
    assert lines[2] == "    | ID | Priority | Requirement | Related |"
    assert lines[4].startswith(
        "    | [`GEN-01-002`](../requirements-general/#gen-01-002) |"
    )
    assert lines[5].startswith(
        "    | [`GEN-01-001`](../requirements-general/#gen-01-001) |"
    )
    assert "<a id=" not in md


def test_callout_title(catalog_registry):
    md = requirement_callout(
        "GEN-01-001",
        title="Context",
        registry=catalog_registry,
        page=_CALLOUT_PAGE,
        pages=_CATALOG_PAGES,
    )
    assert md.startswith('!!! info "Context"\n')


def test_callout_before_publishing_links_the_per_kind_row(catalog_registry):
    md = requirement_callout(
        "GEN-01-001",
        registry=catalog_registry,
        page=_CALLOUT_PAGE,
        pages=_CATALOG_PAGES,
        published=False,
    )
    assert "[`GEN-01-001`](../../specs/protocol/#gen-01-001)" in md


@pytest.mark.spec("DF-12-011")
def test_callout_on_full_page_links_in_page(catalog_registry, monkeypatch):
    monkeypatch.setenv(EXEC_PAGE_ENV, FULL_PAGE)
    md = requirement_callout(
        "GEN-01-002",
        registry=catalog_registry,
        pages=_CATALOG_PAGES,
        published=True,
    )
    assert "[`GEN-01-002`](#gen-01-002)" in md
    assert "[GEN-01-001](#gen-01-001)" in md


@pytest.mark.spec("DF-12-012")
def test_callout_refuses_another_kind(catalog_registry):
    with pytest.raises(NotInCatalogError, match="architecture requirement"):
        requirement_callout(
            "DOM-01-001",
            registry=catalog_registry,
            page=_CALLOUT_PAGE,
            pages=_CATALOG_PAGES,
        )


def test_callout_refuses_unknown_id(catalog_registry):
    with pytest.raises(NotInCatalogError, match="names no requirement"):
        requirement_callout(
            "GEN-09-001",
            registry=catalog_registry,
            page=_CALLOUT_PAGE,
            pages=_CATALOG_PAGES,
        )


def test_callout_refuses_no_id(catalog_registry):
    with pytest.raises(ValueError, match="at least one ID"):
        requirement_callout(registry=catalog_registry, page=_CALLOUT_PAGE)


def test_callout_refuses_a_repeated_id(catalog_registry):
    with pytest.raises(ValueError, match="repeats GEN-01-001"):
        requirement_callout(
            "GEN-01-001",
            "GEN-01-001",
            registry=catalog_registry,
            page=_CALLOUT_PAGE,
            pages=_CATALOG_PAGES,
        )


_DOCS = Path(__file__).resolve().parents[3] / "docs"
_EXEC_FENCE_RE = re.compile(
    r'^(?P<indent>\s*)(?P<fence>`{3,}|~{3,})python\b[^\n]*\bexec="true"'
)
_INCLUDE_RE = re.compile(r'\{%\s*include-markdown\s+"([^"]+)"')
_CALLOUT_LINK_RE = re.compile(r"\]\((?P<href>[^)\s]+)\)")


def _exec_blocks(text: str) -> list[str]:
    """Return the code of each ``markdown-exec`` Python block in *text*.

    Only an exec block prints a callout, so prose or a plain code fence that
    names the helper is not one, and a block may spread a call over several
    lines.
    """
    blocks: list[str] = []
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        opener = _EXEC_FENCE_RE.match(lines[i])
        i += 1
        if opener is None:
            continue
        fence, indent = opener.group("fence"), len(opener.group("indent"))
        body: list[str] = []
        while i < len(lines) and not (
            lines[i].strip().startswith(fence[0] * len(fence))
            and set(lines[i].strip()) == {fence[0]}
        ):
            body.append(lines[i][indent:])
            i += 1
        i += 1
        blocks.append("\n".join(body))
    return blocks


def _callout_ids(code: str) -> list[list[str]]:
    """Return the positional ID arguments of each callout call in *code*."""
    calls = [
        node
        for node in ast.walk(ast.parse(code))
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "requirement_callout"
    ]
    found: list[list[str]] = []
    for call in calls:
        ids = [a.value for a in call.args if isinstance(a, ast.Constant)]
        assert len(ids) == len(call.args), f"non-literal callout ID in {code}"
        found.append([str(i) for i in ids])
    return found


def _hosts() -> dict[str, set[str]]:
    """Map each ``docs/`` file to the pages that render it.

    A page renders itself and, transitively, every file it includes. A
    fragment's exec block runs once per page that includes it, so its links
    are relative to each of those pages, not to the fragment's own path.
    """
    includes: dict[str, set[str]] = {}
    for source in _DOCS.rglob("*.md"):
        path = source.relative_to(_DOCS).as_posix()
        includes[path] = {
            posixpath.normpath(posixpath.join(posixpath.dirname(path), target))
            for target in _INCLUDE_RE.findall(
                source.read_text(encoding="utf-8")
            )
        }
    hosts: dict[str, set[str]] = {}
    for page in includes:
        if posixpath.basename(page).startswith("_"):
            continue
        seen: set[str] = set()
        todo = [page]
        while todo:
            current = todo.pop()
            if current in seen:
                continue
            seen.add(current)
            todo.extend(includes.get(current, ()))
        for rendered in seen:
            hosts.setdefault(rendered, set()).add(page)
    return hosts


def _dangling_links(
    md: str, page: str, target_ids: dict[str, frozenset[str]]
) -> list[str]:
    """Return each link in *md*, printed on *page*, whose id is missing."""
    dangling = []
    for match in _CALLOUT_LINK_RE.finditer(md):
        href = match.group("href")
        link, _, fragment = href.partition("#")
        target = posixpath.normpath(posixpath.join(url_path(page), link))
        if fragment not in target_ids.get(f"{target}.md", frozenset()):
            dangling.append(href)
    return dangling


def test_docs_callouts_link_existing_rows():
    """Every requirement callout in ``docs/`` renders, and every link it
    prints lands on an id its target page defines, on every page that
    renders the callout.

    MkDocs never sees a link an exec block prints, so this is the check that
    the callouts link real rows (``anchor_ids.py``). Each callout is
    rendered for each page that includes its fragment, and each link is
    resolved against the rendered ids of the per-kind and catalog pages, so
    the test holds before and after the catalog publishes. Zero callouts is
    a failure (DF-09-009).
    """
    registry = load_registry()
    target_ids = {
        kind_page(kind): anchor_ids_in(render_for_kind(kind.value, registry))
        for kind in SpecKind
    }
    target_ids.update(
        {
            page.path: anchor_ids_in(
                render_catalog_page(page.key, registry, page=page.path)
            )
            for page in CATALOG_PAGES
        }
    )
    hosts = _hosts()
    rendered = 0
    dangling: list[str] = []
    for source in sorted(_DOCS.rglob("*.md")):
        path = source.relative_to(_DOCS).as_posix()
        text = source.read_text(encoding="utf-8")
        for code in _exec_blocks(text):
            callouts = _callout_ids(code)
            assert not callouts or hosts.get(path), (
                f"docs/{path}: no page renders this callout"
            )
            for ids in callouts:
                for page in sorted(hosts[path]):
                    rendered += 1
                    dangling.extend(
                        f"docs/{path} on {page}: {href}"
                        for href in _dangling_links(
                            requirement_callout(
                                *ids, registry=registry, page=page
                            ),
                            page,
                            target_ids,
                        )
                    )
    assert rendered > 0, "no requirement_callout found under docs/"
    assert not dangling, "\n".join(dangling)


def test_callout_hosts_follow_includes():
    """The include walk finds a fragment's pages, nested includes too."""
    hosts = _hosts()
    assert hosts["reference/vultron-spec/_iana.md"] == {
        "reference/vultron-spec/considerations.md",
        "reference/vultron-spec/full.md",
    }
    oq = hosts["reference/vultron-spec/_oq-embargo-termination-authority.md"]
    assert "reference/vultron-spec/open-questions.md" in oq
    assert "topics/future_work/open_questions.md" in oq


def test_callout_ids_reads_positional_literals_only():
    line = (
        "from vultron.metadata.specs.docs_render import requirement_callout; "
        'print(requirement_callout("VM-10-001", "ID-01-001", title="Context"))'
    )
    assert _callout_ids(line) == [["VM-10-001", "ID-01-001"]]


def test_exec_blocks_find_callouts_only_where_they_print():
    """A callout spread over lines, or nested in an admonition, is read;
    prose and a plain code fence that name the helper are not callouts."""
    text = "\n".join(
        [
            'Use `requirement_callout("X-01-001")` to show a rule.',
            "",
            "```python",
            'requirement_callout("X-02-001")',
            "```",
            "",
            '```python exec="true" idprefix=""',
            "from vultron.metadata.specs.docs_render import (",
            "    requirement_callout,",
            ")",
            "",
            'print(requirement_callout("VM-10-001"))',
            "```",
            "",
            '!!! note "Nested"',
            "",
            '    ````python exec="true"',
            '    print(requirement_callout("ID-01-001", "SYNC-03-003"))',
            "    ````",
        ]
    )
    found = [ids for code in _exec_blocks(text) for ids in _callout_ids(code)]
    assert found == [["VM-10-001"], ["ID-01-001", "SYNC-03-003"]]


def test_renderers_default_to_the_repository_registry(monkeypatch):
    """With no registry given, a callout and a catalog page load the
    repository's ``specs/``, once per state of the directory."""
    from vultron.metadata.specs import docs_render

    monkeypatch.setenv(EXEC_PAGE_ENV, _CALLOUT_PAGE)
    monkeypatch.setattr(docs_render, "_registry_cache", {})
    md = requirement_callout("VM-10-001")
    assert "[`VM-10-001`](../../specs/protocol/#vm-10-001)" in md
    [cached] = docs_render._registry_cache.values()
    assert docs_render._docs_registry() is cached
    page = render_catalog_page("foundation")
    assert '<a id="id-01-001"></a>' in page


def test_repository_registry_reloads_when_specs_change(tmp_path, monkeypatch):
    """An edited requirement file reaches the next ``mkdocs serve`` rebuild."""
    import os

    from vultron.metadata.specs import docs_render

    specs = tmp_path / "specs"
    specs.mkdir()
    spec_file = specs / "gen.yaml"
    spec_file.write_text(yaml.dump(GENERAL_YAML))
    monkeypatch.setattr(docs_render, "repo_root", lambda: tmp_path)
    monkeypatch.setattr(docs_render, "_registry_cache", {})
    first = docs_render._docs_registry()
    assert docs_render._docs_registry() is first
    stat = spec_file.stat()
    os.utime(spec_file, ns=(stat.st_atime_ns, stat.st_mtime_ns + 1_000_000))
    second = docs_render._docs_registry()
    assert second is not first
    assert len(docs_render._registry_cache) == 1


def test_dangling_links_flags_a_missing_id():
    """Guard the link test above against passing vacuously."""
    ids = {"reference/specs/protocol.md": frozenset({"vm-10-001"})}
    md = "[a](../../specs/protocol/#vm-10-001) [b](../../specs/protocol/#nope)"
    assert _dangling_links(md, "reference/vultron-spec/x.md", ids) == [
        "../../specs/protocol/#nope"
    ]
