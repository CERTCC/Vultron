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

"""Shared peer-broadcast BT helper package (BT-14-001, BT-14-002).

Provides reusable leaf nodes and a :func:`peer_broadcast_bt` factory for
all protocol-visible peer fan-out subtrees.  Callers that used the old
status-domain ``BroadcastStatusToPeersNode`` directly can continue to do
so — it now delegates internally to :func:`peer_broadcast_bt`.
"""

from vultron.core.behaviors.broadcast.nodes import (
    BroadcastQueueToOutboxNode,
    CreateBroadcastActivityNode,
    FilterPeerRecipientsNode,
    FindCaseManagerNode,
    _find_case_manager_id,
)
from vultron.core.behaviors.broadcast.peer_broadcast_tree import (
    peer_broadcast_bt,
)

__all__ = [
    "_find_case_manager_id",
    "FindCaseManagerNode",
    "FilterPeerRecipientsNode",
    "CreateBroadcastActivityNode",
    "BroadcastQueueToOutboxNode",
    "peer_broadcast_bt",
]
