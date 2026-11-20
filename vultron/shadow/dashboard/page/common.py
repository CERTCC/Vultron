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


"""What every part of the page shares: its logger and its tables, plain or
shaded."""

from __future__ import annotations

import logging
from collections.abc import Sequence

import pandas as pd
import streamlit as st

from vultron.shadow.dashboard import view

#: The page's logger.  Every part of the page logs under the page's own
#: name, as it did before the page was split into parts, so a log
#: setting or filter on it still reaches every record.
logger = logging.getLogger("vultron.shadow.dashboard.page")


def _table(rows: Sequence[view.Row], empty: str) -> None:
    if rows:
        st.dataframe(list(rows), hide_index=True, width="stretch")
    else:
        st.caption(empty)


def _styled_table(
    rows: Sequence[view.Row],
    shades: Sequence[view.Shade | None],
    column: str | None = None,
) -> None:
    """*rows*, each filled with its shade, in row order: every cell of a
    row, or only its *column* cell; a row whose shade is ``None`` is not
    filled."""
    styles = ["" if s is None else s.css for s in shades]
    blank = [""] * len(styles)
    styler = pd.DataFrame(list(rows)).style.apply(
        lambda cells: styles if column in (None, cells.name) else blank,
        axis=0,
    )
    st.dataframe(styler, hide_index=True, width="stretch")


__all__ = [
    "logger",
]
