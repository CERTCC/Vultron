"""Every desideratum of a vendor's scope reads in words, one row each
with a column per scored vendor (#6366, #6669).

Spec: CRD-02-005.
"""

from fractions import Fraction

import pytest

from test.shadow.dashboard._support import (
    reading_with_d_unobservable,
    recording_analysis,
)
from test.shadow.dashboard.view._support import NAMES, VENDOR
from vultron.core.states.cs import CS_pxa
from vultron.core.states.em import EM
from vultron.core.states.rm import RM
from vultron.measure.advice import scope_shift
from vultron.measure.baselines import (
    EXTENDED,
    ORIGINAL,
    ModelName,
    VendorDesideratum,
    scope_desiderata,
)
from vultron.measure.scoring import UnscoredScope, score_prefix
from vultron.measure.standing import (
    CaseStanding,
    DesideratumStatus,
    ParticipantStanding,
)
from vultron.shadow.analysis import analyse
from vultron.shadow.dashboard import view


def test_a_desideratum_reads_in_words_and_in_event_letters():
    standing = recording_analysis().standing
    assert standing is not None
    vendor = next(p for p in standing.participants if p.desiderata)
    first = vendor.desiderata[0]
    assert view.desideratum_label(first) == (
        f"{view.DESIDERATUM_EVENT_LABELS[first.before]} before"
        f" {view.DESIDERATUM_EVENT_LABELS[first.after]}"
    )
    assert view.desideratum_code(first) == (
        f"{first.before.value} ≺ {first.after.value}"
    )


def test_a_report_handling_desideratum_reads_in_its_own_events():
    standing = recording_analysis().standing
    assert standing is not None
    vendor = next(p for p in standing.participants if p.desiderata)
    (accepted,) = [
        d for d in vendor.desiderata if d.notation == r"$\evAc_i \prec \evP$"
    ]
    assert view.desideratum_label(accepted) == (
        "Report Acceptance before Public Awareness"
    )
    assert view.desideratum_code(accepted) == "Ac ≺ P"


def test_desiderata_rows_give_each_scored_vendor_its_own_column():
    analysis = recording_analysis()
    assert analysis.standing is not None
    rows = view.desiderata_rows(
        analysis.standing.participants, analysis.actor_names
    )
    assert len(rows) == len(scope_desiderata())
    assert set(rows[0]) == {"Desideratum", "Events", "Vendor", "Vendor2"}
    assert rows[0]["Vendor"] in view.DESIDERATUM_BADGES.values()


def _counted_by_move_advice() -> list[str]:
    """Each catalog desideratum whose reading moves a vendor's scope, found
    by asking :func:`scope_shift`, not by reading its list."""
    counted = []
    for d in (*ORIGINAL, *EXTENDED):
        other = 2 if d.model is ModelName.TWO_VENDOR else None
        shift = scope_shift({VendorDesideratum(d, 1, other): Fraction(1)}, 2)
        if any(part for parts in shift for part in parts):
            counted.append(d.notation)
    return counted


def test_the_table_shows_exactly_the_desiderata_move_advice_sums():
    """#6669 AC-2: the table's rows and move advice's scope are one list, so
    a desideratum added to either and not the other fails here."""
    analysis = recording_analysis()
    assert analysis.standing is not None
    participants = analysis.standing.participants
    rows = view.desiderata_rows(participants, analysis.actor_names)
    vendor = next(p for p in participants if p.desiderata)
    assert [row["Events"] for row in rows] == [
        view.desideratum_code(d) for d in vendor.desiderata
    ]
    assert [d.notation for d in vendor.desiderata] == _counted_by_move_advice()


def test_each_group_of_equivalent_desiderata_shows_once():
    """#6669 AC-3: ``E ≺ P`` stands for ``E ≺ X`` and ``E ≺ A``, and
    ``ExOwn ≺ P`` for its two (ADR-0200)."""
    analysis = recording_analysis()
    assert analysis.standing is not None
    codes = [
        row["Events"]
        for row in view.desiderata_rows(
            analysis.standing.participants, analysis.actor_names
        )
    ]
    assert len(codes) == len(set(codes))
    assert {"E ≺ P", "ExOwn ≺ P", "F ≺ ExOwn"} <= set(codes)
    assert not {"E ≺ X", "E ≺ A", "ExOwn ≺ X", "ExOwn ≺ A"} & set(codes)
    assert "V ≺ F" not in codes


def test_an_unwalked_vendor_reads_not_scored_and_its_tally_counts_them():
    unwalked = ParticipantStanding(
        participant=VENDOR,
        rm=RM.RECEIVED,
        case=CaseStanding(em=EM.NONE, pxa=CS_pxa.pxa),
        score=score_prefix("V"),
        extended=UnscoredScope(reason="the case stands in no joint state"),
    )
    rows = view.desiderata_rows([unwalked], NAMES)
    by_code = {row["Events"]: row["Vendor"] for row in rows}
    assert (
        by_code["Ac ≺ P"]
        == view.DESIDERATUM_BADGES[DesideratumStatus.UNSCORED]
    )
    assert by_code["V ≺ P"] == view.DESIDERATUM_BADGES[DesideratumStatus.MET]
    (row,) = view.participant_rows([unwalked], NAMES)
    unscored = len(scope_desiderata()) - len(ORIGINAL)
    assert f"▫️ {unscored}" in str(row["Desiderata"])
    assert row["Not scored because"] == (
        "report-handling and embargo desiderata:"
        " the case stands in no joint state"
    )


def test_vendors_that_share_a_label_keep_their_own_columns():
    analysis = recording_analysis()
    assert analysis.standing is not None
    vendors = [p for p in analysis.standing.participants if p.desiderata]
    same = {p.participant: "Events" for p in vendors}
    rows = view.desiderata_rows(analysis.standing.participants, same)
    assert set(rows[0]) == {
        "Desideratum",
        "Events",
        *(f"Events ({p.participant})" for p in vendors),
    }
    assert rows[0]["Events"] == view.desideratum_code(vendors[0].desiderata[0])


@pytest.mark.spec("CRD-02-005")
def test_an_unknown_desideratum_shows_its_own_badge_and_count():
    analysis = analyse(reading_with_d_unobservable())
    unseen, names = analysis.standing, analysis.actor_names
    assert unseen is not None
    rows = view.desiderata_rows(unseen.participants, names)
    by_code = {row["Events"]: row for row in rows}
    for code in ("D ≺ P", "D ≺ X", "D ≺ A"):
        assert by_code[code]["Vendor"] == "❔ unknown"
    assert by_code["F ≺ P"]["Vendor"] != "❔ unknown"
    vendor = next(
        r
        for r in view.participant_rows(unseen.participants, names)
        if r["Participant"] == "Vendor"
    )
    assert "❔ 3" in str(vendor["Desiderata"])
    # The fix path reads D, which the source cannot see, as unknown.
    assert vendor["Fix path"] == "❔ Fix ready or fix deployed"


def test_no_scored_vendor_gives_no_desiderata_rows():
    assert view.desiderata_rows([], {}) == []
