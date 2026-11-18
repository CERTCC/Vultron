"""A case reading's standing record (#6366).

The bridge turns a reading's ledger into the rows the measure layer reads,
so the shadow's standing is the one ``case_standing`` reads from the file
itself; a reading with no entry has no standing, only its reader's report.

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
from vultron.measure.history import case_narrative
from vultron.measure.ledger import read_case_ledgers
from vultron.measure.standing import DesideratumStatus, case_standing
from vultron.shadow.analysis import analyse, reading_ledger
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
