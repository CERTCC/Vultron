"""The case narrative reads one row per ledger entry, its state changes
in words and a flag the source cannot observe as unknown (#6670).

Spec: CRD-02-005, DRPT-03-009.
"""

from datetime import UTC, datetime

import pytest

from test.adapters.connectors.vince._support import ACTIVE, translate
from test.shadow.dashboard._support import recording_analysis
from test.shadow.dashboard.view._support import (
    NAMES,
    VENDOR,
    narrative_line,
)
from vultron.core.models._helpers import format_timestamp
from vultron.core.states.cs_invariants import CSEvent
from vultron.core.states.em import EM
from vultron.core.states.rm import RM
from vultron.measure.history import StateChange, StateMachine
from vultron.measure.ledger import MISSING_SLOT, UNNAMED_ACTOR
from vultron.shadow.analysis import analyse
from vultron.shadow.dashboard import view

_T0 = datetime(2026, 1, 1, tzinfo=UTC)
_T1 = datetime(2026, 1, 1, 0, 0, 1, tzinfo=UTC)


def test_each_narrative_line_reads_as_a_row_keyed_by_its_log_index():
    """AC-1 and AC-2: one row per line, in order, by log index."""
    analysis = recording_analysis()
    rows = view.narrative_rows(analysis.narrative, analysis.actor_names)
    assert [row["#"] for row in rows] == [
        line.log_index for line in analysis.narrative
    ]
    assert [row["#"] for row in rows] == list(range(len(rows)))
    assert all(row["Activity"] and row["Actor"] for row in rows)
    assert "Notes" not in rows[0]


def test_a_row_shows_the_commit_stamp_only_where_it_differs():
    same, later, unclaimed = view.narrative_rows(
        [
            narrative_line(claimed_at=_T0, committed_at=_T0),
            narrative_line(log_index=1, claimed_at=_T0, committed_at=_T1),
            narrative_line(log_index=2, committed_at=_T1),
        ],
        {},
    )
    assert (same["Time"], same["Committed"]) == (format_timestamp(_T0), "")
    assert (later["Time"], later["Committed"]) == (
        format_timestamp(_T0),
        format_timestamp(_T1),
    )
    assert (unclaimed["Time"], unclaimed["Committed"]) == (
        MISSING_SLOT,
        format_timestamp(_T1),
    )


def test_a_row_names_who_did_what_to_what():
    (row,) = view.narrative_rows(
        [narrative_line(actor="Vendor", object="note → case")], {}
    )
    assert (row["Actor"], row["Activity"], row["Object"]) == (
        "Vendor",
        "Vendor did a thing",
        "note → case",
    )
    (bare,) = view.narrative_rows([narrative_line()], {})
    assert (
        bare["Time"],
        bare["Committed"],
        bare["Actor"],
        bare["Object"],
        bare["State changes"],
    ) == (MISSING_SLOT, "", MISSING_SLOT, MISSING_SLOT, "")


def test_every_state_change_reads_in_words_with_its_participant():
    changes = (
        StateChange(
            machine=StateMachine.RM,
            participant=VENDOR,
            before="RECEIVED",
            after="VALID",
        ),
        StateChange(machine=StateMachine.EM, before="ACTIVE", after="REVISE"),
        StateChange(
            machine=StateMachine.VFD,
            participant=VENDOR,
            before="Vfd",
            after="VFd",
        ),
        StateChange(machine=StateMachine.PXA, before="pxa", after="Pxa"),
    )
    (row,) = view.narrative_rows([narrative_line(changes=changes)], NAMES)
    assert row["State changes"] == "; ".join(
        [
            f"Vendor RM: {view.RM_BADGES[RM.RECEIVED]} →"
            f" {view.RM_BADGES[RM.VALID]}",
            f"EM: {view.EM_BADGES[EM.ACTIVE]} → {view.EM_BADGES[EM.REVISE]}",
            "Vendor VFD: Vfd → VFd",
            "PXA: pxa → Pxa",
        ]
    )


@pytest.mark.spec("DRPT-03-009")
def test_a_participant_with_an_opaque_id_never_reads_as_its_id():
    opaque = "urn:uuid:8128411c-198e-50d1-bf2f-000000000001"
    change = StateChange(
        machine=StateMachine.RM,
        participant=opaque,
        before="START",
        after="RECEIVED",
    )
    text = view.change_text(change, {})
    assert opaque not in text
    assert text.startswith(f"{UNNAMED_ACTOR} RM: ")


@pytest.mark.spec("CRD-02-005")
def test_a_flag_the_source_cannot_observe_reads_as_unknown():
    unobservable = frozenset({CSEvent.F, CSEvent.D})
    assert view.cs_spelling("vfd", unobservable) == "v??"
    assert view.cs_spelling("Vfd", unobservable) == "V??"
    assert view.cs_spelling("Vfd", frozenset()) == "Vfd"
    assert view.cs_spelling("pXa", frozenset({CSEvent.A})) == "pX?"
    change = StateChange(
        machine=StateMachine.VFD, participant=VENDOR, before="vfd", after="Vfd"
    )
    assert view.change_text(change, NAMES, unobservable) == (
        "Vendor VFD: v?? → V??"
    )


def test_a_line_that_could_not_read_its_entry_says_why_in_notes():
    rows = view.narrative_rows(
        [
            narrative_line(),
            narrative_line(
                log_index=1, notes=("no commit stamp", "unknown type")
            ),
        ],
        {},
    )
    assert [row["Notes"] for row in rows] == [
        "",
        "no commit stamp; unknown type",
    ]


def test_a_vince_reading_has_a_narrative_line_per_entry():
    """AC-1: an outside-system reading reads its narrative too."""
    reading = translate(ACTIVE)
    analysis = analyse(reading)
    assert [line.log_index for line in analysis.narrative] == [
        entry.log_index for entry in reading.ledger
    ]
    rows = view.narrative_rows(
        analysis.narrative, analysis.actor_names, reading.unobservable_events
    )
    changes = " ".join(str(row["State changes"]) for row in rows)
    assert "EM: " in changes
    assert "VFD: v?? → V??" in changes
