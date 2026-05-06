#!/usr/bin/env python
"""Behavior tree factory for inbound Reject(CaseLogEntry) handling."""

import py_trees

from vultron.core.behaviors.sync.nodes import (
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
            ReplayMissingEntriesNode(name="ReplayMissingEntries"),
        ],
    )
