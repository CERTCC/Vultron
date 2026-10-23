#!/usr/bin/env python
"""Behavior tree factory for committing and fanning out case ledger entries."""

import json
from typing import TYPE_CHECKING, Any

import py_trees

from vultron.core.behaviors.bridge import BTBridge
from vultron.errors import VultronBTInternalError

if TYPE_CHECKING:
    from vultron.core.ports.case_outbox import CaseOutboxPersistence
    from vultron.core.ports.sync_activity import SyncActivityPort

from vultron.core.behaviors.sync.nodes import (
    CheckLedgerFreshnessNode,
    CreateLogEntryNode,
    DeclineForeignLedgerCommitNode,
    FanOutLogEntryNode,
    PersistLogEntryNode,
    ReconstructChainTailNode,
    RequireSyncPortNode,
)


def create_commit_log_entry_tree(
    case_id: str,
    object_id: str,
    semantic_type: str,
    *,
    payload_snapshot: dict[str, Any] | None = None,
    check_freshness: bool = True,
) -> py_trees.behaviour.Behaviour:
    """Mint a canonical ledger entry for *case_id* and fan it out.

    Guarded by :class:`~vultron.core.behaviors.sync.nodes.ledger_authority.DeclineForeignLedgerCommitNode`
    so that only the store holding the canonical log claims an index in it.  The
    guard is the Sequence's first child and raises, having written nothing, when
    the executing actor is not one this container hosts: no sanctioned path runs
    a commit there, so it is a fault, never a decline (CLP-10-014, BT-05-005,
    ADR-0109).

    The mint sequence opens with
    :class:`~vultron.core.behaviors.sync.nodes.port_guard.RequireSyncPortNode`:
    a store that would mint needs ``/sync_port`` to announce the entry
    (SYNC-02-003), and refusing before anything is persisted keeps the ledger
    free of entries no replica receives (#4113).  The raise surfaces as
    ``internal_error`` on the bridge running this tree, and
    ``CommitCaseLedgerEntryNode`` carries it to the outer bridge, so a received
    handler raises rather than reporting a refusal (ADR-0095).

    *check_freshness* ``False`` drops
    :class:`~vultron.core.behaviors.sync.nodes.conditions.CheckLedgerFreshnessNode`,
    which fails on a gapped local prefix by design (SYNC-10-001/002).  Only
    the case-closure commits pass it — the RM closure step entries — because a
    gapped prefix must not block case closure (CM-23-002).
    """
    freshness: list[py_trees.behaviour.Behaviour] = (
        [
            CheckLedgerFreshnessNode(
                case_id=case_id, name="CheckLedgerFreshness"
            )
        ]
        if check_freshness
        else []
    )
    return py_trees.composites.Sequence(
        name="CommitLogEntryBT",
        memory=False,
        children=[
            DeclineForeignLedgerCommitNode(name="DeclineForeignLedgerCommit"),
            py_trees.composites.Sequence(
                name="MintAndFanOutLogEntry",
                memory=False,
                children=[
                    # Refuse before anything is written: a committed entry
                    # that cannot be announced is a silent fork (#4113).
                    RequireSyncPortNode(name="RequireSyncPort"),
                    *freshness,
                    ReconstructChainTailNode(
                        case_id=case_id, name="ReconstructChainTail"
                    ),
                    CreateLogEntryNode(
                        case_id=case_id,
                        object_id=object_id,
                        semantic_type=semantic_type,
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
    semantic_type: str,
    sync_port: "SyncActivityPort | None" = None,
    check_freshness: bool = True,
) -> dict[str, Any]:
    """Commit an activity this actor just emitted as a canonical entry.

    The one shape every emit node that commits in-tree shares (ADR-0109): the
    sealed *activity_blob* the factory returned is the snapshot, verbatim —
    the same text the outbox delivers (VM-08-003) — and the commit runs as a
    nested tree.  The caller queues the activity first: the entry records a
    completed act, and a send is complete once it is in the outbox
    (SYNC-09-002, ADR-0119).  Returns the decoded snapshot; raises
    ``RuntimeError`` when the ledger refused the commit, so a caller that is
    itself a BT node fails with the activity queued and unrecorded, which a
    retry that rebuilds it under the same id records (OX-06-002), and
    :class:`~vultron.errors.VultronBTInternalError` when the nested commit
    failed on an internal error, so no caller absorbs it as a refusal
    (ADR-0095).

    *sync_port* fans the entry out to the case's participants when given; an
    emit node that reads ``/sync_port`` passes it through so a relayed
    emission is announced like any received commit.  *check_freshness* is
    passed to :func:`create_commit_log_entry_tree`.
    """
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
            semantic_type=semantic_type,
            payload_snapshot=snapshot,
            check_freshness=check_freshness,
        ),
        actor_id=actor_id,
        **context,
    )
    if result.internal_error:
        # Carry the nested bridge's classification across the hop: a missing
        # sync port or a crash in the commit tree is our fault, never a
        # refusal a caller may absorb (ADR-0095, #4113).
        raise VultronBTInternalError(
            f"nested ledger commit for {semantic_type}/{activity_id} failed:"
            f" {result.feedback_message}"
        )
    if result.status != py_trees.common.Status.SUCCESS:
        raise RuntimeError(
            f"ledger commit failed for {semantic_type}/{activity_id}:"
            f" {result.feedback_message}"
        )
    return snapshot
