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
"""Condition nodes for SYNC log-replication workflows."""

from __future__ import annotations

import logging
from typing import Any

import py_trees
from py_trees.common import Status

from vultron.core.behaviors.helpers import DataLayerCondition
from vultron.core.models.case_ledger_entry import VultronCaseLedgerEntry
from vultron.core.models.protocols import is_log_entry_model
from vultron.core.ports.case_persistence import CasePersistence
from vultron.errors import VultronError

logger = logging.getLogger(__name__)


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


def _require_case_actor_id(case_actor: object, node_name: str) -> str:
    case_actor_id = getattr(case_actor, "id_", None)
    if isinstance(case_actor_id, str):
        return case_actor_id
    raise VultronError(f"{node_name}: resolved CaseActor had no id_")


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


class CheckLedgerEntryAlreadyStoredNode(DataLayerCondition):
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


_REMOVE_EMBARGO_EVENT = "remove_embargo_event_from_case"


class IsNotRemoveEmbargoEventNode(DataLayerCondition):
    """Guard: return SUCCESS when this log entry is *not* a remove-embargo event.

    Used as the first child of the ``LogEntryEventEffects`` Selector in
    ``AnnounceLogEntryReceivedBT``.  When the event type does *not* require
    any side-effects (i.e. it is not ``remove_embargo_event_from_case``), the
    Selector short-circuits to SUCCESS without running the teardown branch.
    When the event *is* a remove-embargo event, FAILURE is returned so the
    Selector proceeds to ``ApplyEmbargoTeardownNode``.

    Per specs/behavior-tree-integration.yaml BT-06-001.
    """

    def setup(self, **kwargs: Any) -> None:
        super().setup(**kwargs)
        self.blackboard.register_key(
            key="activity", access=py_trees.common.Access.READ
        )

    def update(self) -> Status:
        entry = _require_log_entry(self.blackboard.activity, self.name)
        if entry.event_type != _REMOVE_EMBARGO_EVENT:
            return Status.SUCCESS
        return Status.FAILURE
