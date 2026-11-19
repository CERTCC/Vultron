"""What the dashboard shows, as words, icons and rows (#6366).

Every state has a badge, every desideratum reads in words, the move advice
reads band by band with each vendor's harm on its own (#6603), and a gap or
a reader's report reads as lines and rows.

The case narrative reads one row per ledger entry, its state changes in
words and a flag the source cannot observe as unknown (#6670).

Spec: SHD-01-004, SHD-03-002, CRD-02-005, DRPT-03-009.
"""

from datetime import UTC, datetime
from fractions import Fraction

import pytest
from pydantic import ValidationError

from test.adapters.connectors.vince._support import ACTIVE, translate
from test.measure.history.builders import (
    VENDOR as BUILT_VENDOR,
    VENDOR_2 as BUILT_VENDOR_2,
    two_vendors_ledger,
)
from vultron.core.models._helpers import format_timestamp
from vultron.core.models.case_reading import (
    CaseReading,
    UnobservableFact,
    UntranslatedFact,
    UntranslatedReason as Reason,
)
from vultron.core.states.cs import CS_pxa
from vultron.core.states.cs_invariants import CSEvent
from vultron.core.states.em import EM
from vultron.core.states.embargo_register import (
    EmbargoRegisterStatus,
    derive_em,
)
from vultron.core.states.rm import RM
from vultron.demo.recordings.layout import RECORDINGS_DIR
from vultron.errors import VultronInvalidStateTransitionError
from vultron.measure.advice import (
    BAND_ORDER,
    CHANCE_EVENT,
    DOMINATED_BY_HARM_FREE,
    AdvisedMove,
    Band,
    BandAdvice,
    CaseAdvice,
    ColourMap,
    Part,
    UnbandedMove,
    VendorHarm,
    VendorShift,
    case_advice,
)
from vultron.measure.history import (
    NarrativeLine,
    StateChange,
    StateMachine,
    UnreadableEntry,
)
from vultron.measure.ledger import MISSING_SLOT, UNNAMED_ACTOR, UnusableRow
from vultron.measure.sequences import (
    UnprojectableParticipant,
    UnprojectableReason,
)
from vultron.measure.standing import (
    CaseStanding,
    DesideratumStatus,
    ParticipantStanding,
    RMMove,
    StandingGap,
    case_standing,
)
from vultron.shadow.analysis import analyse
from vultron.shadow.dashboard import view
from vultron.shadow.readers import VultronCaseReader

VENDOR = "https://vendor.example/actors/vendor"
VENDOR_2 = "https://other.example/actors/vendor2"
NAMES = {VENDOR: "Vendor", VENDOR_2: "Vendor2"}


def _analysis():
    path = RECORDINGS_DIR / "rcvv-embargo" / "case-actor.jsonl"
    return analyse(VultronCaseReader(root=RECORDINGS_DIR).read_case(str(path)))


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
    assert str(vendor["Desiderata"]).startswith("✅ ")
    assert vendor["Not scored because"] == ""
    manager = next(r for r in rows if "CASE_MANAGER" in str(r["Roles"]))
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


def test_vendors_that_share_a_label_keep_their_own_columns():
    analysis = _analysis()
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
    analysis = analyse(_reading_with_d_unobservable())
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


def test_a_tally_with_no_unknown_desideratum_shows_no_unknown_count():
    analysis = _analysis()
    assert analysis.standing is not None
    rows = view.participant_rows(
        analysis.standing.participants, analysis.actor_names
    )
    assert rows
    for row in rows:
        assert "❔" not in str(row["Desiderata"])


def _reading_with_d_unobservable() -> CaseReading:
    path = RECORDINGS_DIR / "rcvv-embargo" / "case-actor.jsonl"
    recorded = VultronCaseReader(root=RECORDINGS_DIR).read_case(str(path))
    return CaseReading(
        ledger=recorded.ledger,
        citations=recorded.citations,
        unobservable=(
            UnobservableFact(
                fact="Fix Deployed (D)",
                why="no field",
                events=frozenset({CSEvent.D}),
            ),
        ),
    )


