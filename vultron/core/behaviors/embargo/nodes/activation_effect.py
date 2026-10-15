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

"""Ledger replay of the case owner's embargo decisions (RSH-08-004).

The CASE_MANAGER commits the owner's ``Accept(EmbargoEvent, target=Case)``
and ``Reject(EmbargoEvent, target=Case)`` (ADR-0122, EP-09-005) and applies
them to the canonical case.  :class:`ApplyEmbargoActivationFromLedgerNode`
and :class:`ApplyEmbargoProposalRejectionFromLedgerNode` apply the same
decision on a participant replica from the committed entry, so the replica's
embargo register follows the CASE_MANAGER's without the activity reaching the
replica directly (PCR-03-001).

The activation copies (ADR-0124, CM-23-016): the ``Accept`` entry is the
whole ``ACTIVATE`` register step, the ``SUPERSEDE`` of the embargo in force
included, and the owner's agreement it states, applied through the one apply
function the CASE_MANAGER uses.  Each ``CARRY_OVER`` row is its own
CASE_MANAGER ``Update(EmbargoConsent)`` entry, which the consent slot copies.
The rejection still goes through ``EmbargoLifecycle`` in ``OBSERVED`` mode
(EMB-18-001) until its arm is converted (#4715).
"""

from __future__ import annotations

from py_trees.common import Status

from vultron.core.behaviors.embargo.nodes.carried_embargo import (
    store_carried_embargo,
)
from vultron.core.behaviors.embargo.nodes.reject_proposed import (
    DecideRejectedEmbargoProposalNode,
)
from vultron.core.behaviors.embargo.nodes.relay_effect import (
    _EmbargoRelayEffectNode,
)
from vultron.core.behaviors.sync.nodes._helpers import _extract_id_from_field
from vultron.core.behaviors.sync.nodes.embargo_copy_effect import (
    ApplyEmbargoChangeFromLedgerNode,
)
from vultron.core.behaviors.sync.nodes.event_conditions import (
    _SingleEventTypeNode,
)
from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.models.embargo_apply import (
    EmbargoCaseFile,
    EmbargoChange,
    RegisterStep,
    RegisterStepKind,
)
from vultron.core.models.embargo_consent_move import owner_agreement
from vultron.core.models.events.base import MessageSemantics
from vultron.core.services.embargo_lifecycle import TransitionMode

#: Ledger ``event_type`` of the case owner's committed activation.
EMBARGO_ACTIVATION_EVENT_TYPE = MessageSemantics.ACTIVATE_EMBARGO_ON_CASE.value

#: Ledger ``event_type`` of the case owner's committed rejection.
EMBARGO_PROPOSAL_REJECTION_EVENT_TYPE = (
    MessageSemantics.REJECT_EMBARGO_PROPOSAL_ON_CASE.value
)


class IsActivateEmbargoEventNode(_SingleEventTypeNode):
    """Precondition: this entry is the owner's activation of an embargo.

    Used in the ``EmbargoActivation`` slot of ``AnnounceLogEntryReceivedBT``.

    Per RSH-08-004, BTND-08-001, SYNC-12-001.
    """

    matched_event_type = EMBARGO_ACTIVATION_EVENT_TYPE


class IsRejectEmbargoProposalEventNode(_SingleEventTypeNode):
    """Precondition: this entry is the owner's rejection of a proposal.

    Used in the ``EmbargoProposalRejection`` slot of
    ``AnnounceLogEntryReceivedBT``.

    Per RSH-08-004, BTND-08-001, SYNC-12-001.
    """

    matched_event_type = EMBARGO_PROPOSAL_REJECTION_EVENT_TYPE


class ApplyEmbargoActivationFromLedgerNode(ApplyEmbargoChangeFromLedgerNode):
    """Copy the owner's activation onto the replica (EM → ACTIVE or REVISE).

    The entry's ``object`` names the embargo.  The change is the
    ``ACTIVATE`` step (with the ``SUPERSEDE`` of the embargo in force), then
    the owner's ``AGREED`` row the ``Accept`` states, decided from the case
    file as the step leaves it, exactly as the CASE_MANAGER decided it
    (:func:`~vultron.core.models.embargo_consent_move.owner_agreement`).  No
    carry-over is computed here: each is its own entry (EP-05-001).

    The embargo's record is stored from the copy the entry carries when this
    replica does not hold it (EMB-18-003); a bare id it does not hold fails.
    An embargo already activated is in place, so a re-delivered entry changes
    nothing.  An entry naming an embargo that is not an open proposal here
    is refused into the gap buffer (ADR-0124); one that names no embargo
    fails, so it is not persisted (SYNC-12-001).  SUCCESS with nothing
    written when the replica holds no copy of the case (Regime 2, ADR-0087).
    """

    def update(self) -> Status:
        # The register entry this activates names an embargo this store must
        # hold (EMB-18-003): the entry carries it inline, so hold it from
        # there before the step is copied.
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None
        entry = self._get_entry()
        embargo_data = entry.payload_snapshot.get("object")
        embargo_id = _extract_id_from_field(embargo_data)
        if embargo_id and self._resolve_case_replica(entry.case_id):
            problem = store_carried_embargo(
                self.datalayer, embargo_data, embargo_id
            )
            if problem is not None:
                self.feedback_message = f"{self.name}: {problem}"
                self.logger.warning("%s", self.feedback_message)
                return Status.FAILURE
        return super().update()

    def _change(self, entry: CaseLedgerEntry) -> EmbargoChange:
        embargo_id = _extract_id_from_field(
            entry.payload_snapshot.get("object")
        )
        if not embargo_id:
            raise TypeError("the Accept names no EmbargoEvent")
        return RegisterStep(kind=RegisterStepKind.ACTIVATE, embargo=embargo_id)

    def _stated_changes(
        self, entry: CaseLedgerEntry, after: EmbargoCaseFile
    ) -> list[EmbargoChange]:
        change = self._change(entry)
        assert isinstance(change, RegisterStep)
        agreement = owner_agreement(after, change.embargo_id)
        return [agreement] if agreement is not None else []


class ApplyEmbargoProposalRejectionFromLedgerNode(_EmbargoRelayEffectNode):
    """Reject the entry's proposal on the replica (ER / EJ).

    Runs :class:`DecideRejectedEmbargoProposalNode` in ``OBSERVED`` mode:
    the register rejects the proposal and EM derives from what is left
    (EP-08-001).  No consent changes.  A proposal this replica no longer
    holds as open is a no-op, so a re-delivered entry changes nothing.  So
    is the last revision with P/X/A set: the CASE_MANAGER answered that
    Reject with ET (EMB-04-002), and the termination entry that follows
    cancels the revision here as it did there (EP-08-004, ADR-0124).

    SUCCESS with nothing written when the replica holds no copy of the case
    (Regime 2, ADR-0087).  FAILURE, so the entry is not persisted
    (SYNC-12-001), when the entry names no embargo or one the replica can
    neither find nor reconstruct.
    """

    def update(self) -> Status:
        entry = self._get_entry()
        resolved = self._resolve(entry.payload_snapshot.get("object"))
        if isinstance(resolved, Status):
            return resolved
        case, embargo_id = resolved
        return self._delegate(
            DecideRejectedEmbargoProposalNode(
                case_id=case.id_,
                embargo_id=embargo_id,
                transition_mode=TransitionMode.OBSERVED,
                name=f"{self.name}.DecideRejectedEmbargoProposal",
            )
        )
