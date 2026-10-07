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

"""Ledger replay of the activity-typed RM moves (RSH-08-004, ADR-0108).

The report verdicts (``validate_report``, ``invalidate_report``,
``close_report``), the case engagement decisions (``engage_case``,
``defer_case``) and a joined participant's judgement of the full-case Invite
(``accept``/``tentative_reject``/``reject_invite_actor_to_full_case``,
CM-11-011) are acts: the activity itself says which RM state its sender moved
to.  The CASE_MANAGER records the move on the *sender's* participant
(RSH-08-001) and commits the activity; this module replays that entry on a
participant replica, so the replica's view of the sender converges without the
act reaching it directly (PCR-03-001).

:data:`RM_VERDICT_TARGETS` names the RM state each event type records.
:class:`IsRmVerdictEventNode` matches any of them and
:class:`ApplyRmVerdictFromLedgerNode` applies the one the entry names, in one
``RmVerdict`` slot of ``AnnounceLogEntryReceivedBT``.

The apply writes the state the ledger records and nothing else (CM-23-016): no
intermediate rung is derived from the replica's own state.  It never moves the
subject backwards on the RM progress scale (RSH-05-007), the same monotonic
visibility rule ``add_participant_status_to_participant`` replay enforces;
same-rank moves (``VALID`` ↔ ``INVALID``, ``ACCEPTED`` ↔ ``DEFERRED``) are
re-adjudication and apply.  The written state must satisfy the composite-state
entailments (CSB-18-001, CSB-17-001); a violation fails the slot, which blocks
persisting the entry (SYNC-12-001).
"""

from __future__ import annotations

import logging
from types import MappingProxyType
from typing import Final

from py_trees.common import Status

from vultron.core.behaviors.helpers import read_rm_states
from vultron.core.behaviors.sync.nodes._helpers import (
    _extract_id_from_field,
    _LedgerEffectNode,
)
from vultron.core.behaviors.sync.nodes.conditions import _require_log_entry
from vultron.core.behaviors.sync.nodes.event_conditions import (
    _ActivityEventNode,
)
from vultron.core.models._helpers import parse_published
from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.dimensions import RmDimension
from vultron.core.models.events.base import MessageSemantics
from vultron.core.models.participant_status import ParticipantStatus
from vultron.core.states.composite_state_invariants import (
    composite_state_violations,
)
from vultron.core.states.rm import RM, is_rm_replay_acceptable

logger = logging.getLogger(__name__)

#: The RM state each activity-typed RM move records for its sender.
RM_VERDICT_TARGETS: Final = MappingProxyType(
    {
        MessageSemantics.VALIDATE_REPORT.value: RM.VALID,
        MessageSemantics.INVALIDATE_REPORT.value: RM.INVALID,
        MessageSemantics.CLOSE_REPORT.value: RM.CLOSED,
        MessageSemantics.ENGAGE_CASE.value: RM.ACCEPTED,
        MessageSemantics.DEFER_CASE.value: RM.DEFERRED,
        # A joined participant's judgement of the full-case Invite
        # (CM-11-011, ADR-0121).
        MessageSemantics.ACCEPT_INVITE_ACTOR_TO_FULL_CASE.value: RM.VALID,
        MessageSemantics.TENTATIVE_REJECT_INVITE_ACTOR_TO_FULL_CASE.value: (
            RM.INVALID
        ),
        MessageSemantics.REJECT_INVITE_ACTOR_TO_FULL_CASE.value: RM.CLOSED,
    }
)


class IsRmVerdictEventNode(_ActivityEventNode):
    """Precondition: this entry records an activity-typed RM move.

    SUCCESS when the entry's ``event_type`` is a key of
    :data:`RM_VERDICT_TARGETS`.  Used in the ``RmVerdict`` slot of
    ``AnnounceLogEntryReceivedBT``.

    Per RSH-08-004, BTND-08-001, SYNC-12-001.
    """

    def update(self) -> Status:
        entry = _require_log_entry(self.activity, self.name)
        if entry.event_type in RM_VERDICT_TARGETS:
            return Status.SUCCESS
        return Status.FAILURE


