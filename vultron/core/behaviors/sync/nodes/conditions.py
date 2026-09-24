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
from vultron.core.participants.authority import resolve_case_manager_id
from vultron.core.sync_helpers import is_ledger_fresh_for_case
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


class VerifySenderIsOwnIdNode(DataLayerConditionWithPorts):
    INPUT_PORTS: dict[str, PortInformation] = {
        **DataLayerConditionWithPorts.INPUT_PORTS,
        "activity": PortInformation(data_type=object, required=True),
        "case_actor_id": PortInformation(data_type=str, required=True),
    }

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


class VerifySenderIsCaseActorNode(DataLayerConditionWithPorts):
    """Reject announces whose sender is not the case's CaseActor (CASE_MANAGER).

    Resolves the case's authoritative CaseActor by the ``CVDRole.CASE_MANAGER``
    role (ADR-0088, via :func:`resolve_case_manager_id`) — the same neutral
    resolver the tree's routing node :class:`CheckIsCaseManagerNode` uses, never
    a URL shape or a per-case ``Service`` object — and returns SUCCESS only when
    the announce ``actor_id`` equals that resolved CaseActor id.

    Passes through (SUCCESS) during the bootstrap window — the case replica is
    not seeded yet, or no CASE_MANAGER is known for it yet — so downstream
    reject-on-missing-case / pre-genesis buffering (SYNC-15-001, SYNC-15-004)
    handles the entry rather than this gate dropping it before those paths run.
    Once the replica embeds the CASE_MANAGER participant (CP-09-004) the sender
    is enforced.

    Per specs/case-ledger-processing.yaml CLP-01-003; SYNC-13-006.
    """

    INPUT_PORTS: dict[str, PortInformation] = {
        **DataLayerConditionWithPorts.INPUT_PORTS,
        "activity": PortInformation(data_type=object, required=True),
    }

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

        try:
            entry = _require_log_entry(self.activity, self.name)
        except VultronError as exc:
            self.logger.error("%s: %s", self.name, exc)
            return Status.FAILURE

        case_id = entry.case_id
        sender_id = getattr(self.activity, "actor_id", None)

        if not sender_id:
            self.logger.warning("%s: announce has no actor_id", self.name)
            return Status.FAILURE

        # Lenient read: an unseeded replica is the bootstrap window, not an
        # error here (unlike the Regime 1 _require_case used by routing nodes),
        # so a missing case must pass through rather than FAIL and starve the
        # downstream buffer/reject paths.
        case = self.datalayer.read_case(case_id)
        case_actor_id = (
            resolve_case_manager_id(case, self.datalayer)
            if case is not None
            else None
        )

        if case_actor_id is None:
            self.logger.debug(
                "%s: no CaseActor known for case '%s'"
                " — passing through for bootstrap handling",
                self.name,
                case_id,
            )
            return Status.SUCCESS

        if sender_id == case_actor_id:
            self.logger.debug(
                "%s: sender '%s' matches CaseActor for case '%s'",
                self.name,
                sender_id,
                case_id,
            )
            return Status.SUCCESS

        self.logger.warning(
            "%s: rejected announce from '%s' for case '%s' (expected '%s')",
            self.name,
            sender_id,
            case_id,
            case_actor_id,
        )
        return Status.FAILURE


class CheckLedgerEntryAlreadyStoredNode(DataLayerConditionWithPorts):
    INPUT_PORTS: dict[str, PortInformation] = {
        **DataLayerConditionWithPorts.INPUT_PORTS,
        "activity": PortInformation(data_type=object, required=True),
    }

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

    INPUT_PORTS: dict[str, PortInformation] = {
        **DataLayerConditionWithPorts.INPUT_PORTS,
        "case_id": PortInformation(data_type=str, required=False),
    }

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
