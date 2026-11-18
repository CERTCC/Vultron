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

"""The case shadow tool's source menu: where the page reads a case from.

:func:`choose_source` draws the menu in the page's sidebar and returns the
source the analyst chose (#6642).  The page opens on the recorded demo
cases.  The analyst may switch, with no restart, to an outside system, such
as VINCE, or to a running Vultron node:

* VINCE can be chosen only when its base URL and credential are set in the
  environment the tool runs in.  The menu has no field for a credential
  (SHD-02-003).
* A running node is named by its API root and its CASE_MANAGER's actor id,
  prefilled from the ``shadow:`` settings.  A typed value is checked by the
  rules the settings are checked by, and a refused one is shown with its
  reason; no reader is built, so no request is sent.

Switching sources, or typing another node, drops the case entered and the
reading kept for it (:func:`~vultron.shadow.dashboard.page.forget_case`).
"""

from __future__ import annotations

from typing import NamedTuple

import streamlit as st

from vultron.config.app import AppConfig
from vultron.config.shadow import VINCE_CONNECTOR
from vultron.config.vince import (
    VINCE_API_TOKEN_ENV_VAR,
    VINCE_BASE_URL_ENV_VAR,
)
from vultron.errors import VultronConfigError
from vultron.shadow.dashboard.page import forget_case
from vultron.shadow.readers import (
    CaseSource,
    VultronNode,
    outside_connector,
    outside_source_ready,
    typed_node,
)

#: The widget key of the source the analyst picks.
SOURCE_KEY = "case_source"
#: The widget keys of the running node's API root and actor id.
NODE_URL_KEY = "node_url"
NODE_ACTOR_KEY = "node_actor_id"
#: The session-state key of the source the page last read through.
CHOSEN_KEY = "chosen_source"

#: What the menu calls each source.
SOURCE_LABELS = {
    CaseSource.RECORDINGS: "Recorded demo cases",
    CaseSource.OUTSIDE: "VINCE",
    CaseSource.NODE: "A running Vultron node",
}

#: What the page says when VINCE is chosen but not set up.
VINCE_NOT_SET_UP = (
    f"VINCE is not set up. Set {VINCE_BASE_URL_ENV_VAR} and"
    f" {VINCE_API_TOKEN_ENV_VAR} in the environment the tool runs in, then"
    " start the tool again. The page never asks for the credential."
)


class ChosenSource(NamedTuple):
    """The source the page reads through.

    Attributes:
        source: The source the analyst chose.
        node: The node typed for :attr:`CaseSource.NODE`; ``None`` for any
            other source.
    """

    source: CaseSource
    node: VultronNode | None = None


def source_label(source: CaseSource, config: AppConfig) -> str:
    """What the menu calls *source*, and whether the outside one is set up."""
    if source != CaseSource.OUTSIDE:
        return SOURCE_LABELS[source]
    name = outside_connector(config.shadow)
    label = (
        SOURCE_LABELS[source]
        if name == VINCE_CONNECTOR
        else f"Outside system ({name})"
    )
    if not outside_source_ready(config.shadow, config.vince):
        label += " (not set up)"
    return label


def _ask_for_node(config: AppConfig) -> VultronNode | None:
    """The node the analyst typed, or ``None``, with why, when it is refused."""
    shadow = config.shadow
    url = st.sidebar.text_input(
        "Node API root",
        value=shadow.node_url or "",
        key=NODE_URL_KEY,
        placeholder="http://case-actor:7999/api/v2",
    )
    actor_id = st.sidebar.text_input(
        "Case Manager actor id",
        value=shadow.node_actor_id or "",
        key=NODE_ACTOR_KEY,
        placeholder="case-actor",
    )
    try:
        return typed_node(url, actor_id)
    except VultronConfigError as exc:
        # The refusal never quotes the value typed (VSD-01-005).
        st.sidebar.error(str(exc))
        return None


def _read_through(chosen: ChosenSource | None) -> None:
    """Record *chosen*; on a change of source, drop the case read before."""
    if st.session_state.get(CHOSEN_KEY) != chosen:
        forget_case()
        st.session_state[CHOSEN_KEY] = chosen


def choose_source(config: AppConfig) -> ChosenSource | None:
    """Draw the source menu; return the source chosen, if it can be read.

    Returns:
        The source the page reads through, or ``None`` when the chosen one
        cannot be read: VINCE with no base URL or credential, or a node
        whose typed values are refused.  The menu has said why.
    """
    picked = st.sidebar.radio(
        "Source",
        options=list(CaseSource),
        format_func=lambda s: source_label(s, config),
        key=SOURCE_KEY,
    )
    # The menu opens on its first option, the recordings, and offers no
    # empty choice; Streamlit types the value as optional all the same.
    source = CaseSource.RECORDINGS if picked is None else picked
    chosen: ChosenSource | None = ChosenSource(source)
    if source == CaseSource.NODE:
        node = _ask_for_node(config)
        chosen = None if node is None else ChosenSource(source, node)
    elif source == CaseSource.OUTSIDE and not outside_source_ready(
        config.shadow, config.vince
    ):
        st.sidebar.info(VINCE_NOT_SET_UP)
        chosen = None
    _read_through(chosen)
    return chosen


__all__ = [
    "CHOSEN_KEY",
    "NODE_ACTOR_KEY",
    "NODE_URL_KEY",
    "SOURCE_KEY",
    "SOURCE_LABELS",
    "VINCE_NOT_SET_UP",
    "ChosenSource",
    "choose_source",
    "source_label",
]
