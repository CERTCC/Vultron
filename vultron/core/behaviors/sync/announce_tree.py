#!/usr/bin/env python
"""Behavior tree factory for inbound Announce(CaseLogEntry) handling."""

import py_trees

from vultron.core.behaviors.sync.nodes import (
    CheckHashOrRejectOnMismatchNode,
    CheckIsOwnCaseActorNode,
    CheckIsNotOwnCaseActorNode,
    CheckLogEntryAlreadyStoredNode,
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
    participant_subtree = py_trees.composites.Sequence(
        name="ParticipantGate",
        memory=False,
        children=[
            CheckIsNotOwnCaseActorNode(name="CheckIsNotOwnCaseActor"),
            participant_flow,
        ],
    )
    return py_trees.composites.Selector(
        name="AnnounceLogEntryReceivedBT",
        memory=False,
        children=[case_actor_subtree, participant_subtree],
    )
