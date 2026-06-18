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
status-specific :class:`CreateStatusBroadcastActivityNode` and the
updated :class:`BroadcastStatusToPeersNode`.

Per DEMOMA-07-003 step 3 and specs/behavior-tree-integration.yaml
BT-14-001, BT-14-002.
"""

import logging
from typing import Any

import py_trees
from py_trees.common import Status

from vultron.core.behaviors.broadcast.nodes import (  # noqa: F401
    BroadcastQueueToOutboxNode,
    FilterPeerRecipientsNode,
    FindCaseManagerNode,
    _find_case_manager_id,
)
from vultron.core.behaviors.helpers import DataLayerAction

logger = logging.getLogger(__name__)


class CreateStatusBroadcastActivityNode(DataLayerAction):
    """Create the broadcast Add(ParticipantStatus, CaseParticipant) activity.

    Reads ``broadcast_case_manager_id`` and ``broadcast_peer_recipient_ids``
    from the blackboard (written by :class:`FindCaseManagerNode` and
    :class:`FilterPeerRecipientsNode`) and calls ``trigger_activity_factory``
    to construct the broadcast activity addressed from the Case Manager to all
    peer recipients.

    Writes the resulting activity ID to the blackboard under
    ``broadcast_activity_id``.

    Returns SUCCESS on successful activity creation.
    Returns FAILURE when:
    - ``trigger_activity_factory`` is not available
    - Required blackboard keys are missing
    - The factory raises :class:`~vultron.errors.VultronError`

    Per DEMOMA-07-003 step 3.
    """

    def __init__(
        self,
        status_id: str,
        participant_id: str,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.status_id = status_id
        self.participant_id = participant_id

    def setup(self, **kwargs: Any) -> None:
        super().setup(**kwargs)
        self.blackboard.register_key(
            key="broadcast_case_manager_id",
            access=py_trees.common.Access.READ,
        )
        self.blackboard.register_key(
            key="broadcast_peer_recipient_ids",
            access=py_trees.common.Access.READ,
        )
        self.blackboard.register_key(
            key="broadcast_activity_id",
            access=py_trees.common.Access.WRITE,
        )

    def update(self) -> Status:
        if self.trigger_activity_factory is None:
            self.feedback_message = "trigger_activity_factory not available"
            self.logger.debug(
                "CreateStatusBroadcastActivity: no trigger_activity_factory"
                " — skipping (DEMOMA-07-003 step 3)"
            )
            return Status.FAILURE

        try:
            case_manager_id: str = self.blackboard.broadcast_case_manager_id
            recipient_ids: list[str] = (
                self.blackboard.broadcast_peer_recipient_ids
            )
        except KeyError as exc:
            self.feedback_message = f"Required blackboard key missing: {exc}"
            return Status.FAILURE

        from vultron.errors import VultronError

        try:
            activity_id = self.trigger_activity_factory.add_participant_status_to_participant(
                status_id=self.status_id,
                participant_id=self.participant_id,
                actor=case_manager_id,
                to=recipient_ids,
            )
        except VultronError as exc:
            self.feedback_message = (
                f"Broadcast activity creation failed: {exc}"
            )
            self.logger.warning(
                "CreateStatusBroadcastActivity: %s", self.feedback_message
            )
            return Status.FAILURE

        self.blackboard.broadcast_activity_id = activity_id
        self.logger.debug(
            "CreateStatusBroadcastActivity: created broadcast activity '%s'"
            " from '%s' to %d peer(s)",
            activity_id,
            case_manager_id,
            len(recipient_ids),
        )
        return Status.SUCCESS


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

        from vultron.core.behaviors.broadcast.nodes import (
            CreateBroadcastActivityNode,
        )

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
