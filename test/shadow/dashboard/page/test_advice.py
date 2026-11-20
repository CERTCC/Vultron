"""The page's move advice, run headless with Streamlit's ``AppTest``: it
reads band by band, with its shades, marks, legends, harms and
unbanded moves (#6603, #6673).

Spec: SHD-03-002, SHD-03-003, SHD-03-004.
"""

from __future__ import annotations

import pytest
from streamlit.testing.v1 import AppTest

from test.measure.history.builders import two_vendors_ledger
from test.shadow.dashboard._support import TIMEOUT, texts
from test.shadow.dashboard.page._support import (
    BACKGROUND,
    COLUMNS,
    page_frame,
    page_table,
)
from vultron.measure.advice import (
    CHANCE_EVENT,
    DOMINATED_BY_HARM_FREE,
    HARM_NOTE,
    HELP_TEXT,
    case_advice,
)
from vultron.measure.standing import case_standing
from vultron.shadow.dashboard import view
from vultron.shadow.dashboard.view import (
    LEADING_MARK,
    LEGEND_BETTER,
    LEGEND_DOMINATED,
    TOP_MARK,
)

_ADVICE_PAGE = """
from test.measure.history.builders import two_vendors_ledger
from vultron.measure.advice import case_advice
from vultron.measure.standing import case_standing
from vultron.shadow.dashboard.page.advice import _show_advice

_show_advice(case_advice(case_standing(two_vendors_ledger().case_ledger())), {})
"""


@pytest.fixture(scope="module")
def advice_app() -> AppTest:
    """The advice section for a case with a move in every band."""
    at = AppTest.from_string(_ADVICE_PAGE, default_timeout=TIMEOUT).run()
    assert not at.exception
    return at


def test_the_bands_are_shown_in_order_with_the_unhelpful_one_collapsed(
    advice_app,
):
    """AC-1: harm-free, trade-off, then the unhelpful band as a closed
    group the analyst can open."""
    at = advice_app
    # Band titles appear in markdown, with legends between them
    markdowns = texts(at.markdown)
    band_titles = [
        m for m in markdowns if m.startswith("**") and m.endswith("**")
    ]
    assert band_titles[:2] == ["**Harm-free**", "**Trade-off**"]
    (unhelpful,) = [
        e for e in at.expander if str(e.label).startswith("Unhelpful")
    ]
    assert unhelpful.label.startswith("Unhelpful (")
    assert unhelpful.proto.expanded is False
    (inside,) = unhelpful.dataframe
    assert inside.value.columns.tolist() == COLUMNS["Unhelpful"]
    headings = texts(at.subheader)
    assert headings == ["Move advice", "Moves with no band"]


def test_each_shaded_band_is_filled_by_layer_and_marks_top_moves(advice_app):
    """AC-2: the harm-free and trade-off rows carry their shades; the
    unhelpful band has neither shade nor mark."""
    at = advice_app
    for heading in ("Harm-free", "Trade-off"):
        styles = page_frame(at, heading).proto.arrow_data.styler.styles
        assert "background-color: #" in styles
        # The layer is a number, so its column sorts as one.
        assert page_table(at, heading)["Layer"].dtype.kind == "i"
    harm_free = page_table(at, "Harm-free")
    assert TOP_MARK in harm_free["Mark"].tolist()
    unhelpful = page_frame(at, "Unhelpful").proto.arrow_data
    assert not unhelpful.HasField("styler")


def test_the_page_shows_the_marks_help_text_and_harm_note(advice_app):
    """AC-3, AC-4, AC-5: the leading mark, the help text and the note on
    negative shifts, each vendor's harm, and the domination message."""
    at = advice_app
    captions = texts(at.caption)
    assert HELP_TEXT in captions
    assert HARM_NOTE in captions
    assert LEADING_MARK in page_table(at, "Harm-free")["Yours"].tolist()
    trade_off = page_table(at, "Trade-off")
    assert all("−" in h for h in trade_off["Harms by vendor"])
    assert DOMINATED_BY_HARM_FREE in trade_off["Dominated by"].tolist()


@pytest.mark.spec("SHD-03-003", "SHD-03-004")
def test_each_shaded_band_shows_a_legend_in_its_rows_shades(advice_app):
    """#6673 AC-1, AC-2: one legend under each shaded band's title, labelled
    at both ends, its cells the band's own layer shades and holding each
    row's shade; the help text is shown and no caption says "darkest"."""
    at = advice_app
    captions = texts(at.caption)
    assert HELP_TEXT in captions
    assert not any("darkest" in c.lower() for c in captions)
    markdowns = texts(at.markdown)
    legends = [m for m in markdowns if LEGEND_BETTER in m]
    assert len(legends) == 2
    expected = {
        b.title: b
        for b in view.band_views(
            case_advice(case_standing(two_vendors_ledger().case_ledger())), {}
        )
    }
    for heading in ("Harm-free", "Trade-off"):
        legend = markdowns[markdowns.index(f"**{heading}**") + 1]
        assert LEGEND_BETTER in legend and LEGEND_DOMINATED in legend
        assert legend.index(LEGEND_BETTER) < legend.index(LEGEND_DOMINATED)
        cells = BACKGROUND.findall(legend)
        assert cells == [s.background for s in expected[heading].legend]
        styles = page_frame(at, heading).proto.arrow_data.styler.styles
        row_backgrounds = set(BACKGROUND.findall(styles))
        assert row_backgrounds and row_backgrounds <= set(cells)


def test_the_moves_with_no_band_are_listed_with_why(advice_app):
    """AC-6: each unbanded move, with its reason."""
    unbanded = page_table(advice_app, "Moves with no band")
    assert CHANCE_EVENT in unbanded["Why no band"].tolist()
