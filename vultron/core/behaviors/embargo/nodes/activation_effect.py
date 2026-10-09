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
replica directly (PCR-03-001).  Like ``ApplyEmbargoTeardownNode`` they go
through ``EmbargoLifecycle`` in ``OBSERVED`` mode (EMB-18-001): the
CASE_MANAGER already decided, so the replica syncs to the decision rather
than re-adjudicating it.
"""

from __future__ import annotations

from py_trees.common import Status

from vultron.core.behaviors.embargo.nodes.lifecycle import SetEmbargoActiveNode
from vultron.core.behaviors.embargo.nodes.reject_proposed import (
    DecideRejectedEmbargoProposalNode,
)
from vultron.core.behaviors.embargo.nodes.relay_effect import (
    _EmbargoRelayEffectNode,
)
from vultron.core.behaviors.sync.nodes.event_conditions import (
    _SingleEventTypeNode,
)
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


class ApplyEmbargoActivationFromLedgerNode(_EmbargoRelayEffectNode):
    """Activate the entry's embargo on the replica (EM → ACTIVE).

    Stores the ``EmbargoEvent`` the entry carries inline when the replica does
    not hold it (EMB-18-003), then runs ``SetEmbargoActiveNode`` in
    ``OBSERVED`` mode, which calls ``EmbargoLifecycle.activate_embargo``: the
    register activates the embargo, the owner's agreement is recorded, and
    signatories carry over to a revision that ends no later (EP-05-001).  An
    embargo already in force is a no-op, so a re-delivered entry changes
    nothing.

    SUCCESS with nothing written when the replica holds no copy of the case
    (Regime 2, ADR-0087).  FAILURE, so the entry is not persisted
    (SYNC-12-001), when the entry names no embargo, names one the replica can
    neither find nor reconstruct, or the activation fails.
    """

    def update(self) -> Status:
        entry = self._get_entry()
        resolved = self._resolve(entry.payload_snapshot.get("object"))
        if isinstance(resolved, Status):
            return resolved
        case, embargo_id = resolved
        status = self._delegate(
            SetEmbargoActiveNode(
                case_id=case.id_,
                embargo_id=embargo_id,
                transition_mode=TransitionMode.OBSERVED,
                name=f"{self.name}.SetEmbargoActive",
            )
        )
        if status == Status.SUCCESS:
            self.logger.info(
                "%s: replayed activation of embargo '%s' on case '%s'"
                " (RSH-08-004)",
                self.name,
                embargo_id,
                case.id_,
            )
        return status


class ApplyEmbargoProposalRejectionFromLedgerNode(_EmbargoRelayEffectNode):
    """Reject the entry's proposal on the replica (ER / EJ).

    Runs :class:`DecideRejectedEmbargoProposalNode` in ``OBSERVED`` mode:
    the register rejects the proposal and EM derives from what is left
    (EP-08-001).  No consent changes.  A proposal this replica no longer
    holds as open is a no-op, so a re-delivered entry changes nothing.

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
