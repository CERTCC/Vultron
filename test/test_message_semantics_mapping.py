"""Tests for the General shorthand mappings and the fault/acknowledgement mechanisms.

Covers MSM-04 (General protocol message shorthands) and MSM-05 (fault and
acknowledgement mechanism evolution). These groups record how the formal
protocol's per-model error and acknowledgement shorthands are realized on the
wire; see `notes/message-type-reference.md` and ADR-0083 for the rationale.
"""

#  Copyright (c) 2025-2026 Carnegie Mellon University and Contributors.
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

from vultron.core.models.events import MessageSemantics
from vultron.semantic_registry import SEMANTIC_REGISTRY
from vultron.wire.as2.enums import as_TransitiveActivityType as TAtype


def _registered() -> set[MessageSemantics]:
    return {e.semantics for e in SEMANTIC_REGISTRY}


def _entry(semantics: MessageSemantics):
    matches = [e for e in SEMANTIC_REGISTRY if e.semantics is semantics]
    assert len(matches) == 1, f"expected exactly one entry for {semantics}"
    return matches[0]


# ---------------------------------------------------------------------------
# MSM-04 — General protocol message shorthands
# ---------------------------------------------------------------------------


@pytest.mark.spec("MSM-04-001")
def test_gi_expands_across_the_note_lifecycle():
    """`GI` is one-to-many on the wire: the note lifecycle carries it."""
    expected = {
        MessageSemantics.CREATE_NOTE,
        MessageSemantics.ADD_NOTE_TO_CASE,
        MessageSemantics.REMOVE_NOTE_FROM_CASE,
    }
    assert expected <= _registered()

    # The expansion is real, not an artifact of one entry doing triple duty.
    assert len({id(_entry(s)) for s in expected}) == len(expected)


@pytest.mark.spec("MSM-04-002")
def test_gi_also_covers_the_actor_suggestion_exchange():
    """Suggesting a participant is a `GI` example, so it expands `GI` too."""
    expected = {
        MessageSemantics.OFFER_ACTOR_TO_CASE,
        MessageSemantics.OFFER_CASE_PARTICIPANT,
        MessageSemantics.ACCEPT_OFFER_CASE_PARTICIPANT,
        MessageSemantics.REJECT_OFFER_CASE_PARTICIPANT,
    }
    assert expected <= _registered()


@pytest.mark.spec("MSM-04-003")
def test_no_semantics_is_named_for_gk_or_ge():
    """`GK` and `GE` get no dispatch value; MSM-05 mechanisms serve them."""
    names = {s.name for s in MessageSemantics}
    for shorthand in ("GK", "GE", "GENERAL_ACK", "GENERAL_ERROR"):
        assert shorthand not in names


# ---------------------------------------------------------------------------
# MSM-05 — Fault and acknowledgement mechanism evolution
# ---------------------------------------------------------------------------


@pytest.mark.spec("MSM-05-001")
def test_faults_are_partitioned_by_failure_mode_not_state_machine():
    """Three mechanisms, one per failure mode — and none per state machine."""
    registered = _registered()

    # received but not understood
    assert MessageSemantics.CREATE_PROCESSING_FAULT in registered
    # received, understood, declined — as:Reject carries this
    assert MessageSemantics.REJECT_CASE_LEDGER_ENTRY in registered
    # needs narrative explanation
    assert MessageSemantics.ADD_NOTE_TO_CASE in registered

    # No per-state-machine error semantics exist, which is the whole point.
    names = {s.name for s in MessageSemantics}
    for shorthand in ("RE", "EE", "CE", "RM_ERROR", "EM_ERROR", "CS_ERROR"):
        assert shorthand not in names


@pytest.mark.spec("MSM-05-002")
def test_ledger_acknowledgement_is_negative_and_cumulative():
    """A mismatch is reported; a match says nothing. No per-message ack."""
    registered = _registered()

    # The NAK path is a registered wire activity ...
    assert MessageSemantics.REJECT_CASE_LEDGER_ENTRY in registered
    # ... paired with the announcement it can reject.
    assert MessageSemantics.ANNOUNCE_CASE_LEDGER_ENTRY in registered

    # ... and there is deliberately no positive per-message acknowledgement
    # for embargo or case-state changes, because hash continuity implies it.
    names = {s.name for s in MessageSemantics}
    for shorthand in ("EK", "CK", "ACK_EMBARGO", "ACK_CASE_STATUS"):
        assert shorthand not in names

    # `RK` is the exception: report submission is not ledger-replicated.
    assert MessageSemantics.ACK_REPORT in registered


@pytest.mark.spec("MSM-05-003")
def test_as_reject_is_overloaded_across_error_and_ordinary_refusal():
    """A receiver cannot infer "error" from the `as:Reject` verb alone."""
    reject_entries = [
        e
        for e in SEMANTIC_REGISTRY
        if e.pattern is not None
        and getattr(e.pattern, "activity_", None) is TAtype.REJECT
    ]

    # More than one thing is spelled with as:Reject ...
    assert len(reject_entries) > 1

    # ... and at least one of them is an ordinary protocol refusal rather than
    # a fault report, which is what makes the verb ambiguous.
    ordinary = {
        MessageSemantics.CLOSE_REPORT,
        MessageSemantics.REJECT_INVITE_ACTOR_TO_CASE,
        MessageSemantics.REJECT_CASE_PROPOSAL,
        MessageSemantics.REJECT_CASE_OWNERSHIP_TRANSFER,
    }
    assert ordinary & {e.semantics for e in reject_entries}
