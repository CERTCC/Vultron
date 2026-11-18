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

"""The Streamlit script the case shadow tool runs (ADR-0192).

``vultron-shadow`` (:mod:`~vultron.shadow.dashboard.cli`) runs this file
with ``streamlit run``.  It reads the settings, draws the source menu
(:func:`~vultron.shadow.dashboard.source_menu.choose_source`), builds the
reader the chosen source reads through
(:func:`~vultron.shadow.readers.configured_case_reader`), and draws the page
(:func:`~vultron.shadow.dashboard.page.render`).  The page opens on the
recorded demo cases.  A setting the run cannot use stops the page with the
reason, before any case is read; a source that cannot be read stops the
page the same way, and the menu stays, so the analyst can pick another.
"""

from __future__ import annotations

from pathlib import Path

import streamlit as st
from pydantic import ValidationError

from vultron.config import get_config
from vultron.config.shadow import ShadowConfig
from vultron.core.ports.case_reader import CaseReader
from vultron.errors import VultronConfigError
from vultron.shadow.dashboard.page import TITLE, render
from vultron.shadow.dashboard.source_menu import ChosenSource, choose_source
from vultron.shadow.readers import CaseSource, configured_case_reader

#: What the page says while the chosen source cannot be read.
NO_SOURCE_NOTE = "Choose a source the page can read, in the menu at the side."


def ledger_suggestions(config: ShadowConfig) -> list[str]:
    """The recorded case-ledger files the page can offer, by name.

    Each is a ``*.jsonl`` file under ``ledger_dir``, named by its path
    relative to it, which is the case id the Vultron case reader takes.
    With no ``ledger_dir``, or one that is not a directory, there is none.
    """
    root = config.ledger_dir
    if root is None or not root.is_dir():
        return []
    return sorted(
        path.relative_to(root).as_posix() for path in root.rglob("*.jsonl")
    )


# A typed node is a new cache entry; the bound keeps a session that tries
# many from holding a reader for each.
@st.cache_resource(max_entries=16)
def _reader(config: ShadowConfig, chosen: ChosenSource) -> CaseReader:
    """The source's case reader, built once per source.

    The cache keeps only a reader that was built, so a source whose reader
    is refused, such as a connector that is not installed, runs the
    connector loader again on each rerun until it can be read.
    """
    return configured_case_reader(config, chosen.source, node=chosen.node)


def _stop(reason: str) -> None:
    st.title(TITLE)
    st.error(reason)


def main() -> None:
    """Draw the case shadow tool's page."""
    st.set_page_config(page_title=TITLE, page_icon="🔍", layout="wide")
    try:
        config = get_config()
    except (VultronConfigError, ValidationError) as exc:
        # A setting the run cannot use, such as a blank
        # VULTRON_SHADOW__CONNECTOR, stops the page with its reason.  The
        # configuration hides input values in its errors (VSD-01-005).
        _stop(str(exc))
        return
    chosen = choose_source(config)
    if chosen is None:
        st.title(TITLE)
        st.info(NO_SOURCE_NOTE)
        return
    try:
        reader = _reader(config.shadow, chosen)
    except VultronConfigError as exc:
        # A connector that is not installed, or reads no case, is refused
        # here, when the outside system is chosen.
        _stop(str(exc))
        return
    suggestions = (
        ledger_suggestions(config.shadow)
        if chosen.source == CaseSource.RECORDINGS
        else []
    )
    render(reader, suggestions)


#: The file ``streamlit run`` runs.
APP_PATH = Path(__file__)

if __name__ == "__main__":
    main()
