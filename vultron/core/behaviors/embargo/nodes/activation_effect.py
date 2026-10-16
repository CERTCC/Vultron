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
The rejection copies the same way: the ``Reject`` entry is the whole
``REJECT`` step, unless the CASE_MANAGER answered it with ET (EMB-04-002).
Deciding that exception on the replica is a tracked deviation from
CM-23-016 (#4789); see :class:`ApplyEmbargoProposalRejectionFromLedgerNode`.
"""

from __future__ import annotations

from py_trees.common import Status

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
from vultron.core.models.embargo_event import EmbargoEvent
from vultron.core.models.events.base import MessageSemantics
from vultron.core.predicates.embargo import (
    pxa_is_embargo_eligible,
    rejection_ends_embargo,
)
from vultron.core.services.carried_embargo import carried_entry_embargo
from vultron.core.states.embargo_register import EmbargoRegisterStatus
from vultron.errors import VultronError

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
    replica does not hold it, once the step has applied (EMB-18-003); a bare
    id it does not hold, or a copy that belongs to another case, fails.
    An embargo already activated is in place, so a re-delivered entry changes
    nothing.  An entry naming an embargo that is not an open proposal here
    is refused into the gap buffer (ADR-0124); one that names no embargo
    fails, so it is not persisted (SYNC-12-001).  SUCCESS with nothing
    written when the replica holds no copy of the case (Regime 2, ADR-0087).
    """

    def update(self) -> Status:
        # The register entry this activates names an embargo this store must
        # hold (EMB-18-003).  The entry carries it inline: check it here,
        # store it once the step has applied, so a refused entry stores
        # nothing.
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None
        entry = self._get_entry()
        pending: EmbargoEvent | None = None
        if self._resolve_case_replica(entry.case_id) is not None:
            try:
                pending = carried_entry_embargo(
                    self.datalayer,
                    entry.case_id,
                    entry.payload_snapshot.get("object"),
                )
            except VultronError as exc:
                self.feedback_message = f"{self.name}: {exc}"
                self.logger.warning("%s", self.feedback_message)
                return Status.FAILURE
        status = super().update()
        if status == Status.SUCCESS and pending is not None:
            self.datalayer.save(pending)
        return status

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


class ApplyEmbargoProposalRejectionFromLedgerNode(
    ApplyEmbargoChangeFromLedgerNode
):
    """Copy the owner's rejection onto the replica (ER / EJ).

    The entry's ``object`` names the proposal, and the entry is the whole
    ``REJECT`` register step: the proposal is rejected and EM derives from
    what is left (EP-08-001).  No consent changes, the owner's included
    (MSM-07-009).  A rejection already in place, so a re-delivered entry,
    changes nothing.

    The owner's rejection of the last revision after disclosure changes
    nothing here either: the CASE_MANAGER answered it with ET rather than
    returning to the prior terms (EMB-04-002), and the ``Remove`` entry that
    follows carries the ``TERMINATE`` step that cancels the revision
    (EP-08-004).  A seeded replica already past that ``Remove`` (the
    revision ``CANCELLED``, the embargo ``TERMINATED``, P/X/A set) skips the
    entry too (ADR-0114).  A revision cancelled any other way has diverged,
    so the entry is refused.

    Tracked deviation from CM-23-016 (#4789): deciding that skip is
    lifecycle logic on replay.  It reads only the case file, so two
    replicas at one ledger position still hold the same case, but it
    evaluates the EMB-04-002 rule and infers a past termination from the
    seed instead of copying what the entry states.  It stays until #4789
    decides how the ledger records a ``Reject`` answered with ET; without it
    the replica would hold the revision ``REJECTED`` where the CASE_MANAGER
    holds it ``CANCELLED`` (#4364).

    An entry naming an embargo that is not an open proposal here is refused
    into the gap buffer (ADR-0124); one that names no embargo fails, so it
    is not persisted (SYNC-12-001).  SUCCESS with nothing written when the
    replica holds no copy of the case (Regime 2, ADR-0087).
    """

    def _change(self, entry: CaseLedgerEntry) -> EmbargoChange:
        embargo_id = _extract_id_from_field(
            entry.payload_snapshot.get("object")
        )
        if not embargo_id:
            raise TypeError("the Reject names no EmbargoEvent")
        return RegisterStep(kind=RegisterStepKind.REJECT, embargo=embargo_id)

    def _left_to_a_later_entry(
        self, before: EmbargoCaseFile, change: EmbargoChange
    ) -> bool:
        # Tracked deviation from CM-23-016 (#4789): this decides a lifecycle
        # rule on replay rather than copying; see the class docstring.
        assert isinstance(change, RegisterStep)
        case = before.case
        if rejection_ends_embargo(case, change.embargo_id):
            return True
        # A seed past that termination: the revision was cancelled in the
        # TERMINATE step, after P/X/A was set.  A revision cancelled any
        # other way has diverged from the CASE_MANAGER, which commits a
        # Reject only for an open proposal, so it stays refused (ADR-0124).
        held = case.embargo_register_entry(change.embargo_id)
        return (
            held is not None
            and held.status is EmbargoRegisterStatus.CANCELLED
            and any(
                entry.status is EmbargoRegisterStatus.TERMINATED
                for entry in case.embargo_register
            )
            and not pxa_is_embargo_eligible(case.current_status.pxa.state)
        )