def test_no_scored_vendor_gives_no_desiderata_rows():
    assert view.desiderata_rows([], {}) == []


@pytest.fixture(scope="module")
def advice() -> CaseAdvice:
    """Advice whose open moves fall in every band (#6603)."""
    return case_advice(case_standing(two_vendors_ledger().case_ledger()))


def _views(advice: CaseAdvice) -> dict[Band, view.BandView]:
    return {b.band: b for b in view.band_views(advice, {})}


def test_the_bands_read_in_order_with_the_unhelpful_band_collapsed(advice):
    """AC-1: harm-free, then trade-off, then the collapsed unhelpful band."""
    views = view.band_views(advice, {})
    assert [v.band for v in views] == [
        Band.HARM_FREE,
        Band.TRADE_OFF,
        Band.UNHELPFUL,
    ]
    assert [v.collapsed for v in views] == [b.collapsed for b in advice.bands]
    assert [v.collapsed for v in views] == [False, False, True]
    assert [v.title for v in views] == ["Harm-free", "Trade-off", "Unhelpful"]


@pytest.mark.spec("SHD-03-002")
def test_each_band_keeps_the_advices_order_and_no_score_column(advice):
    """The page reorders no move, and no column combines vendors."""
    for band, band_view in zip(
        advice.bands, view.band_views(advice, {}), strict=True
    ):
        assert band.moves
        assert [r["Move"] for r in band_view.rows] == [
            m.move.name.partition(".")[2].replace("_", " ").capitalize()
            for m in band.moves
        ]
        for row in band_view.rows:
            assert not any("score" in column.lower() for column in row)


def test_each_shaded_move_takes_its_layers_shade_in_its_bands_map(advice):
    """AC-2: layer 1 at the dark end of viridis or cividis."""
    deepest = max(m.layer or 1 for m in advice.moves)
    assert deepest > 1
    views = _views(advice)
    for band in advice.bands[:2]:
        assert band.colour_map is not None
        shades = views[band.band].shades
        assert shades == tuple(
            view.shade(band.colour_map, m.layer or 0, deepest)
            for m in band.moves
        )
        for move, row in zip(band.moves, views[band.band].rows, strict=True):
            assert row["Layer"] == move.layer
    harm_free = views[Band.HARM_FREE]
    (top,) = [
        s
        for s, r in zip(harm_free.shades, harm_free.rows, strict=True)
        if r["Layer"] == 1
    ]
    assert top.background == view.COLOUR_STOPS[ColourMap.VIRIDIS][0]


def test_only_a_top_move_carries_the_top_icon(advice):
    """AC-2: each top move is marked; no other move is."""
    for band, band_view in zip(
        advice.bands[:2], view.band_views(advice, {})[:2], strict=True
    ):
        assert [r["Mark"] for r in band_view.rows] == [
            view.TOP_MARK if m.top else "" for m in band.moves
        ]
    assert any(m.top for m in advice.moves)


def test_the_unhelpful_band_has_no_shade_and_no_mark(advice):
    """AC-2: no layer, top icon or leading mark in the unhelpful band."""
    unhelpful = _views(advice)[Band.UNHELPFUL]
    assert unhelpful.rows and not unhelpful.shades
    for row in unhelpful.rows:
        assert not {"Layer", "Mark", "Yours"} & set(row)
        assert view.TOP_MARK not in row.values()
        assert view.LEADING_MARK not in row.values()


def test_a_move_leading_among_yours_is_marked(advice):
    """AC-3: the coordinator's undominated move says so; no other does."""
    marked = [
        row["Who"]
        for band_view in view.band_views(advice, {})
        for row in band_view.rows
        if row.get("Yours") == view.LEADING_MARK
    ]
    leading = [m for m in advice.moves if m.leading_among_yours]
    assert len(marked) == len(leading) == 1
    assert marked == ["Owner"]


