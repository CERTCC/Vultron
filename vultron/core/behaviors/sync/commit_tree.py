#!/usr/bin/env python
"""Behavior tree factory for committing and fanning out case ledger entries."""

from typing import Any, Literal

import py_trees

from vultron.core.behaviors.sync.nodes import (
    CreateLogEntryNode,
    FanOutLogEntryNode,
    PersistLogEntryNode,
    ReconstructChainTailNode,
)


def create_commit_log_entry_tree(
    case_id: str,
    object_id: str,
    event_type: str,
    *,
    payload_snapshot: dict[str, Any] | None = None,
    disposition: Literal["recorded", "rejected"] = "recorded",
) -> py_trees.behaviour.Behaviour:
    return py_trees.composites.Sequence(
        name="CommitLogEntryBT",
        memory=False,
        children=[
            ReconstructChainTailNode(
                case_id=case_id, name="ReconstructChainTail"
            ),
            CreateLogEntryNode(
                case_id=case_id,
                object_id=object_id,
                event_type=event_type,
                payload_snapshot=payload_snapshot,
                disposition=disposition,
                name="CreateLogEntry",
            ),
            PersistLogEntryNode(name="PersistLogEntry"),
            FanOutLogEntryNode(case_id=case_id, name="FanOutLogEntry"),
        ],
    )
