#!/usr/bin/env python
"""Behavior tree factory for inbound Announce(CaseLogEntry) handling."""

import py_trees

from vultron.core.behaviors.embargo.nodes import ApplyEmbargoTeardownNode
from vultron.core.behaviors.sync.nodes import (
    CheckHashOrRejectOnMismatchNode,
    CheckIsOwnCaseActorNode,
    CheckIsNotOwnCaseActorNode,
    CheckLogEntryAlreadyStoredNode,
    IsNotRemoveEmbargoEventNode,
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
            CheckLogEntryAlreadyStoredNode(name="CheckLogEntryAlreadyStored"),
            validate_and_persist,
        ],
    )
    log_entry_event_effects = py_trees.composites.Selector(
        name="LogEntryEventEffects",
        memory=False,
        children=[
            IsNotRemoveEmbargoEventNode(name="IsNotRemoveEmbargoEvent"),
            ApplyEmbargoTeardownNode(name="ApplyEmbargoTeardown"),
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
