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

"""The extended desiderata, scored for each vendor in two parts (#6457).

An incomplete case is scored through its completions (ADR-0182), in each
vendor's scope, with an end part and an embargo part (ADR-0200).
The hand-checked values use the baselines of ``process_model_desiderata.md``
§ "The baselines".
"""

from datetime import UTC, datetime, timedelta
from fractions import Fraction
from typing import Any

import pytest
from pydantic import ValidationError

from test.measure.history.builders import (
    VENDOR,
    Ledger,
    exit_embargo,
    publish,
    seat_vendor,
    status,
)
from vultron.core.models.events.base import MessageSemantics
from vultron.core.states.cs_invariants import CSEvent
from vultron.core.states.embargo_register import TerminationReason
from vultron.demo.recordings.layout import RECORDINGS_DIR
from vultron.measure.baselines import (
    EXTENDED,
    EmbargoEnd,
    Event,
    EventKind,
    Group,
    WalkPrefix,
    expected_outcome,
    implications,
)
from vultron.measure.baselines.desiderata import joint_values
from vultron.measure.history import (
    CaseEvent,
    CaseEventHistory,
    CaseEventKind,
    EventKind as RecordKind,
    read_case_event_histories,
)
from vultron.measure.ledger import LedgerSource
from vultron.measure.scoring import (
    CaseRecord,
    CaseScoreSummary,
    ExtendedScore,
    PartScore,
    TermScore,
    UnscoredScope,
    WalkScore,
    exit_end,
    scope_desiderata,
    score_case,
    vendor_scope,
)
from vultron.measure.sequences import case_state_sequences

_CASE = "urn:uuid:case-1"
_V1 = "https://example.org/actors/vendor-1"
_START = datetime(2026, 1, 1, tzinfo=UTC)

_E_WEIGHT = 1 - Fraction(2, 23)
_EX_OWN_WEIGHT = 1 - Fraction(2, 115)


def _event(
    index: int,
    kind: CaseEventKind,
    participant: str | None = None,
    **fields: Any,
) -> CaseEvent:
    return CaseEvent(
        kind=kind,
        participant=participant,
        semantic_type=MessageSemantics.ADD_PARTICIPANT_STATUS_TO_PARTICIPANT,
        log_index=index,
        committed_at=_START + timedelta(seconds=index),
        **fields,
    )


def _history(*events: CaseEvent) -> CaseEventHistory:
    return CaseEventHistory(
        case_id=_CASE,
        source=LedgerSource.COMPLETE_COPY,
        end_confirmed=True,
        events=list(events),
    )


def _start(index: int) -> CaseEvent:
    return _event(index, RecordKind.EMBARGO_START, embargo_id="urn:uuid:e")


def _exit(
    index: int,
    reason: TerminationReason = TerminationReason.EARLY,
    cause: dict[str, Any] | None = None,
) -> CaseEvent:
    return _event(
        index,
        RecordKind.EMBARGO_EXIT,
        embargo_id="urn:uuid:e",
        exit_reason=reason,
        exit_cause=cause,
    )


def _vendor_done_embargo_active() -> CaseEventHistory:
    """A vendor aware, its report accepted and closed, its fix ready and
    deployed, under an active embargo; nothing is public yet."""
    return _history(
        _start(0),
        _event(1, RecordKind.REPORT_RECEIVED, _V1),
        _event(1, CSEvent.V, _V1),
        _event(2, RecordKind.REPORT_VALID, _V1),
        _event(3, RecordKind.REPORT_ACCEPTED, _V1),
        _event(4, CSEvent.F, _V1),
        _event(5, CSEvent.D, _V1),
        _event(6, RecordKind.REPORT_CLOSED, _V1),
    )


def _recording(name: str) -> CaseScoreSummary:
    path = RECORDINGS_DIR / name / "case-actor.jsonl"
    (history,) = read_case_event_histories([path]).histories.values()
    return score_case(history)


def _term(walk, notation_part: str):
    assert isinstance(walk, WalkScore)
    (found,) = [t for t in walk.terms if notation_part in t.notation]
    return found


def _extended(vendor) -> ExtendedScore:
    assert isinstance(vendor.extended, ExtendedScore)
    return vendor.extended


# ---------------------------------------------------------------------------
# A vendor's scope covers the one-vendor extended desiderata once each
# ---------------------------------------------------------------------------


