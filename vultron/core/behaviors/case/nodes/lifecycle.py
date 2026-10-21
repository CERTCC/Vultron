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

from py_trees.common import Status
from py_trees.ports import NoDataAvailable, PortInformation

from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.case.nodes.ledger_payload import (
    _extract_payload_snapshot,
    carries_no_received_body,
    unrecordable_resend_reason,
)
from vultron.core.behaviors.helpers import DataLayerActionWithPorts
from vultron.core.behaviors.sync.commit_tree import (
    create_commit_log_entry_tree,
)
from vultron.core.ports.case_outbox import CaseOutboxPersistence
from vultron.core.predicates.addressing import (
    same_actor_id,
    snapshot_actor_id,
)
from vultron.core.sync_helpers import is_ledgered_activity
from vultron.errors import (
    VultronBTInternalError,
    VultronCanonicalEntryError,
)

logger = logging.getLogger(__name__)


def _assert_actor_identity(
    semantic_type: str, payload_snapshot: dict[str, Any], activity: Any
) -> None:
    """CLP-07-003: payloadSnapshot.actor MUST name the inbound activity's actor.

    The snapshot keeps the sender's spelling while the event's ``actor_id``
    is normalised (OID-01-006), so the two are compared with
    :func:`same_actor_id`: a trailing slash is not a substitution.
    """
    activity_actor_id = getattr(activity, "actor_id", None)
    raw_actor = payload_snapshot.get("actor") if payload_snapshot else None
    # An actor that names no id (not a string, an inline object without
    # one) cannot be shown to be the sender, so it is refused too.
    snapshot_actor = snapshot_actor_id(raw_actor)
    if (
        activity_actor_id
        and raw_actor
        and (
            snapshot_actor is None
            or not same_actor_id(snapshot_actor, activity_actor_id)
        )
    ):
        raise VultronCanonicalEntryError(
            f"{semantic_type}: CLP-07-003 — payloadSnapshot.actor"
            f" {snapshot_actor!r} does not match activity.actor_id"
            f" {activity_actor_id!r}; identity substitution refused"
        )


def _semantic_type_of(activity: Any) -> str:
    """The semantic an entry records *activity* as."""
    semantics = getattr(activity, "semantic_type", None)
    if semantics is not None:
        return cast(str, semantics.value)
    return getattr(activity, "activity_type", "case_event") or "case_event"


