"""The move advice reads band by band, with each vendor's harm on its
own (#6603), each shaded band's legend (#6673) and each move with no
band.

Spec: SHD-03-002, SHD-03-003, DRPT-03-009.
"""

from fractions import Fraction

import pytest
from pydantic import ValidationError

from test.measure.history.builders import (
    VENDOR as BUILT_VENDOR,
    VENDOR_2 as BUILT_VENDOR_2,
    two_vendors_ledger,
)
from test.shadow.dashboard.view._support import NAMES, VENDOR
from vultron.core.states.rm import RM
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
from vultron.measure.ledger import UNNAMED_ACTOR
from vultron.measure.standing import RMMove, case_standing
from vultron.shadow.dashboard import view


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


@pytest.mark.spec("SHD-03-003")
def test_a_bands_legend_holds_each_layers_shade_in_its_own_map(advice):
    """#6673 AC-1: each shaded band's legend is drawn from its own map, and
    every row's shade is its layer's cell on that legend."""
    deepest = max(m.layer or 1 for m in advice.moves)
    views = _views(advice)
    for band in advice.bands[:2]:
        assert band.colour_map is not None
        band_view = views[band.band]
        assert band_view.legend == view.band_legend_shades(
            band.colour_map, deepest
        )
        for move, row_shade in zip(band.moves, band_view.shades, strict=True):
            assert row_shade == band_view.legend[(move.layer or 0) - 1]
    assert views[Band.HARM_FREE].legend != views[Band.TRADE_OFF].legend
    assert views[Band.UNHELPFUL].legend == ()


def test_a_shaded_band_has_a_legend_holding_its_rows_shades():
    """A shaded band's legend is not optional, and a row shade that is not
    on it is refused; the unhelpful band has none."""
    dark, light = view.band_legend_shades(ColourMap.VIRIDIS, 2)
    row: view.Row = {"Layer": 1}
    with pytest.raises(ValueError, match="a shaded band has a legend"):
        view.BandView(
            band=Band.HARM_FREE,
            title="Harm-free",
            collapsed=False,
            rows=(row,),
            shades=(dark,),
            empty="none",
        )
    with pytest.raises(ValueError, match="not on the legend"):
        view.BandView(
            band=Band.HARM_FREE,
            title="Harm-free",
            collapsed=False,
            rows=(row,),
            shades=(view.shade(ColourMap.CIVIDIS, 1, 2),),
            legend=(dark, light),
            empty="none",
        )
    with pytest.raises(ValueError, match="the unhelpful band has no legend"):
        view.BandView(
            band=Band.UNHELPFUL,
            title="Unhelpful",
            collapsed=True,
            rows=(),
            legend=(dark,),
            empty="none",
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
