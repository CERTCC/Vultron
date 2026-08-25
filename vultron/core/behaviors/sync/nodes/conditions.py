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

from py_trees.common import Status
from py_trees.ports import NoDataAvailable

from vultron.core.behaviors.helpers import (
    DataLayerConditionWithPorts,
    PortInformation,
)
from vultron.core.models.case_ledger_entry import VultronCaseLedgerEntry
from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.sync_helpers import is_ledger_fresh_for_case
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
    if isinstance(entry, CaseLedgerEntry):
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


class CheckIsOwnCaseActorNode(DataLayerConditionWithPorts):
    @classmethod
    def input_ports(cls) -> dict[str, PortInformation]:
        ports = super().input_ports()
        ports["activity"] = PortInformation(data_type=object, required=True)
        return ports

    @classmethod
    def output_ports(cls) -> dict[str, PortInformation]:
        return {"case_actor_id": PortInformation(data_type=str, required=True)}

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {
            "activity": "/activity",
            "case_actor_id": "/case_actor_id",
        }

    def initialise(self) -> None:
        super().initialise()
        self.activity = self.get_input("activity")

    def update(self) -> Status:
        if (f := self._require_datalayer_and_actor()) is not None:
            return f
        assert self.datalayer is not None
        assert self.actor_id is not None
        entry = _require_log_entry(self.activity, self.name)
        case_actor = _find_case_actor(
            self.datalayer, entry.case_id, self.actor_id
        )
        if case_actor is None:
            return Status.FAILURE

        case_actor_id = _require_case_actor_id(case_actor, self.name)
        self._set_output("case_actor_id", case_actor_id)
        self.logger.debug(
            "%s: actor '%s' owns CaseActor '%s' for case '%s'",
            self.name,
            self.actor_id,
            case_actor_id,
            entry.case_id,
        )
        return Status.SUCCESS


class CheckIsNotOwnCaseActorNode(DataLayerConditionWithPorts):
    @classmethod
    def input_ports(cls) -> dict[str, PortInformation]:
        ports = super().input_ports()
        ports["activity"] = PortInformation(data_type=object, required=True)
        return ports

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {"activity": "/activity"}

    def initialise(self) -> None:
        super().initialise()
        self.activity = self.get_input("activity")

    def update(self) -> Status:
        if (f := self._require_datalayer_and_actor()) is not None:
            return f
        assert self.datalayer is not None
        assert self.actor_id is not None

        entry = _require_log_entry(self.activity, self.name)
        case_actor = _find_case_actor(
            self.datalayer, entry.case_id, self.actor_id
        )
        if case_actor is None:
            return Status.SUCCESS
        return Status.FAILURE


class VerifySenderIsOwnIdNode(DataLayerConditionWithPorts):
    @classmethod
    def input_ports(cls) -> dict[str, PortInformation]:
        ports = super().input_ports()
        ports["activity"] = PortInformation(data_type=object, required=True)
        ports["case_actor_id"] = PortInformation(data_type=str, required=True)
        return ports

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {"activity": "/activity", "case_actor_id": "/case_actor_id"}

    def initialise(self) -> None:
        super().initialise()
        self.activity = self.get_input("activity")
        self.case_actor_id = self.get_input("case_actor_id")

    def update(self) -> Status:
        sender_id = getattr(self.activity, "actor_id", None)
        case_actor_id = self.case_actor_id
        if sender_id == case_actor_id:
            return Status.SUCCESS

        self.logger.warning(
            "%s: rejected spoofed announce sender '%s' for CaseActor '%s'",
            self.name,
            sender_id,
            case_actor_id,
        )
        return Status.FAILURE


class CheckLedgerEntryAlreadyStoredNode(DataLayerConditionWithPorts):
    @classmethod
    def input_ports(cls) -> dict[str, PortInformation]:
        ports = super().input_ports()
        ports["activity"] = PortInformation(data_type=object, required=True)
        return ports

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {"activity": "/activity"}

    def initialise(self) -> None:
        super().initialise()
        self.activity = self.get_input("activity")

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None

        entry = _require_log_entry(self.activity, self.name)
        if self.datalayer.read(entry.id_) is None:
            return Status.FAILURE

        self.logger.debug(
            "%s: log entry '%s' already stored", self.name, entry.id_
        )
        return Status.SUCCESS


class CheckLedgerFreshnessNode(DataLayerConditionWithPorts):
    """Gate: return SUCCESS only when the local ledger for *case_id* is fresh.

    "Fresh" means the actor's local ledger entries for the case form a
    contiguous, hash-verified sequence from ``log_index=0``
    (``prev_log_hash == <per-case genesis hash>``) through the actor's highest
    stored entry.  The actor does **not** need to be at the CaseActor's current
    tip — lagging is permitted so long as the local prefix has no gaps.

    An empty local ledger is trivially fresh (the acknowledged prefix is the
    empty prefix).

    When the gate fails (not fresh), a WARNING is emitted that includes the
    staleness reason, surfacing the explicit stale-or-catching-up condition
    required by SYNC-10-002.  This FAILURE result blocks or defers any
    protocol-significant case action that depends on ledger freshness per
    SYNC-10-001.

    Constructor args:
        case_id: URI of the case whose ledger to check.  If ``None``, the
            node reads ``case_id`` from the blackboard key ``"case_id"``.

    Spec: SYNC-10-001, SYNC-10-002, SYNC-10-003, SYNC-10-004, SYNC-10-005.
    """

    def __init__(
        self, case_id: str | None = None, name: str | None = None
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self._case_id = case_id

    @classmethod
    def input_ports(cls) -> dict[str, PortInformation]:
        ports = super().input_ports()
        ports["case_id"] = PortInformation(data_type=str, required=False)
        return ports

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {"case_id": "/case_id"}

    def initialise(self) -> None:
        super().initialise()
        self._case_id_bb: str | None = None
        if self._case_id is None:
            try:
                self._case_id_bb = self.get_input("case_id")
            except (NoDataAvailable, NotImplementedError):
                self._case_id_bb = None

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None

        case_id: str | None
        if self._case_id is not None:
            case_id = self._case_id
        else:
            case_id = self._case_id_bb
            if case_id is None:
                self.logger.error(
                    "%s: case_id not on blackboard and not provided at "
                    "construction",
                    self.name,
                )
                return Status.FAILURE

        fresh, reason = is_ledger_fresh_for_case(case_id, self.datalayer)
        if not fresh:
            self.logger.warning(
                "%s: ledger NOT fresh for case '%s' — stale-or-catching-up: %s",
                self.name,
                case_id,
                reason,
            )
            return Status.FAILURE

        self.logger.debug("%s: ledger fresh for case '%s'", self.name, case_id)
        return Status.SUCCESS
