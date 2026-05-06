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
"""Behavior tree nodes for SYNC log-replication workflows."""

from __future__ import annotations

import logging
from typing import Any, Literal, cast

import py_trees
from py_trees.common import Status

from vultron.core.behaviors.helpers import DataLayerAction, DataLayerCondition
from vultron.core.models._helpers import _now_utc
from vultron.core.models.case_log import CaseLogEntry
from vultron.core.models.case_log_entry import VultronCaseLogEntry
from vultron.core.models.protocols import (
    LogEntryModel,
    is_case_model,
    is_log_entry_model,
)
from vultron.core.models.replication_state import VultronReplicationState
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.ports.sync_activity import SyncActivityPort
from vultron.core.sync_helpers import _reconstruct_tail_hash
from vultron.core.use_cases._helpers import case_addressees
from vultron.errors import VultronError

logger = logging.getLogger(__name__)


def _to_persistable_entry(chain_entry: CaseLogEntry) -> VultronCaseLogEntry:
    return VultronCaseLogEntry(
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


def _find_case_actor(
    dl: CasePersistence, case_id: str, owner_actor_id: str | None = None
) -> object | None:
    fallback: object | None = None
    for service in dl.list_objects("Service"):
        if fallback is None:
            fallback = service
        if getattr(service, "context", None) != case_id:
            continue
        if owner_actor_id is None:
            return service
        if getattr(service, "attributed_to", None) == owner_actor_id:
            return service
    if owner_actor_id is None:
        return fallback
    return None


def _require_log_entry(activity: Any, node_name: str) -> VultronCaseLogEntry:
    entry = getattr(activity, "log_entry", None)
    if entry is None:
        entry = getattr(activity, "object_", None)
    if is_log_entry_model(entry):
        if isinstance(entry, VultronCaseLogEntry):
            return entry
        return VultronCaseLogEntry.model_validate(
            entry.model_dump(mode="json")
        )
    raise VultronError(
        f"{node_name}: activity did not carry a VultronCaseLogEntry"
    )


def _require_rejected_entry(
    activity: Any, node_name: str
) -> VultronCaseLogEntry:
    entry = getattr(activity, "rejected_entry", None)
    if entry is None:
        entry = getattr(activity, "object_", None)
    if is_log_entry_model(entry):
        if isinstance(entry, VultronCaseLogEntry):
            return entry
        return VultronCaseLogEntry.model_validate(
            entry.model_dump(mode="json")
        )
    raise VultronError(
        f"{node_name}: activity did not carry a rejected VultronCaseLogEntry"
    )


def _require_case_actor_id(case_actor: object, node_name: str) -> str:
    case_actor_id = getattr(case_actor, "id_", None)
    if isinstance(case_actor_id, str):
        return case_actor_id
    raise VultronError(f"{node_name}: resolved CaseActor had no id_")


def _require_case_id_from_activity(activity: Any, node_name: str) -> str:
    entry = getattr(activity, "log_entry", None)
    if entry is None:
        entry = getattr(activity, "rejected_entry", None)
    if entry is None:
        entry = getattr(activity, "object_", None)
    if is_log_entry_model(entry):
        return entry.case_id
    raise VultronError(f"{node_name}: could not resolve case_id from activity")


class CheckIsOwnCaseActorNode(DataLayerCondition):
    def setup(self, **kwargs: Any) -> None:
        super().setup(**kwargs)
        self.blackboard.register_key(
            key="activity", access=py_trees.common.Access.READ
        )
        self.blackboard.register_key(
            key="case_actor_id", access=py_trees.common.Access.WRITE
        )

    def update(self) -> Status:
        if self.datalayer is None or self.actor_id is None:
            self.logger.error(
                "%s: DataLayer or actor_id not available", self.name
            )
            return Status.FAILURE

        entry = _require_log_entry(self.blackboard.activity, self.name)
        case_actor = _find_case_actor(
            self.datalayer, entry.case_id, self.actor_id
        )
        if case_actor is None:
            return Status.FAILURE

        case_actor_id = _require_case_actor_id(case_actor, self.name)
        self.blackboard.case_actor_id = case_actor_id
        self.logger.debug(
            "%s: actor '%s' owns CaseActor '%s' for case '%s'",
            self.name,
            self.actor_id,
            case_actor_id,
            entry.case_id,
        )
        return Status.SUCCESS


class CheckIsNotOwnCaseActorNode(DataLayerCondition):
    def setup(self, **kwargs: Any) -> None:
        super().setup(**kwargs)
        self.blackboard.register_key(
            key="activity", access=py_trees.common.Access.READ
        )

    def update(self) -> Status:
        if self.datalayer is None or self.actor_id is None:
            self.logger.error(
                "%s: DataLayer or actor_id not available", self.name
            )
            return Status.FAILURE

        entry = _require_log_entry(self.blackboard.activity, self.name)
        case_actor = _find_case_actor(
            self.datalayer, entry.case_id, self.actor_id
        )
        if case_actor is None:
            return Status.SUCCESS
        return Status.FAILURE


class VerifySenderIsOwnIdNode(DataLayerCondition):
    def setup(self, **kwargs: Any) -> None:
        super().setup(**kwargs)
        self.blackboard.register_key(
            key="activity", access=py_trees.common.Access.READ
        )
        self.blackboard.register_key(
            key="case_actor_id", access=py_trees.common.Access.READ
        )

    def update(self) -> Status:
        sender_id = getattr(self.blackboard.activity, "actor_id", None)
        case_actor_id = self.blackboard.case_actor_id
        if sender_id == case_actor_id:
            return Status.SUCCESS

        self.logger.warning(
            "%s: rejected spoofed announce sender '%s' for CaseActor '%s'",
            self.name,
            sender_id,
            case_actor_id,
        )
        return Status.FAILURE


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


class CheckLogEntryAlreadyStoredNode(DataLayerCondition):
    def setup(self, **kwargs: Any) -> None:
        super().setup(**kwargs)
        self.blackboard.register_key(
            key="activity", access=py_trees.common.Access.READ
        )

    def update(self) -> Status:
        if self.datalayer is None:
            self.logger.error("%s: DataLayer not available", self.name)
            return Status.FAILURE

        entry = _require_log_entry(self.blackboard.activity, self.name)
        if self.datalayer.read(entry.id_) is None:
            return Status.FAILURE

        self.logger.debug(
            "%s: log entry '%s' already stored", self.name, entry.id_
        )
        return Status.SUCCESS


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


class CheckHashOrRejectOnMismatchNode(DataLayerAction):
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
        if entry.prev_log_hash == tail_hash:
            return Status.SUCCESS

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
            "%.16s…; sending Reject(CaseLogEntry)",
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


class PersistReceivedLogEntryNode(DataLayerAction):
    def setup(self, **kwargs: Any) -> None:
        super().setup(**kwargs)
        self.blackboard.register_key(
            key="activity", access=py_trees.common.Access.READ
        )

    def update(self) -> Status:
        if self.datalayer is None:
            self.logger.error("%s: DataLayer not available", self.name)
            return Status.FAILURE

        entry = _require_log_entry(self.blackboard.activity, self.name)
        self.datalayer.save(entry)
        self.logger.info(
            "%s: stored received log entry '%s' for case '%s'",
            self.name,
            entry.id_,
            entry.case_id,
        )
        return Status.SUCCESS


class FindCaseActorNode(DataLayerAction):
    def setup(self, **kwargs: Any) -> None:
        super().setup(**kwargs)
        self.blackboard.register_key(
            key="activity", access=py_trees.common.Access.READ
        )
        self.blackboard.register_key(
            key="case_actor_id", access=py_trees.common.Access.WRITE
        )

    def update(self) -> Status:
        if self.datalayer is None:
            self.logger.error("%s: DataLayer not available", self.name)
            return Status.FAILURE

        entry = _require_rejected_entry(self.blackboard.activity, self.name)
        case_actor = _find_case_actor(self.datalayer, entry.case_id)
        if case_actor is None:
            self.logger.warning(
                "%s: no CaseActor found for case '%s'",
                self.name,
                entry.case_id,
            )
            return Status.FAILURE

        self.blackboard.case_actor_id = _require_case_actor_id(
            case_actor, self.name
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

        activity = self.blackboard.activity
        entry = _require_rejected_entry(activity, self.name)
        peer_id = activity.actor_id
        if not peer_id:
            raise VultronError(
                f"{self.name}: Reject(CaseLogEntry) missing peer actor_id"
            )

        state = VultronReplicationState(
            case_id=entry.case_id,
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


class ReplayMissingEntriesNode(DataLayerAction):
    def __init__(self, name: str | None = None) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self._sync_port: SyncActivityPort | None = None

    def setup(self, **kwargs: Any) -> None:
        super().setup(**kwargs)
        self.blackboard.register_key(
            key="activity", access=py_trees.common.Access.READ
        )
        self.blackboard.register_key(
            key="case_actor_id", access=py_trees.common.Access.READ
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
        if self.datalayer is None:
            self.logger.error("%s: DataLayer not available", self.name)
            return Status.FAILURE
        if self._sync_port is None:
            raise VultronError(
                f"{self.name}: sync_port must be injected to replay entries"
            )

        activity = self.blackboard.activity
        entry = _require_rejected_entry(activity, self.name)
        peer_id = activity.actor_id
        if not peer_id:
            raise VultronError(
                f"{self.name}: Reject(CaseLogEntry) missing peer actor_id"
            )

        entries: list[LogEntryModel] = [
            obj
            for obj in self.datalayer.list_objects("CaseLogEntry")
            if is_log_entry_model(obj) and obj.case_id == entry.case_id
        ]
        entries.sort(key=lambda e: e.log_index)

        from_hash = activity.last_accepted_hash
        from_index = -1
        for log_entry in entries:
            if log_entry.entry_hash == from_hash:
                from_index = log_entry.log_index
                break

        replayed = 0
        for log_entry in entries:
            if log_entry.log_index <= from_index:
                continue
            self._sync_port.send_announce_log_entry(
                entry=log_entry,
                actor_id=self.blackboard.case_actor_id,
                to=[peer_id],
            )
            replayed += 1

        self.logger.info(
            "%s: replayed %d entries to peer '%s' for case '%s'",
            self.name,
            replayed,
            peer_id,
            entry.case_id,
        )
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
        chain_entry = CaseLogEntry(
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

        entry = cast(VultronCaseLogEntry, self.blackboard.log_entry)
        self.datalayer.save(entry)
        self.logger.info(
            "%s: committed log entry '%s' for case '%s'",
            self.name,
            entry.id_,
            entry.case_id,
        )
        return Status.SUCCESS


class FanOutLogEntryNode(DataLayerAction):
    def __init__(self, case_id: str, name: str | None = None) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.case_id = case_id
        self._sync_port: SyncActivityPort | None = None

    def setup(self, **kwargs: Any) -> None:
        super().setup(**kwargs)
        self.blackboard.register_key(
            key="log_entry", access=py_trees.common.Access.READ
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
        if self.datalayer is None or self.actor_id is None:
            self.logger.error(
                "%s: DataLayer or actor_id not available", self.name
            )
            return Status.FAILURE

        entry = cast(VultronCaseLogEntry, self.blackboard.log_entry)
        if self._sync_port is None:
            self.logger.debug(
                "%s: sync_port not injected; skipping fan-out for '%s'",
                self.name,
                entry.id_,
            )
            return Status.SUCCESS

        case_obj = self.datalayer.read(self.case_id)
        if not is_case_model(case_obj):
            self.logger.warning(
                "%s: case '%s' not found; skipping fan-out for '%s'",
                self.name,
                self.case_id,
                entry.id_,
            )
            return Status.SUCCESS

        recipients = case_addressees(
            case_obj, excluding_actor_id=self.actor_id
        )
        for recipient_id in recipients:
            self._sync_port.send_announce_log_entry(
                entry=entry,
                actor_id=self.actor_id,
                to=[recipient_id],
            )
        self.logger.info(
            "%s: fanned out log entry '%s' to %d recipients",
            self.name,
            entry.id_,
            len(recipients),
        )
        return Status.SUCCESS