@pytest.mark.spec("SHD-03-002")
def test_each_move_shows_each_vendors_harm_with_its_size(advice):
    """AC-4: each negative part by vendor and size, never summed."""
    publication = next(m for m in advice.band(Band.TRADE_OFF).moves if m.harms)
    names = {BUILT_VENDOR: "Vendor", BUILT_VENDOR_2: "Second"}
    text = view.harm_text(publication, names)
    parts = text.split("; ")
    assert len(parts) == len(publication.harms) > 1
    for part, harm in zip(parts, publication.harms, strict=True):
        assert part == (
            f"{names[harm.vendor]}: {harm.part} −{float(-harm.size):.3g}"
        )
    harmless = next(m for m in advice.band(Band.HARM_FREE).moves)
    assert view.harm_text(harmless, names) == "none"
    for band_view in view.band_views(advice, {}):
        assert all("Harms by vendor" in row for row in band_view.rows)


def test_a_trade_off_move_a_harm_free_move_dominates_says_so(advice):
    """AC-5: the trade-off band names the domination, row by row."""
    trade_off = _views(advice)[Band.TRADE_OFF]
    assert [r["Dominated by"] for r in trade_off.rows] == [
        m.dominated_by_harm_free or ""
        for m in advice.band(Band.TRADE_OFF).moves
    ]
    assert DOMINATED_BY_HARM_FREE in {
        r["Dominated by"] for r in trade_off.rows
    }
    for band in (Band.HARM_FREE, Band.UNHELPFUL):
        assert all("Dominated by" not in r for r in _views(advice)[band].rows)


def test_every_move_with_no_band_is_listed_with_its_reason(advice):
    """AC-6: each unbanded move and the reason it has none."""
    rows = view.unbanded_rows(advice, {})
    assert [r["Why no band"] for r in rows] == [
        u.reason for u in advice.unbanded
    ]
    assert CHANCE_EVENT in {r["Why no band"] for r in rows}


def test_an_unbanded_move_reads_its_own_reason_whatever_it_is(advice):
    """A reason the page has never seen reads as it is given (#6563)."""
    move = advice.unbanded[0].move
    with_reason = advice.model_copy(
        update={
            "unbanded": (
                UnbandedMove(move=move, reason="it waits on an unseen event"),
            )
        }
    )
    (row,) = view.unbanded_rows(with_reason, NAMES)
    assert row["Why no band"] == "it waits on an unseen event"
    assert set(row) == {"Who", "Machine", "Move", "From → to", "Why no band"}


def test_a_shade_runs_from_the_dark_end_to_the_light_end():
    for colour_map, stops in view.COLOUR_STOPS.items():
        assert view.shade(colour_map, 1, 1).background == stops[0]
        assert view.shade(colour_map, 1, 3).background == stops[0]
        assert view.shade(colour_map, 2, 3).background == stops[4]
        assert view.shade(colour_map, 3, 3).background == stops[-1]
        assert view.shade(colour_map, 1, 3).text == "#ffffff"
        assert view.shade(colour_map, 3, 3).text == "#000000"
    assert view.shade(ColourMap.VIRIDIS, 2, 9).background == "#472d7b"


def test_a_shade_between_two_stops_mixes_them():
    """Layer 2 of 33 sits a quarter of the way from viridis's first stop,
    ``#440154``, to its second, ``#472d7b``."""
    assert view.shade(ColourMap.VIRIDIS, 2, 33).background == "#450c5e"


@pytest.mark.parametrize("layer, deepest", [(0, 2), (3, 2), (-1, 1)])
def test_a_layer_outside_the_advice_has_no_shade(layer, deepest):
    with pytest.raises(ValueError, match=f"layer {layer} is not from 1"):
        view.shade(ColourMap.CIVIDIS, layer, deepest)


def test_a_shade_reads_as_a_cells_css():
    assert view.Shade(background="#440154", text="#ffffff").css == (
        "background-color: #440154; color: #ffffff"
    )


_SHADE = view.Shade(background="#440154", text="#ffffff")


