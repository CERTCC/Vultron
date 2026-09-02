"""Unit tests for the MSM mapping renderer.

Covers the AC-6 acceptance criteria:
- collapse row (multiple shorthands, one wire form, discriminator cell)
- expansion row (one shorthand appearing in multiple rows)
- none-status row (no formal shorthand, pattern present)
- invalid slug raises ValueError
- every page slug produces a non-empty table
"""

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

import pytest

from vultron.metadata.msm import (
    PAGE_SLUGS,
    MappingStatus,
    render_page,
)
from vultron.metadata.msm._mapping import ROW_SPECS, SEMANTICS_TO_ROW
from vultron.metadata.msm.render import (
    _format_pattern,
    _render_table_row,
    _wire_form,
)
from vultron.core.models.events.base import MessageSemantics
from vultron.semantic_registry import lookup_entry

# ---------------------------------------------------------------------------
# _format_pattern
# ---------------------------------------------------------------------------


def test_format_pattern_scalar_object():
    """Scalar activity+object renders as Verb(ObjectType)."""
    entry = lookup_entry(MessageSemantics.SUBMIT_REPORT)
    assert entry is not None and entry.pattern is not None
    result = _format_pattern(entry.pattern)
    assert result == "Offer(VulnerabilityReport)"


def test_format_pattern_nested_object():
    """Nested ActivityPattern renders recursively, e.g. Read(Offer(X))."""
    entry = lookup_entry(MessageSemantics.ACK_REPORT)
    assert entry is not None and entry.pattern is not None
    result = _format_pattern(entry.pattern)
    assert "(" in result and ")" in result
    assert result.startswith("Read(")


def test_format_pattern_with_target_qualifier():
    """Patterns with a target include [target=X] qualifier."""
    entry = lookup_entry(MessageSemantics.ADD_CASE_STATUS_TO_CASE)
    assert entry is not None and entry.pattern is not None
    result = _format_pattern(entry.pattern)
    assert "target=" in result


# ---------------------------------------------------------------------------
# Collapse row — multiple shorthands share one wire form
# ---------------------------------------------------------------------------


def test_collapse_row_shorthand_cell():
    """Collapse rows show all shorthands separated by spaces."""
    row = SEMANTICS_TO_ROW[MessageSemantics.ADD_CASE_STATUS_TO_CASE]
    assert row.status == MappingStatus.COLLAPSE
    rendered = _render_table_row(row)
    # CP, CX, CA should all appear
    for shorthand in ("CP", "CX", "CA"):
        assert f"`{shorthand}`" in rendered


def test_collapse_row_discriminator_cell():
    """Collapse rows show the discriminator field."""
    row = SEMANTICS_TO_ROW[MessageSemantics.ADD_CASE_STATUS_TO_CASE]
    rendered = _render_table_row(row)
    assert "pxa_state" in rendered


def test_collapse_row_status_cell():
    row = SEMANTICS_TO_ROW[MessageSemantics.ADD_CASE_STATUS_TO_CASE]
    rendered = _render_table_row(row)
    assert "| collapse |" in rendered


# ---------------------------------------------------------------------------
# Expansion row — one shorthand across multiple wire forms (GI)
# ---------------------------------------------------------------------------


def test_expansion_row_create_note():
    """GI expansion rows show the GI shorthand and 'expansion' status."""
    row = SEMANTICS_TO_ROW[MessageSemantics.CREATE_NOTE]
    assert row.status == MappingStatus.EXPANSION
    rendered = _render_table_row(row)
    assert "`GI`" in rendered
    assert "| expansion |" in rendered


def test_expansion_gi_appears_in_multiple_rows():
    """GI shorthand is present in more than one RowSpec (expansion by definition)."""
    gi_rows = [row for row in ROW_SPECS if "GI" in row.shorthands]
    assert len(gi_rows) > 1, "GI should appear in multiple rows (expansion)"


def test_expansion_ep_appears_in_multiple_rows():
    """EP shorthand is present in more than one RowSpec."""
    ep_rows = [row for row in ROW_SPECS if "EP" in row.shorthands]
    assert len(ep_rows) > 1, "EP should appear in multiple rows (expansion)"


# ---------------------------------------------------------------------------
# None-status row — no formal shorthand, but wire form present
# ---------------------------------------------------------------------------


def test_none_status_row_no_shorthand():
    """NONE rows render '—' in the shorthand cell."""
    row = SEMANTICS_TO_ROW[MessageSemantics.CREATE_REPORT]
    assert row.status == MappingStatus.NONE
    rendered = _render_table_row(row)
    # First cell should be —
    assert rendered.startswith("| — |")


def test_none_status_row_wire_form_present():
    """NONE rows still include the wire form (pattern is defined)."""
    row = SEMANTICS_TO_ROW[MessageSemantics.CREATE_REPORT]
    entry = lookup_entry(MessageSemantics.CREATE_REPORT)
    assert entry is not None
    rendered = _render_table_row(row)
    # Wire form column should not be just —
    wire = _wire_form(entry)
    assert wire != "—"
    assert wire in rendered


# ---------------------------------------------------------------------------
# render_page integration
# ---------------------------------------------------------------------------


def test_render_page_rm_is_markdown_table():
    """render_page('rm') returns a string containing a markdown table."""
    output = render_page("rm")
    assert "| Shorthand(s) |" in output
    assert "|---|" in output
    assert "## Report Management" in output


def test_render_page_em_contains_embargo_semantics():
    output = render_page("em")
    assert "INVITE_TO_EMBARGO_ON_CASE" in output
    assert "EM state context" in output


def test_render_page_cs_contains_collapse_discriminators():
    output = render_page("cs")
    assert "pxa_state" in output
    assert "vf_state" in output


def test_render_page_general_shows_gi_expansion():
    output = render_page("general")
    # GI should appear many times (once per expansion row)
    assert output.count("`GI`") >= 4


def test_render_page_invalid_slug_raises():
    with pytest.raises(ValueError, match="Unknown page slug"):
        render_page("nonexistent_page")


@pytest.mark.parametrize("slug", list(PAGE_SLUGS))
def test_render_page_all_slugs_produce_table(slug):
    """Every page slug renders a non-empty table with the header row."""
    output = render_page(slug)
    assert "| Shorthand(s) |" in output
    # Must have at least one data row (beyond the header and separator)
    lines = [line for line in output.splitlines() if line.startswith("|")]
    assert len(lines) >= 3  # header + separator + ≥1 data row