class CommitCaseLedgerEntryNode(DataLayerActionWithPorts):
    """
    Commit a hash-chained CaseLedgerEntry and fan it out to all case participants.

    Creates a :class:`~vultron.core.models.case_ledger_entry.CaseLedgerEntry`,
    persists it, and queues one ``Announce(CaseLedgerEntry)`` activity per
    participant to the actor's outbox.  The :class:`OutboxMonitor` delivers
    queued activities reactively — this node only writes to the outbox.

    ``case_id`` is resolved in order:

    1. Constructor parameter (if provided at tree-build time).
    2. ``case_id`` key in the py_trees blackboard (written by a prior node
       such as :class:`CreateCaseFromProposalNode`).

    If ``case_id`` cannot be resolved, the node returns ``FAILURE`` so the
    enclosing BT sequence propagates the error (ARCH-15-001).

    ``semantic_type`` and ``object_id`` are derived from the ``activity``
    blackboard key (the inbound :class:`~vultron.core.models.events.base.VultronEvent`
    placed there by :class:`~vultron.core.behaviors.bridge.BTBridge`).

    Per specs/sync-ledger-replication.yaml SYNC-02-002, SYNC-02-003.
    """

    def __init__(
        self,
        case_id: str | None = None,
        name: str | None = None,
    ):
        super().__init__(name=name or self.__class__.__name__)
        self._case_id = case_id
        self._sync_port: Any = None

    INPUT_PORTS: dict[str, PortInformation] = {
        **DataLayerActionWithPorts.INPUT_PORTS,
        "case_id": PortInformation(data_type=str, required=False),
        "activity": PortInformation(data_type=object, required=False),
        "sync_port": PortInformation(data_type=object, required=False),
    }

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {
            "case_id": "/case_id",
            "activity": "/activity",
            "sync_port": "/sync_port",
        }

    def initialise(self) -> None:
        super().initialise()
        try:
            self._case_id_bb: str | None = self.get_input("case_id")
        except (NoDataAvailable, NotImplementedError):
            self._case_id_bb = None
        try:
            self._activity: Any = self.get_input("activity")
        except (NoDataAvailable, NotImplementedError):
            self._activity = None
        try:
            self._sync_port = self.get_input("sync_port")
        except (NoDataAvailable, NotImplementedError):
            self._sync_port = None

    def _resolve_case_id(self) -> str | None:
        return self._case_id or self._case_id_bb

    def _resolve_activity(self) -> Any | None:
        return self._activity

    def _answer_resend(self, activity: Any, case_id: str) -> Status:
        """Answer a resend routed without received evidence (IE-10-001).

        It has no body to record.  When the ledger records its first delivery
        as the same semantic, that entry stands.  Otherwise the resend is
        refused, not recorded: its first delivery was never recorded, or the
        id is recorded for a different activity, which a resend rebuilt from
        a different body would otherwise pass for (CLP-07-013).
        """
        assert self.datalayer is not None
        activity_id = activity.activity_id
        semantic_type = _semantic_type_of(activity)
        if is_ledgered_activity(
            self.datalayer, case_id, activity_id, semantic_type=semantic_type
        ):
            self.logger.info(
                "%s: activity '%s' is a redelivery already recorded for case"
                " '%s'; its first delivery's entry stands",
                self.name,
                activity_id,
                case_id,
            )
            return Status.SUCCESS
        if is_ledgered_activity(self.datalayer, case_id, activity_id):
            self.feedback_message = (
                f"activity '{activity_id}' is recorded for case '{case_id}'"
                f" as another activity than '{semantic_type}', and this"
                " resend carries no received body to record (IE-10-001)"
            )
        else:
            self.feedback_message = unrecordable_resend_reason(
                activity_id, case_id
            )
        self.logger.warning("%s: %s", self.name, self.feedback_message)
        return Status.FAILURE

    def _activity_metadata(
        self, activity: Any | None, case_id: str
    ) -> tuple[str, str, dict[str, Any]]:
        if activity is None:
            return case_id, "case_event", {}

        object_id = getattr(activity, "activity_id", case_id)
        semantic_type = _semantic_type_of(activity)
        payload_snapshot = _extract_payload_snapshot(activity)
        return object_id, semantic_type, payload_snapshot

    def update(self) -> Status:
        if (f := self._require_datalayer_and_actor()) is not None:
            return f
        assert self.datalayer is not None
        assert self.actor_id is not None
        case_id = self._resolve_case_id()
        if not case_id:
            self.logger.error(
                "%s: no case_id available — cannot commit ledger entry",
                self.name,
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

        if carries_no_received_body(activity):
            return self._answer_resend(activity, case_id)

        object_id, semantic_type, payload_snapshot = self._activity_metadata(
            activity, case_id
        )

        # The snapshot is the received body as it arrived, so its ``context``
        # is the sender's: absent on an activity that predates the case, such
        # as the Offer(VulnerabilityReport) that opened it.  The entry names
        # its case on the envelope (``case_id``), which is what the commit
        # boundary checks (CLP-07-011).
        _assert_actor_identity(semantic_type, payload_snapshot, activity)

        tree = create_commit_log_entry_tree(
            case_id=case_id,
            object_id=object_id,
            semantic_type=semantic_type,
            payload_snapshot=payload_snapshot,
        )
        result = BTBridge(
            datalayer=cast(CaseOutboxPersistence, self.datalayer),
            sync_port=self._sync_port,
        ).execute_with_setup(tree=tree, actor_id=self.actor_id)
        if result.internal_error:
            # Carry the nested bridge's classification across the hop: a
            # missing sync port (RequireSyncPortNode) or a crash in the commit
            # tree is our fault, so the outer bridge must flag it too rather
            # than let the received verdict read it as a refusal (ADR-0095,
            # #4113).
            raise VultronBTInternalError(
                f"{self.name}: nested ledger commit for case '{case_id}'"
                f" failed: {result.feedback_message}"
            )
        if result.status == Status.SUCCESS:
            self.logger.info(
                "%s: committed log entry '%s' for case '%s'",
                self.name,
                semantic_type,
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
