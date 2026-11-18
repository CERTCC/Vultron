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

"""Which case reader a case shadow tool run reads through (#6441, #6642).

The dashboard reads one case through one
:class:`~vultron.core.ports.case_reader.CaseReader`, and the analyst picks
the source it reads from on the page (:class:`CaseSource`): Vultron
case-ledger files, such as the recorded demo cases; an outside system, such
as VINCE; or a running Vultron node, read through the live Vultron case
reader (#6530).  How an outside-system reader is found is the connector
loader's job (``vultron/adapters/connectors/loader.py``), and what each
source is configured with is the run's settings'
(:mod:`~vultron.shadow.readers.configured`); this function only builds the
reader the chosen source reads through.
"""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from typing import NamedTuple

from vultron.core.ports.case_reader import CaseReader
from vultron.shadow.readers.vultron_ledger import VultronCaseReader
from vultron.shadow.readers.vultron_node import VultronNodeCaseReader


class CaseSource(StrEnum):
    """Where the case shadow tool reads a case from.

    Attributes:
        RECORDINGS: Vultron case-ledger files under the run's ledger
            directory, such as the recorded demo cases.  The page opens on
            this source.
        OUTSIDE: An outside system, through its connector's case reader,
            such as VINCE.
        NODE: A running Vultron node's case ledger, through the live Vultron
            case reader.
    """

    RECORDINGS = "recordings"
    OUTSIDE = "outside"
    NODE = "node"


class VultronNode(NamedTuple):
    """A running Vultron node, and the CASE_MANAGER whose ledger is read.

    Attributes:
        url: The node's API root, such as ``http://case-actor:7999/api/v2``.
        actor_id: The CASE_MANAGER's actor id on that node, full or short.
    """

    url: str
    actor_id: str


def select_case_reader(
    source: CaseSource = CaseSource.RECORDINGS,
    *,
    outside: CaseReader | None = None,
    node: VultronNode | None = None,
    ledger_root: Path | None = None,
) -> CaseReader:
    """Return the case reader *source* reads through.

    Args:
        source: The source the analyst chose.
        outside: The outside system's case reader; used only, and needed,
            when *source* is :attr:`CaseSource.OUTSIDE`.
        node: The Vultron node to read; used only, and needed, when *source*
            is :attr:`CaseSource.NODE`.
        ledger_root: The directory the Vultron case reader confines its
            ledger files to; when it is ``None``, the reader confines them
            to the working directory at construction.  Used only when
            *source* is :attr:`CaseSource.RECORDINGS`.

    Raises:
        ValueError: *source* needs *outside* or *node* and it is ``None``.
    """
    match source:
        case CaseSource.OUTSIDE:
            if outside is None:
                raise ValueError("an outside source needs its case reader")
            return outside
        case CaseSource.NODE:
            if node is None:
                raise ValueError("a node source needs the node to read")
            return VultronNodeCaseReader(node.url, node.actor_id)
        case CaseSource.RECORDINGS:
            return VultronCaseReader(root=ledger_root)


__all__ = ["CaseSource", "VultronNode", "select_case_reader"]
