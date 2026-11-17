"""A case reading's standing record (#6366).

The bridge turns a reading's ledger into the rows the measure layer reads,
so the shadow's standing is the one ``case_standing`` reads from the file
itself; a reading with no entry has no standing, only its reader's report.

Spec: CRD-01-003, CRD-02-005 (strict xfail, #6563).
"""

import pytest

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


def test_a_reading_with_no_entry_has_no_standing_but_keeps_its_report():
    fact = UntranslatedFact(
        source_record="rec-1", fact="kind = mood", reason=Reason.UNKNOWN_VALUE
    )
    reading = CaseReading(ledger=(), citations=(), untranslated=(fact,))
    analysis = analyse(reading)
    assert reading_ledger(reading) is None
    assert analysis.standing is None
    assert analysis.reading.untranslated == (fact,)


@pytest.mark.spec("CRD-02-005")
@pytest.mark.xfail(
    strict=True,
    reason=(
        "CRD-02-005: a desideratum that orders an event the reading declares"
        " unobservable must read as unknown, not met or broken. Tracked by"
        " #6563."
    ),
)
def test_a_desideratum_over_an_unobservable_event_is_not_scored():
    """A recorded case whose reader declares Fix Deployed unobservable: its
    ``D ≺ P`` reads broken today, where it must read unknown."""
    recorded = VultronCaseReader(root=RECORDINGS_DIR).read_case(
        str(_RECORDING)
    )
    reading = CaseReading(
        ledger=recorded.ledger,
        citations=recorded.citations,
        unobservable=(
            UnobservableFact(
                fact="Fix Deployed (D)", why="The source has no such field."
            ),
        ),
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
