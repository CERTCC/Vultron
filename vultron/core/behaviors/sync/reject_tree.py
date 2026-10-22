#!/usr/bin/env python
"""Behavior tree factory for inbound Reject(CaseLedgerEntry) handling."""

import py_trees

from vultron.core.behaviors.case.nodes.post_close import PostCloseExemption
from vultron.core.behaviors.case.receive_activity_tree import (
    create_receive_activity_tree,
)
from vultron.core.behaviors.sender_entitlement import SenderRule
from vultron.core.behaviors.sender_guard import LedgerActivityContext
from vultron.core.behaviors.sync.nodes import (
    AnnounceCaseOnGenesisRejectNode,
    FindCaseActorNode,
    ReplayMissingEntriesNode,
    UpdateReplicationStateNode,
)


def create_reject_log_entry_tree(
    case_id: str,
    *,
    sender_rule: SenderRule,
) -> py_trees.behaviour.Behaviour:
    """Create the BT for inbound ``Reject(CaseLedgerEntry)`` handling.

    Answering a peer's ``Reject(CaseLedgerEntry)`` — a redelivery request
    about the ledger, not a case event (CLP-02-013) — is the CASE_MANAGER's
    act alone (SYNC-03-005): it holds the canonical ledger, the per-peer
    replication state is its own, and the replay is sent in its name.  So
    every effect sits in ``manager_effects``, gated by the factory on the
    case's CASE_MANAGER role (BT-17-001, BT-17-008); a replica that receives
    a ``Reject`` sends nothing and records nothing, and the use case reports
    it ``REFUSED``.
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
    halts the tree before replication state is written.  The factory composes
    that guard from the use case's declared ``LEDGER_PEER`` rule; its node
    reads the case from the rejected entry when the tree runs
    (:class:`~vultron.core.behaviors.sender_guard.LedgerActivityContext`),
    or, for the ``Reject`` that names no entry because the peer holds none,
    from its ``target``; that form carries an empty hash, so it is answered
    as a replay from genesis (SYNC-16-007).

    Args:
        case_id: The case the peer's ``Reject`` is about: its rejected
            entry's case, or the case its ``target`` names when it names no
            entry (SYNC-16-007).  Its CASE_MANAGER gates the answer.
        sender_rule: The use case's declared sender rule (HP-01-008).
    """
    # The envelope is never a canonical entry (CLP-10-004): no commit stage.
    # Resync replays entries the ledger already holds, so it keeps working
    # after the case closes (ADR-0085, CM-23-013).
    return create_receive_activity_tree(
        name="RejectLogEntryReceivedBT",
        case_id=None,
        precondition_guards=[],
        post_close_exemption=PostCloseExemption.LEDGER_RESYNC,
        # Sender entitlement (SYNC-03-005, HP-01-006): only an active
        # participant's ``Reject`` is acted on, and the check precedes any
        # write so a stranger leaves no replication state.
        sender_rule=sender_rule,
        sender_context=LedgerActivityContext(),
        replica_effects=[FindCaseActorNode(name="FindCaseActor")],
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
