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
reader is used when one is configured.  Otherwise a configured Vultron node
is read through the live Vultron case reader (#6530), and with no node the
run reads Vultron case-ledger files through the Vultron case reader: both
are sources with nothing left untranslated.  How an outside-system reader is
found is the connector loader's job (``vultron/adapters/connectors/loader.py``),
and which one a run uses is its settings'
(:mod:`~vultron.shadow.readers.configured`); this function only makes the
choice.
"""

from __future__ import annotations

from pathlib import Path
from typing import NamedTuple

from vultron.core.ports.case_reader import CaseReader
from vultron.shadow.readers.vultron_ledger import VultronCaseReader
from vultron.shadow.readers.vultron_node import VultronNodeCaseReader


class VultronNode(NamedTuple):
    """A running Vultron node, and the CASE_MANAGER whose ledger is read.

    Attributes:
        url: The node's API root, such as ``http://case-actor:7999/api/v2``.
        actor_id: The CASE_MANAGER's actor id on that node, full or short.
    """

    url: str
    actor_id: str


def select_case_reader(
    outside: CaseReader | None = None,
    *,
    node: VultronNode | None = None,
    ledger_root: Path | None = None,
) -> CaseReader:
    """Return *outside*, else the live reader over *node*, else the file one.

    Args:
        outside: The outside-system case reader the run is configured with,
            or ``None`` when no outside system is configured.
        node: The Vultron node the run is configured to read, or ``None``
            when none is configured.  Not used when *outside* is set.
        ledger_root: The directory the Vultron case reader confines its
            ledger files to; when it is ``None``, the reader confines them
            to the working directory at construction.  Not used when
            *outside* or *node* is set.
    """
    if outside is not None:
        return outside
    if node is not None:
        return VultronNodeCaseReader(node.url, node.actor_id)
    return VultronCaseReader(root=ledger_root)


__all__ = ["VultronNode", "select_case_reader"]
