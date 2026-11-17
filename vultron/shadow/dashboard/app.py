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
with ``streamlit run``.  It reads the ``shadow:`` settings, picks the case
reader they name (:func:`~vultron.shadow.readers.configured_case_reader`),
and draws the page (:func:`~vultron.shadow.dashboard.page.render`).  A
setting the reader cannot use stops the page with the reason, before any
case is read.
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
from vultron.shadow.readers import configured_case_reader


def ledger_suggestions(config: ShadowConfig) -> list[str]:
    """The case-ledger files a Vultron case reader run can offer, by name.

    Each is a ``*.jsonl`` file under ``ledger_dir``, named by its path
    relative to it, which is the case id the reader takes.  A run through a
    connector, or with no ``ledger_dir``, offers none.
    """
    root = config.ledger_dir
    if config.connector is not None or root is None or not root.is_dir():
        return []
    return sorted(
        path.relative_to(root).as_posix() for path in root.rglob("*.jsonl")
    )


@st.cache_resource
def _reader(config: ShadowConfig) -> CaseReader:
    """The run's case reader, built once: the connector loader runs once."""
    return configured_case_reader(config)


def main() -> None:
    """Draw the case shadow tool's page."""
    st.set_page_config(page_title=TITLE, page_icon="🔍", layout="wide")
    try:
        config = get_config().shadow
        reader = _reader(config)
    except (VultronConfigError, ValidationError) as exc:
        # A setting the run cannot use, such as a blank
        # VULTRON_SHADOW__CONNECTOR, stops the page with its reason.  The
        # configuration hides input values in its errors (VSD-01-005).
        st.title(TITLE)
        st.error(str(exc))
        return
    render(reader, ledger_suggestions(config))


#: The file ``streamlit run`` runs.
APP_PATH = Path(__file__)

if __name__ == "__main__":
    main()
