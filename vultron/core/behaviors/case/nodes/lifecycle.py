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

"""
Case lifecycle action nodes for case behavior trees.

Provides the CommitCaseLedgerEntryNode for hash-chained case ledger replication.

Per specs/sync-ledger-replication.yaml SYNC-02-002, SYNC-02-003.
"""

import logging
from typing import Any, cast

import py_trees
from py_trees.common import Status

from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.helpers import DataLayerAction
from vultron.core.behaviors.sync.commit_tree import (
    create_commit_log_entry_tree,
)
from vultron.core.ports.case_persistence import (
    CaseOutboxPersistence,
    CasePersistence,
)
from vultron.core.use_cases._helpers import build_activity_payload_snapshot

logger = logging.getLogger(__name__)


def _extract_payload_snapshot(
    activity: Any, dl: CasePersistence | None = None
) -> dict[str, Any]:
    """Build a normalized payload snapshot for case-ledger commits."""
    event_activity = getattr(activity, "activity", None)
    if event_activity is not None:
        return cast(
            dict[str, Any],
            build_activity_payload_snapshot(event_activity, dl=dl),
        )
    return cast(
        dict[str, Any], build_activity_payload_snapshot(activity, dl=dl)
    )


class CommitCaseLedgerEntryNode(DataLayerAction):
    """
    Commit a hash-chained CaseLedgerEntry and fan it out to all case participants.

    Creates a :class:`~vultron.core.models.case_ledger_entry.VultronCaseLedgerEntry`,
    persists it, and queues one ``Announce(CaseLedgerEntry)`` activity per
    participant to the actor's outbox.  The :class:`OutboxMonitor` delivers
    queued activities reactively — this node only writes to the outbox.

    ``case_id`` is resolved in order:

    1. Constructor parameter (if provided at tree-build time).
    2. ``case_id`` key in the py_trees blackboard (written by a prior node
       such as :class:`CreateCaseNode` or :class:`PersistCase`).

    If ``case_id`` cannot be resolved, the node returns ``SUCCESS`` silently
    (no-op for trees that run in a non-case context).

    ``event_type`` and ``object_id`` are derived from the ``activity``
    blackboard key (the inbound :class:`~vultron.core.models.events.base.VultronEvent`
    placed there by :class:`~vultron.core.behaviors.bridge.BTBridge`).

    Per specs/sync-ledger-replication.yaml SYNC-02-002, SYNC-02-003.
    """

    def __init__(
        self,
        case_id: str | None = None,
        name: str | None = None,
    ):
        """
        Args:
            case_id: ID of the ``VulnerabilityCase`` to log against.  When
                ``None`` the node reads ``case_id`` from the blackboard.
            name: Optional display name for the node.
        """
        super().__init__(name=name or self.__class__.__name__)
        self._case_id = case_id
        self._sync_port: Any = None

    def setup(self, **kwargs: Any) -> None:
        super().setup(**kwargs)
        self.blackboard.register_key(
            key="case_id", access=py_trees.common.Access.READ
        )
        self.blackboard.register_key(
            key="activity", access=py_trees.common.Access.READ
        )
        self.blackboard.register_key(
            key="sync_port", access=py_trees.common.Access.READ
        )

    def initialise(self) -> None:
        super().initialise()
        try:
            self._sync_port = self.blackboard.sync_port
        except (AttributeError, KeyError):
            self._sync_port = None

    def update(self) -> Status:
        if self.datalayer is None or self.actor_id is None:
            self.logger.error(
                f"{self.name}: DataLayer or actor_id not available"
            )
            return Status.FAILURE

        try:
            case_id = self._case_id or self.blackboard.get("case_id")
        except KeyError:
            case_id = self._case_id
        if not case_id:
            self.logger.debug(
                f"{self.name}: no case_id available — skipping log entry"
            )
            return Status.SUCCESS

        try:
            activity = self.blackboard.get("activity")
        except KeyError:
            activity = None
        if activity is not None:
            object_id: str = getattr(activity, "activity_id", case_id)
            semantic_type = getattr(activity, "semantic_type", None)
            event_type: str = (
                semantic_type.value
                if semantic_type is not None
                else getattr(activity, "activity_type", "case_event")
                or "case_event"
            )
        else:
            object_id = case_id
            event_type = "case_event"
        payload_snapshot = (
            _extract_payload_snapshot(activity, dl=self.datalayer)
            if activity is not None
            else {}
        )

        tree = create_commit_log_entry_tree(
            case_id=case_id,
            object_id=object_id,
            event_type=event_type,
            payload_snapshot=payload_snapshot,
        )
        result = BTBridge(
            datalayer=cast(CaseOutboxPersistence, self.datalayer)
        ).execute_with_setup(
            tree=tree,
            actor_id=self.actor_id,
            sync_port=self._sync_port,
        )
        if result.status == Status.SUCCESS:
            self.logger.info(
                "%s: committed log entry '%s' for case '%s'",
                self.name,
                event_type,
                case_id,
            )
            return Status.SUCCESS
        self.logger.error(
            "%s: failed to commit log entry for case '%s': %s",
            self.name,
            case_id,
            result.feedback_message,
        )
        return Status.FAILURE
