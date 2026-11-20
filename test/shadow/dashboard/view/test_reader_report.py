"""A reader's report reads as rows (#6366).

Spec: SHD-01-004.
"""

import pytest

from vultron.core.models.case_reading import (
    CaseReading,
    UnobservableFact,
    UntranslatedFact,
    UntranslatedReason as Reason,
)
from vultron.core.states.cs_invariants import CSEvent
from vultron.shadow.dashboard import view


@pytest.mark.spec("SHD-01-004")
def test_the_readers_report_reads_as_rows():
    reading = CaseReading(
        ledger=(),
        citations=(),
        untranslated=(
            UntranslatedFact(
                source_record="rec-1",
                fact="kind = mood",
                reason=Reason.NO_COUNTERPART,
            ),
        ),
        unobservable=(
            UnobservableFact(
                fact="Fix Deployed",
                why="no field",
                events=frozenset({CSEvent.D}),
            ),
            UnobservableFact(fact="Activity log", why="not in the API"),
        ),
    )
    assert view.untranslated_rows(reading) == [
        {
            "Source record": "rec-1",
            "Fact": "kind = mood",
            "Why": "no counterpart",
        }
    ]
    assert view.unobservable_rows(reading) == [
        {
            "Fact": "Fix Deployed",
            "Why": "no field",
            "Reads as unknown": "Fix Deployed",
        },
        {
            "Fact": "Activity log",
            "Why": "not in the API",
            "Reads as unknown": "—",
        },
    ]
    assert view.inference_rows(reading) == []
