#!/usr/bin/env python
"""Behavior tree factory for committing and fanning out case ledger entries."""

import json
from typing import TYPE_CHECKING, Any

import py_trees

if TYPE_CHECKING:
    from vultron.core.ports.case_persistence import CaseOutboxPersistence
    from vultron.core.ports.sync_activity import SyncActivityPort

from vultron.core.behaviors.sync.nodes import (
    CheckLedgerFreshnessNode,
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
                    CheckLedgerFreshnessNode(
                        case_id=case_id, name="CheckLedgerFreshness"
                    ),
                    ReconstructChainTailNode(
                        case_id=case_id, name="ReconstructChainTail"
                    ),
                    CreateLogEntryNode(
                        case_id=case_id,
                        object_id=object_id,
                        event_type=event_type,
                        payload_snapshot=payload_snapshot,
                        name="CreateLogEntry",
                    ),
                    PersistLogEntryNode(name="PersistLogEntry"),
                    FanOutLogEntryNode(case_id=case_id, name="FanOutLogEntry"),
                ],
            ),
        ],
    )


def commit_emitted_activity(
    *,
    datalayer: "CaseOutboxPersistence",
    actor_id: str,
    case_id: str,
    activity_id: str,
    activity_blob: str,
    event_type: str,
    sync_port: "SyncActivityPort | None" = None,
) -> dict[str, Any]:
    """Commit an activity this actor just emitted as a canonical entry.

    The one shape every emit node that commits in-tree shares (ADR-0109): the
    sealed *activity_blob* the factory returned is the snapshot, verbatim —
    the same text the outbox delivers (VM-08-003) — and the commit runs as a
    nested tree so the ledger commit precedes the outbox write.  Returns the
    decoded snapshot; raises ``RuntimeError`` when the commit did not succeed,
    so a caller that is itself a BT node fails rather than queuing an
    emission the ledger never recorded.

    *sync_port* fans the entry out to the case's participants when given; an
    emit node that reads ``/sync_port`` passes it through so a relayed
    emission is announced like any received commit.
    """
    from vultron.core.behaviors.bridge import BTBridge

    snapshot: dict[str, Any] = json.loads(activity_blob)
    # Passed only when given: an explicit ``sync_port=None`` would shadow the
    # outer execution's port on the blackboard and silence the fan-out that a
    # nested commit otherwise inherits.
    context: dict[str, Any] = (
        {"sync_port": sync_port} if sync_port is not None else {}
    )
    result = BTBridge(datalayer=datalayer).execute_with_setup(
        tree=create_commit_log_entry_tree(
            case_id=case_id,
            object_id=activity_id,
            event_type=event_type,
            payload_snapshot=snapshot,
        ),
        actor_id=actor_id,
        **context,
    )
    if result.status != py_trees.common.Status.SUCCESS:
        raise RuntimeError(
            f"ledger commit failed for {event_type}/{activity_id}:"
            f" {result.feedback_message}"
        )
    return snapshot
