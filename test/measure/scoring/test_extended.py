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

"""The extended desiderata, scored for each vendor and each case-wide group (#6457).

An incomplete case is scored through its completions (ADR-0182), in each
scope: each vendor, the embargo group and the multi-party group (ADR-0200).  The hand-checked values use the baselines of
``process_model_desiderata.md`` § "The baselines".
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
    baseline,
    implications,
)
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
    ScopeScore,
    TermScore,
    UnscoredScope,
    WalkScore,
    exit_end,
    multi_party_scope,
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
_F_BEFORE_P_WEIGHT = 1 - Fraction(1, 24)


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


def _term(scope, notation_part: str, vendors: tuple[str, ...] | None = None):
    assert isinstance(scope, ScopeScore)
    (found,) = [
        t
        for t in scope.terms
        if notation_part in t.notation
        and (vendors is None or t.vendors == vendors)
    ]
    return found


# ---------------------------------------------------------------------------
# The scopes cover the extended desiderata once each
# ---------------------------------------------------------------------------


def test_every_extended_desideratum_is_scored_once_in_one_scope():
    """Each lands in one scope, unless an equivalent one is listed before
    it: the embargo group keeps ``E ≺ P`` and ``Ex_own ≺ P``."""
    scopes = scope_desiderata()
    listed = [d for scope in scopes for d in scope]
    assert len(set(listed)) == len(listed)
    equivalent = {
        frozenset((i.stronger, i.weaker))
        for i in implications()
        if i.equivalent
    }
    for d in EXTENDED:
        assert d in listed or any(
            frozenset((d, kept)) in equivalent for kept in listed
        ), d.notation
    assert [d.notation for d in scopes.embargo] == [
        r"$\evE \prec \evP$",
        r"$\evExOwn \prec \evP$",
    ]
    assert {d.group for d in scopes.vendor} == {
        Group.REPORT_HANDLING,
        Group.EMBARGO,
    }
    assert [d.notation for d in scopes.vendor if d.group is Group.EMBARGO] == [
        r"$\evF_i \prec \evExOwn$"
    ]


# ---------------------------------------------------------------------------
# AC-1: a recorded vendor's score includes its extended desiderata
# ---------------------------------------------------------------------------


def test_a_recorded_vendors_score_includes_its_report_handling_desiderata():
    """``rcv``: the vendor accepts at log index 22, the case goes public at
    28 and the embargo ends on that threat signal at 29.

    So every report-handling desideratum is met, and ``F_i ≺ Ex_own`` is
    out of scope for good: an embargo that ended on a threat signal never
    ends on its own terms.
    """
    (vendor,) = _recording("rcv").vendors
    extended = vendor.extended
    assert isinstance(extended, ScopeScore)
    accepted_before_public = _term(extended, r"\evAc_i \prec \evP")
    assert accepted_before_public.met == 1
    assert accepted_before_public.weight == 1 - Fraction(5, 96)
    assert _term(extended, r"\evExOwn").met == 0
    by_hand = (
        (1 - Fraction(5, 96))  # Ac_i ≺ P
        + (1 - Fraction(16, 81))  # Ac_i ≺ X
        + (1 - Fraction(2, 9))  # Ac_i ≺ A
        + (1 - Fraction(1, 6))  # Va_i ≺ P
        + (1 - Fraction(1, 3))  # Ac_i ≺ F_i
    )
    assert extended.expected == extended.best == extended.worst == by_hand
    assert vendor.expected == vendor.score.expected + by_hand


@pytest.mark.parametrize(
    "path",
    sorted(RECORDINGS_DIR.glob("*/case-actor.jsonl")),
    ids=lambda p: p.parent.name,
)
def test_every_recorded_vendor_and_group_is_scored(path):
    (history,) = read_case_event_histories([path]).histories.values()
    summary = score_case(history)
    for vendor in summary.vendors:
        assert isinstance(vendor.extended, ScopeScore)
        assert [t.notation for t in vendor.extended.terms] == [
            d.notation for d in scope_desiderata().vendor
        ]
    assert isinstance(summary.embargo, ScopeScore)
    if summary.vendors:
        assert isinstance(summary.multi_party, ScopeScore)


# ---------------------------------------------------------------------------
# AC-2: the case summary scores the embargo and the multi-party group
# ---------------------------------------------------------------------------


def test_a_recorded_case_scores_its_embargo_and_multi_party_groups():
    """``rcv``: the embargo starts at creation and ends on a threat signal,
    so ``E`` precedes ``P``, ``X`` and ``A`` and ``Ex_own`` never comes;
    the one vendor's fix (26) precedes public awareness (28)."""
    summary = _recording("rcv")
    embargo = summary.embargo
    assert isinstance(embargo, ScopeScore)
    assert _term(embargo, r"\evE \prec \evP").met == 1
    assert _term(embargo, r"\evExOwn \prec \evP").met == 0
    assert embargo.expected == embargo.best == embargo.worst == _E_WEIGHT
    multi_party = summary.multi_party
    assert isinstance(multi_party, ScopeScore)
    (term,) = multi_party.terms
    assert term.notation == r"$\evF_i \prec \evP$"
    assert multi_party.expected == _F_BEFORE_P_WEIGHT


# ---------------------------------------------------------------------------
# AC-3: an incomplete history is scored through its completions
# ---------------------------------------------------------------------------


