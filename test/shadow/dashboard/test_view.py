"""What the dashboard shows, as words, icons and rows (#6366).

Every state has a badge, every desideratum reads in words, a move's effect
is each vendor's own, and a gap or a reader's report reads as lines and
rows.

Spec: SHD-01-004, SHD-03-002.
"""

from fractions import Fraction

import pytest

from vultron.core.models.case_reading import (
    CaseReading,
    UnobservableFact,
    UntranslatedFact,
    UntranslatedReason as Reason,
)
from vultron.core.states.cs import CS_pxa
from vultron.core.states.cs_invariants import CSEvent
from vultron.core.states.em import EM, EM_Trigger
from vultron.core.states.rm import RM
from vultron.demo.recordings.layout import RECORDINGS_DIR
from vultron.measure.history import UnreadableEntry
from vultron.measure.ledger import UnusableRow
from vultron.measure.sequences import (
    UnprojectableParticipant,
    UnprojectableReason,
)
from vultron.measure.standing import (
    CaseStanding,
    DesideratumChange,
    DesideratumStatus,
    EMMove,
    ParticipantStanding,
    RMMove,
    ScoredMove,
    StandingGap,
)
from vultron.shadow.analysis import analyse
from vultron.shadow.dashboard import view
from vultron.shadow.readers import VultronCaseReader

VENDOR = "https://vendor.example/actors/vendor"
VENDOR_2 = "https://other.example/actors/vendor2"
NAMES = {VENDOR: "Vendor", VENDOR_2: "Vendor2"}


def _analysis():
    path = RECORDINGS_DIR / "rcvv-embargo" / "case-actor.jsonl"
    return analyse(VultronCaseReader().read_case(str(path)))


def test_every_state_and_status_has_a_badge():
    assert set(view.RM_BADGES) == set(RM)
    assert set(view.EM_BADGES) == set(EM)
    assert set(view.DESIDERATUM_BADGES) == set(DesideratumStatus)
    assert set(view.EVENT_LABELS) == set(CSEvent)


def test_the_public_state_reads_as_three_badges():
    assert view.public_badges(CS_pxa.pxa) == (
        "🤫 Not public",
        "🛡️ No public exploit",
        "🛡️ No attacks observed",
    )
    assert view.public_badges(CS_pxa.PXA) == (
        "📢 Public aware",
        "💥 Exploit public",
        "🎯 Attacks observed",
    )


def test_a_desideratum_reads_in_words_and_in_event_letters():
    standing = _analysis().standing
    assert standing is not None
    vendor = next(p for p in standing.participants if p.desiderata)
    first = vendor.desiderata[0]
    assert view.desideratum_label(first) == (
        f"{view.EVENT_LABELS[first.before]} before"
        f" {view.EVENT_LABELS[first.after]}"
    )
    assert view.desideratum_code(first) == (
        f"{first.before.value} ≺ {first.after.value}"
    )


def test_participant_rows_show_report_state_case_state_and_tally():
    analysis = _analysis()
    assert analysis.standing is not None
    rows = view.participant_rows(
        analysis.standing.participants, analysis.actor_names
    )
    vendor = next(r for r in rows if r["Participant"] == "Vendor")
    assert vendor["Report"] == view.RM_BADGES[RM.CLOSED]
    assert vendor["Case state"] == "VFdPxa"
    assert vendor["Desiderata"].startswith("✅ ")
    assert vendor["Not scored because"] == ""
    manager = next(r for r in rows if "CASE_MANAGER" in r["Roles"])
    assert manager["Case state"] == "—"
    assert manager["Not scored because"]


def test_an_invitee_with_no_roles_reads_as_invited_with_none():
    invitee = ParticipantStanding(
        participant=VENDOR,
        joined=False,
        rm=RM.START,
        case=CaseStanding(em=EM.NONE, pxa=CS_pxa.pxa),
        unscored=UnprojectableParticipant(
            participant=VENDOR,
            reason=UnprojectableReason.NO_CASE_STATE_EVENTS,
            detail="it has no event of its own",
        ),
    )
    (row,) = view.participant_rows([invitee], NAMES)
    assert row["Participant"] == "Vendor"
    assert row["Roles"] == "—"
    assert row["Joined"] == "✉️ invited"
    assert row["Report"] == view.RM_BADGES[RM.START]
    assert row["Not scored because"] == "it has no event of its own"