@pytest.mark.parametrize(
    "band, shades, message",
    [
        (Band.HARM_FREE, (_SHADE, _SHADE), "2 shades for 1 rows"),
        (Band.TRADE_OFF, (), "0 shades for 1 rows"),
        (Band.UNHELPFUL, (_SHADE,), "the unhelpful band is not shaded"),
    ],
)
def test_a_band_view_refuses_shades_that_miss_its_rows(band, shades, message):
    with pytest.raises(ValidationError, match=message):
        view.BandView(
            band=band,
            title="x",
            collapsed=band is Band.UNHELPFUL,
            rows=({"Move": "x"},),
            shades=shades,
            empty="none",
        )


def test_a_harm_free_move_shows_its_embargo_harm():
    """End parts decide the band, so a harm-free move can lower a vendor's
    embargo part, and the page shows that harm (ADR-0200)."""
    move = RMMove(participant=VENDOR, source=RM.RECEIVED, destination=RM.VALID)
    advised = AdvisedMove(
        move=move,
        shift=(
            VendorShift(
                vendor=VENDOR, end=Fraction(1, 4), embargo=Fraction(-1, 8)
            ),
        ),
        band=Band.HARM_FREE,
        layer=1,
        top=True,
        leading_among_yours=False,
        harms=(
            VendorHarm(vendor=VENDOR, part=Part.EMBARGO, size=Fraction(-1, 8)),
        ),
    )
    advice = CaseAdvice(
        case_id="urn:uuid:case-1",
        end_confirmed=True,
        vendors=(VENDOR,),
        bands=tuple(BandAdvice.of(b, [advised]) for b in BAND_ORDER),
    )
    (row,) = _views(advice)[Band.HARM_FREE].rows
    assert row["Harms by vendor"] == "Vendor: embargo −0.125"
    assert row["Mark"] == view.TOP_MARK


def _register_problem() -> str:
    """The words :func:`derive_em` gives a register with two active entries."""
    with pytest.raises(VultronInvalidStateTransitionError) as raised:
        derive_em([EmbargoRegisterStatus.ACTIVE, EmbargoRegisterStatus.ACTIVE])
    return str(raised.value)


def test_every_kind_of_hole_reads_as_a_line(tmp_path):
    """The register problem reads once, in derive_em's own words, never
    behind a second "Embargo register:"."""
    problem = _register_problem()
    gap = StandingGap(
        missing_log_indices=[2],
        conflicting_log_indices=[4],
        unusable_rows=[
            UnusableRow(path=tmp_path / "x.jsonl", line=3, reason="not JSON")
        ],
        unreadable_entries=[UnreadableEntry(log_index=5, reason="no stamp")],
        register_problem=problem,
    )
    lines = view.gap_lines(gap)
    assert lines[0] == "Missing log indices: [2]"
    assert lines[1] == "Conflicting log indices: [4]"
    assert "not JSON" in lines[2]
    assert lines[3] == "Unreadable entry at log index 5: no stamp"
    assert lines[4] == problem


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


# -- the case narrative (#6670) -----------------------------------------


def _line(**fields) -> NarrativeLine:
    return NarrativeLine(
        **{"log_index": 0, "phrase": "Vendor did a thing", **fields}
    )


_T0 = datetime(2026, 1, 1, tzinfo=UTC)
_T1 = datetime(2026, 1, 1, 0, 0, 1, tzinfo=UTC)


def test_each_narrative_line_reads_as_a_row_keyed_by_its_log_index():
    """AC-1 and AC-2: one row per line, in order, by log index."""
    analysis = _analysis()
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
            _line(claimed_at=_T0, committed_at=_T0),
            _line(log_index=1, claimed_at=_T0, committed_at=_T1),
            _line(log_index=2, committed_at=_T1),
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
        [_line(actor="Vendor", object="note → case")], {}
    )
    assert (row["Actor"], row["Activity"], row["Object"]) == (
        "Vendor",
        "Vendor did a thing",
        "note → case",
    )
    (bare,) = view.narrative_rows([_line()], {})
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
    (row,) = view.narrative_rows([_line(changes=changes)], NAMES)
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
            _line(),
            _line(log_index=1, notes=("no commit stamp", "unknown type")),
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


