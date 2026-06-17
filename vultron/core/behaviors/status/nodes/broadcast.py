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

"""Peer broadcast nodes for the AddParticipantStatus workflow.

Contains the Case Manager resolution, peer recipient filtering, broadcast
activity creation, and outbox queuing leaf nodes, plus the composite
:class:`BroadcastStatusToPeersNode` that orchestrates them.

Per DEMOMA-07-003 step 3.
"""

import logging
from typing import TYPE_CHECKING, Any, cast

import py_trees
from py_trees.common import Status

from vultron.core.behaviors.helpers import DataLayerAction
from vultron.core.models.protocols import is_case_model
from vultron.core.states.roles import CVDRole

if TYPE_CHECKING:
    from vultron.core.ports.case_persistence import CasePersistence

logger = logging.getLogger(__name__)


def _find_case_manager_id(dl: "CasePersistence", case: Any) -> str | None:
    """Return the attributed_to actor ID for the CASE_MANAGER participant."""
    for p_id in case.actor_participant_index.values():
        p = dl.read(p_id)
        if p is None:
            continue
        roles = getattr(p, "case_roles", [])
        if CVDRole.CASE_MANAGER in roles:
            attr = getattr(p, "attributed_to", None)
            if attr:
                return str(attr)
    return None


class FindCaseManagerNode(DataLayerAction):
    """Resolve the CASE_MANAGER actor ID and write it to the blackboard.

    Reads the :class:`VulnerabilityCase` from the DataLayer, iterates its
    participants, and finds the one holding :attr:`CVDRole.CASE_MANAGER`.
    Writes the attributed-to actor ID to the blackboard under the key
    ``broadcast_case_manager_id``.

    Designed for use in broadcast subtrees where the Case Manager is the
    designated broadcast sender.

    Returns SUCCESS when a Case Manager is found.
    Returns FAILURE when:
    - DataLayer or case_id is not available
    - Case is not found in the DataLayer
    - No CASE_MANAGER participant exists in the case
    """

    def __init__(self, case_id: str | None, name: str | None = None) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.case_id = case_id

    def setup(self, **kwargs: Any) -> None:
        super().setup(**kwargs)
        self.blackboard.register_key(
            key="broadcast_case_manager_id",
            access=py_trees.common.Access.WRITE,
        )

    def update(self) -> Status:
        if self.datalayer is None or not self.case_id:
            self.feedback_message = "DataLayer or case_id not available"
            return Status.FAILURE

        case = self.datalayer.read(self.case_id)
        if not is_case_model(case):
            self.feedback_message = f"Case '{self.case_id}' not found"
            return Status.FAILURE

        case_manager_id = _find_case_manager_id(self.datalayer, case)
        if case_manager_id is None:
            self.feedback_message = (
                f"No CASE_MANAGER found in case '{self.case_id}'"
            )
            return Status.FAILURE

        self.blackboard.broadcast_case_manager_id = case_manager_id
        self.logger.debug(
            "FindCaseManager: resolved CASE_MANAGER actor '%s' for case '%s'",
            case_manager_id,
            self.case_id,
        )
        return Status.SUCCESS