def test_every_one_vendor_extended_desideratum_is_scored_once():
    """Each lands in one part, unless an equivalent one is listed before
    it: the embargo part keeps ``E ≺ P`` and ``Ex_own ≺ P``.  The
    multi-party desiderata are in neither part (ADR-0200)."""
    scopes = scope_desiderata()
    listed = [d for part in scopes for d in part]
    assert len(set(listed)) == len(listed)
    equivalent = {
        frozenset((i.stronger, i.weaker))
        for i in implications()
        if i.equivalent
    }
    for d in EXTENDED:
        if d.group is Group.MULTI_PARTY:
            assert d not in listed, d.notation
            continue
        assert d in listed or any(
            frozenset((d, kept)) in equivalent for kept in listed
        ), d.notation
    assert [d.notation for d in scopes.embargo] == [
        r"$\evE \prec \evP$",
        r"$\evExOwn \prec \evP$",
        r"$\evF_i \prec \evExOwn$",
    ]
    assert {d.group for d in scopes.end} == {Group.REPORT_HANDLING}


# ---------------------------------------------------------------------------
# AC-1: a recorded vendor's score includes its extended desiderata
# ---------------------------------------------------------------------------

_RCV_END = (
    (1 - Fraction(5, 96))  # Ac_i ≺ P
    + (1 - Fraction(16, 81))  # Ac_i ≺ X
    + (1 - Fraction(2, 9))  # Ac_i ≺ A
    + (1 - Fraction(1, 6))  # Va_i ≺ P
    + (1 - Fraction(1, 3))  # Ac_i ≺ F_i
)
_F_BEFORE_EX_OWN_WEIGHT = 1 - Fraction(11515607, 250253192)


def test_a_recorded_vendors_score_includes_its_report_handling_desiderata():
    """``rcv``: the vendor accepts at log index 22, the case goes public at
    28 and the embargo ends on that threat signal at 29.

    So every report-handling desideratum is met, and ``F_i ≺ Ex_own`` is
    out of scope for good, which counts as met: an embargo that ended on a
    threat signal never ends on its own terms.
    """
    (vendor,) = _recording("rcv").vendors
    extended = _extended(vendor)
    accepted_before_public = _term(extended.end, r"\evAc_i \prec \evP")
    assert accepted_before_public.met == 1
    assert accepted_before_public.weight == 1 - Fraction(5, 96)
    fix_first = _term(extended.embargo, r"\evF_i \prec \evExOwn")
    assert fix_first.met == 1
    assert fix_first.weight == _F_BEFORE_EX_OWN_WEIGHT
    end = extended.end
    assert end.expected == end.best == end.worst == _RCV_END


@pytest.mark.parametrize(
    "path",
    sorted(RECORDINGS_DIR.glob("*/case-actor.jsonl")),
    ids=lambda p: p.parent.name,
)
def test_every_recorded_vendor_is_scored_in_both_parts(path):
    (history,) = read_case_event_histories([path]).histories.values()
    desiderata = scope_desiderata()
    for vendor in score_case(history).vendors:
        extended = _extended(vendor)
        assert [t.notation for t in extended.end.terms] == [
            d.notation for d in desiderata.end
        ]
        assert [t.notation for t in extended.embargo.terms] == [
            d.notation for d in desiderata.embargo
        ]


# ---------------------------------------------------------------------------
# AC-2: each vendor's score has an end part and an embargo part
# ---------------------------------------------------------------------------


def test_a_recorded_vendors_score_has_an_end_part_and_an_embargo_part():
    """``rcv``: the embargo starts at creation and ends on a threat signal,
    so ``E`` precedes ``P``, ``X`` and ``A``, ``Ex_own`` never comes, and
    ``F_i ≺ Ex_own`` is never entered."""
    (vendor,) = _recording("rcv").vendors
    embargo = _extended(vendor).embargo
    assert _term(embargo, r"\evE \prec \evP").met == 1
    assert _term(embargo, r"\evExOwn \prec \evP").met == 0
    by_hand = _E_WEIGHT + _F_BEFORE_EX_OWN_WEIGHT
    assert embargo.expected == embargo.best == embargo.worst == by_hand
    assert vendor.embargo is not None
    assert vendor.embargo.expected == by_hand
    assert vendor.end is not None
    assert vendor.end.expected == vendor.score.expected + _RCV_END
    assert vendor.total is not None
    assert vendor.total.expected == vendor.end.expected + by_hand


