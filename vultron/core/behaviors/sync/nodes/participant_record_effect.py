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

"""Replica replay of the CASE_MANAGER's changes to a participant record.

Every state change the CASE_MANAGER makes emits an entry (ADR-0114,
ADR-0124), and a replica stores what the entry carries, as received (ADR-0103,
CLP-15-007).  It reconstructs nothing: no id, time, status or consent row is
derived here.

- :class:`ApplyCreateCaseParticipantFromLedgerNode` -- ``create_case_participant``:
  stores the record the entry carries and puts it on the roster.
- :class:`ApplyUpdateCaseParticipantFromLedgerNode` -- ``update_case_participant``:
  copies the entry's ``joined`` mark, consent rows and ``updated`` time onto the
  held record, never moving it backwards (a stale entry replayed over a seed
  that is already ahead changes nothing).  A record the replica does not hold is a broken invariant (the
  chain is complete and in order, SYNC-14, SYNC-15), so the node FAILS and
  writes nothing.

Per CM-11-006, CM-31-012, SYNC-02-002, SYNC-12-001, RSH-08-004.
"""

from __future__ import annotations

from datetime import datetime

from py_trees.common import Status

from vultron.core.behaviors.sync.nodes._helpers import _LedgerEffectNode
from vultron.core.models._helpers import project_wire_snapshot_to_core
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.states.participant_embargo_consent import (
    consent_move_is_legal,
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


def _later(a: datetime | None, b: datetime | None) -> datetime | None:
    if a is None or b is None:
        return a or b
    return max(a, b)


class ApplyUpdateCaseParticipantFromLedgerNode(_LedgerEffectNode):
    """Copy an ``update_case_participant`` entry's changes onto the held record.

    The entry carries the record as the CASE_MANAGER held it after one change
    (``joined`` or a consent row).  The node copies the fields that change can
    touch -- ``joined``, the consent rows and ``updated`` -- exactly as
    received, and never an earlier-written status or role.

    FAILS, with a reason and without writing, when the replica holds no such
    record: the ``create_case_participant`` entry came first on the
    CASE_MANAGER, so a missing record means a broken chain.  Lenient only on a
    replica that holds no copy of the case (Regime 2, ADR-0087).
    """

    @staticmethod
    def _copy_forward(held: CaseParticipant, carried: CaseParticipant) -> None:
        """Copy what the entry carries onto *held*, never moving it backwards.

        A replica seeded with the case replays the ledger from genesis over a
        seed that may already be ahead (ADR-0124, SYNC-15), so an old entry
        must leave newer state alone: ``joined`` is only ever set, a consent
        row is added when the replica holds none for that embargo, and an
        existing row is replaced only when the entry's state is a legal move
        from the held one (CM-18-003).  In order, on a replica that is not
        ahead, this is exactly the carried record.
        """
        held.joined = held.joined or carried.joined
        rows = {row.embargo_id: row for row in held.embargo_consents}
        for row in carried.embargo_consents:
            current = rows.get(row.embargo_id)
            if current is None or (
                row.state != current.state
                and consent_move_is_legal(current.state, row.state)
            ):
                rows[row.embargo_id] = row
        held.embargo_consents = list(rows.values())
        held.updated = _later(held.updated, carried.updated)

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
        if held is None:
            self.feedback_message = (
                f"update_case_participant entry {entry.log_index} for"
                f" '{record.attributed_to}' in case '{entry.case_id}' but this"
                " replica holds no participant record: the"
                " create_case_participant entry has not been applied, so the"
                " chain is incomplete or out of order (CM-11-006, SYNC-14)"
            )
            self.logger.error("%s: %s", self.name, self.feedback_message)
            return Status.FAILURE

        self._copy_forward(held, record)
        self.datalayer.save(held)
        self.logger.info(
            "%s: updated participant '%s' as the entry carries it"
            " (joined=%s, SYNC-02-002)",
            self.name,
            held.id_,
            held.joined,
        )
        return Status.SUCCESS
