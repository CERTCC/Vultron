"""A case reading's standing record (#6366).

The bridge turns a reading's ledger into the rows the measure layer reads,
so the shadow's standing is the one ``case_standing`` reads from the file
itself; a reading with no entry has no standing, only its reader's report.

The standing at an earlier point is the same computation over a prefix of
the reading: it equals the standing of a reading that holds only those
entries, read from a file cut after them (#6671).

Each narrative line's hindsight mark grades its step by the advice for the
entries before it, worked out only for a line whose entry changes a state
(#6672).

Spec: CRD-01-003, CRD-02-005 (strict xfail, #6563).
"""

import pytest

import vultron.measure.history.narrative as narrative_module
import vultron.measure.standing.read as standing_read
import vultron.shadow.analysis as analysis_module
from test.support.case_reader import (
    FAKE_CASE,
    FakeCaseReader,
    fake_case_records,
)
from vultron.core.models.case_reading import (
    CaseReading,
    UnobservableFact,
    UntranslatedFact,
    UntranslatedReason as Reason,
)
from vultron.core.states.cs_invariants import CSEvent
from vultron.demo.recordings.layout import RECORDINGS_DIR
from vultron.measure.advice import HindsightMark, case_advice
from vultron.measure.advice.hindsight import NO_ADVICE, NO_STATE_CHANGE
from vultron.measure.history import case_narrative
from vultron.measure.ledger import read_case_ledgers
from vultron.measure.standing import CSMove, DesideratumStatus, case_standing
from vultron.shadow.analysis import (
    analyse,
    analyse_prefix,
    count_through,
    ledger_advice,
    narrative_marks,
    point_analysis,
    prefix_advice,
    reading_ledger,
    reading_prefix,
)
from vultron.shadow.readers import VultronCaseReader

_RECORDING = RECORDINGS_DIR / "rcvv-embargo" / "case-actor.jsonl"


@pytest.mark.spec("CRD-01-003")
def test_the_standing_is_the_one_the_file_itself_yields():
    reading = VultronCaseReader(root=RECORDINGS_DIR).read_case(str(_RECORDING))
    (from_file,) = read_case_ledgers([_RECORDING]).cases.values()
    assert analyse(reading).standing == case_standing(from_file)


def test_the_bridged_ledger_is_one_complete_copy_in_log_index_order():
    reading = FakeCaseReader({FAKE_CASE: fake_case_records()}).read_case(
        FAKE_CASE
    )
    ledger = reading_ledger(reading)
    assert ledger is not None
    assert ledger.case_id == FAKE_CASE
    assert not ledger.merged
    assert [row.log_index for row in ledger.rows] == [
        entry.log_index for entry in reading.ledger
    ]


def test_the_analysis_names_actors_by_their_payload_names():
    analysis = analyse(
        VultronCaseReader(root=RECORDINGS_DIR).read_case(str(_RECORDING))
    )
    assert "Vendor" in analysis.actor_names.values()


def test_the_narrative_is_the_one_the_bridged_ledger_reads():
    """#6670 AC-1: a line per entry of the reading, from its own ledger."""
    reading = FakeCaseReader({FAKE_CASE: fake_case_records()}).read_case(
        FAKE_CASE
    )
    ledger = reading_ledger(reading)
    assert ledger is not None
    narrative = analyse(reading).narrative
    assert narrative == case_narrative(ledger)
    assert [line.log_index for line in narrative] == [
        entry.log_index for entry in reading.ledger
    ]


def test_the_standing_and_the_narrative_share_one_walk(monkeypatch):
    """One walk, so an entry the walk cannot read is reported once."""
    walks: list[object] = []
    real = analysis_module.derive_case_steps

    def counted(ledger):
        walks.append(ledger)
        return real(ledger)

    def refused(_ledger):
        raise AssertionError("the standing walked the ledger again")

    monkeypatch.setattr(analysis_module, "derive_case_steps", counted)
    monkeypatch.setattr(standing_read, "derive_case", refused)
    monkeypatch.setattr(narrative_module, "derive_case_steps", refused)
    reading = VultronCaseReader(root=RECORDINGS_DIR).read_case(str(_RECORDING))
    analysis = analyse(reading)
    assert len(walks) == 1
    assert analysis.standing is not None and analysis.narrative


