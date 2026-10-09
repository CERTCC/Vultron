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

"""Replica replay of a participant removal and reinstatement (ADR-0116).

:class:`IsRemoveCaseParticipantEventNode` and
:class:`ApplyRemoveCaseParticipantFromLedgerNode` form the
``RemoveCaseParticipantEffects`` slot in ``create_announce_log_entry_tree``;
:class:`IsReinstateCaseParticipantEventNode` and
:class:`ApplyReinstateCaseParticipantFromLedgerNode` form the
``ReinstateCaseParticipantEffects`` slot (CM-31-007, CM-31-011, RSH-08-004).

The CASE_MANAGER commits the Case Owner's received ``Remove(CaseParticipant)``
as the removal's one ledger entry (CM-31-005), and its received
``Add(CaseParticipant)`` as the reinstatement's.  A replica applies each here,
writing the same fact the CASE_MANAGER wrote — :meth:`CaseParticipant.record_removal`
records the id of that ``Remove`` activity, :meth:`CaseParticipant.clear_removal`
clears it.  A replica never applies either from the CASE_MANAGER's direct
notice (RSH-08-003); the received tree stores that notice and writes nothing.

The removed participant's own replica is among the removal entry's
recipients (its fan-out is selected before the fact is set), so it applies the
removal to its own record too (CM-31-006).  It is sent the reinstatement entry
by the admission backfill that follows the reinstatement (CM-10-006), so it
clears the fact on its own record the same way.
"""

from __future__ import annotations

from py_trees.common import Status

from vultron.core.behaviors.sync.nodes._helpers import (
    _extract_id_from_field,
    _LedgerEffectNode,
)
from vultron.core.behaviors.sync.nodes.conditions import _require_log_entry
from vultron.core.behaviors.sync.nodes.event_conditions import (
    _ActivityEventNode,
)
from vultron.core.models._helpers import _as_id
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.events.base import MessageSemantics
from vultron.core.models.wire_keys import wire_key
from vultron.errors import VultronNotFoundError

#: Ledger ``event_type`` of the Case Owner's removal request, as the guarded
#: commit derives it from the received activity's semantics.
REMOVE_CASE_PARTICIPANT_EVENT_TYPE = (
    MessageSemantics.REMOVE_CASE_PARTICIPANT_FROM_CASE.value
)

#: Ledger ``event_type`` of the Case Owner's reinstatement request.
REINSTATE_CASE_PARTICIPANT_EVENT_TYPE = (
    MessageSemantics.ADD_CASE_PARTICIPANT_TO_CASE.value
)

_ATTRIBUTED_TO = wire_key("attributed_to")


class IsRemoveCaseParticipantEventNode(_ActivityEventNode):
    """Precondition: SUCCESS when this log entry IS a participant removal.

    Precondition of the ``RemoveCaseParticipantEffects`` slot, in the same
    ``Selector(Seq(Is, Apply), Inverter(Is))`` shape as every other slot.

    Per BTND-08-001, BTND-08-002, SYNC-12-001, RSH-08-004, CM-31-007.
    """

    def update(self) -> Status:
        entry = _require_log_entry(self.activity, self.name)
        if entry.event_type == REMOVE_CASE_PARTICIPANT_EVENT_TYPE:
            return Status.SUCCESS
        return Status.FAILURE


