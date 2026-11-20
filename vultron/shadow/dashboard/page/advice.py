#!/usr/bin/env python

#  Copyright (c) 2026 Carnegie Mellon University and Contributors.
#  - see Contributors.md for a full list of Contributors
#  - see ContributionInstructions.md for information on how you can Contribute to this project
#  Vultron Multiparty Coordinated Vulnerability Disclosure Protocol Prototype is
#  licensed under a MIT (SEI)-style license, please see LICENSE.md distributed
#  with this Software or contact permission@sei.cmu.edu for full terms.
#  Created, in part, with funding and support from the United States Government
#  (see Acknowledgments file). This program may include and/or can make use of
#  certain third party source code, object code, documentation and other files
#  ("Third Party Software"). See LICENSE.md for more details.
#  Carnegie Mellon®, CERT® and CERT Coordination Center® are registered in the
#  U.S. Patent and Trademark Office by Carnegie Mellon University


"""The move advice on the page: the open moves in their bands (ADR-0200),
each shaded band with its legend strip (SHD-03-003), and the moves with no
band.
"""

from __future__ import annotations

from collections.abc import Mapping

import pandas as pd
import streamlit as st

from vultron.measure.advice import CaseAdvice
from vultron.shadow.dashboard import view
from vultron.shadow.dashboard.page.common import _table


def _show_legend(band: view.BandView) -> None:
    """*band*'s legend strip: one cell per layer, numbered and in its rows'
    shades, from better to dominated (SHD-03-003)."""
    cells = "".join(
        f'<div style="{s.css}; flex: 1; text-align: center;">{layer}</div>'
        for layer, s in enumerate(band.legend, start=1)
    )
    st.markdown(
        '<div style="display: flex; align-items: center; margin: 0.5em 0;">'
        f'<span style="margin-right: 0.5em;">{view.LEGEND_BETTER}</span>'
        f'<div style="display: flex; flex: 1;">{cells}</div>'
        f'<span style="margin-left: 0.5em;">{view.LEGEND_DOMINATED}</span>'
        "</div>",
        unsafe_allow_html=True,
    )


def _shaded_table(band: view.BandView) -> None:
    """*band*'s moves, each row filled with its shade."""
    styles = [s.css for s in band.shades]
    # Each column takes the rows' styles in row order.
    styler = pd.DataFrame(list(band.rows)).style.apply(
        lambda _column: styles, axis=0
    )
    st.dataframe(styler, hide_index=True, width="stretch")


def _show_band(band: view.BandView) -> None:
    if not band.rows:
        st.caption(band.empty)
    elif band.shaded:
        _show_legend(band)
        _shaded_table(band)
    else:
        _table(band.rows, band.empty)


def _show_advice(advice: CaseAdvice, names: Mapping[str, str]) -> None:
    """The open moves in their bands, and the moves with no band (ADR-0200).

    The page lays out what :func:`case_advice` returns and computes nothing
    of its own: no combined score orders any move (SHD-03-002).
    """
    st.subheader("Move advice")
    st.caption(advice.help_text)
    st.caption(advice.harm_note)
    for band in view.band_views(advice, names):
        if band.collapsed:
            with st.expander(f"{band.title} ({len(band.rows)})"):
                _show_band(band)
        else:
            st.markdown(f"**{band.title}**")
            _show_band(band)
    st.subheader("Moves with no band")
    _table(
        view.unbanded_rows(advice, names),
        "None: every allowed move is in a band.",
    )
