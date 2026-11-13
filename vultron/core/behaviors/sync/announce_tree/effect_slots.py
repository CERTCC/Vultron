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

"""The replica's per-entry effect slots of the ``Announce(CaseLedgerEntry)`` tree.

Each slot applies one kind of ledger entry to the replica's copy of the
case, and is a no-op for every other kind (SYNC-12-004).
"""

from collections.abc import Callable

import py_trees

from vultron.core.behaviors.embargo.nodes import (
    ApplyCreatedEmbargoFromLedgerNode,
    ApplyEmbargoAbandonmentFromLedgerNode,
    ApplyEmbargoAcceptanceFromLedgerNode,
    ApplyEmbargoActivationFromLedgerNode,
    ApplyEmbargoInviteFromLedgerNode,
    ApplyEmbargoProposalFromLedgerNode,
    ApplyEmbargoProposalRejectionFromLedgerNode,
    ApplyEmbargoRejectionFromLedgerNode,
    ApplyEmbargoTeardownNode,
    ApplyEmbargoWithdrawalFromLedgerNode,
    IsActivateEmbargoEventNode,
    IsRejectEmbargoProposalEventNode,
)
from vultron.core.behaviors.sync.nodes import (
    ApplyCaseParticipantRoleGrantFromLedgerNode,
    ApplyCaseParticipantUpdateFromLedgerNode,
    ApplyCaseReferenceFromLedgerNode,
    ApplyCaseStatusFromLedgerNode,
    ApplyCreateCaseParticipantFromLedgerNode,
    ApplyInviteAcceptFromLedgerNode,
    ApplyInviteRejectFromLedgerNode,
    ApplyNoteFromLedgerNode,
    ApplyOfferReportFromLedgerNode,
    ApplyOwnershipTransferFromLedgerNode,
    ApplyParticipantStatusFromLedgerNode,
    ApplyReinstateCaseParticipantFromLedgerNode,
    ApplyRemoveCaseParticipantFromLedgerNode,
    ApplyRemoveNoteFromLedgerNode,
    ApplyVulnerabilityItemFromLedgerNode,
    IsAcceptCaseParticipantRoleEventNode,
    IsAcceptEmbargoInviteEventNode,
    IsAddCaseReferenceEventNode,
    IsAddCaseStatusEventNode,
    IsAddNoteEventNode,
    IsAddVulnerabilityItemEventNode,
    IsCreateCaseParticipantEventNode,
    IsCreateEmbargoEventNode,
    IsEmbargoAbandonmentEventNode,
    IsEmbargoInviteRelayEventNode,
    IsEmbargoProposalEventNode,
    IsInviteAcceptEventNode,
    IsInviteRejectEventNode,
    IsOwnershipTransferEventNode,
    IsParticipantStatusEventNode,
    IsReinstateCaseParticipantEventNode,
    IsRejectEmbargoInviteEventNode,
    IsRemoveCaseParticipantEventNode,
    IsRemoveEmbargoEventNode,
    IsRemoveNoteEventNode,
    IsSubmitReportEventNode,
    IsUndoEmbargoInviteEventNode,
    IsUpdateCaseParticipantEventNode,
    IsWithdrawFromEmbargoEventNode,
)
from vultron.core.behaviors.sync.nodes.embargo_copy_effect import (
    ApplyEmbargoConsentFromLedgerNode,
    IsEmbargoConsentEventNode,
)
from vultron.core.behaviors.sync.nodes.participant_status_effect import (
    EmitImpossibleStateFaultNode,
)


def _event_effect_slot(
    label: str,
    condition: Callable[..., py_trees.behaviour.Behaviour],
    apply: Callable[..., py_trees.behaviour.Behaviour],
) -> py_trees.behaviour.Behaviour:
    """Build one ``Selector(Seq(IsX, ApplyX), Inverter(IsX))`` effect slot.

    *label* names the slot (``"<label>Effects"``) and its nodes, so a tree
    dump reads the same for every slot.  ``ParticipantStatusEffects`` alone is
    built by hand: its apply step is an ``ApplyOrFault`` selector (RSH-09-006, RSH-09-013).
    """
    return py_trees.composites.Selector(
        name=f"{label}Effects",
        memory=False,
        children=[
            py_trees.composites.Sequence(
                name=f"Apply{label}EffectsSeq",
                memory=False,
                children=[
                    condition(name=f"Is{label}Event"),
                    apply(name=f"Apply{label}FromLedger"),
                ],
            ),
            py_trees.decorators.Inverter(
                name=f"SkipIfNot{label}Event",
                child=condition(name=f"CheckNot{label}Event"),
            ),
        ],
    )