class _ParticipantMoveLedgerEffectNode(_LedgerEffectNode):
    """Shared frame of the replica's removal and reinstatement apply nodes.

    Resolves the named participant in the replica's own roster — by the
    actor the snapshot's ``object`` is attributed to, through
    ``actor_participant_index`` (CM-19-003), falling back to the record id
    the snapshot names when that id is on the replica's roster — and hands
    the record to :meth:`_apply`.  Resolving by actor first is safe because
    the CASE_MANAGER refused any move whose inline ``attributedTo`` disagrees
    with the record it judged (CM-31-004, CM-31-011), and a replica's own
    record id may differ from the CASE_MANAGER's.  The record stays on the
    roster (CM-31-001) and its embargo consent rows are untouched
    (CM-31-008).

    Lenient on missing data, as the other apply nodes are: a replica that
    holds no copy of the case or of the participant, or a snapshot with no
    participant or activity id, skips with ``SUCCESS`` so a partial replica
    cannot wedge replication (Regime 2, ADR-0087).
    """

    #: The move this node applies, for log lines.
    _MOVE: str

    def _apply(self, record: CaseParticipant, activity_id: str) -> bool:
        """Write the move to *record*; ``False`` when it already holds."""
        raise NotImplementedError

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None

        entry = self._get_entry()
        snapshot = entry.payload_snapshot
        case_id = entry.case_id
        activity_id = (
            _extract_id_from_field(snapshot.get("id")) or entry.log_object_id
        )
        participant_data = snapshot.get("object")
        if not case_id or not activity_id or not participant_data:
            self.logger.debug(
                "%s: payload_snapshot missing the participant, the activity"
                " id or the case id — skipping %s apply (non-fatal)",
                self.name,
                self._MOVE,
            )
            return Status.SUCCESS

        case = self._resolve_case_replica(case_id)
        if case is None:
            return Status.SUCCESS  # Regime 2 (ADR-0087): partial replica, skip

        try:
            record = self._replica_record(case, participant_data)
        except VultronNotFoundError:
            self.logger.info(
                "%s: replica of case '%s' holds no record for the participant"
                " — skipping %s apply",
                self.name,
                case_id,
                self._MOVE,
            )
            return Status.SUCCESS

        if not self._apply(record, activity_id):
            self.logger.debug(
                "%s: participant '%s' of case '%s' already reflects the %s"
                " — idempotent no-op",
                self.name,
                record.id_,
                case_id,
                self._MOVE,
            )
            return Status.SUCCESS
        self.datalayer.save(record)
        self.logger.info(
            "%s: applied ledger %s of participant '%s' in case '%s'",
            self.name,
            self._MOVE,
            record.id_,
            case_id,
        )
        return Status.SUCCESS

    def _replica_record(
        self, case: VulnerabilityCase, participant_data: object
    ) -> CaseParticipant:
        """The replica's own record for the participant the snapshot names.

        Raises:
            VultronNotFoundError: The replica holds no such record.
        """
        assert self.datalayer is not None
        candidates: list[str] = []
        if isinstance(participant_data, dict):
            actor_id = _extract_id_from_field(
                participant_data.get(_ATTRIBUTED_TO)
            )
            if actor_id and actor_id in case.actor_participant_index:
                candidates.append(case.actor_participant_index[actor_id])
        snapshot_id = _extract_id_from_field(participant_data)
        if snapshot_id and snapshot_id in [
            _as_id(p) for p in case.case_participants
        ]:
            candidates.append(snapshot_id)
        for participant_id in candidates:
            record = self.datalayer.read(participant_id)
            if isinstance(record, CaseParticipant):
                return record
        raise VultronNotFoundError(
            "CaseParticipant",
            f"no record of the {self._MOVE} participant on case '{case.id_}'",
        )


class ApplyRemoveCaseParticipantFromLedgerNode(
    _ParticipantMoveLedgerEffectNode
):
    """Apply a ``remove_case_participant_from_case`` entry to the local replica.

    Records the removal fact from the snapshot's activity id through
    :meth:`CaseParticipant.record_removal` (CM-31-007).  Idempotent: a
    participant already removed keeps its first removal.
    """

    _MOVE = "removal"

    def _apply(self, record: CaseParticipant, activity_id: str) -> bool:
        return record.record_removal(activity_id)


class IsReinstateCaseParticipantEventNode(_ActivityEventNode):
    """Precondition: SUCCESS when this log entry IS a participant reinstatement.

    Precondition of the ``ReinstateCaseParticipantEffects`` slot.  The Case
    Owner's ``Add(CaseParticipant)`` is reinstatement only (CM-31-011), so
    every entry of this type is one.

    Per BTND-08-001, BTND-08-002, SYNC-12-001, RSH-08-004, CM-31-011.
    """

    def update(self) -> Status:
        entry = _require_log_entry(self.activity, self.name)
        if entry.event_type == REINSTATE_CASE_PARTICIPANT_EVENT_TYPE:
            return Status.SUCCESS
        return Status.FAILURE


class ApplyReinstateCaseParticipantFromLedgerNode(
    _ParticipantMoveLedgerEffectNode
):
    """Apply an ``add_case_participant_to_case`` entry to the local replica.

    Clears the removal fact through :meth:`CaseParticipant.clear_removal`,
    as the CASE_MANAGER did (CM-31-011).  Idempotent: a participant that is
    not removed is left as it is.
    """

    _MOVE = "reinstatement"

    def _apply(self, record: CaseParticipant, activity_id: str) -> bool:
        return record.clear_removal()


__all__ = [
    "REINSTATE_CASE_PARTICIPANT_EVENT_TYPE",
    "REMOVE_CASE_PARTICIPANT_EVENT_TYPE",
    "ApplyReinstateCaseParticipantFromLedgerNode",
    "ApplyRemoveCaseParticipantFromLedgerNode",
    "IsReinstateCaseParticipantEventNode",
    "IsRemoveCaseParticipantEventNode",
]
