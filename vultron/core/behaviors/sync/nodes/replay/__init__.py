#!/usr/bin/env python
#
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

"""Action nodes for SYNC log-replication replay.

Replay is catch-up for one peer that has fallen behind, driven by an inbound
``Reject(CaseLedgerEntry)`` or by the position a ``Read(CaseLedgerEntry)``
states (SYNC-03-002, SYNC-17-004).  The fan-out nodes that used to live here — the
distribution of a single entry to every recipient — now sit in ``fanout.py``
alongside their RM.CLOSED-filtered variants (BTND-07-004), and the genesis
pre-seed ``AnnounceCaseOnGenesisRejectNode`` sits in ``genesis_announce.py``
(CS-18-001).

Split by concern (CS-18-005): ``divergence`` finds where the peer's copy
diverges and ``send`` sends what follows.
"""

from vultron.core.behaviors.sync.nodes.replay.divergence import (
    CollectAndSortCaseLedgerEntriesNode,
    FindCaseActorNode,
    FindDivergenceIndexNode,
)
from vultron.core.behaviors.sync.nodes.replay.send import (
    ReplayMissingEntriesNode,
    SendMissingEntriesNode,
)

__all__ = [
    "CollectAndSortCaseLedgerEntriesNode",
    "FindCaseActorNode",
    "FindDivergenceIndexNode",
    "ReplayMissingEntriesNode",
    "SendMissingEntriesNode",
]
