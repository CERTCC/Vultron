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

"""Shared peer-broadcast BT leaf nodes (BT-14-001, BT-14-002).

Provides reusable building blocks for all protocol-visible peer fan-out
subtrees:

- :func:`_find_case_manager_id` — locate the Case Manager actor ID from
  a case object
- :class:`FindCaseManagerNode` — resolve CASE_MANAGER actor to the
  blackboard key ``broadcast_case_manager_id``
- :class:`FilterPeerRecipientsNode` — filter eligible peer recipients to
  ``broadcast_peer_recipient_ids`` (returns SUCCESS with an empty list
  when no recipients remain; broadcast is a no-op, not a failure)
- :class:`CreateBroadcastActivityNode` — invoke a caller-supplied
  ``activity_builder`` to create the outbound AS2 activity; short-circuits
  to SUCCESS when the recipient list is empty; returns FAILURE when
  construction fails
- :class:`BroadcastQueueToOutboxNode` — enqueue the activity to the Case
  Manager's outbox; short-circuits to SUCCESS when no activity was created
  (no-op path); returns FAILURE on enqueue errors

Blackboard contract (node numbers match the sequence order in
:func:`~vultron.core.behaviors.broadcast.peer_broadcast_tree.peer_broadcast_bt`):

+----------------------------------+--------+---------+
| Key                              | Reads  | Written |
+==================================+========+=========+
| ``broadcast_case_manager_id``    | 2, 3, 4| 1       |
+----------------------------------+--------+---------+
| ``broadcast_peer_recipient_ids`` | 3, 4   | 2       |
+----------------------------------+--------+---------+
| ``broadcast_activity_id``        | 4      | 3       |
+----------------------------------+--------+---------+

Per specs/behavior-tree-integration.yaml BT-14-001, BT-14-002.
"""

import logging
from typing import TYPE_CHECKING, Any, Callable, cast

import py_trees
from py_trees.common import Status

from vultron.core.behaviors.helpers import DataLayerAction
from vultron.core.models.protocols import is_case_model
from vultron.core.states.roles import CVDRole

if TYPE_CHECKING:
    from vultron.core.ports.case_persistence import CasePersistence
    from vultron.core.ports.trigger_activity import TriggerActivityPort

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

    Reads the :class:`~vultron.wire.as2.vocab.objects.vulnerability_case.VulnerabilityCase`
    from the DataLayer, iterates its participants, and finds the one holding
    :attr:`~vultron.core.states.roles.CVDRole.CASE_MANAGER`.  Writes the
    attributed-to actor ID to ``broadcast_case_manager_id``.

    Returns SUCCESS when a Case Manager is found.
    Returns FAILURE when:

    - DataLayer or case_id is not available
    - Case is not found in the DataLayer
    - No CASE_MANAGER participant exists in the case

    Per BT-14-001, BT-14-002.
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
            "FindCaseManager: resolved CASE_MANAGER actor '%s'"
            " for case '%s'",
            case_manager_id,
            self.case_id,
        )
        return Status.SUCCESS


