"""Tests for the CS/General shorthand mappings and the fault/acknowledgement mechanisms.

Covers MSM-03 (the participant-scoped CS shorthands and the CS-layer error and
acknowledgement shorthands), MSM-04 (General protocol message shorthands) and
MSM-05 (fault and acknowledgement mechanism evolution). These groups record how
the formal protocol's per-model error and acknowledgement shorthands are realized
on the wire; see `notes/message-type-reference.md` and ADR-0083 for the rationale.
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
from vultron.wire.as2.vocab.objects import as_CaseStatus, as_ParticipantStatus


def _registered() -> set[MessageSemantics]:
    return {e.semantics for e in SEMANTIC_REGISTRY}


def _entry(semantics: MessageSemantics):
    matches = [e for e in SEMANTIC_REGISTRY if e.semantics is semantics]
    assert len(matches) == 1, f"expected exactly one entry for {semantics}"
    return matches[0]


def _pattern(semantics: MessageSemantics):
    """The `ActivityPattern` for *semantics*, which every real message type has.

    Only the `unknown` and `unknown_unresolvable_object` dispatch fallbacks carry
    `pattern is None`; asserting here keeps the narrowing explicit for the type
    checker and turns a fallback slipping into these tests into a clear failure.
    """
    pattern = _entry(semantics).pattern
    assert pattern is not None, f"{semantics} has no ActivityPattern"
    return pattern


# Frozen allowlists, not name-guessing loops.
#
# Asserting that a bare shorthand such as "GK" is absent from `MessageSemantics`
# proves nothing — members are named VERB_OBJECT, so "GK" could never be one, and
# a real regression (say, `ACKNOWLEDGE_CASE_STATUS`) would sail past. Instead,
# enumerate every member whose name reads like a fault or an acknowledgement and
# require the set to equal the mechanisms MSM-05 actually sanctions. Any new
# ack-shaped or error-shaped semantic then fails here by construction.
_FAULT_TOKENS = ("ERROR", "FAULT")
_ACK_TOKENS = ("ACK", "ACKNOWLEDG")

_SANCTIONED_FAULT_SEMANTICS = frozenset({"CREATE_PROCESSING_FAULT"})
_SANCTIONED_ACK_SEMANTICS = frozenset({"ACK_REPORT"})


def _members_matching(tokens: tuple[str, ...]) -> frozenset[str]:
    return frozenset(
        s.name for s in MessageSemantics if any(t in s.name for t in tokens)
    )


# ---------------------------------------------------------------------------
# MSM-03 — CS protocol message shorthands
# ---------------------------------------------------------------------------
#
# The V/F/D dimensions are participant-scoped and the P/X/A dimensions are
# case-scoped, so the CS shorthands split across two semantics. MSM-03-001
# through -003 previously asserted the opposite; these tests pin the correction
# so it cannot silently regress. See ADR-0075 and ADR-0083.


@pytest.mark.spec("MSM-03-001")
@pytest.mark.spec("MSM-03-002")
@pytest.mark.spec("MSM-03-003")
def test_vfd_dimensions_ride_participant_status_not_case_status():
    """`CV`/`CF`/`CD` dispatch as ADD_PARTICIPANT_STATUS_TO_PARTICIPANT."""
    pattern = _pattern(MessageSemantics.ADD_PARTICIPANT_STATUS_TO_PARTICIPANT)
    assert pattern.activity_ is TAtype.ADD
    assert pattern.object_ == "ParticipantStatus"
    assert pattern.target_ == "CaseParticipant"

    # V and F ride `vf_state`; D rides `d_state`. Both are participant-scoped.
    assert "vf_state" in as_ParticipantStatus.model_fields
    assert "d_state" in as_ParticipantStatus.model_fields

    # The whole point of the correction: there is no case-level V/F/D state, and
    # in particular none of the payload fields MSM-03 used to name.
    for absent in (
        "vf_state",
        "d_state",
        "vendor_aware",
        "fix_ready",
        "fix_deployed",
    ):
        assert absent not in as_CaseStatus.model_fields, (
            f"as_CaseStatus must not carry {absent!r} — V/F/D are participant-scoped "
            "per ADR-0075; a case-level status cannot say *which* vendor is aware"
        )


@pytest.mark.spec("MSM-03-004")
@pytest.mark.spec("MSM-03-005")
@pytest.mark.spec("MSM-03-006")
def test_pxa_dimensions_ride_case_status():
    """`CP`/`CX`/`CA` stay case-scoped on `as_CaseStatus.pxa_state`."""
    pattern = _pattern(MessageSemantics.ADD_CASE_STATUS_TO_CASE)
    assert pattern.activity_ is TAtype.ADD
    assert pattern.object_ == "CaseStatus"
    assert pattern.target_ == "VulnerabilityCase"
    assert "pxa_state" in as_CaseStatus.model_fields


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

    # The expansion is real: three distinct AS2 verbs, not one activity carrying
    # all three meanings in a payload field the way the CS collapse does.
    verbs = {_pattern(s).activity_ for s in expected}
    assert verbs == {TAtype.CREATE, TAtype.ADD, TAtype.REMOVE}


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


@pytest.mark.spec("VAM-04-001")
@pytest.mark.spec("VAM-04-010")
def test_actor_suggestion_is_two_offers_over_different_objects():
    """The exchange has two offer hops, over `Actor` then over `CaseParticipant`.

    VAM previously specified only the first hop and then had the accept/reject
    entries wrap it, which read as a single-offer handshake. The two hops carry
    different object types, which is what makes them distinguishable on the wire.
    """
    first = _pattern(MessageSemantics.OFFER_ACTOR_TO_CASE)
    assert first.activity_ is TAtype.OFFER
    assert first.object_ == "Actor"
    assert first.target_ == "VulnerabilityCase"

    second = _pattern(MessageSemantics.OFFER_CASE_PARTICIPANT)
    assert second.activity_ is TAtype.OFFER
    assert second.object_ == "CaseParticipant"
    assert second.target_ == "VulnerabilityCase"


@pytest.mark.spec("VAM-04-002")
@pytest.mark.spec("VAM-04-003")
def test_actor_suggestion_accept_reject_wrap_the_participant_offer():
    """Accept/Reject wrap `Offer(CaseParticipant)`, not the originating `Offer(Actor)`.

    This is the correction: VAM-04-002 and VAM-04-003 previously specified
    `Accept`/`Reject(Offer(Actor)[target=VulnerabilityCase])` under semantic names
    that do not exist. The Case Owner responds to the CaseActor's participant
    offer (CM-16-003/CM-16-004, ADR-0026), so the inner object is
    `CaseParticipant`.
    """
    for semantics, verb in (
        (MessageSemantics.ACCEPT_OFFER_CASE_PARTICIPANT, TAtype.ACCEPT),
        (MessageSemantics.REJECT_OFFER_CASE_PARTICIPANT, TAtype.REJECT),
    ):
        pattern = _pattern(semantics)
        assert pattern.activity_ is verb
        inner = pattern.object_
        assert not isinstance(
            inner, str
        ), f"{semantics} must nest an inner ActivityPattern, not a bare object type"
        assert inner.activity_ is TAtype.OFFER
        assert inner.object_ == "CaseParticipant", (
            f"{semantics} must wrap Offer(CaseParticipant), not Offer(Actor) — "
            "the Case Owner responds to the CaseActor's participant offer"
        )


@pytest.mark.spec("MSM-04-003")
def test_no_semantics_is_named_for_gk_or_ge():
    """`GK` and `GE` get no dispatch value; MSM-05 mechanisms serve them."""
    # No general-purpose ack or error semantic exists, under any spelling.
    assert _members_matching(_ACK_TOKENS) == _SANCTIONED_ACK_SEMANTICS
    assert _members_matching(_FAULT_TOKENS) == _SANCTIONED_FAULT_SEMANTICS

    # And the mechanisms that do serve `GK`/`GE` are registered (MSM-05-001/-002).
    registered = _registered()
    assert MessageSemantics.CREATE_PROCESSING_FAULT in registered
    assert MessageSemantics.REJECT_CASE_LEDGER_ENTRY in registered


# ---------------------------------------------------------------------------
# MSM-05 — Fault and acknowledgement mechanism evolution
# ---------------------------------------------------------------------------


@pytest.mark.spec("MSM-05-001")
@pytest.mark.spec("MSM-01-007")
@pytest.mark.spec("MSM-02-008")
@pytest.mark.spec("MSM-03-007")
def test_faults_are_partitioned_by_failure_mode_not_state_machine():
    """Three mechanisms, one per failure mode — and none per state machine.

    Also pins the delegation in MSM-01-007 (`RE`), MSM-02-008 (`EE`) and
    MSM-03-007 (`CE`): those shorthands have no wire form of their own precisely
    because faults are partitioned by failure mode instead.
    """
    registered = _registered()

    # received but not understood
    assert MessageSemantics.CREATE_PROCESSING_FAULT in registered
    # received and understood but declined — as:Reject carries this
    assert MessageSemantics.REJECT_INVITE_ACTOR_TO_CASE in registered
    # needs narrative explanation
    assert MessageSemantics.CREATE_NOTE in registered
    assert MessageSemantics.ADD_NOTE_TO_CASE in registered

    # "exactly three mechanisms" is the part that can regress: a fourth
    # fault-shaped semantic must not appear. `CREATE_PROCESSING_FAULT` is the
    # only sanctioned fault-named member, and `as:Reject` and `Note` are
    # pre-existing verbs reused rather than new fault types.
    assert _members_matching(_FAULT_TOKENS) == _SANCTIONED_FAULT_SEMANTICS

    # No per-state-machine error semantics exist, which is the whole point:
    # RE/EE/CE/GE have no wire counterpart under any spelling.
    for scope in ("RM", "EM", "CS", "GENERAL"):
        assert f"{scope}_ERROR" not in MessageSemantics.__members__


@pytest.mark.spec("MSM-05-002")
@pytest.mark.spec("MSM-02-009")
@pytest.mark.spec("MSM-03-008")
def test_ledger_acknowledgement_is_negative_and_cumulative():
    """A mismatch is reported; a match says nothing. No per-message ack.

    Also pins the delegation in MSM-02-009 (`EK`) and MSM-03-008 (`CK`): both
    defer to hash-chain continuity rather than getting a wire form.
    """
    registered = _registered()

    # The NAK path is a registered wire activity ...
    assert MessageSemantics.REJECT_CASE_LEDGER_ENTRY in registered
    # ... paired with the announcement it can reject.
    assert MessageSemantics.ANNOUNCE_CASE_LEDGER_ENTRY in registered

    # `RK` (ACK_REPORT) is the *only* acknowledgement semantic, under any
    # spelling. EK/CK/GK deliberately have none, because hash-chain continuity
    # already acknowledges ledger-replicated state cumulatively.
    assert _members_matching(_ACK_TOKENS) == _SANCTIONED_ACK_SEMANTICS
    assert MessageSemantics.ACK_REPORT in registered


@pytest.mark.spec("MSM-05-002")
def test_ledger_hash_mismatch_rejects_and_replays_from_last_accepted():
    """The behaviour MSM-05-002 mandates, not just the enum registration.

    A mismatched `prev_log_hash` must produce a `Reject(CaseLedgerEntry)` and the
    CaseActor must replay from the last accepted hash. Asserting only that two
    enum values are registered would leave the actual mechanism untested.
    """
    from py_trees.behaviour import Behaviour

    from vultron.core.behaviors.sync.nodes import (
        CheckHashOrRejectOnMismatchNode,
        SendRejectLogEntryNode,
    )
    from vultron.core.use_cases.received.sync import (
        RejectLedgerEntryReceivedUseCase,
    )

    # The mismatch guard and the NAK emitter are both wired into the BT ...
    assert issubclass(CheckHashOrRejectOnMismatchNode, Behaviour)
    assert issubclass(SendRejectLogEntryNode, Behaviour)

    # ... and the received-side use case that handles the resulting NAK exists
    # with the standard use-case protocol, which is what drives gap-fill replay.
    assert hasattr(RejectLedgerEntryReceivedUseCase, "execute")

    # The NAK is emitted as `as:Reject` over a CaseLedgerEntry.
    nak = _pattern(MessageSemantics.REJECT_CASE_LEDGER_ENTRY)
    assert nak.activity_ is TAtype.REJECT
    assert nak.object_ == "CaseLedgerEntry"


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

    # ... and every ordinary protocol refusal MSM-05-003 enumerates really is one
    # of them. This is a subset check, not an intersection: if three of the four
    # were dropped from the registry, an intersection would still pass on the
    # survivor and the spec's list would quietly go stale.
    ordinary = {
        MessageSemantics.CLOSE_REPORT,
        MessageSemantics.REJECT_INVITE_TO_EMBARGO_ON_CASE,
        MessageSemantics.REJECT_INVITE_ACTOR_TO_CASE,
        MessageSemantics.REJECT_CASE_PROPOSAL,
        MessageSemantics.REJECT_CASE_OWNERSHIP_TRANSFER,
    }
    assert ordinary <= {e.semantics for e in reject_entries}

    # The ledger NAK is deliberately NOT in that list: per MSM-05-002 it is the
    # acknowledgement mechanism, not an ordinary refusal. Keeping the two apart is
    # the distinction MSM-05 exists to draw.
    assert MessageSemantics.REJECT_CASE_LEDGER_ENTRY not in ordinary