def test_a_reading_with_no_entry_has_no_standing_but_keeps_its_report():
    fact = UntranslatedFact(
        source_record="rec-1", fact="kind = mood", reason=Reason.UNKNOWN_VALUE
    )
    reading = CaseReading(ledger=(), citations=(), untranslated=(fact,))
    analysis = analyse(reading)
    assert reading_ledger(reading) is None
    assert analysis.standing is None
    assert analysis.narrative == ()
    assert analysis.reading.untranslated == (fact,)


def _recorded_with(*unobservable: UnobservableFact) -> CaseReading:
    """The recorded case, read from a source that declares *unobservable*."""
    recorded = VultronCaseReader(root=RECORDINGS_DIR).read_case(
        str(_RECORDING)
    )
    return CaseReading(
        ledger=recorded.ledger,
        citations=recorded.citations,
        unobservable=unobservable,
    )


_NO_FIX = UnobservableFact(
    fact="Fix ready (F), fix deployed (D)",
    why="The source has no such field.",
    events=frozenset({CSEvent.F, CSEvent.D}),
)


@pytest.mark.spec("CRD-02-005")
def test_a_desideratum_over_an_unobservable_event_is_not_scored():
    """A recorded case whose reader declares Fix Deployed unobservable: its
    ``D ≺ P`` reads unknown, never met or broken."""
    reading = _recorded_with(
        UnobservableFact(
            fact="Fix Deployed (D)",
            why="The source has no such field.",
            events=frozenset({CSEvent.D}),
        )
    )
    standing = analyse(reading).standing
    assert standing is not None
    over_d = [
        d
        for p in standing.participants
        for d in p.desiderata
        if CSEvent.D in (d.before, d.after)
    ]
    assert over_d
    assert all(
        d.status not in (DesideratumStatus.MET, DesideratumStatus.BROKEN)
        for d in over_d
    )


@pytest.mark.spec("CRD-02-005")
def test_no_desideratum_about_the_fix_is_broken_when_fix_readiness_is_unseen():
    standing = analyse(_recorded_with(_NO_FIX)).standing
    assert standing is not None
    for p in standing.participants:
        for d in p.desiderata:
            fix = {CSEvent.F, CSEvent.D} & {d.before, d.after}
            unknown = d.status is DesideratumStatus.UNKNOWN
            assert unknown == bool(fix), d.notation


def test_a_fact_that_names_no_event_leaves_the_standing_as_it_was():
    plain = analyse(_recorded_with()).standing
    log_only = UnobservableFact(fact="The activity log", why="Not exposed.")
    assert analyse(_recorded_with(log_only)).standing == plain


@pytest.mark.spec("CRD-02-005")
def test_a_move_that_rests_on_an_unobservable_event_has_a_reason_not_a_number():
    plain = analyse(_recorded_with()).standing
    unseen = analyse(_recorded_with(_NO_FIX)).standing
    assert plain is not None and unseen is not None
    pairs = list(zip(plain.moves, unseen.moves, strict=True))
    newly = [
        u for p, u in pairs if p.changes is not None and u.changes is None
    ]
    assert newly
    for move in newly:
        assert move.unscored is not None
        assert "cannot observe" in move.unscored


def _cut_reading(tmp_path, count: int) -> CaseReading:
    """The recorded case read from a copy of its file cut after *count*
    entries: a reading that holds only those entries."""
    lines = _RECORDING.read_text().splitlines()[:count]
    (tmp_path / "cut.jsonl").write_text("\n".join(lines) + "\n")
    return VultronCaseReader(root=tmp_path).read_case("cut.jsonl")


