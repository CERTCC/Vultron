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

"""Ledger effect nodes for add_participant_status_to_participant entries.

Provides :class:`ApplyParticipantStatusFromLedgerNode`, which applies an
``add_participant_status_to_participant`` ledger entry to the local participant
record, enforcing the RM ratchet (RSH-05-007) and composite-state entailments
(RSH-05-021, ADR-0061).

Provides :class:`EmitImpossibleStateFaultNode`, which emits
``Create(ProcessingFault)`` with failure class
``StatusAssertionRefused/ImpossibleState`` to the CaseActor when the Apply node
returns FAILURE.  The two nodes are wired in a Selector in ``announce_tree.py``
to guarantee that either the status is applied successfully or a fault is emitted.

Per specs/multi-actor-demo.yaml DEMOMA-07-003 step 3,
specs/sync-ledger-replication.yaml SYNC-02-002, and
specs/received-status-handling.yaml RSH-05-021.
"""

from __future__ import annotations

import logging

from py_trees.common import Status

from vultron.core.behaviors.helpers import (
    DataLayerActionWithPorts,
    PortInformation,
    read_rm_states,
)
from vultron.core.behaviors.sync.nodes.effects import _extract_id_from_field
from vultron.core.models._helpers import _as_id
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.dimensions import RmDimension
from vultron.core.models.fault_classes import (
    VULTRON_FAILURE_STATUS_ASSERTION_REFUSED_IMPOSSIBLE_STATE,
)
from vultron.core.models.participant_status import ParticipantStatus
from vultron.core.states.composite_state_invariants import (
    composite_state_violations,
)
from vultron.core.states.rm import RM, is_rm_at_least

logger = logging.getLogger(__name__)


def _ratchet_rm(
    status_obj: ParticipantStatus, local_rm: RM | None
) -> tuple[ParticipantStatus, RM | None]:
    """Carry *local_rm* forward when *status_obj* would regress it.

    Monotonic visibility (``notes/sync-ledger-replication.md``): a replica must
    never move an RM state backwards on the progress scale, even on an entry
    from the authoritative Case Actor.  A replayed, reordered, or divergent
    entry would otherwise un-see progress the replica has already observed.

    Lateral moves at the same rank (``VALID`` ↔ ``INVALID``,
    ``DEFERRED`` ↔ ``ACCEPTED``) are *not* regressions: the Case Actor is
    authoritative for re-adjudication and those are applied unchanged.

    Returns:
        The status to record and the refused RM value, or ``(status_obj, None)``
        when nothing was refused.
    """
    if local_rm is None:
        return status_obj, None
    entry_rm = status_obj.rm.state
    if entry_rm == local_rm or is_rm_at_least(entry_rm, local_rm):
        return status_obj, None
    return (
        status_obj.model_copy(
            update={"rm": RmDimension(state=local_rm), "name": None}
        ),
        entry_rm,
    )