@pytest.mark.spec("DRPT-03-009")
def test_a_vince_participant_never_reads_as_its_opaque_id():
    """#6685: a reading whose payloads name no actor shows no ``urn:uuid``."""
    analysis = analyse(translate(ACTIVE))
    assert analysis.standing is not None
    participants = analysis.standing.participants
    rows = view.participant_rows(participants, analysis.actor_names)
    assert rows
    assert {row["Participant"] for row in rows} == {UNNAMED_ACTOR}
    assert all(str(row["Actor"]).startswith("urn:uuid:") for row in rows)
    columns = view.desiderata_rows(participants, analysis.actor_names)
    assert len(columns) == 12
    for row in columns:
        vendor_columns = [c for c in row if c not in ("Desideratum", "Events")]
        assert len(set(vendor_columns)) == len(vendor_columns)
        assert all(c.startswith(UNNAMED_ACTOR) for c in vendor_columns)


@pytest.mark.spec("DRPT-03-009")
def test_a_move_and_a_harm_by_an_unnamed_actor_read_as_unnamed():
    """#6685: the move tables and the harm text name an opaque id as
    unnamed, as the participants table does."""
    opaque = "urn:uuid:1e7a421f-b727-4c1d-9a3e-0f6b2c9d8e71"
    move = RMMove(participant=opaque, source=RM.RECEIVED, destination=RM.VALID)
    advice = CaseAdvice(
        case_id="urn:uuid:case-1",
        end_confirmed=True,
        vendors=(opaque,),
        bands=tuple(BandAdvice.of(b, []) for b in BAND_ORDER),
        unbanded=(UnbandedMove(move=move, reason="it waits"),),
    )
    (row,) = view.unbanded_rows(advice, {})
    assert row["Who"] == UNNAMED_ACTOR
    advised = AdvisedMove(
        move=move,
        shift=(
            VendorShift(
                vendor=opaque, end=Fraction(1, 4), embargo=Fraction(-1, 8)
            ),
        ),
        band=Band.HARM_FREE,
        layer=1,
        top=True,
        leading_among_yours=False,
        harms=(
            VendorHarm(vendor=opaque, part=Part.EMBARGO, size=Fraction(-1, 8)),
        ),
    )
    assert view.harm_text(advised, {}) == f"{UNNAMED_ACTOR}: embargo −0.125"


def test_an_actor_with_no_name_reads_by_its_uri_or_as_unnamed():
    assert view.actor_label(VENDOR, NAMES) == "Vendor"
    assert view.actor_label("https://example.org/actors/reporter", {}) == (
        "Reporter"
    )
    assert view.actor_label(
        "urn:uuid:1e7a421f-b727-4c1d-9a3e-0f6b2c9d8e71", {}
    ) == (UNNAMED_ACTOR)


# -- the point picker (#6671) ----------------------------------------------


_POINTS = (
    _line(log_index=0, phrase="Case Actor created the case"),
    _line(log_index=1, phrase="Vendor accepted the embargo"),
    _line(log_index=3, phrase="Vendor closed the report"),
)


def test_the_points_are_now_then_each_line_in_ledger_order():
    assert view.point_options(_POINTS) == [view.LATEST_POINT, 0, 1, 3]
    assert view.point_options(()) == [view.LATEST_POINT]


def test_a_point_reads_as_its_line_and_now_reads_as_now():
    """A line reads by its activity, which names its actor (DRPT-03-009)."""
    assert view.point_label(1, _POINTS) == "#1 · Vendor accepted the embargo"
    assert view.point_label(view.LATEST_POINT, _POINTS) == (
        view.LATEST_POINT_LABEL
    )
    with pytest.raises(ValueError, match="no line at 2"):
        view.point_label(2, _POINTS)


def test_the_point_note_names_the_entry_and_how_many_entries_it_reads():
    """Entry #3 follows a hole, so it is the third entry of three."""
    note = view.point_note(1, _POINTS)
    assert "just after entry #1" in note
    assert "first 2 of 3 entries only" in note
    assert "first 3 of 3 entries only" in view.point_note(3, _POINTS)
