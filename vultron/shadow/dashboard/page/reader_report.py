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


"""The case reader's report on the page, always beside the analysis: the
facts it could not translate, the states it inferred, and what its source
never records (SHD-01-004, CRD-02-005).
"""

from __future__ import annotations

import streamlit as st

from vultron.core.models.case_reading import CaseReading
from vultron.shadow.dashboard import view
from vultron.shadow.dashboard.page.common import _table


def _show_reader_report(reading: CaseReading) -> None:
    st.subheader("Not translated")
    st.caption(view.NOT_TRANSLATED_NOTE)
    _table(
        view.untranslated_rows(reading),
        "None: the case reader translated every fact it read.",
    )
    st.subheader("Inferred")
    _table(
        view.inference_rows(reading), "None: the source stated every state."
    )
    st.subheader("Not observable")
    st.caption(view.UNOBSERVABLE_NOTE)
    _table(
        view.unobservable_rows(reading),
        "None: the source records every fact the analysis reads.",
    )
