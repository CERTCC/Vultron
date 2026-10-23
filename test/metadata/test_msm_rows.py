"""Unit tests for the wire-form summary and the derived mapping rows.

The per-page mapping tables these rows used to render were retired by #4431:
the message pages include the occasion fragments instead (MSM-06-001).  The
rows stay, as the derived page, shorthands and status of each entry.
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

from vultron.core.models.events.base import MessageSemantics
from vultron.metadata.msm import MappingStatus
from vultron.metadata.msm._mapping import ROW_SPECS, SEMANTICS_TO_ROW
from vultron.metadata.msm.occasions import (
    emitted_type,
    format_pattern,
    wire_summary,
)
from vultron.semantic_registry import lookup_entry

# ---------------------------------------------------------------------------
# format_pattern
# ---------------------------------------------------------------------------


def test_format_pattern_scalar_object():
    """Scalar activity+object renders as Verb(ObjectType)."""
    entry = lookup_entry(MessageSemantics.SUBMIT_REPORT)
    assert entry is not None and entry.pattern is not None
    assert format_pattern(entry.pattern) == "Offer(VulnerabilityReport)"


def test_format_pattern_nested_object():
    """Nested ActivityPattern renders recursively, e.g. Read(Offer(X))."""
    entry = lookup_entry(MessageSemantics.ACK_REPORT)
    assert entry is not None and entry.pattern is not None
    assert format_pattern(entry.pattern) == "Read(Offer(VulnerabilityReport))"


def test_format_pattern_with_target_qualifier():
    """Patterns with a target include a [target=X] qualifier."""
    entry = lookup_entry(MessageSemantics.ADD_CASE_STATUS_TO_CASE)
    assert entry is not None and entry.pattern is not None
    assert "target=" in format_pattern(entry.pattern)


@pytest.mark.parametrize(
    ("semantics", "expected"),
    [
        (
            MessageSemantics.INVITE_TO_EMBARGO_ON_CASE,
            "Invite(EmbargoEvent)[context=VulnerabilityCase]",
        ),
        (
            MessageSemantics.ACCEPT_INVITE_TO_EMBARGO_ON_CASE,
            "Accept(Invite(EmbargoEvent)[context=VulnerabilityCase])",
        ),
        (
            MessageSemantics.REMOVE_EMBARGO_EVENT_FROM_CASE,
            "Remove(EmbargoEvent)",
        ),
        (MessageSemantics.CREATE_EMBARGO_EVENT, "Create(EmbargoEvent)"),
    ],
)
def test_format_pattern_writes_the_embargo_type_the_sender_emits(
    semantics: MessageSemantics, expected: str
):
    """An embargo pattern matches ``Event``, but the sender emits
    ``EmbargoEvent``, which is what Wire Activity notation writes (Annex C,
    #5155)."""
    entry = lookup_entry(semantics)
    assert entry is not None and entry.pattern is not None
    assert format_pattern(entry.pattern) == expected


def test_emitted_type_passes_other_types_through():
    assert emitted_type("Event") == "EmbargoEvent"
    assert emitted_type("VulnerabilityCase") == "VulnerabilityCase"


def test_wire_summary_of_a_none_status_entry_is_its_pattern():
    """An entry with no formal shorthand still has a wire form."""
    entry = lookup_entry(MessageSemantics.CREATE_REPORT)
    assert entry is not None and entry.pattern is not None
    assert wire_summary(entry) == format_pattern(entry.pattern)


# ---------------------------------------------------------------------------
# Collapse row — multiple shorthands share one wire form
# ---------------------------------------------------------------------------


def test_collapse_row_carries_every_shorthand():
    row = SEMANTICS_TO_ROW[MessageSemantics.ADD_CASE_STATUS_TO_CASE]
    assert row.status == MappingStatus.COLLAPSE
    assert set(row.shorthands) == {"CP", "CX", "CA"}


# ---------------------------------------------------------------------------
# Expansion row — one shorthand across multiple wire forms (GI)
# ---------------------------------------------------------------------------


def test_expansion_row_add_note_to_case():
    """GI expansion rows carry the GI shorthand and 'expansion' status."""
    row = SEMANTICS_TO_ROW[MessageSemantics.ADD_NOTE_TO_CASE]
    assert row.status == MappingStatus.EXPANSION
    assert "GI" in row.shorthands


def test_expansion_gi_appears_in_multiple_rows():
    """GI is present in more than one row (expansion by definition)."""
    gi_rows = [row for row in ROW_SPECS if "GI" in row.shorthands]
    assert len(gi_rows) > 1, "GI should appear in multiple rows (expansion)"


def test_ep_maps_only_to_invite_embargo():
    """EP is Invite(EmbargoEvent) only (MSM-02-001), not an expansion."""
    ep_rows = [row for row in ROW_SPECS if "EP" in row.shorthands]
    assert [row.semantics for row in ep_rows] == [
        MessageSemantics.INVITE_TO_EMBARGO_ON_CASE
    ]


def test_announce_embargo_event_has_no_shorthand():
    """Announcing embargo terms proposes nothing, so carries no EP."""
    row = SEMANTICS_TO_ROW[MessageSemantics.ANNOUNCE_EMBARGO_EVENT_TO_CASE]
    assert row.shorthands == ()
    assert row.status == MappingStatus.NONE


def test_none_status_row_has_no_shorthand():
    row = SEMANTICS_TO_ROW[MessageSemantics.CREATE_REPORT]
    assert row.status == MappingStatus.NONE
    assert row.shorthands == ()