def test_no_vendor_is_scored_on_a_multi_party_desideratum():
    """``F_i ≺ P`` is the original twelve's ``F ≺ P``, already counted, and
    move advice does not use ``V_i ≺ F_j`` (ADR-0200, #6502)."""
    for vendor in _recording("rvv").vendors:
        extended = _extended(vendor)
        terms = extended.end.terms + extended.embargo.terms
        assert all(t.group is not Group.MULTI_PARTY for t in terms)


# ---------------------------------------------------------------------------
# AC-3: an incomplete history is scored through its completions
# ---------------------------------------------------------------------------


def test_an_open_embargo_is_scored_through_its_completions():
    """From an active embargo with nothing public, five steps settle
    ``Ex_own ≺ P`` — ``P``, ``X``, ``A``, an own-terms exit and another
    exit — and a revision only delays them.  So it is met with probability
    1/5; ``E ≺ P`` is already met.

    The vendor's fix is ready, so ``F_i ≺ Ex_own`` is met if the embargo
    ends on its own terms, and out of scope, which counts as met, if not.
    """
    (vendor,) = score_case(_vendor_done_embargo_active()).vendors
    embargo = _extended(vendor).embargo
    assert _term(embargo, r"\evE \prec \evP").met == 1
    assert _term(embargo, r"\evExOwn \prec \evP").met == Fraction(1, 5)
    assert _term(embargo, r"\evF_i \prec \evExOwn").met == 1
    certain = _E_WEIGHT + _F_BEFORE_EX_OWN_WEIGHT
    assert embargo.expected == certain + _EX_OWN_WEIGHT / 5
    assert embargo.best == certain + _EX_OWN_WEIGHT
    assert embargo.worst == certain


def test_a_scope_the_case_may_never_enter_counts_as_met_when_not_entered():
    """The vendor's report is closed after acceptance under an embargo
    still in force, so every report-handling desideratum is settled met."""
    (vendor,) = score_case(_vendor_done_embargo_active()).vendors
    end = _extended(vendor).end
    assert all(t.met == 1 for t in end.terms)
    total = sum((t.weight for t in end.terms), Fraction(0))
    assert end.expected == end.best == end.worst == total


def test_an_open_scope_combines_its_chance_and_its_conditional_value():
    """A vendor aware, its report only received: ``Va_i ≺ P`` is in scope
    only if the report reaches Valid, so its outcome is
    P(not entered) + P(entered) * P(met | entered)."""
    history = _history(
        _start(0),
        _event(1, RecordKind.REPORT_RECEIVED, _V1),
        _event(1, CSEvent.V, _V1),
    )
    record = CaseRecord(history, case_state_sequences(history).sequences)
    (vendor,) = score_case(history).vendors
    end = _extended(vendor).end
    (desideratum,) = [
        d for d in scope_desiderata().end if r"\evVa_i" in d.notation
    ]
    prefix = WalkPrefix(
        record.state((record.path(_V1),)),
        (frozenset({Event(EventKind.V, 1)}),),
    )
    reading = joint_values(desideratum.model, desideratum.query).reading(
        prefix
    )
    assert 0 < reading.entered < 1
    assert reading.value is not None
    assert 0 < reading.value < 1
    term = _term(end, r"\evVa_i")
    assert term.met == expected_outcome(reading.entered, reading.value)
    assert term.met == 1 - reading.entered + reading.entered * reading.value
    assert end.worst < end.expected < end.best


def test_a_case_whose_events_have_all_happened_has_one_score():
    (vendor,) = _recording("rcv").vendors
    extended = _extended(vendor)
    for walk in (extended.end, extended.embargo):
        assert walk.best == walk.worst == walk.expected


# ---------------------------------------------------------------------------
# AC-4: no vendor's sequence is combined with another's
# ---------------------------------------------------------------------------


@pytest.mark.spec("CEH-05-006")
def test_each_walk_reads_one_vendor():
    """``rvv`` has two vendors: every term of a vendor's two parts names
    that vendor alone."""
    summary = _recording("rvv")
    assert len(summary.vendors) == 2
    for vendor in summary.vendors:
        extended = _extended(vendor)
        for walk in (extended.end, extended.embargo):
            assert {t.vendors for t in walk.terms} == {(vendor.participant,)}


