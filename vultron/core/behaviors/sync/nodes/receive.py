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
"""Action nodes for SYNC log-replication receive workflows."""

from __future__ import annotations

import logging
from typing import Any, cast

import py_trees
from py_trees.common import Status

from vultron.core.behaviors.helpers import DataLayerAction, DataLayerCondition
from vultron.core.models.case_ledger_entry import VultronCaseLedgerEntry
from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.models.ledger_gap_buffer import LedgerGapBuffer
from vultron.core.ports.sync_activity import SyncActivityPort
from vultron.errors import VultronError

logger = logging.getLogger(__name__)


def _require_log_entry(
    activity: Any, node_name: str
) -> VultronCaseLedgerEntry:
    entry = getattr(activity, "log_entry", None)
    if entry is None:
        entry = getattr(activity, "object_", None)
    if isinstance(entry, CaseLedgerEntry):
        if isinstance(entry, VultronCaseLedgerEntry):
            return entry
        return VultronCaseLedgerEntry.model_validate(
            entry.model_dump(mode="json")
        )
    raise VultronError(
        f"{node_name}: activity did not carry a VultronCaseLedgerEntry"
    )


class LogDeliveryConfirmationNode(DataLayerAction):
    def setup(self, **kwargs: Any) -> None:
        super().setup(**kwargs)
        self.blackboard.register_key(
            key="activity", access=py_trees.common.Access.READ
        )

    def update(self) -> Status:
        entry = _require_log_entry(self.blackboard.activity, self.name)
        self.logger.debug(
            "%s: received round-trip delivery confirmation for log entry '%s'",
            self.name,
            entry.id_,
        )
        return Status.SUCCESS


class PersistReceivedLogEntryNode(DataLayerAction):
    def setup(self, **kwargs: Any) -> None:
        super().setup(**kwargs)
        self.blackboard.register_key(
            key="activity", access=py_trees.common.Access.READ
        )

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None
        entry = _require_log_entry(self.blackboard.activity, self.name)
        self.datalayer.save(entry)
        self.logger.info(
            "%s: stored received log entry '%s' for case '%s'",
            self.name,
            entry.id_,
            entry.case_id,
        )
        return Status.SUCCESS


class CheckHashMatchesNode(DataLayerCondition):
    def setup(self, **kwargs: Any) -> None:
        super().setup(**kwargs)
        self.blackboard.register_key(
            key="activity", access=py_trees.common.Access.READ
        )
        self.blackboard.register_key(
            key="tail_hash", access=py_trees.common.Access.READ
        )

    def update(self) -> Status:
        entry = _require_log_entry(self.blackboard.activity, self.name)
        tail_hash = self.blackboard.tail_hash
        if entry.prev_log_hash == tail_hash:
            return Status.SUCCESS
        return Status.FAILURE


class BufferOutOfOrderEntryNode(DataLayerAction):
    """Hold a forward-gap ledger entry so it is not permanently dropped.

    When a received entry's ``prev_log_hash`` does not match the local tail
    *and* the entry sits ahead of the tail (``log_index > tail_index + 1``),
    it is a genuine forward gap: a predecessor has not yet been delivered.
    Because delivery is not ordered (and Vultron may not be the only
    implementation on the wire), dropping such an entry can lose it
    permanently.  This node parks the entry in the actor-local
    :class:`~vultron.core.models.ledger_gap_buffer.LedgerGapBuffer` keyed by its
    ``prev_log_hash`` so the receive path can drain it once its predecessor
    arrives (issue #1556, SYNC-10-004).

    Returns SUCCESS when the entry was buffered, FAILURE otherwise (buffering
    disabled, no gap buffer injected, a stale/duplicate entry at-or-behind the
    tail, or the size bound dropped it).  Its status only structures the
    enclosing tree — a ``Reject(CaseLedgerEntry)`` is sent on **every** mismatch
    regardless of whether buffering succeeded, so the CaseActor's replay remains
    the backstop against a predecessor that is genuinely lost (never delivered)
    rather than merely reordered.  The entry is deliberately NOT persisted here;
    the drain applies effects before persisting, honouring SYNC-12-001.
    """

    def __init__(self, name: str | None = None) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self._gap_buffer: LedgerGapBuffer | None = None

    def setup(self, **kwargs: Any) -> None:
        super().setup(**kwargs)
        self.blackboard.register_key(
            key="activity", access=py_trees.common.Access.READ
        )
        self.blackboard.register_key(
            key="tail_index", access=py_trees.common.Access.READ
        )
        self.blackboard.register_key(
            key="gap_buffer", access=py_trees.common.Access.READ
        )

    def initialise(self) -> None:
        super().initialise()
        try:
            self._gap_buffer = cast(
                LedgerGapBuffer, self.blackboard.gap_buffer
            )
        except (AttributeError, KeyError):
            self._gap_buffer = None

    def update(self) -> Status:
        if self._gap_buffer is None:
            return Status.FAILURE

        entry = _require_log_entry(self.blackboard.activity, self.name)
        try:
            tail_index = cast(int, self.blackboard.tail_index)
        except (AttributeError, KeyError):
            return Status.FAILURE

        # Only buffer genuine *forward* gaps.  An entry at or behind the tail
        # index is stale, a duplicate, or a fork — not a reorder we can heal by
        # waiting, so let it fall through to the rejection path.
        if entry.log_index <= tail_index + 1:
            self.logger.debug(
                "%s: entry index=%d is not a forward gap (tail_index=%d) — "
                "not buffering",
                self.name,
                entry.log_index,
                tail_index,
            )
            return Status.FAILURE

        if self._gap_buffer.buffer(entry):
            self.logger.info(
                "%s: buffered out-of-order entry '%s' (index=%d) pending "
                "predecessor",
                self.name,
                entry.id_,
                entry.log_index,
            )
            return Status.SUCCESS
        return Status.FAILURE