class FilterPeerRecipientsNode(DataLayerAction):
    """Filter broadcast recipients, excluding sender, self, and Case Manager.

    Reads the case from the DataLayer and computes the list of eligible peer
    recipients by excluding the original sender (``sender_actor_id``), the
    currently executing actor (``self.actor_id``), and the Case Manager
    (``broadcast_case_manager_id`` from the blackboard).

    Writes the resulting list — possibly empty — to
    ``broadcast_peer_recipient_ids`` and returns SUCCESS.  An empty list
    signals that broadcast is a no-op for this tick; downstream nodes
    short-circuit gracefully.

    Returns SUCCESS in all non-error cases (including no eligible recipients).
    Returns FAILURE when:

    - DataLayer or case_id is not available
    - ``broadcast_case_manager_id`` is not in the blackboard
    - Case is not found in the DataLayer

    Per BT-14-001, BT-14-002.
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

        self.blackboard.broadcast_peer_recipient_ids = recipient_ids

        if not recipient_ids:
            self.logger.debug(
                "FilterPeerRecipients: no eligible recipients in case '%s'"
                " — broadcast not needed",
                self.case_id,
            )
        else:
            self.logger.debug(
                "FilterPeerRecipients: %d eligible recipient(s)"
                " for case '%s'",
                len(recipient_ids),
                self.case_id,
            )
        return Status.SUCCESS


class CreateBroadcastActivityNode(DataLayerAction):
    """Create a broadcast activity via a domain-supplied factory callable.

    Reads ``broadcast_case_manager_id`` and ``broadcast_peer_recipient_ids``
    from the blackboard.  When the recipient list is empty, skips activity
    creation and returns SUCCESS without calling the factory (no-op path).

    Otherwise, calls::

        activity_id = activity_builder(factory, case_manager_id, recipient_ids)

    and writes the result to ``broadcast_activity_id``.

    The ``activity_builder`` callable receives:

    - *factory* — the :class:`~vultron.core.ports.trigger_activity.TriggerActivityPort`
      instance from the blackboard
    - *case_manager_id* — the Case Manager actor ID string
    - *recipient_ids* — the filtered list of peer actor ID strings

    It must return the newly created activity ID as a ``str``.

    Returns SUCCESS after creating the activity or when the recipient list is
    empty.
    Returns FAILURE when:

    - Required blackboard keys are missing
    - Recipients exist but ``trigger_activity_factory`` is not available
    - The ``activity_builder`` raises
      :class:`~vultron.errors.VultronError`

    Per BT-14-001, BT-14-002.
    """

    def __init__(
        self,
        activity_builder: Callable[
            ["TriggerActivityPort", str, list[str]], str
        ],
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self._activity_builder = activity_builder

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
        try:
            case_manager_id: str = self.blackboard.broadcast_case_manager_id
            recipient_ids: list[str] = (
                self.blackboard.broadcast_peer_recipient_ids
            )
        except KeyError as exc:
            self.feedback_message = f"Required blackboard key missing: {exc}"
            return Status.FAILURE

        if not recipient_ids:
            self.logger.debug(
                "%s: no recipients — skipping activity creation", self.name
            )
            return Status.SUCCESS

        if self.trigger_activity_factory is None:
            self.feedback_message = "trigger_activity_factory not available"
            self.logger.warning(
                "%s: %s — broadcast FAILURE (BT-14-001)",
                self.name,
                self.feedback_message,
            )
            return Status.FAILURE

        from vultron.errors import VultronError

        try:
            activity_id = self._activity_builder(
                self.trigger_activity_factory,
                case_manager_id,
                recipient_ids,
            )
        except VultronError as exc:
            self.feedback_message = (
                f"Broadcast activity creation failed: {exc}"
            )
            self.logger.warning("%s: %s", self.name, self.feedback_message)
            return Status.FAILURE

        self.blackboard.broadcast_activity_id = activity_id
        self.logger.debug(
            "%s: created broadcast activity '%s' from '%s' to %d peer(s)",
            self.name,
            activity_id,
            case_manager_id,
            len(recipient_ids),
        )
        return Status.SUCCESS


class BroadcastQueueToOutboxNode(DataLayerAction):
    """Queue the broadcast activity to the Case Manager's outbox.

    Reads ``broadcast_case_manager_id``, ``broadcast_activity_id``, and
    ``broadcast_peer_recipient_ids`` from the blackboard.

    When ``broadcast_activity_id`` is absent (no-op path set by
    :class:`CreateBroadcastActivityNode` when recipients were empty),
    returns SUCCESS immediately without touching the outbox.

    Returns SUCCESS after successfully queuing (or when nothing to queue).
    Returns FAILURE when:

    - ``broadcast_case_manager_id`` is missing from the blackboard
    - DataLayer is not available (and an activity to queue exists)
    - An exception is raised while queuing

    Per BT-14-001, BT-14-002.
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
        try:
            case_manager_id: str = self.blackboard.broadcast_case_manager_id
        except KeyError as exc:
            self.feedback_message = f"Required blackboard key missing: {exc}"
            return Status.FAILURE

        # No activity was created (no-op path when recipient list was empty).
        try:
            activity_id: str = self.blackboard.broadcast_activity_id
        except KeyError:
            self.logger.debug(
                "%s: no broadcast_activity_id — skipping outbox enqueue",
                self.name,
            )
            return Status.SUCCESS

        try:
            recipient_ids: list[str] = (
                self.blackboard.broadcast_peer_recipient_ids
            )
        except KeyError as exc:
            self.feedback_message = f"Required blackboard key missing: {exc}"
            return Status.FAILURE

        if self.datalayer is None:
            self.feedback_message = "DataLayer not available"
            return Status.FAILURE

        from vultron.core.ports.case_persistence import CaseOutboxPersistence
        from vultron.errors import VultronError

        try:
            cast(CaseOutboxPersistence, self.datalayer).record_outbox_item(
                case_manager_id, activity_id
            )
            self.logger.info(
                "%s: Case Manager '%s' queued broadcast activity '%s'"
                " to %d peer(s) (BT-14-001)",
                self.name,
                case_manager_id,
                activity_id,
                len(recipient_ids),
            )
        except VultronError as exc:
            self.feedback_message = (
                f"Failed to queue broadcast to outbox: {exc}"
            )
            self.logger.warning("%s: %s", self.name, self.feedback_message)
            return Status.FAILURE

        return Status.SUCCESS
