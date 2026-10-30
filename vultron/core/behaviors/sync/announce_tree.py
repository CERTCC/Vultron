#!/usr/bin/env python
"""Behavior tree factory for inbound Announce(CaseLedgerEntry) handling."""

from collections.abc import Callable

import py_trees

from vultron.core.behaviors.case.nodes.conditions import CheckIsCaseManagerNode
from vultron.core.behaviors.case.receive_activity_tree import (
    create_receive_activity_tree,
)
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
    CheckEntryAgreesWithCasePositionNode,
    CheckEntryHashIntactNode,
    CheckHashOrRejectOnMismatchNode,
    CheckLedgerEntryAlreadyStoredNode,
    EntryReflectedByCaseCopyNode,
    IsAcceptCaseParticipantRoleEventNode,
    IsAcceptEmbargoInviteEventNode,
    IsAddCaseStatusEventNode,
    IsAddNoteEventNode,
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
    LogDeliveryConfirmationNode,
    PersistReceivedLogEntryNode,
    ReconstructChainTailNode,
    ReplayHeldSuccessorNode,
    SendRejectLogEntryNode,
)
from vultron.core.behaviors.sync.nodes.case_copy_effect import (
    StoreRecordsReflectedEntryCarriesNode,
)
from vultron.core.behaviors.sync.nodes.embargo_copy_effect import (
    ApplyEmbargoConsentFromLedgerNode,
    IsEmbargoConsentEventNode,
)
from vultron.core.behaviors.sync.nodes.ledger_entry_fault import (
    EmitLedgerEntryFaultNode,
)
from vultron.core.behaviors.sync.nodes.participant_status_effect import (
    EmitImpossibleStateFaultNode,
)
from vultron.core.models.fault_classes import (
    VULTRON_FAILURE_LEDGER_ENTRY_REFUSED_HASH_MISMATCH,
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
    # Both role checks read a case this actor does not hold as "not the
    # CASE_MANAGER" (ADR-0087 Regime 3): the manager holds every case it
    # manages, and a participant in the pre-genesis window takes the
    # participant arm, whose replay Reject repairs it (SYNC-15-001, #5513).
    case_actor_subtree = py_trees.composites.Sequence(
        name="CaseActorSubtree",
        memory=False,
        children=[
            CheckIsCaseManagerNode(
                name=AT_CASE_MANAGER, case_may_be_absent=True
            ),
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
    # Wrap reconstruct in a Selector so that on failure we (1) hold the received
    # Announce so the case-seed path can replay it once the genesis anchor is
    # known (SYNC-15-004, SYNC-15-005, #2186), and (2) still send a Reject
    # (stating no ledger position, read as "replay from genesis") as the loss
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
                    # Fallback: send the Reject, with the sentinel tail_hash=""
                    # ReconstructChainTailNode wrote before failing keying its
                    # id; it states no ledger position (SYNC-18-001).
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
            # An entry at the case's position with another hash is from a
            # different chain than the copy that set it: refused at ERROR,
            # never stored as a no-op (SYNC-16-007).
            CheckEntryAgreesWithCasePositionNode(
                name="CheckEntryAgreesWithCasePosition"
            ),
            # An entry the case copy that replaced this replica's case
            # already reflects is stored without its effects, an idempotent
            # no-op: applying it again over the copy could move the case
            # backwards, or refuse an entry the copy is past.  Only the
            # records it carries that the copy names by id are copied
            # (SYNC-16-007, CM-23-016).
            py_trees.composites.Selector(
                name="ApplyEffectsUnlessReflected",
                memory=False,
                children=[
                    py_trees.composites.Sequence(
                        name="StoreReflectedEntry",
                        memory=False,
                        children=[
                            EntryReflectedByCaseCopyNode(
                                name="EntryReflectedByCaseCopy"
                            ),
                            StoreRecordsReflectedEntryCarriesNode(
                                name="StoreRecordsReflectedEntryCarries"
                            ),
                        ],
                    ),
                    # A reflected entry whose records fail to store must not
                    # fall through to its effects: the guard is repeated so
                    # that branch admits only an entry the copy lacks.
                    py_trees.composites.Sequence(
                        name="ApplyUnreflectedEntry",
                        memory=False,
                        children=[
                            py_trees.decorators.Inverter(
                                name="EntryNotReflectedByCaseCopy",
                                child=EntryReflectedByCaseCopyNode(
                                    name="CheckEntryReflectedByCaseCopy"
                                ),
                            ),
                            log_entry_event_effects,
                        ],
                    ),
                ],
            ),
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
                child=CheckIsCaseManagerNode(
                    name="CheckIsCaseManagerInverse", case_may_be_absent=True
                ),
            ),
            # An entry that fails its own hash is refused before it can be
            # buffered, applied or stored, and before the already-stored
            # shortcut could skip it unlogged (SYNC-03-006).  The refusal is
            # reported to the CASE_MANAGER with its own fault, and the
            # Selector still fails (SYNC-03-007).
            py_trees.composites.Selector(
                name="HashIntactOrFault",
                memory=False,
                children=[
                    CheckEntryHashIntactNode(name="CheckEntryHashIntact"),
                    EmitLedgerEntryFaultNode(
                        VULTRON_FAILURE_LEDGER_ENTRY_REFUSED_HASH_MISMATCH,
                        name="EmitHashMismatchFault",
                    ),
                ],
            ),
            entry_processing,
            # The entry this delivery stored (or found stored) may be the
            # predecessor a held Announce waits on.  That Announce, as it was
            # received, is replayed through this actor's inbox as its own
            # delivery; its tree replays the next one (SYNC-14-009, ADR-0135).
            ReplayHeldSuccessorNode(name="ReplayHeldSuccessor"),
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
