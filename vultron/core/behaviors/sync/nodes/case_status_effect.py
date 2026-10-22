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

"""Ledger replay of ``add_case_status_to_case`` entries (RSH-08-004, AC-2 #3814).

The CASE_MANAGER commits an ``add_case_status_to_case`` entry for the
``Add(CaseStatus)`` it accepts from a participant — the status as received,
which it accepts whole or refuses whole (RSH-09-005) — and for the case-status
snapshot it takes
after each EM or P/X/A change of its own (RSH-04-002, RSH-04-003).  This module
replays the entry on a participant replica, so the replica's
``case.case_statuses`` and ``current_status`` follow the CASE_MANAGER's without
the ``Add(CaseStatus)`` reaching the replica directly (PCR-03-001).

The replica copies the status the entry carries, id, times and every
dimension included (CM-23-016, ADR-0124).  The entry records the
CASE_MANAGER's own ``Add(CaseStatus)``, the status it derived or adopted
(RSH-04-001, RSH-01-003), so the replica does not adjudicate it, and it never
carries its own EM or P/X/A value forward over the entry's: two replicas at
the same ledger position hold the same case statuses.

The status is appended the way the CASE_MANAGER's
``EmitCaseStatusUpdateNode`` appends it, so both stores record the same
object under the same id (ADR-0124).
"""

from __future__ import annotations

import logging
from typing import Any

from py_trees.common import Status

from vultron.core.behaviors.sync.nodes._helpers import (
    _LedgerEffectNode,
)
from vultron.core.behaviors.sync.nodes.event_conditions import (
    _SingleSemanticTypeNode,
)
from vultron.core.models._helpers import _as_id
from vultron.core.models.case_status import CaseStatus
from vultron.core.models.events.base import MessageSemantics
from vultron.core.sync_helpers import case_status_from_snapshot
from vultron.errors import VultronValidationError

logger = logging.getLogger(__name__)

#: Ledger ``semantic_type`` of a case-status entry.
ADD_CASE_STATUS_SEMANTIC_TYPE = MessageSemantics.ADD_CASE_STATUS_TO_CASE.value


class IsAddCaseStatusEventNode(_SingleSemanticTypeNode):
    """Precondition: this entry is an ``add_case_status_to_case`` event.

    Used in the ``CaseStatus`` slot of ``AnnounceLogEntryReceivedBT``.

    Per RSH-08-004, BTND-08-001, SYNC-12-001.
    """

    matched_semantic_type = ADD_CASE_STATUS_SEMANTIC_TYPE


class ApplyCaseStatusFromLedgerNode(_LedgerEffectNode):
    """Append an ``add_case_status_to_case`` entry's CaseStatus to the replica.

    No-ops, each SUCCESS with nothing written:

    * the replica holds no copy of the case (Regime 2, ADR-0087);
    * the status is already in ``case.case_statuses`` — the genesis status a
      seeded replica holds, or a re-delivery (CLP-13-001).

    FAILURE, so the entry is not persisted (SYNC-12-001): the snapshot names
    no status, or carries one that is not a valid ``CaseStatus``.  Persisting
    such an entry would record a transition the replica never applied
    (SYNC-12-002).
    """

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None

        entry = self._get_entry()
        case = self._resolve_case_replica(entry.case_id)
        if case is None:
            return Status.SUCCESS  # Regime 2 (ADR-0087): partial replica

        status = self._reconstruct(entry.payload_snapshot.get("object"))
        if status is None:
            return Status.FAILURE
        if status.id_ in {_as_id(s) for s in case.case_statuses}:
            self.logger.debug(
                "%s: status '%s' already in case '%s' — idempotent no-op",
                self.name,
                status.id_,
                case.id_,
            )
            return Status.SUCCESS

        self.datalayer.save(status)
        case.add_case_status(status)
        self.datalayer.save(case)
        self.logger.info(
            "%s: replayed case status '%s' on case '%s' (em=%s, pxa=%s;"
            " RSH-08-004)",
            self.name,
            status.id_,
            case.id_,
            status.em.state,
            status.pxa.state,
        )
        return Status.SUCCESS

    def _reconstruct(self, status_data: Any) -> CaseStatus | None:
        """Return the entry's CaseStatus, or ``None`` after reporting why."""
        try:
            return case_status_from_snapshot(status_data)
        except VultronValidationError as exc:
            self.feedback_message = str(exc)
            self.logger.warning("%s: %s", self.name, self.feedback_message)
            return None
