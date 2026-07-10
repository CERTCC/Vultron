#!/usr/bin/env python
"""Behavior tree factory for inbound Announce(CaseLedgerEntry) handling."""

import py_trees

from vultron.core.behaviors.embargo.nodes import ApplyEmbargoTeardownNode
from vultron.core.behaviors.sync.nodes import (
    ApplyInviteAcceptFromLedgerNode,
    ApplyNoteFromLedgerNode,
    ApplyParticipantStatusFromLedgerNode,
    CheckHashOrRejectOnMismatchNode,
    CheckIsOwnCaseActorNode,
    CheckIsNotOwnCaseActorNode,
    CheckLedgerEntryAlreadyStoredNode,
    IsAddNoteEventNode,
    IsInviteAcceptEventNode,
    IsParticipantStatusEventNode,
    IsRemoveEmbargoEventNode,
    LogDeliveryConfirmationNode,
    PersistReceivedLogEntryNode,
    ReconstructChainTailNode,
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
    validate_and_persist = py_trees.composites.Sequence(
        name="ValidateAndPersistFlow",
        memory=False,
        children=[
            ReconstructChainTailNode(name="ReconstructChainTail"),
            CheckHashOrRejectOnMismatchNode(
                name="CheckHashOrRejectOnMismatch"
            ),
            PersistReceivedLogEntryNode(name="PersistReceivedLogEntry"),
        ],
    )
    participant_flow = py_trees.composites.Selector(
        name="ParticipantSubtree",
        memory=False,
        children=[
            CheckLedgerEntryAlreadyStoredNode(
                name="CheckLogEntryAlreadyStored"
            ),
            validate_and_persist,
        ],
    )
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
                    py_trees.behaviours.Success(name="EmbargoEffectsSkipped"),
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
                    py_trees.behaviours.Success(
                        name="ParticipantStatusEffectsSkipped"
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
                    py_trees.behaviours.Success(name="NoteEffectsSkipped"),
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
                    py_trees.behaviours.Success(
                        name="InviteAcceptEffectsSkipped"
                    ),
                ],
            ),
        ],
    )
    participant_subtree = py_trees.composites.Sequence(
        name="ParticipantGate",
        memory=False,
        children=[
            CheckIsNotOwnCaseActorNode(name="CheckIsNotOwnCaseActor"),
            participant_flow,
            log_entry_event_effects,
        ],
    )
    return py_trees.composites.Selector(
        name="AnnounceLogEntryReceivedBT",
        memory=False,
        children=[case_actor_subtree, participant_subtree],
    )