def _embargo_relay_effect_slots() -> list[py_trees.behaviour.Behaviour]:
    """The embargo negotiation's replay slots (EP-09-007, RSH-08-004, ADR-0113).

    An embargo the case's creation wrote (#5122), the proposal the
    CASE_MANAGER received, each Invite it relayed (a re-invite among them,
    EMB-17-003), each participant's ``Accept`` or
    ``Reject`` of an Invite — the sender's own consent, an honoured late
    ``Accept`` included (EMB-17-002) — a signatory's withdrawal from the
    embargo in force (MSM-07-010), the manager's abandonment of an open
    proposal once P/X/A is set, its ``Reject`` and ``Undo`` entries
    (EMB-16-001, ADR-0152), and the manager's own consent-row entries.
    """
    return [
        _event_effect_slot(
            "CreatedEmbargo",
            IsCreateEmbargoEventNode,
            ApplyCreatedEmbargoFromLedgerNode,
        ),
        _event_effect_slot(
            "EmbargoProposal",
            IsEmbargoProposalEventNode,
            ApplyEmbargoProposalFromLedgerNode,
        ),
        _event_effect_slot(
            "EmbargoInviteRelay",
            IsEmbargoInviteRelayEventNode,
            ApplyEmbargoInviteFromLedgerNode,
        ),
        _event_effect_slot(
            "EmbargoAcceptance",
            IsAcceptEmbargoInviteEventNode,
            ApplyEmbargoAcceptanceFromLedgerNode,
        ),
        _event_effect_slot(
            "EmbargoRejection",
            IsRejectEmbargoInviteEventNode,
            ApplyEmbargoRejectionFromLedgerNode,
        ),
        _event_effect_slot(
            "EmbargoWithdrawal",
            IsWithdrawFromEmbargoEventNode,
            ApplyEmbargoWithdrawalFromLedgerNode,
        ),
        # The CASE_MANAGER's abandonment of an open proposal (EMB-16-001,
        # ADR-0152): its Reject of the proposal it received, told from a
        # participant's Reject by the payload's actor, then its Undo of each
        # Invite it sent for the proposal.  Each is the proposal's CANCEL
        # step; the first moves the register and the rest find it in place.
        _event_effect_slot(
            "EmbargoAbandonment",
            IsEmbargoAbandonmentEventNode,
            ApplyEmbargoAbandonmentFromLedgerNode,
        ),
        _event_effect_slot(
            "EmbargoInviteWithdrawal",
            IsUndoEmbargoInviteEventNode,
            ApplyEmbargoAbandonmentFromLedgerNode,
        ),
        # The CASE_MANAGER's own consent-row entries, each one row copied
        # through the one apply function (ADR-0122, ADR-0124, CM-23-016).
        _event_effect_slot(
            "EmbargoConsent",
            IsEmbargoConsentEventNode,
            ApplyEmbargoConsentFromLedgerNode,
        ),
    ]