class ApplyRmVerdictFromLedgerNode(_LedgerEffectNode):
    """Apply an activity-typed RM move to the sender's participant replica.

    The subject is the entry's ``payloadSnapshot.actor`` — the sender of the
    act the CASE_MANAGER committed (RSH-08-001), never the actor whose replica
    this is.  The node appends one ``ParticipantStatus`` at the recorded RM
    state, carrying the participant's VF, D and roles forward.

    No-ops, each SUCCESS with nothing written:

    * the replica holds no copy of the case, or the subject has no participant
      record in it (Regime 2, ADR-0087: a partial view);
    * the subject is already at the recorded state (idempotent re-delivery);
    * the recorded state is behind the subject's current one on the RM
      progress scale (RSH-05-007): the local value is carried forward.

    FAILURE, so the entry is not persisted (SYNC-12-001):

    * the subject's recorded status is not core-shaped, so the ratchet has no
      floor to enforce (ARCH-15-001, ADR-0062);
    * the state to write violates a composite-state entailment.
    """

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        entry = self._get_entry()
        subject_id = _extract_id_from_field(
            entry.payload_snapshot.get("actor")
        )
        participant = self._subject_participant(entry.case_id, subject_id)
        if participant is None:
            return Status.SUCCESS  # Regime 2 (ADR-0087): partial view
        assert subject_id is not None
        current = participant.participant_status
        local_rm: RM | None = None
        if current is not None:
            states = read_rm_states(self, current)
            if states is None:
                return Status.FAILURE
            (local_rm,) = states
        target = RM_VERDICT_TARGETS[entry.event_type]
        if not self._advances(entry.event_type, subject_id, local_rm, target):
            return Status.SUCCESS
        status = self._next_status(entry, subject_id, current, target)
        if status is None:
            return Status.FAILURE
        assert self.datalayer is not None
        self.datalayer.save(status)
        participant.add_participant_status(status)
        self.datalayer.save(participant)
        self.logger.info(
            "%s: replayed '%s' — participant '%s' rm %s → %s in case '%s'"
            " (RSH-08-004)",
            self.name,
            entry.event_type,
            subject_id,
            local_rm,
            target,
            entry.case_id,
        )
        return Status.SUCCESS

    def _subject_participant(
        self, case_id: str, subject_id: str | None
    ) -> CaseParticipant | None:
        """The subject's participant record on this replica, if it holds one."""
        assert self.datalayer is not None
        case = self._resolve_case_replica(case_id)
        if case is None:
            return None
        participant_id = (
            case.actor_participant_index.get(subject_id)
            if subject_id
            else None
        )
        participant = (
            self.datalayer.read(participant_id) if participant_id else None
        )
        if isinstance(participant, CaseParticipant):
            return participant
        self.logger.debug(
            "%s: no participant record for '%s' in case '%s' — skipping"
            " (non-fatal, partial case view)",
            self.name,
            subject_id,
            case_id,
        )
        return None

    def _advances(
        self, event_type: str, subject_id: str, local_rm: RM | None, target: RM
    ) -> bool:
        """False for a same-state re-delivery or a backward move (RSH-05-007)."""
        if local_rm == target:
            self.logger.debug(
                "%s: '%s' already at rm=%s — idempotent no-op",
                self.name,
                subject_id,
                target,
            )
            return False
        if not is_rm_replay_acceptable(local_rm, target):
            self.logger.warning(
                "%s: '%s' entry would regress participant '%s' from rm=%s to"
                " rm=%s — carrying the local value forward (RSH-05-007)",
                self.name,
                event_type,
                subject_id,
                local_rm,
                target,
            )
            return False
        return True

    def _next_status(
        self,
        entry: CaseLedgerEntry,
        subject_id: str,
        current: ParticipantStatus | None,
        target: RM,
    ) -> ParticipantStatus | None:
        """The status to append, or ``None`` when it is impossible (CSB-18-001).

        VF, D and roles are carried forward from *current*; with none, the
        model defaults apply.
        """
        violations = composite_state_violations(
            target,
            current.vf.state if current and current.vf else None,
            current.d.state if current and current.d else None,
        )
        if violations:
            # Report every violation, not the first (EH-07-001).
            self.feedback_message = "; ".join(v.message for v in violations)
            self.logger.warning(
                "%s: '%s' entry would give participant '%s' an impossible"
                " composite state: %s — refusing to apply (CSB-18-001)",
                self.name,
                entry.event_type,
                subject_id,
                self.feedback_message,
            )
            return None
        carried: dict[str, object] = (
            {"vf": current.vf, "d": current.d, "cvd_role": current.cvd_role}
            if current is not None
            else {}
        )
        return ParticipantStatus.model_validate(
            {
                "context": entry.case_id,
                "attributed_to": subject_id,
                "rm": RmDimension(state=target),
                **carried,
                **_claimed_times(entry.payload_snapshot.get("published")),
            }
        )


def _claimed_times(published: object) -> dict[str, object]:
    """The sender's claimed time for the replayed status, when it has one.

    The replica records the move at the time its sender claimed, not at its
    own clock's reading (CLP-15-007, ADR-0124).
    """
    claimed = parse_published(published)
    if claimed is None:
        return {}
    return {"published": claimed, "updated": claimed}
