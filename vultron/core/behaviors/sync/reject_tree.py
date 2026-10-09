#!/usr/bin/env python
"""Behavior tree factory for inbound Reject(CaseLedgerEntry) handling."""

import py_trees

from vultron.core.behaviors.case.receive_activity_tree import (
    create_receive_activity_tree,
)
from vultron.core.behaviors.sender_entitlement import (
    SenderIsActiveLedgerParticipantNode,
)
from vultron.core.behaviors.sync.nodes import (
    AnnounceCaseOnGenesisRejectNode,
    FindCaseActorNode,
    ReplayMissingEntriesNode,
    UpdateReplicationStateNode,
)


def create_reject_log_entry_tree(
    case_id: str,
) -> py_trees.behaviour.Behaviour:
    """Create the BT for inbound ``Reject(CaseLedgerEntry)`` handling.

    Answering a rejection is the CASE_MANAGER's act alone (SYNC-03-005): it
    holds the canonical ledger, the per-peer replication state is its own,
    and the replay is sent in its name.  So every effect sits in
    ``manager_effects``, gated by the factory on the case's CASE_MANAGER
    role (BT-17-001, BT-17-008); a replica that receives a ``Reject`` sends
    nothing and records nothing, and the use case reports it ``REFUSED``.
    The role is resolved **from the case** rather than compared against the
    address ``FindCaseActorNode`` looks up: the authority is a role, and its
    holder may be any Actor type (CLP-09 precedent; see ADR-0073).

    Inside the gate the genesis pre-seed precedes the replay: when the peer
    has no ``VulnerabilityCase`` yet (``last_accepted_hash=""``) it is sent
    ``Announce(VulnerabilityCase)`` first, so it can anchor its hash chain
    before the entries arrive (SYNC-15-002).  A pre-seed that fails at the
    CASE_MANAGER — its embargo gate undecidable — fails the tree before the
    replay, instead of reading as "not the CASE_MANAGER" (BTND-07-005).

    The sender must be an active participant (SYNC-03-005); any other sender
    halts the tree before replication state is written.

    Args:
        case_id: The case the rejected entry belongs to, whose CASE_MANAGER
            gates the answer.
    """
    # The envelope is never a canonical entry (CLP-10-004): no commit stage.
    return create_receive_activity_tree(
        name="RejectLogEntryReceivedBT",
        case_id=None,
        precondition_guards=[],
        replica_effects=[
            FindCaseActorNode(name="FindCaseActor"),
            # Sender entitlement (SYNC-03-005, HP-01-006): only an active
            # participant's rejection is acted on, and the check precedes any
            # write so a stranger leaves no replication state.
            SenderIsActiveLedgerParticipantNode(
                name="SenderIsActiveParticipant"
            ),
        ],
        manager_effects=[
            UpdateReplicationStateNode(name="UpdateReplicationState"),
            AnnounceCaseOnGenesisRejectNode(
                name="AnnounceCaseOnGenesisReject"
            ),
            ReplayMissingEntriesNode(name="ReplayMissingEntries"),
        ],
        manager_case_id=case_id,
        manager_gate_name="AnswerRejectIfCaseManager",
    )
