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
"""Action nodes for SYNC chain reconstruction and log entry creation."""

from __future__ import annotations

import logging
from typing import Any, Literal, cast

import py_trees
from py_trees.common import Status

from vultron.core.behaviors.helpers import DataLayerAction
from vultron.core.models._helpers import _now_utc
from vultron.core.models.case_ledger import HashChainLedgerRecord
from vultron.core.models.case_ledger_entry import VultronCaseLedgerEntry
from vultron.core.models.protocols import is_log_entry_model
from vultron.core.sync_helpers import _reconstruct_tail_hash
from vultron.errors import VultronError

logger = logging.getLogger(__name__)


def _require_log_entry(
    activity: Any, node_name: str
) -> VultronCaseLedgerEntry:
    entry = getattr(activity, "log_entry", None)
    if entry is None:
        entry = getattr(activity, "object_", None)
    if is_log_entry_model(entry):
        if isinstance(entry, VultronCaseLedgerEntry):
            return entry
        return VultronCaseLedgerEntry.model_validate(
            entry.model_dump(mode="json")
        )
    raise VultronError(
        f"{node_name}: activity did not carry a VultronCaseLedgerEntry"
    )


def _require_case_id_from_activity(activity: Any, node_name: str) -> str:
    entry = getattr(activity, "log_entry", None)
    if entry is None:
        entry = getattr(activity, "rejected_entry", None)
    if entry is None:
        entry = getattr(activity, "object_", None)
    if is_log_entry_model(entry):
        return entry.case_id
    raise VultronError(f"{node_name}: could not resolve case_id from activity")


def _to_persistable_entry(
    chain_entry: HashChainLedgerRecord,
) -> VultronCaseLedgerEntry:
    return VultronCaseLedgerEntry(
        case_id=chain_entry.case_id,
        log_index=chain_entry.log_index,
        disposition=chain_entry.disposition,
        term=chain_entry.term,
        log_object_id=chain_entry.object_id,
        event_type=chain_entry.event_type,
        payload_snapshot=dict(chain_entry.payload_snapshot),
        prev_log_hash=chain_entry.prev_log_hash,
        entry_hash=chain_entry.entry_hash,
        reason_code=chain_entry.reason_code,
        reason_detail=chain_entry.reason_detail,
    )


class ReconstructChainTailNode(DataLayerAction):
    def __init__(
        self, case_id: str | None = None, name: str | None = None
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self._case_id = case_id

    def setup(self, **kwargs: Any) -> None:
        super().setup(**kwargs)
        self.blackboard.register_key(
            key="tail_hash", access=py_trees.common.Access.WRITE
        )
        self.blackboard.register_key(
            key="tail_index", access=py_trees.common.Access.WRITE
        )
        if self._case_id is None:
            self.blackboard.register_key(
                key="activity", access=py_trees.common.Access.READ
            )

    def update(self) -> Status:
        if self.datalayer is None:
            self.logger.error("%s: DataLayer not available", self.name)
            return Status.FAILURE

        if self._case_id is not None:
            case_id = self._case_id
        else:
            case_id = _require_case_id_from_activity(
                self.blackboard.activity, self.name
            )

        tail_hash, tail_index = _reconstruct_tail_hash(case_id, self.datalayer)
        self.blackboard.tail_hash = tail_hash
        self.blackboard.tail_index = tail_index
        self.logger.debug(
            "%s: reconstructed case '%s' tail hash %.16s… at index %d",
            self.name,
            case_id,
            tail_hash,
            tail_index,
        )
        return Status.SUCCESS


class UpdateReplicationStateNode(DataLayerAction):
    def setup(self, **kwargs: Any) -> None:
        super().setup(**kwargs)
        self.blackboard.register_key(
            key="activity", access=py_trees.common.Access.READ
        )

    def update(self) -> Status:
        if self.datalayer is None:
            self.logger.error("%s: DataLayer not available", self.name)
            return Status.FAILURE

        from vultron.core.models.replication_state import (
            VultronReplicationState,
        )

        activity = self.blackboard.activity
        entry = getattr(activity, "rejected_entry", None)
        if entry is None:
            entry = getattr(activity, "object_", None)
        if not is_log_entry_model(entry):
            raise VultronError(
                f"{self.name}: activity did not carry a VultronCaseLedgerEntry"
            )

        if isinstance(entry, VultronCaseLedgerEntry):
            rejected_entry = entry
        else:
            rejected_entry = VultronCaseLedgerEntry.model_validate(
                entry.model_dump(mode="json")
            )

        peer_id = activity.actor_id
        if not peer_id:
            raise VultronError(
                f"{self.name}: Reject(CaseLedgerEntry) missing peer actor_id"
            )

        state = VultronReplicationState(
            case_id=rejected_entry.case_id,
            peer_id=peer_id,
            last_acknowledged_hash=activity.last_accepted_hash,
        )
        existing = self.datalayer.read(state.id_)
        if existing is not None:
            existing_state = cast(VultronReplicationState, existing)
            existing_state.last_acknowledged_hash = activity.last_accepted_hash
            existing_state.updated_at = _now_utc()
            self.datalayer.save(existing_state)
        else:
            self.datalayer.save(state)
        return Status.SUCCESS


class CreateLogEntryNode(DataLayerAction):
    def __init__(
        self,
        case_id: str,
        object_id: str,
        event_type: str,
        *,
        payload_snapshot: dict[str, Any] | None = None,
        term: int | None = None,
        reason_code: str | None = None,
        reason_detail: str | None = None,
        disposition: Literal["recorded", "rejected"] = "recorded",
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.case_id = case_id
        self.object_id = object_id
        self.event_type = event_type
        self.payload_snapshot = payload_snapshot or {}
        self.term = term
        self.reason_code = reason_code
        self.reason_detail = reason_detail
        self.disposition: Literal["recorded", "rejected"] = disposition

    def setup(self, **kwargs: Any) -> None:
        super().setup(**kwargs)
        self.blackboard.register_key(
            key="tail_hash", access=py_trees.common.Access.READ
        )
        self.blackboard.register_key(
            key="tail_index", access=py_trees.common.Access.READ
        )
        self.blackboard.register_key(
            key="log_entry", access=py_trees.common.Access.WRITE
        )

    def update(self) -> Status:
        tail_hash = self.blackboard.tail_hash
        tail_index = self.blackboard.tail_index
        chain_entry = HashChainLedgerRecord(
            case_id=self.case_id,
            log_index=tail_index + 1,
            object_id=self.object_id,
            event_type=self.event_type,
            disposition=self.disposition,
            payload_snapshot=self.payload_snapshot,
            prev_log_hash=tail_hash,
            term=self.term,
            reason_code=self.reason_code,
            reason_detail=self.reason_detail,
        )
        self.blackboard.log_entry = _to_persistable_entry(chain_entry)
        return Status.SUCCESS


class PersistLogEntryNode(DataLayerAction):
    def setup(self, **kwargs: Any) -> None:
        super().setup(**kwargs)
        self.blackboard.register_key(
            key="log_entry", access=py_trees.common.Access.READ
        )

    def update(self) -> Status:
        if self.datalayer is None:
            self.logger.error("%s: DataLayer not available", self.name)
            return Status.FAILURE

        entry = cast(VultronCaseLedgerEntry, self.blackboard.log_entry)
        self.datalayer.save(entry)
        self.logger.info(
            "%s: committed log entry '%s' for case '%s'",
            self.name,
            entry.id_,
            entry.case_id,
        )
        return Status.SUCCESS