class FilterPeerRecipientsNode(DataLayerAction):
    """Filter broadcast recipients, excluding sender, self, and Case Manager.

    Reads the :class:`VulnerabilityCase` from the DataLayer and computes the
    list of eligible peer recipients by excluding the original status sender,
    the currently executing actor (``self.actor_id``), and the Case Manager
    actor (``broadcast_case_manager_id`` from the blackboard).

    Writes the resulting list to the blackboard under
    ``broadcast_peer_recipient_ids``.

    Returns SUCCESS when at least one eligible recipient is found.
    Returns FAILURE when:
    - DataLayer or case_id is not available
    - ``broadcast_case_manager_id`` is not in the blackboard
    - Case is not found
    - No eligible recipients remain after filtering

    Per DEMOMA-07-003 step 3 filtering rules.
    """

    def __init__(
        self,
        sender_actor_id: str,
        case_id: str | None,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.sender_actor_id = sender_actor_id
        self.case_id = case_id

    def setup(self, **kwargs: Any) -> None:
        super().setup(**kwargs)
        self.blackboard.register_key(
            key="broadcast_case_manager_id",
            access=py_trees.common.Access.READ,
        )
        self.blackboard.register_key(
            key="broadcast_peer_recipient_ids",
            access=py_trees.common.Access.WRITE,
        )

    def update(self) -> Status:
        if self.datalayer is None or not self.case_id:
            self.feedback_message = "DataLayer or case_id not available"
            return Status.FAILURE

        try:
            case_manager_id: str = self.blackboard.broadcast_case_manager_id
        except KeyError:
            self.feedback_message = (
                "broadcast_case_manager_id not set in blackboard"
            )
            return Status.FAILURE

        case = self.datalayer.read(self.case_id)
        if not is_case_model(case):
            self.feedback_message = f"Case '{self.case_id}' not found"
            return Status.FAILURE

        recipient_ids = [
            a_id
            for a_id in case.actor_participant_index.keys()
            if (
                a_id != self.sender_actor_id
                and a_id != self.actor_id
                and a_id != case_manager_id
            )
        ]
        if not recipient_ids:
            self.feedback_message = (
                f"No eligible peer recipients in case '{self.case_id}'"
            )
            self.logger.debug(
                "FilterPeerRecipients: no eligible recipients in case '%s'"
                " — broadcast not needed",
                self.case_id,
            )
            return Status.FAILURE

        self.blackboard.broadcast_peer_recipient_ids = recipient_ids
        self.logger.debug(
            "FilterPeerRecipients: %d eligible recipient(s) for case '%s'",
            len(recipient_ids),
            self.case_id,
        )
        return Status.SUCCESS


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


class BroadcastQueueToOutboxNode(DataLayerAction):
    """Queue the broadcast activity to the Case Manager's outbox.

    Reads ``broadcast_case_manager_id``, ``broadcast_activity_id``, and
    ``broadcast_peer_recipient_ids`` from the blackboard and queues the
    activity to the Case Manager actor's outbox via
    :meth:`~vultron.core.ports.case_persistence.CaseOutboxPersistence.record_outbox_item`.

    Returns SUCCESS after successfully queuing.
    Returns FAILURE when:
    - DataLayer is not available
    - Required blackboard keys are missing
    - An exception is raised while queuing

    Per DEMOMA-07-003 step 3.
    """

    def __init__(self, name: str | None = None) -> None:
        super().__init__(name=name or self.__class__.__name__)

    def setup(self, **kwargs: Any) -> None:
        super().setup(**kwargs)
        self.blackboard.register_key(
            key="broadcast_case_manager_id",
            access=py_trees.common.Access.READ,
        )
        self.blackboard.register_key(
            key="broadcast_activity_id",
            access=py_trees.common.Access.READ,
        )
        self.blackboard.register_key(
            key="broadcast_peer_recipient_ids",
            access=py_trees.common.Access.READ,
        )

    def update(self) -> Status:
        if self.datalayer is None:
            self.feedback_message = "DataLayer not available"
            return Status.FAILURE

        try:
            case_manager_id: str = self.blackboard.broadcast_case_manager_id
            activity_id: str = self.blackboard.broadcast_activity_id
            recipient_ids: list[str] = (
                self.blackboard.broadcast_peer_recipient_ids
            )
        except KeyError as exc:
            self.feedback_message = f"Required blackboard key missing: {exc}"
            return Status.FAILURE

        from vultron.core.ports.case_persistence import CaseOutboxPersistence
        from vultron.errors import VultronError

        try:
            cast(CaseOutboxPersistence, self.datalayer).record_outbox_item(
                case_manager_id, activity_id
            )
            self.logger.info(
                "BroadcastQueueToOutbox: Case Manager '%s' queued status"
                " broadcast activity '%s' to %d peer(s)"
                " (DEMOMA-07-003 step 3)",
                case_manager_id,
                activity_id,
                len(recipient_ids),
            )
        except VultronError as exc:
            self.feedback_message = (
                f"Failed to queue broadcast to outbox: {exc}"
            )
            self.logger.warning(
                "BroadcastQueueToOutbox: %s", self.feedback_message
            )
            return Status.FAILURE

        return Status.SUCCESS


class BroadcastStatusToPeersNode(py_trees.composites.Selector):
    """Step 3: Broadcast Add(ParticipantStatus, CaseParticipant) to peers.

    The current actor re-sends the status update to all other participants,
    excluding the original sender, itself, and the Case Manager. Skips
    silently when no trigger factory is available, when the case or Case
    Manager is not found, or when there are no eligible recipients.

    Always returns SUCCESS (failure to broadcast is not fatal).

    Implemented as a ``py_trees.composites.Selector`` (memory=False):

    - Child 1 ``_BroadcastWorkSequence``: inner Sequence of four leaf nodes
      that resolves the Case Manager, filters eligible peers, creates the
      broadcast activity, and queues it to the Case Manager's outbox.
    - Child 2 ``py_trees.behaviours.Success``: non-fatal fallback — only
      reached when the work sequence returns FAILURE on a known skip path
      (no recipients, no Case Manager, ``VultronError`` from factory or
      outbox operations). Non-``VultronError`` exceptions propagate
      normally and are not swallowed.

    Inner broadcast sequence:

    .. code-block:: text

        ├── FindCaseManagerNode          # resolve Case Manager → blackboard
        ├── FilterPeerRecipientsNode     # exclude sender/self/manager → blackboard
        ├── CreateStatusBroadcastActivityNode  # factory call → blackboard
        └── BroadcastQueueToOutboxNode   # queue activity to Case Manager outbox

    Per DEMOMA-07-003 step 3.
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
        inner_sequence = py_trees.composites.Sequence(
            name="BroadcastWorkSequence",
            memory=False,
            children=[
                FindCaseManagerNode(case_id=case_id),
                FilterPeerRecipientsNode(
                    sender_actor_id=sender_actor_id,
                    case_id=case_id,
                ),
                CreateStatusBroadcastActivityNode(
                    status_id=status_id,
                    participant_id=participant_id,
                ),
                BroadcastQueueToOutboxNode(),
            ],
        )
        self.add_children(
            [
                inner_sequence,
                py_trees.behaviours.Success(name="BroadcastSkipped"),
            ]
        )
