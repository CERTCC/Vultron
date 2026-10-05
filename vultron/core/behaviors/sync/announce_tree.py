#!/usr/bin/env python
"""Behavior tree factory for inbound Announce(CaseLedgerEntry) handling."""

from collections.abc import Callable

import py_trees

from vultron.core.behaviors.case.nodes.close_case_effect import (
    ApplyCloseCaseFromLedgerNode,
)
from vultron.core.behaviors.case.nodes.conditions import CheckIsCaseManagerNode
from vultron.core.behaviors.embargo.nodes import (
    ApplyEmbargoAbandonmentFromLedgerNode,
    ApplyEmbargoAcceptanceFromLedgerNode,
    ApplyEmbargoInviteFromLedgerNode,
    ApplyEmbargoProposalFromLedgerNode,
    ApplyEmbargoRejectionFromLedgerNode,
    ApplyEmbargoTeardownNode,
    ApplyHonourLateAcceptFromLedgerNode,
    ApplyInviteExpiryFromLedgerNode,
    ApplyInviteExpiryNoopFromLedgerNode,
)
from vultron.core.behaviors.sync.nodes import (
    ApplyInviteAcceptFromLedgerNode,
    ApplyNoteFromLedgerNode,
    ApplyOfferOwnershipTransferFromLedgerNode,
    ApplyOfferReportFromLedgerNode,
    ApplyOwnershipTransferFromLedgerNode,
    ApplyParticipantStatusFromLedgerNode,
    BufferPreGenesisEntryNode,
    CheckHashOrRejectOnMismatchNode,
    CheckLedgerEntryAlreadyStoredNode,
    IsAcceptEmbargoInviteEventNode,
    IsAddNoteEventNode,
    IsCloseCaseEventNode,
    IsEmbargoAbandonmentEventNode,
    IsEmbargoInviteRelayEventNode,
    IsEmbargoProposalEventNode,
    IsHonourLateAcceptEventNode,
    IsInviteAcceptEventNode,
    IsInviteExpiryEventNode,
    IsInviteExpiryNoopEventNode,
    IsOfferOwnershipTransferEventNode,
    IsOwnershipTransferEventNode,
    IsParticipantStatusEventNode,
    IsRejectEmbargoInviteEventNode,
    IsRemoveEmbargoEventNode,
    IsSubmitReportEventNode,
    LogDeliveryConfirmationNode,
    PersistReceivedLogEntryNode,
    ReconstructChainTailNode,
    SendRejectLogEntryNode,
    VerifySenderIsCaseActorNode,
    VerifySenderIsOwnIdNode,
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
    built by hand: its apply step is an ``ApplyOrFault`` selector (RSH-05-021).
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
    ``Accept``/``Reject`` of an Invite — the owner's decision included — each
    invite expiry the CASE_MANAGER evaluated (CM-28-014, ADR-0118), each
    honour decision for a late Accept whose embargo is still active
    (EMB-17-001, ADR-0118), each no-op acknowledgement of a late Accept with
    no active embargo (EMB-17-004, ADR-0118), and the manager's abandonment
    of an open proposal once P/X/A is set (EMB-16-001).
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
            "InviteExpiry",
            IsInviteExpiryEventNode,
            ApplyInviteExpiryFromLedgerNode,
        ),
        _event_effect_slot(
            "InviteExpiryNoop",
            IsInviteExpiryNoopEventNode,
            ApplyInviteExpiryNoopFromLedgerNode,
        ),
        _event_effect_slot(
            "InviteHonourLateAccept",
            IsHonourLateAcceptEventNode,
            ApplyHonourLateAcceptFromLedgerNode,
        ),
        _event_effect_slot(
            "EmbargoAbandonment",
            IsEmbargoAbandonmentEventNode,
            ApplyEmbargoAbandonmentFromLedgerNode,
        ),
    ]


def create_announce_log_entry_tree() -> py_trees.behaviour.Behaviour:
    case_actor_subtree = py_trees.composites.Sequence(
        name="CaseActorSubtree",
        memory=False,
        children=[
            CheckIsCaseManagerNode(name="CheckIsCaseManager"),
            VerifySenderIsOwnIdNode(name="VerifySenderIsOwnId"),
            LogDeliveryConfirmationNode(name="LogDeliveryConfirmation"),
        ],
    )
    # Each effect slot uses Selector(Seq(IsX, ApplyX), Inverter(IsX)) instead
    # of Selector(Seq(IsX, ApplyX), Success("Skipped")).
    #
    # The Inverter fires SUCCESS only when the condition does NOT match (routing
    # no-op for the wrong event type).  When the condition matches but ApplyX
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
                            # RSH-05-021: either Apply succeeds or fault is
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
                "InviteAccept",
                IsInviteAcceptEventNode,
                ApplyInviteAcceptFromLedgerNode,
            ),
            _event_effect_slot(
                "CloseCase",
                IsCloseCaseEventNode,
                ApplyCloseCaseFromLedgerNode,
            ),
            _event_effect_slot(
                "OfferReport",
                IsSubmitReportEventNode,
                ApplyOfferReportFromLedgerNode,
            ),
            _event_effect_slot(
                "OwnershipTransfer",
                IsOwnershipTransferEventNode,
                ApplyOwnershipTransferFromLedgerNode,
            ),
            _event_effect_slot(
                "OfferOwnershipTransfer",
                IsOfferOwnershipTransferEventNode,
                ApplyOfferOwnershipTransferFromLedgerNode,
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
            VerifySenderIsCaseActorNode(name="VerifySenderIsCaseActor"),
            entry_processing,
        ],
    )
    return py_trees.composites.Selector(
        name="AnnounceLogEntryReceivedBT",
        memory=False,
        children=[case_actor_subtree, participant_subtree],
    )
