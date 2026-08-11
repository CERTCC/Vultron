#!/usr/bin/env python
"""Behavior tree factory for inbound Announce(CaseLedgerEntry) handling."""

import py_trees

from vultron.core.behaviors.embargo.nodes import ApplyEmbargoTeardownNode
from vultron.core.behaviors.sync.nodes import (
    ApplyCloseCaseFromLedgerNode,
    ApplyInviteAcceptFromLedgerNode,
    ApplyNoteFromLedgerNode,
    ApplyOfferReportFromLedgerNode,
    ApplyOwnershipTransferFromLedgerNode,
    ApplyParticipantStatusFromLedgerNode,
    CheckHashOrRejectOnMismatchNode,
    CheckIsOwnCaseActorNode,
    CheckIsNotOwnCaseActorNode,
    CheckLedgerEntryAlreadyStoredNode,
    IsAddNoteEventNode,
    IsCloseCaseEventNode,
    IsInviteAcceptEventNode,
    IsOwnershipTransferEventNode,
    IsParticipantStatusEventNode,
    IsRemoveEmbargoEventNode,
    IsSubmitReportEventNode,
    LogDeliveryConfirmationNode,
    PersistReceivedLogEntryNode,
    ReconstructChainTailNode,
    SendRejectLogEntryNode,
    VerifySenderIsOwnIdNode,
)


def create_announce_log_entry_tree() -> py_trees.behaviour.Behaviour:
    case_actor_subtree = py_trees.composites.Sequence(
        name="CaseActorSubtree",
        memory=False,
        children=[
            CheckIsOwnCaseActorNode(name="CheckIsOwnCaseActor"),
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
            py_trees.composites.Selector(
                name="EmbargoEffects",
                memory=False,
                children=[
                    py_trees.composites.Sequence(
                        name="ApplyEmbargoEffectsSeq",
                        memory=False,
                        children=[
                            IsRemoveEmbargoEventNode(
                                name="IsRemoveEmbargoEvent"
                            ),
                            ApplyEmbargoTeardownNode(
                                name="ApplyEmbargoTeardown"
                            ),
                        ],
                    ),
                    py_trees.decorators.Inverter(
                        name="SkipIfNotEmbargoEvent",
                        child=IsRemoveEmbargoEventNode(
                            name="CheckNotEmbargoEvent"
                        ),
                    ),
                ],
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
                            ApplyParticipantStatusFromLedgerNode(
                                name="ApplyParticipantStatusFromLedger"
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
            py_trees.composites.Selector(
                name="NoteEffects",
                memory=False,
                children=[
                    py_trees.composites.Sequence(
                        name="ApplyNoteEffectsSeq",
                        memory=False,
                        children=[
                            IsAddNoteEventNode(name="IsAddNoteEvent"),
                            ApplyNoteFromLedgerNode(
                                name="ApplyNoteFromLedger"
                            ),
                        ],
                    ),
                    py_trees.decorators.Inverter(
                        name="SkipIfNotNoteEvent",
                        child=IsAddNoteEventNode(name="CheckNotNoteEvent"),
                    ),
                ],
            ),
            py_trees.composites.Selector(
                name="InviteAcceptEffects",
                memory=False,
                children=[
                    py_trees.composites.Sequence(
                        name="ApplyInviteAcceptEffectsSeq",
                        memory=False,
                        children=[
                            IsInviteAcceptEventNode(
                                name="IsInviteAcceptEvent"
                            ),
                            ApplyInviteAcceptFromLedgerNode(
                                name="ApplyInviteAcceptFromLedger"
                            ),
                        ],
                    ),
                    py_trees.decorators.Inverter(
                        name="SkipIfNotInviteAcceptEvent",
                        child=IsInviteAcceptEventNode(
                            name="CheckNotInviteAcceptEvent"
                        ),
                    ),
                ],
            ),
            py_trees.composites.Selector(
                name="CloseCaseEffects",
                memory=False,
                children=[
                    py_trees.composites.Sequence(
                        name="ApplyCloseCaseEffectsSeq",
                        memory=False,
                        children=[
                            IsCloseCaseEventNode(name="IsCloseCaseEvent"),
                            ApplyCloseCaseFromLedgerNode(
                                name="ApplyCloseCaseFromLedger"
                            ),
                        ],
                    ),
                    py_trees.decorators.Inverter(
                        name="SkipIfNotCloseCaseEvent",
                        child=IsCloseCaseEventNode(
                            name="CheckNotCloseCaseEvent"
                        ),
                    ),
                ],
            ),
            py_trees.composites.Selector(
                name="OfferReportEffects",
                memory=False,
                children=[
                    py_trees.composites.Sequence(
                        name="ApplyOfferReportEffectsSeq",
                        memory=False,
                        children=[
                            IsSubmitReportEventNode(
                                name="IsSubmitReportEvent"
                            ),
                            ApplyOfferReportFromLedgerNode(
                                name="ApplyOfferReportFromLedger"
                            ),
                        ],
                    ),
                    py_trees.decorators.Inverter(
                        name="SkipIfNotSubmitReportEvent",
                        child=IsSubmitReportEventNode(
                            name="CheckNotSubmitReportEvent"
                        ),
                    ),
                ],
            ),
            py_trees.composites.Selector(
                name="OwnershipTransferEffects",
                memory=False,
                children=[
                    py_trees.composites.Sequence(
                        name="ApplyOwnershipTransferEffectsSeq",
                        memory=False,
                        children=[
                            IsOwnershipTransferEventNode(
                                name="IsOwnershipTransferEvent"
                            ),
                            ApplyOwnershipTransferFromLedgerNode(
                                name="ApplyOwnershipTransferFromLedger"
                            ),
                        ],
                    ),
                    py_trees.decorators.Inverter(
                        name="SkipIfNotOwnershipTransferEvent",
                        child=IsOwnershipTransferEventNode(
                            name="CheckNotOwnershipTransferEvent"
                        ),
                    ),
                ],
            ),
        ],
    )
    # When the VulnerabilityCase is not yet seeded on this replica, chain tail
    # reconstruction fails and no tail_hash is available for the mismatch check.
    # Wrap reconstruct in a Selector so that on failure we still send a Reject
    # (with last_accepted_hash="" meaning "replay from genesis") and exit the
    # Sequence without persisting the entry (SYNC-15-001, CLP-08-005).
    reconstruct_or_reject = py_trees.composites.Selector(
        name="ReconstructOrRejectOnMissingCase",
        memory=False,
        children=[
            ReconstructChainTailNode(name="ReconstructChainTail"),
            # Fallback: send Reject carrying the sentinel tail_hash="" that
            # ReconstructChainTailNode wrote before failing.
            SendRejectLogEntryNode(name="RejectOnMissingCase"),
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
            CheckIsNotOwnCaseActorNode(name="CheckIsNotOwnCaseActor"),
            entry_processing,
        ],
    )
    return py_trees.composites.Selector(
        name="AnnounceLogEntryReceivedBT",
        memory=False,
        children=[case_actor_subtree, participant_subtree],
    )
