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
"""Action nodes for SYNC log-replication replay and fan-out workflows."""

from __future__ import annotations

import logging
from typing import Any, cast

import py_trees
from py_trees.common import Status

from vultron.core.behaviors.helpers import DataLayerAction
from vultron.core.models.case_log_entry import VultronCaseLogEntry
from vultron.core.models.protocols import (
    LogEntryModel,
    is_case_model,
    is_log_entry_model,
)
from vultron.core.ports.sync_activity import SyncActivityPort
from vultron.core.use_cases._helpers import case_addressees
from vultron.errors import VultronError

logger = logging.getLogger(__name__)


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


def _find_case_actor(
    dl: Any, case_id: str, owner_actor_id: str | None = None
) -> object | None:
    fallback: object | None = None
    for service in dl.list_objects("Service"):
        if fallback is None:
            fallback = cast(object, service)
        if getattr(service, "context", None) != case_id:
            continue
        if owner_actor_id is None:
            return cast(object, service)
        if getattr(service, "attributed_to", None) == owner_actor_id:
            return cast(object, service)
    return fallback


def _require_case_actor_id(case_actor: object, node_name: str) -> str:
    case_actor_id = getattr(case_actor, "id_", None)
    if isinstance(case_actor_id, str):
        return case_actor_id
    raise VultronError(f"{node_name}: resolved CaseActor had no id_")


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


class CollectAndSortCaseLogEntriesNode(DataLayerAction):
    def setup(self, **kwargs: Any) -> None:
        super().setup(**kwargs)
        self.blackboard.register_key(
            key="activity", access=py_trees.common.Access.READ
        )
        self.blackboard.register_key(
            key="replay_entry", access=py_trees.common.Access.WRITE
        )
        self.blackboard.register_key(
            key="replay_peer_id", access=py_trees.common.Access.WRITE
        )
        self.blackboard.register_key(
            key="replay_case_log_entries",
            access=py_trees.common.Access.WRITE,
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

        entries: list[LogEntryModel] = [
            obj
            for obj in self.datalayer.list_objects("CaseLogEntry")
            if is_log_entry_model(obj) and obj.case_id == entry.case_id
        ]
        entries.sort(key=lambda log_entry: log_entry.log_index)

        self.blackboard.replay_entry = entry
        self.blackboard.replay_peer_id = peer_id
        self.blackboard.replay_case_log_entries = entries
        return Status.SUCCESS


class FindDivergenceIndexNode(DataLayerAction):
    def setup(self, **kwargs: Any) -> None:
        super().setup(**kwargs)
        self.blackboard.register_key(
            key="activity", access=py_trees.common.Access.READ
        )
        self.blackboard.register_key(
            key="replay_case_log_entries",
            access=py_trees.common.Access.READ,
        )
        self.blackboard.register_key(
            key="replay_from_index", access=py_trees.common.Access.WRITE
        )

    def update(self) -> Status:
        entries = cast(
            list[LogEntryModel], self.blackboard.replay_case_log_entries
        )
        from_hash = self.blackboard.activity.last_accepted_hash
        from_index = -1
        for log_entry in entries:
            if log_entry.entry_hash == from_hash:
                from_index = log_entry.log_index
                break

        self.blackboard.replay_from_index = from_index
        return Status.SUCCESS


class SendMissingEntriesNode(DataLayerAction):
    def __init__(self, name: str | None = None) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self._sync_port: SyncActivityPort | None = None

    def setup(self, **kwargs: Any) -> None:
        super().setup(**kwargs)
        self.blackboard.register_key(
            key="case_actor_id", access=py_trees.common.Access.READ
        )
        self.blackboard.register_key(
            key="replay_entry", access=py_trees.common.Access.READ
        )
        self.blackboard.register_key(
            key="replay_peer_id", access=py_trees.common.Access.READ
        )
        self.blackboard.register_key(
            key="replay_case_log_entries",
            access=py_trees.common.Access.READ,
        )
        self.blackboard.register_key(
            key="replay_from_index", access=py_trees.common.Access.READ
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

        entry = cast(VultronCaseLogEntry, self.blackboard.replay_entry)
        peer_id = cast(str, self.blackboard.replay_peer_id)
        entries = cast(
            list[LogEntryModel], self.blackboard.replay_case_log_entries
        )
        from_index = cast(int, self.blackboard.replay_from_index)

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


class ReplayMissingEntriesNode(py_trees.composites.Sequence):
    def __init__(self, name: str | None = None) -> None:
        super().__init__(
            name=name or self.__class__.__name__,
            memory=False,
            children=[
                CollectAndSortCaseLogEntriesNode(
                    name="CollectAndSortCaseLogEntries"
                ),
                FindDivergenceIndexNode(name="FindDivergenceIndex"),
                SendMissingEntriesNode(name="SendMissingEntries"),
            ],
        )


class CollectLogEntryRecipientsNode(DataLayerAction):
    def __init__(self, case_id: str, name: str | None = None) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.case_id = case_id

    def setup(self, **kwargs: Any) -> None:
        super().setup(**kwargs)
        self.blackboard.register_key(
            key="log_entry", access=py_trees.common.Access.READ
        )
        self.blackboard.register_key(
            key="fanout_recipients", access=py_trees.common.Access.WRITE
        )

    def update(self) -> Status:
        if self.datalayer is None or self.actor_id is None:
            self.logger.error(
                "%s: DataLayer or actor_id not available", self.name
            )
            return Status.FAILURE

        entry = cast(VultronCaseLogEntry, self.blackboard.log_entry)
        case_obj = self.datalayer.read(self.case_id)
        if not is_case_model(case_obj):
            self.logger.warning(
                "%s: case '%s' not found; skipping fan-out for '%s'",
                self.name,
                self.case_id,
                entry.id_,
            )
            self.blackboard.fanout_recipients = []
            return Status.SUCCESS

        recipients = case_addressees(
            case_obj, excluding_actor_id=self.actor_id
        )
        self.blackboard.fanout_recipients = recipients
        return Status.SUCCESS


class SendLogEntryToEachNode(DataLayerAction):
    def __init__(self, name: str | None = None) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self._sync_port: SyncActivityPort | None = None

    def setup(self, **kwargs: Any) -> None:
        super().setup(**kwargs)
        self.blackboard.register_key(
            key="log_entry", access=py_trees.common.Access.READ
        )
        self.blackboard.register_key(
            key="fanout_recipients", access=py_trees.common.Access.READ
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

        entry = cast(VultronCaseLogEntry, self.blackboard.log_entry)
        recipients = cast(list[str], self.blackboard.fanout_recipients)
        if self._sync_port is None:
            self.logger.debug(
                "%s: sync_port not injected; skipping fan-out for '%s'",
                self.name,
                entry.id_,
            )
            return Status.SUCCESS

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


class FanOutLogEntryNode(py_trees.composites.Sequence):
    def __init__(self, case_id: str, name: str | None = None) -> None:
        super().__init__(
            name=name or self.__class__.__name__,
            memory=False,
            children=[
                CollectLogEntryRecipientsNode(
                    case_id=case_id,
                    name="CollectLogEntryRecipients",
                ),
                SendLogEntryToEachNode(name="SendLogEntryToEach"),
            ],
        )
