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


"""The scoreboard: the case's standing, each state on a small map of its
state machine (#6674), its participants, desiderata and move advice, and
the action rules beside the bands (ADR-0216).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

import streamlit as st

from vultron.measure.advice import case_advice
from vultron.measure.standing import ParticipantStanding
from vultron.shadow.analysis import CaseAnalysis
from vultron.shadow.dashboard import minimap, view
from vultron.shadow.dashboard.page.action_rules import _show_action_rules
from vultron.shadow.dashboard.page.advice import _show_advice
from vultron.shadow.dashboard.page.common import _table

#: What the scoreboard says when the ledger does not prove its end.
END_UNCONFIRMED_NOTE = (
    "The ledger does not prove its last entry is the case's last: the case"
    " may have moved on since."
)


def _show_standing(analysis: CaseAnalysis, past_point: bool) -> None:
    """The scoreboard of *analysis*'s standing.

    At a *past_point* the case is known to have moved on, so the page does
    not hedge that it may have: the point note says how far.
    """
    standing = analysis.standing
    if standing is None:
        st.warning(
            "The case reader translated no ledger entry, so there is no"
            " standing to show."
        )
        return
    if standing.gap is not None:
        st.error(
            "The ledger has a hole, so it gives no standing: a measure over"
            " a history with a hole is wrong, not imprecise."
        )
        for line in view.gap_lines(standing.gap):
            st.markdown(f"- {line}")
        return
    assert standing.case is not None, "a record with no gap has a case"
    names = analysis.actor_names
    columns = st.columns(4)
    columns[0].metric("Embargo", view.EM_BADGES[standing.case.em])
    for column, badge in zip(
        columns[1:],
        view.public_badges(standing.case.pxa, standing.case.unobservable),
        strict=True,
    ):
        column.metric("Public state", badge)
    for column, case_map in zip(
        st.columns(2), minimap.case_minimaps(standing.case), strict=True
    ):
        with column:
            _show_minimap(case_map)
    if not standing.end_confirmed and not past_point:
        st.caption(END_UNCONFIRMED_NOTE)
    st.subheader("Participants")
    _table(view.participant_rows(standing.participants, names), "None.")
    _show_participant_minimaps(standing.participants, names)
    st.subheader("Desiderata")
    desiderata = view.desiderata_rows(standing.participants, names)
    _table(desiderata, "No vendor has a case-state history to score yet.")
    if desiderata:
        st.caption(view.DESIDERATA_NOTE)
    _show_advice(case_advice(standing), names)
    _show_action_rules(standing, names)


def _show_minimap(state_map: minimap.Minimap) -> None:
    """One state on its machine's map, with the state in words below."""
    st.markdown(f"**{state_map.title}**")
    st.graphviz_chart(
        state_map.dot, alt=f"{state_map.title}: {state_map.caption}"
    )
    st.caption(state_map.caption)


def _show_participant_minimaps(
    participants: Sequence[ParticipantStanding], names: Mapping[str, str]
) -> None:
    """Each participant's RM and VFD maps, one tab per participant."""
    maps = minimap.participant_minimaps(participants, names)
    if not maps:
        return
    for tab, participant in zip(
        st.tabs([m.tab for m in maps]), maps, strict=True
    ):
        with tab:
            rm_column, vfd_column = st.columns(2)
            with rm_column:
                _show_minimap(participant.rm)
            with vfd_column:
                if participant.vfd is None:
                    st.caption(minimap.NO_FIX_PATH)
                else:
                    _show_minimap(participant.vfd)


__all__ = [
    "END_UNCONFIRMED_NOTE",
]
