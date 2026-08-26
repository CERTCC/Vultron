#!/usr/bin/env python
"""Behavior tree factory for committing and fanning out case ledger entries."""

from typing import Any, Literal

import py_trees

from vultron.core.behaviors.sync.nodes import (
    CreateLogEntryNode,
    DeclineForeignLedgerCommitNode,
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
    """Mint a canonical ledger entry for *case_id* and fan it out.

    Guarded by :class:`~vultron.core.behaviors.sync.nodes.ledger_authority.DeclineForeignLedgerCommitNode`
    so that only the store holding the canonical log claims an index in it.  The
    guard is the Selector's first child and reports SUCCESS when it declines, so
    a caller still reads a non-SUCCESS result as a real failure — "the canonical
    log is somewhere else, and replication will bring the entry here" is not one
    (ADR-0073, BT-05-006).
    """
    return py_trees.composites.Selector(
        name="CommitLogEntryBT",
        memory=False,
        children=[
            DeclineForeignLedgerCommitNode(name="DeclineForeignLedgerCommit"),
            py_trees.composites.Sequence(
                name="MintAndFanOutLogEntry",
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
            ),
        ],
    )
