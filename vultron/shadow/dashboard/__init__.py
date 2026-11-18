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

"""The case shadow tool's dashboard (ADR-0192).

* :mod:`~vultron.shadow.dashboard.view` — what the page shows, as words,
  icons and rows, with no Streamlit call.
* :mod:`~vultron.shadow.dashboard.page` — the page, laid out with Streamlit.
* :mod:`~vultron.shadow.dashboard.source_menu` — the menu the analyst picks
  the page's source from: the recorded demo cases, VINCE, or a running
  Vultron node.
* :mod:`~vultron.shadow.dashboard.app` — the script ``streamlit run`` runs.
* :mod:`~vultron.shadow.dashboard.cli` — ``vultron-shadow``, which starts it.

Streamlit is sanctioned for this package only (SHD-02-004).
"""
