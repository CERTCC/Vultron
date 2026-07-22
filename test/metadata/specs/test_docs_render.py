"""Tests for vultron.metadata.specs.docs_render.render_for_kind (AC-1).

Covers: priority badges, group/file headers, behavioral ECA blocks,
cross-kind relationship links, ValueError for unknown/empty kind,
and SpecTag.BEHAVIORAL detection.
"""

import yaml
import pytest

from vultron.metadata.specs.registry import load_registry
from vultron.metadata.specs.schema import SpecKind, SpecTag
from vultron.metadata.specs.docs_render import render_for_kind

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

GENERAL_YAML = {
    "id": "GEN",
    "title": "General Test Specs",
    "description": "A general kind spec for testing docs_render",
    "version": "0.1",
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
                },
                {
                    "id": "GEN-01-004",
                    "priority": "MUST_NOT",
                    "kind": "protocol",
                    "statement": "GEN-01-004 MUST NOT do the bad thing",
                },
                {
                    "id": "GEN-01-005",
                    "priority": "SHOULD_NOT",
                    "kind": "protocol",
                    "statement": "GEN-01-005 SHOULD NOT be used",
                },
            ],
        }
    ],
}

DOMAIN_YAML = {
    "id": "DOM",
    "title": "Domain Test Specs",
    "description": "A domain kind spec with relationships",
    "version": "0.1",
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
    "version": "0.1",
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
# ValueError for unknown / empty kind
# ---------------------------------------------------------------------------


def test_render_for_kind_unknown_raises(general_registry):
    with pytest.raises(ValueError, match="Unknown SpecKind"):
        render_for_kind("nonexistent-kind", general_registry)


def test_render_for_kind_no_matching_files_raises(general_registry):
    """Requesting a kind with no files should raise ValueError."""
    with pytest.raises(ValueError, match="No spec files with kind"):
        render_for_kind("process", general_registry)


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

    with pytest.raises(Exception):
        BehavioralSpec(
            id="BHV-01-001",
            priority=RFC2119Priority.MUST,
            kind=SpecKind.PROTOCOL,
            statement="test",
            scope=[],
        )


def test_behavioral_spec_empty_preconditions_raises():
    """BehavioralSpec rejects preconditions=[] via its own validator."""
    from vultron.metadata.specs.schema import (
        BehavioralSpec,
        RFC2119Priority,
        Scope,
    )

    with pytest.raises(Exception):
        BehavioralSpec(
            id="BHV-01-001",
            priority=RFC2119Priority.MUST,
            kind=SpecKind.PROTOCOL,
            statement="test",
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
    "version": "0.1",
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
    "version": "0.1",
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
                },
                {
                    "id": "MRL-01-002",
                    "priority": "SHOULD",
                    "kind": "protocol",
                    "statement": "MRL multi-rel spec",
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


@pytest.mark.parametrize("kind", list(SpecKind))
def test_render_for_kind_real_registry_produces_output(kind: SpecKind):
    """Every SpecKind must render non-empty output from the real spec registry."""
    registry = load_registry()
    md = render_for_kind(kind.value, registry)
    assert len(md) > 0
    # At minimum one spec ID pattern should appear
    import re

    assert re.search(
        r"[A-Z]{2,8}-\d{2}-\d{3}", md
    ), f"No spec IDs found in rendered output for kind={kind.value!r}"


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
    "version": "0.1",
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
    "version": "0.1",
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
                },
                {
                    "id": "MGR-01-002",
                    "priority": "SHOULD",
                    "kind": "project",
                    "statement": "MGR-01-002 is implementation",
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
    "version": "0.1",
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
        "Item from group with kind=project should appear on " "project page"
    )


def test_group_kind_override_absent_from_wrong_kind_page(
    mixed_kind_file_registry,
):
    """SR-09-002: a group with kind=project must NOT appear on the
    general page."""
    md = render_for_kind("protocol", mixed_kind_file_registry)
    assert "MIX-02-001" not in md, (
        "Item from group with kind=project should NOT appear on "
        "general page"
    )


def test_inherited_kind_group_appears_on_file_kind_page(
    mixed_kind_file_registry,
):
    """SR-09-001: a group that inherits file kind=general appears on the
    general page."""
    md = render_for_kind("protocol", mixed_kind_file_registry)
    assert (
        "MIX-01-001" in md
    ), "Item inheriting file kind=general should appear on general page"


def test_item_kind_override_appears_on_overridden_page(
    mixed_kind_group_registry,
):
    """SR-09-001: an item with kind=project appears on the
    project page even though its group and file have kind=general."""
    md = render_for_kind("project", mixed_kind_group_registry)
    assert (
        "MGR-01-002" in md
    ), "Item with kind=project should appear on project page"


def test_item_kind_override_suppressed_on_wrong_page(
    mixed_kind_group_registry,
):
    """SR-09-002: an item with kind=project is suppressed on the
    general page while the rest of the group still renders."""
    md = render_for_kind("protocol", mixed_kind_group_registry)
    assert (
        "MGR-01-001" in md
    ), "General item should still appear on general page"
    assert (
        "MGR-01-002" not in md
    ), "Implementation item must be suppressed on the general page"


def test_mixed_group_appears_on_both_kind_pages(mixed_kind_group_registry):
    """SR-09-002: a group with mixed-kind items appears on both the general
    and project pages (with different items visible on each)."""
    gen_md = render_for_kind("protocol", mixed_kind_group_registry)
    impl_md = render_for_kind("project", mixed_kind_group_registry)
    # The group heading must appear on both pages
    assert "MGR-01" in gen_md
    assert "MGR-01" in impl_md
