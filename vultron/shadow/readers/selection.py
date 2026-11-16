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

"""Which case reader a case shadow run reads through (#6441).

The dashboard reads one case through one
:class:`~vultron.core.ports.case_reader.CaseReader`.  An outside system's
reader is used when one is configured; otherwise the run reads Vultron
case-ledger files through the Vultron case reader, the source with nothing
left untranslated.  How an outside-system reader is found and configured is
the connector loader's job (``vultron/adapters/connectors/loader.py``) and
the dashboard's; this function only makes the choice.
"""

from __future__ import annotations

from vultron.core.ports.case_reader import CaseReader
from vultron.shadow.readers.vultron_ledger import VultronCaseReader


def select_case_reader(outside: CaseReader | None = None) -> CaseReader:
    """Return *outside*, or the Vultron case reader when it is ``None``.

    Args:
        outside: The outside-system case reader the run is configured with,
            or ``None`` when no outside system is configured.
    """
    if outside is None:
        return VultronCaseReader()
    return outside


__all__ = ["select_case_reader"]
