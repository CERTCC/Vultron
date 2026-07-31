#!/usr/bin/env python
"""Behavior tree factory for inbound Reject(CaseLedgerEntry) handling."""

import py_trees

from vultron.core.behaviors.sync.nodes import (
    AnnounceCaseOnGenesisRejectNode,
    FindCaseActorNode,
    ReplayMissingEntriesNode,
    UpdateReplicationStateNode,
)


def create_reject_log_entry_tree() -> py_trees.behaviour.Behaviour:
    return py_trees.composites.Sequence(
        name="RejectLogEntryReceivedBT",
        memory=False,
        children=[
            UpdateReplicationStateNode(name="UpdateReplicationState"),
            FindCaseActorNode(name="FindCaseActor"),
            # When the peer has no VulnerabilityCase yet (last_accepted_hash=""),
            # send Announce(VulnerabilityCase) before replaying entries so the
            # peer can anchor its hash chain (SYNC-15-002).
            AnnounceCaseOnGenesisRejectNode(
                name="AnnounceCaseOnGenesisReject"
            ),
            ReplayMissingEntriesNode(name="ReplayMissingEntries"),
        ],
    )
