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

"""Replica replay of the CASE_MANAGER's own participant-record entries.

The ledger holds the wire messages exchanged (ADR-0114).  Creating the inert
record is the CASE_MANAGER's own act, with no wire message of its own, so it has
its own entry, ``create_case_participant``, whose object is the whole record as
the CASE_MANAGER stored it.  A replica stores that record as received (ADR-0103,
CLP-15-007) and reconstructs nothing: no id, time, status or consent row is
derived here.  The changes the invitee's reply makes to the record are the
effect of the reply's own entry (``stub_reply_effect``).

A change the CASE_MANAGER makes to a record as the consequence of an act, such
as moving ``CASE_OWNER`` on an ownership transfer, is its own
``update_case_participant`` entry carrying the changed record in full
(CLP-07-013).  A replica stores that copy in place of the one it holds
(CM-23-016): no role, id or time is derived here either.

Per CM-11-006, CM-21-002, CM-21-003, CM-23-016, SYNC-02-002, SYNC-12-001,
RSH-08-004.
"""

from __future__ import annotations

from py_trees.common import Status

from vultron.core.behaviors.sync.nodes._helpers import _LedgerEffectNode
from vultron.core.behaviors.sync.nodes.event_conditions import (
    _SingleEventTypeNode,
)
from vultron.core.models._helpers import project_wire_snapshot_to_core
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.participant_event_types import (
    UPDATE_CASE_PARTICIPANT_EVENT_TYPE,
)


def _carried_participant(
    node: _LedgerEffectNode, snapshot: dict
) -> CaseParticipant | None:
    """The record the entry carries, or ``None`` (the node then fails)."""
    data = snapshot.get("object")
    if not isinstance(data, dict):
        node.feedback_message = (
            f"{node.name}: the entry carries no CaseParticipant object"
        )
        return None
    try:
        return CaseParticipant.model_validate(
            project_wire_snapshot_to_core(CaseParticipant, data)
        )
    except ValueError as exc:
        node.feedback_message = (
            f"{node.name}: the entry's CaseParticipant is not valid: {exc}"
        )
        return None


def _record_held(
    node: _LedgerEffectNode, case: VulnerabilityCase, record: CaseParticipant
) -> CaseParticipant | None:
    """The replica's stored record for *record*'s actor, or ``None``."""
    assert node.datalayer is not None
    actor_id = str(record.attributed_to)
    held_id = case.actor_participant_index.get(actor_id)
    held = node.datalayer.read(held_id) if held_id else None
    return held if isinstance(held, CaseParticipant) else None


class ApplyCreateCaseParticipantFromLedgerNode(_LedgerEffectNode):
    """Store the participant record a ``create_case_participant`` entry carries.

    Lenient only on a replica that holds no copy of the case (Regime 2,
    ADR-0087).  A record the replica already holds is left alone (idempotent,
    a replay).  An entry whose object is not a valid ``CaseParticipant`` fails
    with a reason.
    """

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None

        entry = self._get_entry()
        record = _carried_participant(self, entry.payload_snapshot)
        if record is None:
            self.logger.error("%s", self.feedback_message)
            return Status.FAILURE

        case = self._resolve_case_replica(entry.case_id)
        if case is None:
            return Status.SUCCESS  # Regime 2 (ADR-0087): partial replica, skip

        if _record_held(self, case, record) is not None:
            self.logger.debug(
                "%s: '%s' already holds a record for '%s' — idempotent no-op",
                self.name,
                entry.case_id,
                record.attributed_to,
            )
            return Status.SUCCESS

        if self.datalayer.read(record.id_) is None:
            self.datalayer.create(record)
        # The record already holds a row for every register entry, as the
        # CASE_MANAGER stored it, so seating it writes none.
        if case.add_participant(record):
            self.datalayer.save(record)
        self.datalayer.save(case)
        self.logger.info(
            "%s: stored participant '%s' for case '%s' as the entry carries it"
            " (CM-11-006)",
            self.name,
            record.id_,
            entry.case_id,
        )
        return Status.SUCCESS


class IsUpdateCaseParticipantEventNode(_SingleEventTypeNode):
    """Precondition: SUCCESS when this log entry IS an ``update_case_participant``.

    Precondition of the ``UpdateCaseParticipant`` slot.  The CASE_MANAGER
    commits it for each participant record an act of its own changes, such
    as the ``CASE_OWNER`` role moving on an ownership transfer (CM-21-002,
    CM-21-003, CLP-07-013).

    Per BTND-08-001, CM-23-016, SYNC-12-001, RSH-08-004.
    """

    matched_event_type = UPDATE_CASE_PARTICIPANT_EVENT_TYPE


class ApplyCaseParticipantUpdateFromLedgerNode(_LedgerEffectNode):
    """Store the changed record an ``update_case_participant`` entry carries.

    The carried record replaces the replica's copy of it, as the CASE_MANAGER
    stored it (CM-23-016).  Lenient on a replica that holds no copy of the
    case (Regime 2, ADR-0087), or none of the record, which it then learns
    with the roster entry that seats it; both are SUCCESS with nothing
    written.  An entry whose object is not a valid ``CaseParticipant`` fails
    with a reason, so it is not persisted (SYNC-12-001).
    """

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None

        entry = self._get_entry()
        record = _carried_participant(self, entry.payload_snapshot)
        if record is None:
            self.logger.error("%s", self.feedback_message)
            return Status.FAILURE

        case = self._resolve_case_replica(entry.case_id)
        if case is None:
            return Status.SUCCESS  # Regime 2 (ADR-0087): partial replica, skip

        held = _record_held(self, case, record)
        if held is None or held.id_ != record.id_:
            self.logger.warning(
                "%s: case '%s' holds no record '%s' for '%s' — skipping the"
                " update (non-fatal)",
                self.name,
                entry.case_id,
                record.id_,
                record.attributed_to,
            )
            return Status.SUCCESS

        self.datalayer.save(record)
        self.logger.info(
            "%s: stored participant '%s' of case '%s' as the entry carries it"
            " (roles %s; CM-23-016)",
            self.name,
            record.id_,
            entry.case_id,
            [role.value for role in record.case_roles],
        )
        return Status.SUCCESS