def test_desiderata_rows_give_each_scored_vendor_its_own_column():
    analysis = _analysis()
    assert analysis.standing is not None
    rows = view.desiderata_rows(
        analysis.standing.participants, analysis.actor_names
    )
    assert len(rows) == 12
    assert set(rows[0]) == {"Desideratum", "Events", "Vendor", "Vendor2"}
    assert rows[0]["Vendor"] in view.DESIDERATUM_BADGES.values()


def test_no_scored_vendor_gives_no_desiderata_rows():
    assert view.desiderata_rows([], {}) == []


def _cs_move() -> ScoredMove:
    analysis = _analysis()
    assert analysis.standing is not None
    move: ScoredMove = analysis.standing.moves[0]
    return move


@pytest.mark.spec("SHD-03-002")
def test_a_moves_effect_is_each_vendors_own_count():
    move = ScoredMove(
        move=_cs_move().move,
        changes=(
            DesideratumChange(
                vendor=VENDOR, notation="a", change=Fraction(1, 4)
            ),
            DesideratumChange(
                vendor=VENDOR, notation="b", change=Fraction(-1, 8)
            ),
            DesideratumChange(vendor=VENDOR_2, notation="a", change=0),
        ),
    )
    assert view.move_effect(move, NAMES) == "Vendor: ▲1 ▼1; Vendor2: no change"


def test_a_move_with_no_change_entries_reads_no_change():
    move = ScoredMove(move=_cs_move().move, changes=())
    assert view.move_effect(move, NAMES) == "no change"


def test_an_unscored_move_says_why():
    move = ScoredMove(
        move=RMMove(
            participant=VENDOR, source=RM.RECEIVED, destination=RM.VALID
        ),
        unscored="the case has no vendor to score a move for",
    )
    assert view.move_effect(move, NAMES) == (
        "not scored: the case has no vendor to score a move for"
    )


def test_a_move_that_keeps_every_state_is_advice():
    move = ScoredMove(
        move=EMMove(
            participant=VENDOR,
            trigger=EM_Trigger.PROPOSE,
            source=EM.PROPOSED,
            destination=EM.PROPOSED,
        )
    )
    assert view.move_effect(move, NAMES) == "advice: changes no state"
    (row,) = view.move_rows([move], NAMES)
    assert row == {
        "Who": "Vendor",
        "Machine": "EM",
        "Move": "Propose",
        "From → to": "PROPOSED → PROPOSED",
        "Effect by vendor": "advice: changes no state",
    }


def test_move_rows_keep_the_standing_records_order():
    analysis = _analysis()
    assert analysis.standing is not None
    rows = view.move_rows(analysis.standing.moves, analysis.actor_names)
    assert [r["Move"] for r in rows] == [
        m.move.name.partition(".")[2].replace("_", " ").capitalize()
        for m in analysis.standing.moves
    ]


def test_every_kind_of_hole_reads_as_a_line(tmp_path):
    gap = StandingGap(
        missing_log_indices=[2],
        conflicting_log_indices=[4],
        unusable_rows=[
            UnusableRow(path=tmp_path / "x.jsonl", line=3, reason="not JSON")
        ],
        unreadable_entries=[UnreadableEntry(log_index=5, reason="no stamp")],
        register_problem="two active embargoes",
    )
    lines = view.gap_lines(gap)
    assert lines[0] == "Missing log indices: [2]"
    assert lines[1] == "Conflicting log indices: [4]"
    assert "not JSON" in lines[2]
    assert lines[3] == "Unreadable entry at log index 5: no stamp"
    assert lines[4] == "Embargo register: two active embargoes"


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
        unobservable=(UnobservableFact(fact="Fix Deployed", why="no field"),),
    )
    assert view.untranslated_rows(reading) == [
        {
            "Source record": "rec-1",
            "Fact": "kind = mood",
            "Why": "no counterpart",
        }
    ]
    assert view.unobservable_rows(reading) == [
        {"Fact": "Fix Deployed", "Why": "no field"}
    ]
    assert view.inference_rows(reading) == []