def create_log_entry_event_effects() -> py_trees.composites.Sequence:
    """Build ``LogEntryEventEffects``, one effect slot per kind of entry."""
    # Each effect slot uses Selector(Seq(IsX, ApplyX), Inverter(IsX)) instead
    # of Selector(Seq(IsX, ApplyX), Success("Skipped")).
    #
    # The Inverter fires SUCCESS only when the condition does NOT match (routing
    # no-op for the wrong semantic type).  When the condition matches but ApplyX
    # fails, both branches of the Selector fail, so the FAILURE propagates to
    # LogEntryEventEffects and blocks PersistReceivedLogEntry (SYNC-12-004).
    return py_trees.composites.Sequence(
        name="LogEntryEventEffects",
        memory=False,
        children=[
            _event_effect_slot(
                "EmbargoTeardown",
                IsRemoveEmbargoEventNode,
                ApplyEmbargoTeardownNode,
            ),
            # The case owner's decision on a proposal (ADR-0122).
            _event_effect_slot(
                "EmbargoActivation",
                IsActivateEmbargoEventNode,
                ApplyEmbargoActivationFromLedgerNode,
            ),
            _event_effect_slot(
                "EmbargoProposalRejection",
                IsRejectEmbargoProposalEventNode,
                ApplyEmbargoProposalRejectionFromLedgerNode,
            ),
            _event_effect_slot(
                "CaseStatus",
                IsAddCaseStatusEventNode,
                ApplyCaseStatusFromLedgerNode,
            ),
            # No RmVerdict slot: a report verdict, an engagement decision or a
            # full-case Invite reply records the act, and the status the
            # CASE_MANAGER wrote for it arrives as the participant-status
            # entry after it, copied below (CLP-07-013, CM-23-016).
            py_trees.composites.Selector(
                name="ParticipantStatusEffects",
                memory=False,
                children=[
                    py_trees.composites.Sequence(
                        name="ApplyParticipantStatusEffectsSeq",
                        memory=False,
                        children=[
                            IsParticipantStatusEventNode(
                                name="IsParticipantStatusEvent"
                            ),
                            # RSH-09-006, RSH-09-013: either Apply succeeds or fault is
                            # emitted to CaseActor and FAILURE propagates.
                            py_trees.composites.Selector(
                                name="ApplyOrFault",
                                memory=False,
                                children=[
                                    ApplyParticipantStatusFromLedgerNode(
                                        name="ApplyParticipantStatusFromLedger"
                                    ),
                                    EmitImpossibleStateFaultNode(
                                        name="EmitImpossibleStateFault"
                                    ),
                                ],
                            ),
                        ],
                    ),
                    py_trees.decorators.Inverter(
                        name="SkipIfNotParticipantStatusEvent",
                        child=IsParticipantStatusEventNode(
                            name="CheckNotParticipantStatusEvent"
                        ),
                    ),
                ],
            ),
            _event_effect_slot(
                "Note",
                IsAddNoteEventNode,
                ApplyNoteFromLedgerNode,
            ),
            # A case's items and references, each one Add carrying the
            # record in full (CLP-07-021).
            _event_effect_slot(
                "VulnerabilityItem",
                IsAddVulnerabilityItemEventNode,
                ApplyVulnerabilityItemFromLedgerNode,
            ),
            _event_effect_slot(
                "CaseReference",
                IsAddCaseReferenceEventNode,
                ApplyCaseReferenceFromLedgerNode,
            ),
            # Unreachable from this implementation's CASE_MANAGER, which
            # commits no remove_note_from_case entry: removing ledgered
            # content has no defined meaning yet (CM-30-003, #6430).  Kept so
            # a replica can still replay such an entry if a ledger holds one.
            _event_effect_slot(
                "RemoveNote",
                IsRemoveNoteEventNode,
                ApplyRemoveNoteFromLedgerNode,
            ),
            # The ledger holds the wire messages exchanged (ADR-0114): creating
            # the record is the CASE_MANAGER's own act and has its own entry; the
            # invitee's Accept and Reject are the entries for their own effects.
            _event_effect_slot(
                "CreateCaseParticipant",
                IsCreateCaseParticipantEventNode,
                ApplyCreateCaseParticipantFromLedgerNode,
            ),
            _event_effect_slot(
                "InviteAccept",
                IsInviteAcceptEventNode,
                ApplyInviteAcceptFromLedgerNode,
            ),
            _event_effect_slot(
                "InviteReject",
                IsInviteRejectEventNode,
                ApplyInviteRejectFromLedgerNode,
            ),
            # The Case Owner's removal of a participant (CM-31-007).
            _event_effect_slot(
                "RemoveCaseParticipant",
                IsRemoveCaseParticipantEventNode,
                ApplyRemoveCaseParticipantFromLedgerNode,
            ),
            # The Case Owner's reinstatement of a participant (CM-31-011).
            _event_effect_slot(
                "ReinstateCaseParticipant",
                IsReinstateCaseParticipantEventNode,
                ApplyReinstateCaseParticipantFromLedgerNode,
            ),
            # No CloseCase slot: close_case records the received Leave, and
            # the RM moves it caused arrive as the participant-status entries
            # after it, copied above.  A replica never walks a closure path
            # from its own stored state (CM-23-023, CM-23-044, #4091).
            _event_effect_slot(
                "OfferReport",
                IsSubmitReportEventNode,
                ApplyOfferReportFromLedgerNode,
            ),
            # An ownership transfer's consequences, each the CASE_MANAGER's
            # own entry after the Accept (CLP-07-013, ADR-0124): every
            # participant record whose CASE_OWNER role moved, then the case
            # naming its new owner.  The Accept entry itself moves nothing.
            _event_effect_slot(
                "UpdateCaseParticipant",
                IsUpdateCaseParticipantEventNode,
                ApplyCaseParticipantUpdateFromLedgerNode,
            ),
            _event_effect_slot(
                "OwnershipTransfer",
                IsOwnershipTransferEventNode,
                ApplyOwnershipTransferFromLedgerNode,
            ),
            # No OfferOwnershipTransfer slot: the transferee answers the
            # CASE_MANAGER's Offer from the body its intake recorded, the owner holds
            # its own proposal, and a bystander never answers, so the entry
            # has nothing to apply at a replica (ADR-0148, SYNC-12-001).
            # Accepting a delegated role grants it to the target participant
            # (CM-02-020, ADR-0039); the offer half carries no grant (#3764).
            _event_effect_slot(
                "RoleGrant",
                IsAcceptCaseParticipantRoleEventNode,
                ApplyCaseParticipantRoleGrantFromLedgerNode,
            ),
            *_embargo_relay_effect_slots(),
        ],
    )
