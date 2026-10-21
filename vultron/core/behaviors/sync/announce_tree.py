#!/usr/bin/env python
"""Behavior tree factory for inbound Announce(CaseLedgerEntry) handling."""

from collections.abc import Callable

import py_trees

from vultron.core.behaviors.case.nodes.conditions import CheckIsCaseManagerNode
from vultron.core.behaviors.case.receive_activity_tree import (
    create_receive_activity_tree,
)
from vultron.core.behaviors.embargo.nodes import (
    ApplyEmbargoAbandonmentFromLedgerNode,
    ApplyEmbargoAcceptanceFromLedgerNode,
    ApplyEmbargoActivationFromLedgerNode,
    ApplyEmbargoInviteFromLedgerNode,
    ApplyEmbargoProposalFromLedgerNode,
    ApplyEmbargoProposalRejectionFromLedgerNode,
    ApplyEmbargoReinviteFromLedgerNode,
    ApplyEmbargoRejectionFromLedgerNode,
    ApplyEmbargoTeardownNode,
    ApplyEmbargoWithdrawalFromLedgerNode,
    ApplyInviteExpiryNoopFromLedgerNode,
    IsActivateEmbargoEventNode,
    IsRejectEmbargoProposalEventNode,
)
from vultron.core.behaviors.sender_entitlement import SenderRule
from vultron.core.behaviors.sender_guard import LedgerActivityContext
from vultron.core.behaviors.sync.nodes import (
    ApplyCaseParticipantRoleGrantFromLedgerNode,
    ApplyCaseParticipantUpdateFromLedgerNode,
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
    BufferPreGenesisEntryNode,
    CheckEntryHashIntactNode,
    CheckHashOrRejectOnMismatchNode,
    CheckLedgerEntryAlreadyStoredNode,
    HandBackBufferedSuccessorNode,
    IsAcceptCaseParticipantRoleEventNode,
    IsAcceptEmbargoInviteEventNode,
    IsAddCaseStatusEventNode,
    IsAddNoteEventNode,
    IsCreateCaseParticipantEventNode,
    IsEmbargoAbandonmentEventNode,
    IsEmbargoInviteRelayEventNode,
    IsEmbargoProposalEventNode,
    IsEmbargoReinviteEventNode,
    IsInviteAcceptEventNode,
    IsInviteExpiryNoopEventNode,
    IsInviteRejectEventNode,
    IsOwnershipTransferEventNode,
    IsParticipantStatusEventNode,
    IsReinstateCaseParticipantEventNode,
    IsRejectEmbargoInviteEventNode,
    IsRemoveCaseParticipantEventNode,
    IsRemoveEmbargoEventNode,
    IsRemoveNoteEventNode,
    IsSubmitReportEventNode,
    IsUpdateCaseParticipantEventNode,
    IsWithdrawFromEmbargoEventNode,
    LogDeliveryConfirmationNode,
    PersistReceivedLogEntryNode,
    ReconstructChainTailNode,
    SendRejectLogEntryNode,
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
    built by hand: its apply step is an ``ApplyOrFault`` selector (RSH-09-006).
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

    The proposal the CASE_MANAGER received, each Invite it relayed, each
    ``Accept``/``Reject`` of an Invite — each sender's own consent — each
    invite expiry the CASE_MANAGER evaluated (CM-28-014, ADR-0118), each
    honour decision for a late Accept whose embargo is still active
    (EMB-17-001, ADR-0118), each no-op acknowledgement of a late Accept with
    no active embargo (EMB-17-004, ADR-0118), the manager's abandonment
    of an open proposal once P/X/A is set (EMB-16-001), and a signatory's
    withdrawal from the embargo in force (MSM-07-010).
    """
    return [
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
            "EmbargoReinvite",
            IsEmbargoReinviteEventNode,
            ApplyEmbargoReinviteFromLedgerNode,
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
        _event_effect_slot(
            "InviteExpiryNoop",
            IsInviteExpiryNoopEventNode,
            ApplyInviteExpiryNoopFromLedgerNode,
        ),
        _event_effect_slot(
            "EmbargoAbandonment",
            IsEmbargoAbandonmentEventNode,
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


#: The role check of the CASE_MANAGER arm: past the sender guard, an
#: announcement it admits is the CASE_MANAGER's own, echoed back.
AT_CASE_MANAGER = "CheckIsCaseManager"


def create_announce_log_entry_tree(
    *, sender_rule: SenderRule
) -> py_trees.behaviour.Behaviour:
    """Create the BT for an inbound ``Announce(CaseLedgerEntry)``.

    The sender must be the CASE_MANAGER of the case the announced entry
    names (SYNC-13-006, HP-01-006).  The factory composes that guard from the
    use case's declared rule, ahead of both role arms; its node reads the case
    from the entry when the tree runs
    (:class:`~vultron.core.behaviors.sender_guard.LedgerActivityContext`).
    At the CASE_MANAGER an admitted announcement is therefore its own, echoed
    back, and only confirms delivery; at a participant it is processed
    against the local chain.

    Args:
        sender_rule: The use case's declared sender rule (HP-01-008).
    """
    case_actor_subtree = py_trees.composites.Sequence(
        name="CaseActorSubtree",
        memory=False,
        children=[
            CheckIsCaseManagerNode(name=AT_CASE_MANAGER),
            LogDeliveryConfirmationNode(name="LogDeliveryConfirmation"),
        ],
    )
    # Each effect slot uses Selector(Seq(IsX, ApplyX), Inverter(IsX)) instead
    # of Selector(Seq(IsX, ApplyX), Success("Skipped")).
    #
    # The Inverter fires SUCCESS only when the condition does NOT match (routing
    # no-op for the wrong semantic type).  When the condition matches but ApplyX
    # fails, both branches of the Selector fail, so the FAILURE propagates to
    # LogEntryEventEffects and blocks PersistReceivedLogEntry (SYNC-12-001).
    log_entry_event_effects = py_trees.composites.Sequence(
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
                            # RSH-09-006: either Apply succeeds or fault is
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
            # from its own stored state (CM-23-001, CM-23-016, #4091).
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
            # CASE_MANAGER's Offer from its intake archive, the owner holds
            # its own proposal, and a bystander never answers, so the entry
            # has nothing to apply at a replica (ADR-0148, SYNC-12-001).
            # Accepting a delegated role grants it to the target participant
            # (CM-02-016, ADR-0039); the offer half carries no grant (#3764).
            _event_effect_slot(
                "RoleGrant",
                IsAcceptCaseParticipantRoleEventNode,
                ApplyCaseParticipantRoleGrantFromLedgerNode,
            ),
            *_embargo_relay_effect_slots(),
        ],
    )
    # When the VulnerabilityCase is not yet seeded on this replica, chain tail
    # reconstruction fails and no tail_hash is available for the mismatch check.
    # Wrap reconstruct in a Selector so that on failure we (1) park the entry in
    # the actor-local gap buffer so the case-seed path can drain it once the
    # genesis anchor is known (SYNC-15-004, #2186), and (2) still send a Reject
    # (with last_accepted_hash="" meaning "replay from genesis") as the loss
    # backstop, exiting the Sequence without persisting the entry (SYNC-15-001,
    # CLP-08-005).  FailureIsSuccess lets the reject fire whether or not the
    # entry was buffered, mirroring CheckHashOrRejectOnMismatchNode's forward-gap
    # buffer-and-reject structure.
    reconstruct_or_reject = py_trees.composites.Selector(
        name="ReconstructOrRejectOnMissingCase",
        memory=False,
        children=[
            ReconstructChainTailNode(name="ReconstructChainTail"),
            py_trees.composites.Sequence(
                name="BufferAndRejectOnMissingCase",
                memory=False,
                children=[
                    py_trees.decorators.FailureIsSuccess(
                        name="BufferIfPreGenesis",
                        child=BufferPreGenesisEntryNode(
                            name="BufferPreGenesisEntry"
                        ),
                    ),
                    # Fallback: send Reject carrying the sentinel tail_hash=""
                    # that ReconstructChainTailNode wrote before failing.
                    SendRejectLogEntryNode(name="RejectOnMissingCase"),
                ],
            ),
        ],
    )
    process_and_store = py_trees.composites.Sequence(
        name="ProcessAndStore",
        memory=False,
        children=[
            reconstruct_or_reject,
            CheckHashOrRejectOnMismatchNode(
                name="CheckHashOrRejectOnMismatch"
            ),
            log_entry_event_effects,
            PersistReceivedLogEntryNode(name="PersistReceivedLogEntry"),
        ],
    )
    entry_processing = py_trees.composites.Selector(
        name="EntryProcessing",
        memory=False,
        children=[
            CheckLedgerEntryAlreadyStoredNode(
                name="CheckLogEntryAlreadyStored"
            ),
            process_and_store,
        ],
    )
    participant_subtree = py_trees.composites.Sequence(
        name="ParticipantGate",
        memory=False,
        children=[
            py_trees.decorators.Inverter(
                name="CheckIsNotCaseManager",
                child=CheckIsCaseManagerNode(name="CheckIsCaseManagerInverse"),
            ),
            # An entry that fails its own hash is refused before it can be
            # buffered, applied or stored, and before the already-stored
            # shortcut could skip it unlogged (SYNC-03-006).
            CheckEntryHashIntactNode(name="CheckEntryHashIntact"),
            entry_processing,
            # The entry this delivery stored (or found stored) may be the
            # predecessor a buffered entry waits on.  That successor is its
            # own delivery, handed back to this actor's inbox; its tree hands
            # back the next one (SYNC-14-009, ADR-0135).
            HandBackBufferedSuccessorNode(name="HandBackBufferedSuccessor"),
        ],
    )
    # The replication envelope is never itself a canonical entry (CLP-10-004),
    # so there is no commit stage (``case_id=None``); intake archives the
    # received Announce only and leaves the inlined entry to the chain check.
    return create_receive_activity_tree(
        name="AnnounceLogEntryReceivedBT",
        case_id=None,
        precondition_guards=[],
        sender_rule=sender_rule,
        sender_context=LedgerActivityContext(),
        replica_effects=[
            py_trees.composites.Selector(
                name="AnnounceLogEntryRoles",
                memory=False,
                children=[case_actor_subtree, participant_subtree],
            )
        ],
    )