@pytest.mark.parametrize("count", [1, 4, 20, 45])
def test_the_standing_at_a_prefix_is_that_of_a_reading_of_only_it(
    tmp_path, count
):
    """#6671 AC-2: the case just after its *count*-th entry, read from the
    whole reading, is the case a reading of only those entries gives."""
    whole = VultronCaseReader(root=RECORDINGS_DIR).read_case(str(_RECORDING))
    assert count < len(whole.ledger)
    cut = analyse(_cut_reading(tmp_path, count))
    at_prefix = analyse_prefix(whole, count)
    assert at_prefix.standing is not None
    assert at_prefix.standing == cut.standing
    assert at_prefix.narrative == cut.narrative
    assert at_prefix.standing != analyse(whole).standing


def test_the_whole_prefix_is_the_whole_reading():
    whole = VultronCaseReader(root=RECORDINGS_DIR).read_case(str(_RECORDING))
    assert analyse_prefix(whole, len(whole.ledger)) == analyse(whole)


def test_the_advice_at_a_prefix_is_the_advice_of_its_standing(tmp_path):
    whole = VultronCaseReader(root=RECORDINGS_DIR).read_case(str(_RECORDING))
    standing = analyse(_cut_reading(tmp_path, 4)).standing
    assert standing is not None
    assert prefix_advice(whole, 4) == case_advice(standing)


def test_before_the_first_entry_there_is_no_advice():
    whole = VultronCaseReader(root=RECORDINGS_DIR).read_case(str(_RECORDING))
    assert analyse_prefix(whole, 0).standing is None
    assert prefix_advice(whole, 0) is None


def test_a_prefix_keeps_what_its_entries_carry_and_the_reader_report():
    """Each kept entry keeps its citation and inferences; the untranslated
    facts and the unobservable declaration stay whole (CRD-02-005)."""
    reading = FakeCaseReader({FAKE_CASE: fake_case_records()}).read_case(
        FAKE_CASE
    )
    prefix = reading_prefix(reading, 2)
    kept = {entry.id_ for entry in reading.ledger[:2]}
    assert prefix.ledger == reading.ledger[:2]
    assert {c.entry_id for c in prefix.citations} == kept
    assert prefix.inferences == tuple(
        i for i in reading.inferences if i.entry_id in kept
    )
    assert len(prefix.inferences) < len(reading.inferences)
    assert prefix.untranslated == reading.untranslated
    assert prefix.unobservable == reading.unobservable
    assert prefix.unobservable_events == reading.unobservable_events