class SendRejectLogEntryNode(DataLayerAction):
    def __init__(self, name: str | None = None) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self._sync_port: SyncActivityPort | None = None

    def setup(self, **kwargs: Any) -> None:
        super().setup(**kwargs)
        self.blackboard.register_key(
            key="activity", access=py_trees.common.Access.READ
        )
        self.blackboard.register_key(
            key="tail_hash", access=py_trees.common.Access.READ
        )
        self.blackboard.register_key(
            key="sync_port", access=py_trees.common.Access.READ
        )

    def initialise(self) -> None:
        super().initialise()
        try:
            self._sync_port = cast(SyncActivityPort, self.blackboard.sync_port)
        except (AttributeError, KeyError):
            self._sync_port = None

    def update(self) -> Status:
        if self.actor_id is None:
            self.logger.error("%s: actor_id not available", self.name)
            return Status.FAILURE

        entry = _require_log_entry(self.blackboard.activity, self.name)
        tail_hash = self.blackboard.tail_hash

        sender_id = getattr(self.blackboard.activity, "actor_id", None)
        if self._sync_port is None:
            raise VultronError(
                f"{self.name}: sync_port must be injected to send rejection"
            )
        if not sender_id:
            raise VultronError(
                f"{self.name}: activity.actor_id missing for rejection target"
            )

        self.logger.warning(
            "%s: log entry '%s' prev_log_hash %.16s… does not match local tail "
            "%.16s…; sending Reject(CaseLedgerEntry)",
            self.name,
            entry.id_,
            entry.prev_log_hash,
            tail_hash,
        )
        self._sync_port.send_reject_log_entry(
            entry=entry,
            tail_hash=tail_hash,
            actor_id=self.actor_id,
            to=[sender_id],
        )
        return Status.FAILURE


class CheckHashOrRejectOnMismatchNode(py_trees.composites.Selector):
    """Accept a chain-extending entry, or buffer-and-reject a mismatch.

    Structure::

        Selector(CheckHashOrRejectOnMismatch)
          CheckHashMatches                      ← SUCCESS: entry extends tail
          Sequence(BufferAndReject)
            FailureIsSuccess(BufferOutOfOrderEntry)  ← buffer forward gaps; the
                                                        wrapper lets the reject
                                                        fire whether or not the
                                                        entry was buffered
            SendRejectLogEntry                  ← FAILURE: reject sent, entry
                                                  not persisted this pass

    When the hash matches, the Selector short-circuits SUCCESS and the parent
    Sequence proceeds to apply effects and persist.  On a mismatch, the entry
    is buffered when it is a genuine forward gap (so it is not permanently
    dropped) and a ``Reject(CaseLedgerEntry)`` is always sent as the loss
    backstop; the Selector then returns FAILURE so ``PersistReceivedLogEntry``
    does not run for the out-of-order entry (issue #1556, SYNC-10-004).
    """

    def __init__(self, name: str | None = None) -> None:
        super().__init__(
            name=name or self.__class__.__name__,
            memory=False,
            children=[
                CheckHashMatchesNode(name="CheckHashMatches"),
                py_trees.composites.Sequence(
                    name="BufferAndReject",
                    memory=False,
                    children=[
                        py_trees.decorators.FailureIsSuccess(
                            name="BufferIfForwardGap",
                            child=BufferOutOfOrderEntryNode(
                                name="BufferOutOfOrderEntry"
                            ),
                        ),
                        SendRejectLogEntryNode(name="SendRejectLogEntry"),
                    ],
                ),
            ],
        )
