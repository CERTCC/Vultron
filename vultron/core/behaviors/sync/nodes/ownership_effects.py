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

"""Ownership-transfer side-effect node for Announce(CaseLedgerEntry) processing.

Provides :class:`ApplyOwnershipTransferFromLedgerNode`, which updates the
local ``VulnerabilityCase.attributed_to`` field when a participant receives an
``accept_case_ownership_transfer`` ledger entry (CM-21-007, SYNC-02-002).
"""

from __future__ import annotations

import logging

from py_trees.common import Status
from py_trees.ports import NoDataAvailable, PortInformation

from vultron.core.behaviors.helpers import DataLayerActionWithPorts
from vultron.core.behaviors.sync.nodes._helpers import _extract_id_from_field
from vultron.core.models._helpers import _as_id

logger = logging.getLogger(__name__)


class ApplyOwnershipTransferFromLedgerNode(DataLayerActionWithPorts):
    """Apply an ``accept_case_ownership_transfer`` ledger entry to the local case replica.

    When a non-CaseActor participant receives ``Announce(CaseLedgerEntry)``
    and the entry's ``event_type`` is ``accept_case_ownership_transfer``, this
    node extracts the new owner actor ID from ``payload_snapshot["actor"]``
    and updates ``VulnerabilityCase.attributed_to`` on the local DataLayer
    replica (CM-21-007).

    This is the fan-out counterpart of the CaseActor's
    ``AcceptCaseOwnershipTransferNode`` effect: both paths MUST converge on the
    same ``attributed_to`` value on every replica (CM-21-002, CM-21-004).

    Lenient on missing data: if the case replica is absent, the new owner ID
    cannot be extracted, or the case already has the correct owner, the node
    returns SUCCESS to avoid blocking the ``Announce`` processing flow.

    Per specs/case-management.yaml CM-21-002, CM-21-007,
    specs/sync-ledger-replication.yaml SYNC-02-002.
    """

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
        try:
            self.activity = self.get_input("activity")
        except (NoDataAvailable, NotImplementedError):
            self.activity = None

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None

        from vultron.core.behaviors.sync.nodes.conditions import (
            _require_log_entry,
        )

        entry = _require_log_entry(self.activity, self.name)
        snapshot = entry.payload_snapshot
        case_id = entry.case_id

        new_owner_id = _extract_id_from_field(snapshot.get("actor"))
        if not new_owner_id or not case_id:
            self.logger.debug(
                "%s: payload_snapshot missing 'actor' id or case_id"
                " — skipping ownership-transfer apply (non-fatal)",
                self.name,
            )
            return Status.SUCCESS

        case = self._resolve_case_replica(case_id)
        if case is None:
            return Status.SUCCESS  # Regime 2 (ADR-0087): partial replica, skip

        current_owner = _as_id(case.attributed_to)
        if current_owner == new_owner_id:
            self.logger.debug(
                "%s: case '%s' already attributed to '%s' — idempotent no-op",
                self.name,
                case_id,
                new_owner_id,
            )
            return Status.SUCCESS

        case.attributed_to = new_owner_id  # type: ignore[assignment]
        self.datalayer.save_many(
            [case]
        )  # CM-21-004, BTND-06-008: attributed_to must use save_many
        self.logger.info(
            "%s: applied ledger ownership-transfer — case '%s' attributed_to"
            " updated to '%s' (CM-21-002, CM-21-007, SYNC-02-002)",
            self.name,
            case_id,
            new_owner_id,
        )
        return Status.SUCCESS
