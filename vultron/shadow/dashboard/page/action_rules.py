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


"""The action rules on the page, beside the move bands (ADR-0216 rule 7):
the rules the bands check, any flagged result, and the rules with no
number.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

import streamlit as st

from vultron.measure.action_rules import AuthoredRule
from vultron.measure.standing import StandingRecord
from vultron.shadow.dashboard import view
from vultron.shadow.dashboard.page.common import _table


def _show_action_rules(
    standing: StandingRecord,
    names: Mapping[str, str],
    rules: Sequence[AuthoredRule] | None = None,
) -> None:
    """The authored rules matching each vendor's position in *standing*,
    each compared with the move's band for that vendor (SHD-06-001 to
    SHD-06-003, SHD-06-006).

    *rules* defaults to the authored table.  The page lays out what
    :func:`~vultron.shadow.dashboard.view.action_rule_rows` returns and
    computes nothing of its own.
    """
    st.subheader("Action rules")
    st.caption(view.ACTION_RULES_NOTE)
    rows = view.action_rule_rows(
        view.rule_comparisons(standing, rules), names, rules
    )
    warning = view.flagged_note(rows)
    if warning is not None:
        st.warning(warning)
    _table(rows.checked, view.NO_CHECKED_RULE)
    with st.expander(f"Rules with no number ({len(rows.unnumbered)})"):
        _table(rows.unnumbered, "None: every matching rule is checked.")