def test_an_open_embargo_is_scored_through_its_completions():
    """From an active embargo with nothing public, five steps settle
    ``Ex_own ≺ P`` — ``P``, ``X``, ``A``, an own-terms exit and another
    exit — and a revision only delays them.  So it is met with probability
    1/5; ``E ≺ P`` is already met."""
    summary = score_case(_vendor_done_embargo_active())
    embargo = summary.embargo
    assert isinstance(embargo, ScopeScore)
    assert _term(embargo, r"\evE \prec \evP").met == 1
    assert _term(embargo, r"\evExOwn \prec \evP").met == Fraction(1, 5)
    assert embargo.expected == _E_WEIGHT + _EX_OWN_WEIGHT / 5
    assert embargo.best == _E_WEIGHT + _EX_OWN_WEIGHT
    assert embargo.worst == _E_WEIGHT


def test_an_open_scope_event_still_has_to_occur():
    """The vendor's fix is ready under an embargo still in force, so
    ``F_i ≺ Ex_own`` counts once the embargo ends on its own terms, with
    the same 1/5."""
    (vendor,) = score_case(_vendor_done_embargo_active()).vendors
    extended = vendor.extended
    assert isinstance(extended, ScopeScore)
    fix_first = _term(extended, r"\evExOwn")
    assert fix_first.met == Fraction(1, 5)
    others = [t for t in extended.terms if t is not fix_first]
    assert all(t.met == 1 for t in others)
    settled = sum((t.weight for t in others), Fraction(0))
    assert extended.expected == settled + fix_first.weight / 5
    assert extended.best == settled + fix_first.weight
    assert extended.worst == settled


def test_a_case_whose_events_have_all_happened_has_one_score():
    (vendor,) = _recording("rcv").vendors
    for scope in (vendor.extended, _recording("rcv").embargo):
        assert isinstance(scope, ScopeScore)
        assert scope.best == scope.worst == scope.expected


# ---------------------------------------------------------------------------
# AC-4: no vendor's sequence is combined with another's
# ---------------------------------------------------------------------------


@pytest.mark.spec("CEH-05-006")
def test_each_walk_reads_one_vendor_or_one_pair():
    """``rvv`` has two vendors: each scope term names at most two, the
    vendor scope only its own, and the pair desideratum both orders."""
    summary = _recording("rvv")
    vendors = [v.participant for v in summary.vendors]
    assert len(vendors) == 2
    for vendor in summary.vendors:
        assert isinstance(vendor.extended, ScopeScore)
        assert {t.vendors for t in vendor.extended.terms} == {
            (vendor.participant,)
        }
    multi_party = summary.multi_party
    assert isinstance(multi_party, ScopeScore)
    pairs = [
        t.vendors for t in multi_party.terms if t.notation.count("_") == 2
    ]
    assert sorted(pairs) == sorted(
        [(vendors[0], vendors[1]), (vendors[1], vendors[0])]
    )
    assert all(len(walk.terms) == 1 for walk in multi_party.walks)
    singles = [t.vendors for t in multi_party.terms if len(t.vendors) == 1]
    assert sorted(singles) == sorted((v,) for v in vendors)


def test_a_pair_term_weighs_the_two_vendor_baseline():
    summary = _recording("rvv")
    multi_party = summary.multi_party
    assert isinstance(multi_party, ScopeScore)
    (pair_desideratum,) = [
        d for d in scope_desiderata().multi_party if "F_j" in d.notation
    ]
    for term in multi_party.terms:
        if len(term.vendors) == 2:
            assert term.weight == 1 - baseline(pair_desideratum)
            assert term.weight == Fraction(7, 400)


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
    assert (vendor.expected, vendor.best, vendor.worst) == (None, None, None)


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
    assert isinstance(before.embargo, ScopeScore)
    assert before.embargo == after.embargo
    assert before.multi_party == after.multi_party
    assert _term(before.embargo, r"\evExOwn \prec \evP").met == 0


def test_an_embargo_that_starts_after_publication_is_not_scored():
    """No embargo is in force beside public awareness (CSB-18-002)."""
    history = _history(
        _event(1, CSEvent.V, _V1),
        _event(2, CSEvent.P),
        _start(3),
    )
    summary = score_case(history)
    assert isinstance(summary.embargo, UnscoredScope)
    assert "no joint-model state" in summary.embargo.reason
    assert isinstance(summary.multi_party, UnscoredScope)


def test_one_vendor_the_model_cannot_walk_leaves_the_group_unscored():
    """The second vendor's fix comes before its report is accepted, so the
    multi-party group, which walks it too, has no score, while the first
    vendor keeps its own."""
    v2 = "https://example.org/actors/vendor-2"
    history = _history(
        _start(0),
        _event(1, CSEvent.V, _V1),
        _event(2, CSEvent.V, v2),
        _event(3, CSEvent.F, v2),
    )
    summary = score_case(history)
    first, second = summary.vendors
    assert isinstance(first.extended, ScopeScore)
    assert isinstance(second.extended, UnscoredScope)
    assert isinstance(summary.multi_party, UnscoredScope)
    assert isinstance(summary.embargo, ScopeScore)


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


def test_a_case_with_no_vendor_has_no_multi_party_group():
    history = _history(_start(0))
    record = CaseRecord(history, ())
    assert multi_party_scope(record) is None


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
    with pytest.raises(ValidationError, match="not in"):
        _scored(met)


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
