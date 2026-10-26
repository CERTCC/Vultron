#!/usr/bin/env python
"""Behavior tree factory for inbound Read(CaseLedgerEntry) handling (SYNC-17).

``Read(CaseLedgerEntry)`` is a participant's statement that it has applied the
case's ledger up to the entry it names (ADR-0155).  The tree here answers it
at the CASE_MANAGER; ``state_positions_tree`` sends one (SYNC-17-007).
"""

from vultron.core.behaviors.case.nodes.post_close import PostCloseExemption
from vultron.core.behaviors.case.receive_activity_tree import (
    ReceivedActivityTree,
    create_receive_activity_tree,
)
from vultron.core.behaviors.sender_check_context import SenderCheckContext
from vultron.core.behaviors.sender_entitlement import SenderRule
from vultron.core.behaviors.sync.nodes import (
    CheckStatedPositionInLedgerNode,
    FindCaseActorNode,
    ReplayMissingEntriesNode,
    UpdateReplicationStateNode,
)


def create_read_log_entry_tree(
    case_id: str,
    *,
    sender_id: str,
    sender_rule: SenderRule,
) -> ReceivedActivityTree:
    """Create the BT for inbound ``Read(CaseLedgerEntry)`` handling.

    The answer is the one a ``Reject(CaseLedgerEntry)`` gets, composed from
    the same nodes (``create_reject_log_entry_tree``): record the stated
    position as the sender's acknowledged position (SYNC-17-003) and replay
    every entry after it, under the replay rate bound and the outbox
    de-duplication (SYNC-17-004).  At the tail the replay sends nothing.
    Before either, :class:`CheckStatedPositionInLedgerNode` turns away a
    position the ledger does not hold, logging it at WARNING, so nothing is
    recorded or sent (SYNC-17-005).

    Every effect is the CASE_MANAGER's act alone, so it sits in
    ``manager_effects``, gated by the factory on the case's CASE_MANAGER role
    (BT-17-001, BT-17-008); a replica that receives a ``Read`` does nothing,
    and the use case reports it ``REFUSED``.

    The sender guard is the use case's declared ``ACTIVE_PARTICIPANT``
    standing on the case the ``context`` names: a removed, unconsented or
    closed participant's statement is refused before any write (SYNC-17-002,
    CM-10-004, CM-23-018).  Nothing is committed: a position statement
    changes nothing in the case file (SYNC-17-006, ADR-0152).  Like the
    ``Reject`` replay, it replays only entries the ledger already holds, so
    it keeps working after the case closes (ADR-0085, CM-23-013).

    Args:
        case_id: The case the ``Read`` names in its ``context``.
        sender_id: The ``Read``'s ``actor``.
        sender_rule: The use case's declared sender rule (HP-01-008).
    """
    return create_receive_activity_tree(
        name="ReadLogEntryReceivedBT",
        case_id=None,
        precondition_guards=[],
        post_close_exemption=PostCloseExemption.LEDGER_RESYNC,
        sender_rule=sender_rule,
        sender_context=SenderCheckContext(
            sender_id=sender_id, case_id=case_id
        ),
        replica_effects=[FindCaseActorNode(name="FindCaseActor")],
        manager_effects=[
            CheckStatedPositionInLedgerNode(
                name="CheckStatedPositionInLedger"
            ),
            UpdateReplicationStateNode(name="UpdateReplicationState"),
            ReplayMissingEntriesNode(name="ReplayMissingEntries"),
        ],
        manager_case_id=case_id,
        manager_gate_name="AnswerReadIfCaseManager",
    )


__all__ = ["create_read_log_entry_tree"]