# ---------------------------------------------------------------------------
# The record: positions, exit causes and refusals
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("reason", "cause", "end"),
    [
        (TerminationReason.END_TIME_REACHED, None, EmbargoEnd.OWN_TERMS),
        (TerminationReason.EARLY, {"kind": "FIX_READY"}, EmbargoEnd.OWN_TERMS),
        (
            TerminationReason.EARLY,
            {"kind": "FIX_DEPLOYED"},
            EmbargoEnd.OWN_TERMS,
        ),
        (
            TerminationReason.EARLY,
            {"kind": "THREAT_SIGNAL", "signals": ["P"]},
            EmbargoEnd.THREAT_SIGNAL,
        ),
        (TerminationReason.EARLY, {"kind": "OTHER"}, EmbargoEnd.OTHER),
        (TerminationReason.EARLY, None, EmbargoEnd.OTHER),
        (TerminationReason.EARLY, {"kind": ["FIX_READY"]}, EmbargoEnd.OTHER),
    ],
)
def test_an_embargo_exit_splits_by_its_cause(reason, cause, end):
    assert exit_end(_exit(3, reason, cause)) is end


def test_only_an_embargo_exit_has_an_exit_cause():
    with pytest.raises(ValueError, match="not an embargo exit"):
        exit_end(_start(0))


def test_public_awareness_sits_no_later_than_a_published_exploit():
    """``pX`` forces ``P`` (CSB-17-003): ``X`` at 2 and ``P`` at 5 put
    ``P`` at 2."""
    history = _history(
        _event(1, CSEvent.V, _V1),
        _event(2, CSEvent.X),
        _event(5, CSEvent.P),
    )
    record = CaseRecord(history, case_state_sequences(history).sequences)
    assert record.position(Event(EventKind.P), ()) == 2
    assert record.position(Event(EventKind.X), ()) == 2


def test_a_vendor_made_aware_by_publication_is_aware_at_publication():
    """``vP`` forces ``V`` (CEH-05-009): recorded ``P, X, V`` is ``P, V,
    X``, so the awareness recorded at 4 sits with public awareness at 2."""
    history = _history(
        _event(2, CSEvent.P),
        _event(3, CSEvent.X),
        _event(4, CSEvent.V, _V1),
    )
    record = CaseRecord(history, case_state_sequences(history).sequences)
    assert record.position(Event(EventKind.V, 1), (_V1,)) == 2
    assert record.position(Event(EventKind.X), ()) == 3


def test_a_fix_ready_before_acceptance_is_not_scored():
    """A fix needs the report accepted, deferred or closed (CSB-18-001)."""
    ledger = Ledger()
    ledger.standard_genesis()
    seat_vendor(ledger, VENDOR, "Vf")
    ledger.add_status(VENDOR, status("v-F", VENDOR, "RECEIVED", vf="VF"))
    (vendor,) = score_case(ledger.history()).vendors
    assert isinstance(vendor.extended, UnscoredScope)
    assert "no joint-model state" in vendor.extended.reason
    assert (vendor.end, vendor.embargo, vendor.total) == (None, None, None)


def test_public_awareness_ends_an_embargo_in_force_at_once():
    """Public awareness ends the embargo as a threat signal (CSB-18-002),
    so a ledger that has not yet recorded the exit is read as ended."""
    ledger = Ledger()
    ledger.standard_genesis()
    seat_vendor(ledger, VENDOR, "Vf")
    publish(ledger, "Pxa")
    before = score_case(ledger.history())
    exit_embargo(ledger, cause={"kind": "THREAT_SIGNAL", "signals": ["P"]})
    after = score_case(ledger.history())
    assert before.vendors == after.vendors
    (vendor,) = before.vendors
    embargo = _extended(vendor).embargo
    assert _term(embargo, r"\evExOwn \prec \evP").met == 0


def _accepted_then_public(*rest: CaseEvent) -> CaseEventHistory:
    """An embargo in force, a vendor that accepts the report, then public
    awareness at log index 2, which ends the embargo as a threat signal."""
    return _history(
        _start(0),
        _event(1, RecordKind.REPORT_RECEIVED, _V1),
        _event(1, CSEvent.V, _V1),
        _event(1, RecordKind.REPORT_VALID, _V1),
        _event(1, RecordKind.REPORT_ACCEPTED, _V1),
        _event(2, CSEvent.P),
        *rest,
    )