@pytest.mark.spec("CRD-02-005")
def test_an_unobservable_event_reads_as_unknown_at_every_point():
    whole = _recorded_with(_NO_FIX)
    for count in (20, len(whole.ledger) // 2):
        standing = analyse_prefix(whole, count).standing
        assert standing is not None
        over_fix = [
            d
            for p in standing.participants
            for d in p.desiderata
            if {CSEvent.F, CSEvent.D} & {d.before, d.after}
        ]
        assert over_fix, f"no desideratum over F or D after {count} entries"
        assert all(d.status is DesideratumStatus.UNKNOWN for d in over_fix)


def test_a_prefix_before_a_hole_has_a_standing_and_one_past_it_has_none(
    tmp_path,
):
    rows = _RECORDING.read_text().splitlines()
    (tmp_path / "holed.jsonl").write_text(
        "\n".join(rows[:2] + rows[3:]) + "\n"
    )
    holed = VultronCaseReader(root=tmp_path).read_case("holed.jsonl")
    before = analyse_prefix(holed, 2).standing
    past = analyse_prefix(holed, 3).standing
    assert before is not None and before.gap is None
    assert past is not None and past.gap is not None
    assert past.gap.missing_log_indices == [2]


@pytest.mark.parametrize("count", [-1, 99])
def test_a_prefix_longer_than_the_reading_or_negative_is_refused(count):
    reading = FakeCaseReader({FAKE_CASE: fake_case_records()}).read_case(
        FAKE_CASE
    )
    with pytest.raises(ValueError, match=f"cannot hold {count}"):
        reading_prefix(reading, count)
    with pytest.raises(ValueError, match=f"cannot hold {count}"):
        prefix_advice(reading, count)


def test_the_prefix_through_an_entry_ends_with_it():
    whole = VultronCaseReader(root=RECORDINGS_DIR).read_case(str(_RECORDING))
    third = whole.ledger[2].log_index
    assert count_through(whole, third) == 3
    assert (
        reading_prefix(whole, count_through(whole, third)).ledger[-1]
        == (whole.ledger[2])
    )
    with pytest.raises(ValueError, match="no ledger entry at 9999"):
        count_through(whole, 9999)


def test_a_point_reads_its_prefix_and_keeps_the_whole_readings_names():
    """The dashboard's point: the prefix's standing, with the names the
    whole reading gives its actors, which its first entries do not."""
    whole = analyse(
        VultronCaseReader(root=RECORDINGS_DIR).read_case(str(_RECORDING))
    )
    log_index = whole.reading.ledger[3].log_index
    prefix = analyse_prefix(whole.reading, 4)
    assert prefix.actor_names != whole.actor_names
    at_point = point_analysis(whole, log_index)
    assert at_point.standing == prefix.standing
    assert at_point.narrative == prefix.narrative
    assert at_point.actor_names == whole.actor_names
    with pytest.raises(ValueError, match="no ledger entry at 9999"):
        point_analysis(whole, 9999)


# -- hindsight marks (#6672) ----------------------------------------------

_RV = RECORDINGS_DIR / "rv" / "case-actor.jsonl"


def _rv() -> CaseReading:
    return VultronCaseReader(root=RECORDINGS_DIR).read_case(str(_RV))


def test_each_line_is_graded_by_the_advice_for_the_entries_before_it():
    """#6672 AC-1: one mark per narrative line, each read from the advice
    for the ledger prefix before its entry, asked only where the entry
    changes a state."""
    reading = _rv()
    asked: list[int] = []

    def advice_of(entries, unobservable):
        assert entries == reading.ledger[: len(entries)]
        assert unobservable == reading.unobservable_events
        asked.append(len(entries))
        return ledger_advice(entries, unobservable)

    marks = narrative_marks(reading, advice_of)
    narrative = analyse(reading).narrative
    assert [m.log_index for m in marks] == [n.log_index for n in narrative]
    changed = [i for i, line in enumerate(narrative) if line.changes]
    assert asked == changed
    assert marks[0].note == NO_ADVICE
    assert all(
        marks[i].note == NO_STATE_CHANGE
        for i in range(len(marks))
        if i not in asked
    )
    assert marks == narrative_marks(reading)


def test_the_advice_for_a_prefix_reads_its_entries_alone():
    reading = _rv()
    assert ledger_advice(reading.ledger[:12]) == prefix_advice(reading, 12)
    assert ledger_advice(()) is None


def test_making_the_case_public_is_graded_as_the_publication_move():
    """The user's ruling for #6672: publishing is a participant's move, and
    the first publication is the one that makes the case public, so its
    line is graded as the advice's public-awareness move, never as chance."""
    reading = _rv()
    narrative = analyse(reading).narrative
    marks = narrative_marks(reading)
    (public,) = [
        mark
        for line, mark in zip(narrative, marks, strict=True)
        if any(c.machine == "PXA" for c in line.changes)
    ]
    assert isinstance(public.move, CSMove)
    assert public.move.event is CSEvent.P
    assert public.mark not in (HindsightMark.CHANCE, HindsightMark.NOT_A_MOVE)


def test_a_consent_answer_is_not_a_move():
    """PEC moves are not in the move advice yet (#6677), so an embargo
    consent answer changes no state the advice weighs."""
    reading = VultronCaseReader(root=RECORDINGS_DIR).read_case(str(_RECORDING))
    narrative = analyse(reading).narrative
    marks = narrative_marks(reading, lambda entries, unobservable: None)
    answers = [
        mark
        for line, mark in zip(narrative, marks, strict=True)
        if line.semantic_type == "accept_invite_to_embargo_on_case"
    ]
    assert answers
    assert all(
        (m.mark, m.note) == (HindsightMark.NOT_A_MOVE, NO_STATE_CHANGE)
        for m in answers
    )


def test_a_reading_with_no_entry_has_no_marks():
    reading = CaseReading(ledger=(), citations=())
    assert narrative_marks(reading) == ()
