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

"""Status-domain peer broadcast nodes for the AddParticipantStatus workflow.

Re-exports the shared generic nodes from
:mod:`vultron.core.behaviors.broadcast.nodes` and provides the
status-specific :class:`BroadcastStatusToPeersNode`.

Per DEMOMA-07-003 step 3 and specs/behavior-tree-integration.yaml
BT-14-001, BT-14-002.
"""

import logging
from typing import Any

import py_trees

from vultron.core.behaviors.broadcast.nodes import (  # noqa: F401
    BroadcastQueueToOutboxNode,
    CreateBroadcastActivityNode,
    FilterPeerRecipientsNode,
    FindCaseManagerNode,
    _find_case_manager_id,
)

logger = logging.getLogger(__name__)


class BroadcastStatusToPeersNode(py_trees.composites.Sequence):
    """Step 3: Fail-fast broadcast of Add(ParticipantStatus) to peers.

    The current actor re-sends the status update to all other participants,
    excluding the original sender, itself, and the Case Manager.

    Implemented as a ``py_trees.composites.Sequence`` (memory=False) via
    :func:`~vultron.core.behaviors.broadcast.peer_broadcast_tree.peer_broadcast_bt`.
    Returns FAILURE when broadcast preparation or outbox enqueueing fails
    (BT-14-001).  Returns SUCCESS when the recipient list is empty (no peers
    to notify — broadcast is a no-op, not a failure).

    Broadcast sequence:

    .. code-block:: text

        ├── FindCaseManagerNode          # resolve Case Manager → blackboard
        ├── FilterPeerRecipientsNode     # exclude sender/self/manager → blackboard
        ├── CreateBroadcastActivityNode  # factory call → blackboard
        └── BroadcastQueueToOutboxNode   # queue activity to Case Manager outbox

    Per DEMOMA-07-003 step 3 and specs/behavior-tree-integration.yaml
    BT-14-001, BT-14-002.
    """

    def __init__(
        self,
        status_id: str,
        participant_id: str,
        sender_actor_id: str,
        case_id: str | None,
        name: str | None = None,
    ):
        super().__init__(name=name or self.__class__.__name__, memory=False)

        def _status_activity_builder(
            factory: Any, case_manager_id: str, recipient_ids: list[str]
        ) -> str:
            result: str = factory.add_participant_status_to_participant(
                status_id=status_id,
                participant_id=participant_id,
                actor=case_manager_id,
                to=recipient_ids,
            )
            return result

        self.add_children(
            [
                FindCaseManagerNode(case_id=case_id),
                FilterPeerRecipientsNode(
                    sender_actor_id=sender_actor_id,
                    case_id=case_id,
                ),
                CreateBroadcastActivityNode(
                    activity_builder=_status_activity_builder
                ),
                BroadcastQueueToOutboxNode(),
            ]
        )