@pytest.mark.parametrize(
    ("reason", "cause"),
    [
        (TerminationReason.END_TIME_REACHED, None),
        (TerminationReason.EARLY, {"kind": "FIX_READY"}),
        (TerminationReason.EARLY, {"kind": "OTHER"}),
    ],
)
def test_a_later_exit_of_an_embargo_a_threat_ended_changes_nothing(
    reason, cause
):
    """Public awareness ended the embargo at 2 as a threat signal, so the
    ledger's own-terms exit at 3 is not an own-terms exit: ``F_i ≺
    Ex_own`` stays out of scope, met, as with no exit recorded."""
    fix = _event(4, CSEvent.F, _V1)
    with_exit = score_case(_accepted_then_public(_exit(3, reason, cause), fix))
    without = score_case(_accepted_then_public(fix))
    assert with_exit.vendors == without.vendors
    (vendor,) = with_exit.vendors
    embargo = _extended(vendor).embargo
    assert _term(embargo, r"\evF_i \prec \evExOwn").met == 1
    record_history = _accepted_then_public(_exit(3, reason, cause), fix)
    record = CaseRecord(
        record_history, case_state_sequences(record_history).sequences
    )
    assert record.position(Event(EventKind.EXIT_THREAT), ()) == 2
    assert record.position(Event(EventKind.EXIT_OWN_TERMS), ()) is None


@pytest.mark.parametrize("after", [(), (CSEvent.X,)])
def test_an_embargo_that_starts_after_publication_is_not_scored(after):
    """No embargo is in force beside public awareness (CSB-18-002), even
    when a later public exploit would end it."""
    history = _history(
        _event(1, CSEvent.V, _V1),
        _event(2, CSEvent.P),
        _start(3),
        *(_event(4 + i, kind) for i, kind in enumerate(after)),
    )
    (vendor,) = score_case(history).vendors
    assert isinstance(vendor.extended, UnscoredScope)
    assert "no joint-model state" in vendor.extended.reason
    assert "log index 3" in vendor.extended.reason


def test_one_vendor_the_model_cannot_walk_leaves_the_others_scored():
    """The second vendor's fix comes before its report is accepted, so it
    has no extended score, while the first vendor keeps its own; the case
    then has no median."""
    v2 = "https://example.org/actors/vendor-2"
    history = _history(
        _start(0),
        _event(1, CSEvent.V, _V1),
        _event(2, CSEvent.V, v2),
        _event(3, CSEvent.F, v2),
    )
    summary = score_case(history)
    first, second = summary.vendors
    assert isinstance(first.extended, ExtendedScore)
    assert isinstance(second.extended, UnscoredScope)
    assert summary.expected is None


def test_a_vendor_the_record_did_not_read_is_refused():
    history = _vendor_done_embargo_active()
    record = CaseRecord(history, case_state_sequences(history).sequences)
    with pytest.raises(KeyError):
        vendor_scope(record, "https://example.org/actors/nobody")
    with pytest.raises(KeyError, match="not among"):
        record.position(Event(EventKind.F, 2), (_V1,))
    with pytest.raises(KeyError, match="not among"):
        record.position(Event(EventKind.F, 0), (_V1,))
    with pytest.raises(KeyError):
        record.position(Event(EventKind.F, 1), ("https://example.org/x",))


# ---------------------------------------------------------------------------
# The score models refuse what no walk could give
# ---------------------------------------------------------------------------


def _scored(met: Fraction = Fraction(1, 2)) -> TermScore:
    return TermScore(
        notation=r"$\evE \prec \evP$",
        group=Group.EMBARGO,
        weight=Fraction(1, 2),
        met=met,
    )


@pytest.mark.parametrize("met", [Fraction(-1), Fraction(3, 2)])
def test_a_probability_outside_zero_and_one_is_refused(met):
    with pytest.raises(ValidationError, match=r"probability .* is not in"):
        _scored(met)


@pytest.mark.parametrize("weight", [Fraction(-1), Fraction(3, 2)])
def test_a_weight_outside_zero_and_one_is_refused(weight):
    with pytest.raises(ValidationError, match=r"weight .* is not in"):
        TermScore(
            notation=r"$\evE \prec \evP$",
            group=Group.EMBARGO,
            weight=weight,
            met=Fraction(1, 2),
        )


def test_a_part_score_out_of_order_is_refused():
    with pytest.raises(ValidationError, match="not between"):
        PartScore(expected=Fraction(1), best=Fraction(1, 2), worst=Fraction(0))


@pytest.mark.parametrize(
    ("met", "best", "worst", "match"),
    [
        (Fraction(1, 2), Fraction(1), Fraction(0), "more than"),
        (Fraction(1), Fraction(1, 2), Fraction(0), "less than"),
        (Fraction(1, 2), Fraction(1, 8), Fraction(0), "not between"),
    ],
)
def test_a_walk_score_no_end_could_have_is_refused(met, best, worst, match):
    with pytest.raises(ValidationError, match=match):
        WalkScore(terms=(_scored(met),), best=best, worst=worst)
