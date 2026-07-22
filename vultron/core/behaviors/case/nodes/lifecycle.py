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

    If ``case_id`` cannot be resolved, the node returns ``FAILURE`` so the
    enclosing BT sequence propagates the error (ARCH-15-001).

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

    def _resolve_case_id(self) -> str | None:
        try:
            return self._case_id or self.blackboard.get("case_id")
        except KeyError:
            return self._case_id

    def _resolve_activity(self) -> Any | None:
        try:
            return self.blackboard.get("activity")
        except KeyError:
            return None

    def _activity_metadata(
        self, activity: Any | None, case_id: str
    ) -> tuple[str, str, dict[str, Any]]:
        if activity is None:
            return case_id, "case_event", {}

        object_id = getattr(activity, "activity_id", case_id)
        semantic_type = getattr(activity, "semantic_type", None)
        event_type = (
            semantic_type.value
            if semantic_type is not None
            else getattr(activity, "activity_type", "case_event")
            or "case_event"
        )
        payload_snapshot = _extract_payload_snapshot(
            activity, dl=self.datalayer
        )
        return object_id, event_type, payload_snapshot

    def update(self) -> Status:
        if (f := self._require_datalayer_and_actor()) is not None:
            return f
        assert self.datalayer is not None
        assert self.actor_id is not None
        case_id = self._resolve_case_id()
        if not case_id:
            self.logger.error(
                f"{self.name}: no case_id available — cannot commit ledger"
                " entry"
            )
            return Status.FAILURE

        activity = self._resolve_activity()
        if activity is None:
            self.logger.warning(
                "%s: no activity on blackboard for case '%s' — skipping"
                " log entry",
                self.name,
                case_id,
            )
            return Status.FAILURE

        object_id, event_type, payload_snapshot = self._activity_metadata(
            activity, case_id
        )

        # Normalize context to case_id for activities that predate the case
        # (e.g., Offer(VulnerabilityReport) submitted before the case existed).
        if payload_snapshot and payload_snapshot.get("context") != case_id:
            payload_snapshot = dict(payload_snapshot)
            payload_snapshot["context"] = case_id

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


def create_guarded_commit_case_ledger_entry_tree(
    case_id: str | None = None,
) -> py_trees.composites.Selector:
    """Create a guarded commit subtree for canonical case-ledger entries.

    The commit runs only when the executing actor holds ``CVDRole.CASE_MANAGER``
    for the case. Non-manager actors take the success fallback and skip the
    canonical commit silently.

    Structure::

        GuardedCommitCaseLedgerEntryBT (Selector)
        ├── SkipIfNotCaseManager (Sequence)
        │   └── Inverter(CheckIsCaseManagerNode)  # SUCCESS when NOT case manager
        └── CommitCaseLedgerEntryNode             # only reached when IS case manager

    Using an ``Inverter`` separates the two distinct FAILURE modes:

    - Actor is NOT the case manager → ``Inverter`` converts FAILURE→SUCCESS,
      ``SkipIfNotCaseManager`` succeeds, Selector returns SUCCESS (skip).
    - Actor IS the case manager but commit fails → ``Inverter`` converts
      SUCCESS→FAILURE, ``SkipIfNotCaseManager`` fails, Selector tries
      ``CommitCaseLedgerEntryNode`` which returns FAILURE, Selector returns
      FAILURE (propagates the infrastructure error to abort effect nodes).

    This prevents the old fallback-Success pattern from masking a genuine
    commit failure as a benign skip.

    Called internally by :func:`create_receive_activity_tree`.  Direct callers
    in tree-factory modules are a CLP-10-006 ordering violation; use
    ``create_receive_activity_tree`` instead.
    """
    from vultron.core.behaviors.case.nodes.conditions import (
        CheckIsCaseManagerNode,
    )

    check_node = CheckIsCaseManagerNode(case_id=case_id)
    return py_trees.composites.Selector(
        name="GuardedCommitCaseLedgerEntryBT",
        memory=False,
        children=[
            py_trees.composites.Sequence(
                name="SkipIfNotCaseManager",
                memory=False,
                children=[
                    py_trees.decorators.Inverter(
                        name="InvertIsNotCaseManager",
                        child=check_node,
                    ),
                ],
            ),
            CommitCaseLedgerEntryNode(case_id=case_id),
        ],
    )


def create_receive_activity_tree(
    name: str,
    case_id: str | None,
    precondition_guards: list[py_trees.behaviour.Behaviour],
    effect_nodes: list[py_trees.behaviour.Behaviour],
) -> py_trees.composites.Sequence:
    """Compose a receive-side BT with CLP-10-006 ordering.

    Structurally enforces the correct receive-side ordering::

        [*precondition_guards] → GuardedCommit(receipt) → [*effect_nodes]

    Precondition guards are read-only checks that may return FAILURE to abort
    the tree before any state is written.  The guarded commit ledgers receipt
    of the triggering activity (which is on the blackboard before any node
    runs, placed there by ``BTBridge.execute_with_setup``).  Effect nodes
    perform state transitions, outbox enqueues, and participant mutations —
    all of which happen only after the receipt is recorded.

    When ``case_id`` is ``None`` the commit step is omitted entirely,
    preserving behaviour for trees that receive no explicit case context.

    Per ``specs/case-ledger-processing.yaml`` CLP-10-006.

    Args:
        name: Display name for the root Sequence node.
        case_id: ID of the ``VulnerabilityCase`` to ledger against.  Pass
            ``None`` to skip the commit step (no ledger entry written).
        precondition_guards: Zero or more read-only condition nodes placed
            before the commit.  These nodes MUST NOT write to the DataLayer.
        effect_nodes: Zero or more action nodes placed after the commit.
            These may perform any state mutation.

    Returns:
        Root ``Sequence`` node ready for execution via
        :class:`~vultron.core.behaviors.bridge.BTBridge`.
    """
    children: list[py_trees.behaviour.Behaviour] = list(precondition_guards)
    if case_id is not None:
        children.append(
            create_guarded_commit_case_ledger_entry_tree(case_id=case_id)
        )
    else:
        logger.debug(
            "create_receive_activity_tree(%s): case_id is None"
            " — commit step omitted",
            name,
        )
    children.extend(effect_nodes)
    return py_trees.composites.Sequence(
        name=name,
        memory=False,
        children=children,
    )
