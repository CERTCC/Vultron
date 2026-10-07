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
``Add(CaseStatus)`` it accepts from a participant — the accepted portion, after
per-dimension adjudication (RSH-05) — and for the case-status snapshot it takes
after each EM or P/X/A change of its own (RSH-04-002, RSH-04-003).  This module
replays the entry on a participant replica, so the replica's
``case.case_statuses`` and ``current_status`` follow the CASE_MANAGER's without
the ``Add(CaseStatus)`` reaching the replica directly (PCR-03-001).

The replica adjudicates EM and P/X/A with the same acceptance rules the
CASE_MANAGER's ``add_case_status_tree`` uses (RSH-05-018, RSH-05-019), through
the shared predicates :func:`~vultron.core.states.em.is_em_assertion_acceptable`
and :func:`~vultron.core.states.cs.is_pxa_assertion_acceptable`: a refused
dimension carries the replica's current value forward.  For an entry in ledger
order both rules accept: the CASE_MANAGER already adjudicated, and the EM
transitions an embargo act causes arrive first in that act's own entry, applied
through ``EmbargoLifecycle`` (EMB-18-001), so the snapshot's EM is the
replica's own.  The rules guard a replica that has diverged.

The status is appended the way the CASE_MANAGER's
``AppendCaseStatusToCaseNode`` appends it, so both stores record the same
object under the same id (ADR-0124).
"""

from __future__ import annotations

import logging
from typing import Any

from py_trees.common import Status
from pydantic import ValidationError

from vultron.core.behaviors.sync.nodes._helpers import (
    _extract_id_from_field,
    _LedgerEffectNode,
)
from vultron.core.behaviors.sync.nodes.conditions import _require_log_entry
from vultron.core.behaviors.sync.nodes.event_conditions import (
    _ActivityEventNode,
)
from vultron.core.models._helpers import _as_id, project_wire_snapshot_to_core
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_status import CaseStatus
from vultron.core.models.dimensions import EmDimension, PxaDimension
from vultron.core.models.events.base import MessageSemantics
from vultron.core.states.cs import is_pxa_assertion_acceptable
from vultron.core.states.em import is_em_assertion_acceptable

logger = logging.getLogger(__name__)

#: Ledger ``event_type`` of a case-status entry.
ADD_CASE_STATUS_EVENT_TYPE = MessageSemantics.ADD_CASE_STATUS_TO_CASE.value


class IsAddCaseStatusEventNode(_ActivityEventNode):
    """Precondition: this entry is an ``add_case_status_to_case`` event.

    Used in the ``CaseStatus`` slot of ``AnnounceLogEntryReceivedBT``.

    Per RSH-08-004, BTND-08-001, SYNC-12-001.
    """

    def update(self) -> Status:
        entry = _require_log_entry(self.activity, self.name)
        if entry.event_type == ADD_CASE_STATUS_EVENT_TYPE:
            return Status.SUCCESS
        return Status.FAILURE


def _adjudicate(current: CaseStatus, asserted: CaseStatus) -> CaseStatus:
    """Carry *current* forward on each dimension the rules refuse (RSH-05)."""
    updates: dict[str, Any] = {}
    if not is_em_assertion_acceptable(current.em.state, asserted.em.state):
        updates["em"] = EmDimension(state=current.em.state)
    if not is_pxa_assertion_acceptable(current.pxa.state, asserted.pxa.state):
        updates["pxa"] = PxaDimension(state=current.pxa.state)
    return asserted.model_copy(update=updates) if updates else asserted


class ApplyCaseStatusFromLedgerNode(_LedgerEffectNode):
    """Append an ``add_case_status_to_case`` entry's CaseStatus to the replica.

    No-ops, each SUCCESS with nothing written:

    * the replica holds no copy of the case (Regime 2, ADR-0087);
    * the status is already in ``case.case_statuses`` — the genesis status a
      seeded replica holds, or a re-delivery (CLP-13-001);
    * every dimension is refused and the result is the replica's current
      state, so there is nothing new to record (RSH-05-005).

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

        asserted = self._reconstruct(entry.payload_snapshot.get("object"))
        if asserted is None:
            return Status.FAILURE
        if asserted.id_ in {_as_id(s) for s in case.case_statuses}:
            self.logger.debug(
                "%s: status '%s' already in case '%s' — idempotent no-op",
                self.name,
                asserted.id_,
                case.id_,
            )
            return Status.SUCCESS

        status = self._adjudicated(case, asserted)
        if status is None:
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
        status_id = _extract_id_from_field(status_data)
        if not status_id or not isinstance(status_data, dict):
            self.feedback_message = (
                "add_case_status_to_case entry carries no inline CaseStatus"
            )
            self.logger.warning("%s: %s", self.name, self.feedback_message)
            return None
        try:
            # Projected, not validated raw: the snapshot is AS2-shaped, and its
            # timestamps are the CASE_MANAGER's to carry (CLP-15-007).
            return CaseStatus.model_validate(
                project_wire_snapshot_to_core(CaseStatus, status_data)
            )
        except ValidationError as exc:
            self.feedback_message = (
                f"CaseStatus '{status_id}' in the entry is malformed: {exc}"
            )
            self.logger.warning("%s: %s", self.name, self.feedback_message)
            return None

    def _adjudicated(
        self, case: VulnerabilityCase, asserted: CaseStatus
    ) -> CaseStatus | None:
        """Apply the RSH-05 rules; ``None`` when nothing new is accepted."""
        try:
            current = case.current_status
        except ValueError:
            return asserted  # the case's first CaseStatus: nothing to compare
        status = _adjudicate(current, asserted)
        if status is asserted:
            return status
        if (status.em.state, status.pxa.state) == (
            current.em.state,
            current.pxa.state,
        ):
            self.logger.warning(
                "%s: case status '%s' refused in full on case '%s'"
                " (em %s → %s, pxa %s → %s) — the replica has diverged from"
                " the ledger; nothing applied (RSH-05-005)",
                self.name,
                asserted.id_,
                case.id_,
                current.em.state,
                asserted.em.state,
                current.pxa.state,
                asserted.pxa.state,
            )
            return None
        self.logger.warning(
            "%s: case status '%s' partly refused on case '%s'; carrying the"
            " replica's value forward (RSH-05-018, RSH-05-019)",
            self.name,
            asserted.id_,
            case.id_,
        )
        return status