class ApplyParticipantStatusFromLedgerNode(DataLayerActionWithPorts):
    """Apply an ``add_participant_status_to_participant`` ledger entry locally.

    When a non-Case-Actor participant receives
    ``Announce(CaseLedgerEntry)`` and the entry's ``event_type`` is
    ``add_participant_status_to_participant``, this node reconstructs the
    :class:`~vultron.core.models.participant_status.ParticipantStatus` from
    the entry's ``payload_snapshot`` and appends it to the matching
    :class:`~vultron.core.models.case_participant.CaseParticipant` in the
    local DataLayer.

    The Case Actor is considered authoritative for *which* transition happened
    — it already adjudicated the assertion before committing the entry — so
    this node does not re-run the RM transition rules.  It does enforce one
    invariant the Case Actor cannot vouch for from the replica's vantage point:
    RM state must never move backwards on the progress scale (monotonic
    visibility).  A replayed, reordered, or divergent entry that would regress
    the local RM state has that dimension carried forward at the local value;
    every other dimension is applied as the entry describes it.  Lateral moves
    at the same rank (``VALID`` ↔ ``INVALID``) are applied unchanged.

    Idempotency is preserved — if the status ID is already present in the
    participant's list, the node returns SUCCESS without modifying the
    DataLayer.

    Lenient on missing data: if the participant is not found in the local
    DataLayer (this actor may have a partial view of the case), or the
    payload snapshot is incomplete, the node returns SUCCESS without error to
    avoid blocking the ``Announce`` processing flow.  It is *not* lenient on a
    malformed local record: a participant whose recorded status is not
    core-shaped yields FAILURE, because the ratchet cannot be enforced against
    an unreadable floor (ARCH-15-001, ADR-0062).

    Per specs/multi-actor-demo.yaml DEMOMA-07-003 step 3,
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
        self.activity = self.get_input("activity")

    def _apply_rm_ratchet(
        self,
        status_obj: ParticipantStatus,
        participant: CaseParticipant,
        status_id: str,
        participant_id: str,
    ) -> ParticipantStatus | None:
        """Enforce monotonic RM visibility, logging a carried-forward value.

        Returns ``None`` when the participant's recorded status is not
        core-shaped, and the caller must then return ``Status.FAILURE``.  A
        shape mismatch is not an absence: reading it as "no local RM known"
        would hand :func:`_ratchet_rm` a ``None`` floor and skip the ratchet
        entirely, letting a regressing entry through unchecked — the defect
        behind #2264 (ARCH-15-001, ARCH-15-002, ADR-0062).  Genuine absence —
        a replica whose participant record carries no status yet — has no
        floor to enforce and is handled here as such.
        """
        current = getattr(participant, "participant_status", None)
        local_rm: RM | None = None
        if current is not None:
            states = read_rm_states(self, current)
            if states is None:
                return None
            (local_rm,) = states

        ratcheted, refused_rm = _ratchet_rm(status_obj, local_rm)
        if refused_rm is not None:
            self.logger.warning(
                "%s: ledger entry for '%s' would regress participant '%s'"
                " from rm=%s to rm=%s — carrying the local value forward"
                " (monotonic visibility, SYNC-02-002)",
                self.name,
                status_id,
                participant_id,
                ratcheted.rm.state,
                refused_rm,
            )
        return ratcheted

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None
        from vultron.core.behaviors.sync.nodes.conditions import (
            _require_log_entry,
        )

        entry = _require_log_entry(self.activity, self.name)
        snapshot = entry.payload_snapshot

        status_data = snapshot.get("object")
        target_data = snapshot.get("target")

        status_id = _extract_id_from_field(status_data)
        participant_id = _extract_id_from_field(target_data)

        if not status_id or not participant_id:
            self.logger.debug(
                "%s: payload_snapshot missing 'object' or 'target' id"
                " — skipping status apply (non-fatal)",
                self.name,
            )
            return Status.SUCCESS

        participant = self.datalayer.read(participant_id)
        if not isinstance(participant, CaseParticipant):
            self.logger.debug(
                "%s: participant '%s' not found in local DataLayer"
                " — skipping (non-fatal, partial case view)",
                self.name,
                participant_id,
            )
            return Status.SUCCESS

        existing_ids = [_as_id(s) for s in participant.participant_statuses]
        if status_id in existing_ids:
            self.logger.debug(
                "%s: status '%s' already present on participant '%s'"
                " — idempotent no-op",
                self.name,
                status_id,
                participant_id,
            )
            return Status.SUCCESS

        if not isinstance(status_data, dict):
            self.logger.warning(
                "%s: payload_snapshot 'object' is not a dict"
                " — cannot reconstruct ParticipantStatus for '%s'",
                self.name,
                status_id,
            )
            return Status.SUCCESS

        try:
            status_obj = ParticipantStatus.model_validate(status_data)
        except Exception as exc:
            self.logger.warning(
                "%s: failed to reconstruct ParticipantStatus from"
                " payload_snapshot for '%s': %s",
                self.name,
                status_id,
                exc,
            )
            return Status.SUCCESS

        ratcheted = self._apply_rm_ratchet(
            status_obj, participant, status_id, participant_id
        )
        if ratcheted is None:
            self.logger.error(
                "%s: cannot enforce monotonic RM visibility for participant"
                " '%s' — its recorded status is not core-shaped; refusing to"
                " apply ledger entry '%s' (ARCH-15-001, ADR-0062)",
                self.name,
                participant_id,
                status_id,
            )
            return Status.FAILURE
        status_obj = ratcheted

        rm = status_obj.rm.state
        vf = status_obj.vf.state if status_obj.vf is not None else None
        d = status_obj.d.state if status_obj.d is not None else None
        violations = composite_state_violations(rm, vf, d)
        if violations:
            self.feedback_message = violations[0].message
            self.logger.warning(
                "%s: ledger entry '%s' for participant '%s' describes an"
                " impossible composite state (rm=%s, vf=%s, d=%s):"
                " %s — refusing to apply (RSH-05-021)",
                self.name,
                status_id,
                participant_id,
                rm.name,
                vf.name if vf is not None else "None",
                d.name if d is not None else "None",
                violations[0].message,
            )
            return Status.FAILURE

        # Saved unconditionally: ``status_obj`` carries the RM ratchet applied
        # above; skipping the save would silently discard that ratchet,
        # regressing the replica's RM visibility (RSH-05-007, SYNC-02-002).
        self.datalayer.save(status_obj)

        participant.add_participant_status(status_obj)
        self.datalayer.save(participant)

        self.logger.info(
            "%s: applied ledger status update '%s' to participant '%s'"
            " (DEMOMA-07-003 step 3 receiver-side)",
            self.name,
            status_id,
            participant_id,
        )
        return Status.SUCCESS


class EmitImpossibleStateFaultNode(DataLayerActionWithPorts):
    """Emit ``Create(ProcessingFault)`` for an impossible composite state.

    This node is the fallback in the Selector that wraps
    :class:`ApplyParticipantStatusFromLedgerNode`.  When the Apply node returns
    FAILURE (either from a composite-state entailment violation or from an
    unreadable local participant record), this node emits a
    ``Create(ProcessingFault)`` with failure class
    ``StatusAssertionRefused/ImpossibleState`` to the CaseActor and then returns
    FAILURE, so the Selector's FAILURE propagates up to block
    ``PersistReceivedLogEntry`` (SYNC-12-001, RSH-05-021).

    The fault is omitted gracefully when no ``TriggerActivityPort`` is wired
    (integration tests, demo runners without a trigger factory), so the tree
    still fails correctly without raising.
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
        self.activity = self.get_input("activity")

    def update(self) -> Status:
        activity = self.activity
        if activity is None or self.actor_id is None:
            self.logger.warning(
                "%s: missing activity or actor_id — cannot emit ProcessingFault",
                self.name,
            )
            return Status.FAILURE

        failed_id = getattr(activity, "activity_id", None)
        sender_id = getattr(activity, "actor_id", None)
        case_id = getattr(activity, "context_id", None)

        if self.trigger_activity_factory is None:
            self.logger.warning(
                "%s: no TriggerActivityPort — ProcessingFault not emitted"
                " for failed activity '%s' (RSH-05-021)",
                self.name,
                failed_id,
            )
            return Status.FAILURE

        if failed_id and sender_id:
            self.trigger_activity_factory.emit_processing_fault(
                actor=self.actor_id,
                failed_activity_id=failed_id,
                failure_class=VULTRON_FAILURE_STATUS_ASSERTION_REFUSED_IMPOSSIBLE_STATE,
                to=[sender_id],
                case_id=case_id,
            )
            self.logger.info(
                "%s: emitted ProcessingFault/ImpossibleState to '%s'"
                " for failed activity '%s' (RSH-05-021)",
                self.name,
                sender_id,
                failed_id,
            )

        return Status.FAILURE
