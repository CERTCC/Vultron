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

"""Invite expiry replica replay node (CM-28-014, ADR-0118).

The CASE_MANAGER evaluates invite expiry lazily when it processes a late
``Accept`` (via
:meth:`~vultron.core.services.embargo_lifecycle.EmbargoLifecycle.detect_and_apply_expiry`),
commits an ``invite_to_embargo_on_case_expired`` ledger entry (CM-28-009), and
routes the late answer through EMB-17.  A participant replica never evaluates a
deadline; it applies the manager's decision from the committed entry through
:class:`ApplyInviteExpiryFromLedgerNode`, reached from
``create_announce_log_entry_tree`` (RSH-08-004, CM-28-014).
"""

from py_trees.common import Status

from vultron.core.behaviors.sync.nodes._helpers import (
    _extract_id_from_field,
    _LedgerEffectNode,
)
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.services.embargo_lifecycle.results import (
    ParticipantPECChange,
)
from vultron.core.states.participant_embargo_consent import PEC, PEC_Trigger


class ApplyInviteExpiryFromLedgerNode(_LedgerEffectNode):
    """Replay the CASE_MANAGER's expiry entry on a replica (CM-28-014, ADR-0118).

    The entry's ``actor`` is the expired invitee (the snapshot is attributed to
    it, CM-28-009); the replica applies ``EXPIRE`` (``INVITED → EXPIRED``)
    idempotently — only from ``INVITED``, any other state is left unchanged —
    and evaluates no deadline of its own.
    Regime 2 (ADR-0087): a replica holding no copy of the case, or no record
    of the invitee, skips with SUCCESS.  An entry that names no invitee fails,
    so it is not persisted as applied (SYNC-12-001).
    """

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None
        entry = self._get_entry()
        case = self._resolve_case_replica(entry.case_id)
        if case is None:
            return Status.SUCCESS  # Regime 2 (ADR-0087): partial replica
        invitee_id = _extract_id_from_field(
            entry.payload_snapshot.get("actor")
        )
        if not invitee_id:
            self.feedback_message = (
                f"expiry entry on case '{case.id_}' names no invitee"
            )
            self.logger.warning("%s: %s", self.name, self.feedback_message)
            return Status.FAILURE
        participant_id = case.actor_participant_index.get(invitee_id)
        if not participant_id:
            self.feedback_message = (
                f"no participant record for '{invitee_id}' on case"
                f" '{case.id_}' — skipping (partial replica)"
            )
            self.logger.debug("%s: %s", self.name, self.feedback_message)
            return Status.SUCCESS
        participant = self.datalayer.read(participant_id)
        if not isinstance(participant, CaseParticipant):
            self.feedback_message = (
                f"participant id '{participant_id}' for '{invitee_id}' on"
                f" case '{case.id_}' is not a CaseParticipant — skipping"
            )
            self.logger.debug("%s: %s", self.name, self.feedback_message)
            return Status.SUCCESS
        changes: list[ParticipantPECChange] = []
        if participant.embargo_consent_state == PEC.INVITED.value:
            pec_before = participant.embargo_consent_state
            participant.apply_pec_transition(PEC_Trigger.EXPIRE)
            self.datalayer.save(participant)
            changes.append(
                ParticipantPECChange(
                    participant_id=participant_id,
                    pec_before=pec_before,
                    pec_after=participant.embargo_consent_state,
                )
            )
        self.feedback_message = (
            f"Replayed invite expiry of '{invitee_id}' on case '{case.id_}'"
            f" ({len(changes)} PEC state change(s))"
        )
        if changes:
            self.logger.info("%s: %s", self.name, self.feedback_message)
        else:
            self.logger.debug("%s: %s", self.name, self.feedback_message)
        return Status.SUCCESS


__all__ = ["ApplyInviteExpiryFromLedgerNode"]
