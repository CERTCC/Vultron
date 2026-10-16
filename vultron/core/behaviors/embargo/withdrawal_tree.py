#!/usr/bin/env python

#  Copyright (c) 2026 Carnegie Mellon University and Contributors.
#  - see Contributors.md for a full list of Contributors
#  - see ContributionInstructions.md for information on how you can Contribute to this project
#  Vultron Multiparty Coordinated Vulnerability Disclosure Protocol Prototype is
#  licensed under a MIT (SEI)-style license, please see LICENSE.md distributed
#  with this Software or contact permission@sei.cmu.edu for full terms.
#  Created, in part, with funding and support from the United States Government
#  (see Acknowledgments file). This program may include and/or can make use of
#  certain third party source code, object code, documentation and other files
#  ("Third Party Software"). See LICENSE.md for more details.
#  Carnegie Mellon®, CERT® and CERT Coordination Center® are registered in the
#  U.S. Patent and Trademark Office by Carnegie Mellon University

"""Received-side tree for ``Leave(EmbargoEvent)``: withdrawal (MSM-07-010).

A signatory leaves the embargo in force by sending ``Leave(EmbargoEvent)``
to the CASE_MANAGER (EP-09-013, PCR-08).  The withdrawal is the sender's own
consent and changes no register entry, so the embargo stays in force for
everyone else (VP-13-017).  Only the CASE_MANAGER records it (BT-17-001);
every replica learns it from the ``Announce(CaseLedgerEntry)`` broadcast
(EP-09-007), and a receiver the gate turns away reports ``REFUSED``
(HP-01-005).
"""

import logging

import py_trees

from vultron.core.behaviors.case.receive_activity_tree import (
    create_receive_activity_tree,
)
from vultron.core.behaviors.embargo.embargo_clock_decisions import (
    embargo_clock_decisions,
)
from vultron.core.behaviors.embargo.nodes import (
    IsWithdrawableEmbargoNode,
    RecordParticipantWithdrawalNode,
)
from vultron.core.behaviors.embargo.nodes.withdrawal import (
    case_manager_admits_withdrawal_guard,
)
from vultron.core.behaviors.sender_entitlement import SenderRule
from vultron.core.behaviors.sender_guard import SenderCheckContext

logger = logging.getLogger(__name__)


def withdraw_from_embargo_on_case_tree(
    case_id: str,
    embargo_id: str,
    withdrawing_actor_id: str,
    activity_id: str,
    *,
    sender_rule: SenderRule,
) -> py_trees.behaviour.Behaviour:
    """Create the BT for a received ``Leave(EmbargoEvent)`` (MSM-07-010)::

        WithdrawFromEmbargoOnCaseBT (Sequence)
        ├─ IntakeReceivedActivityNode
        ├─ <sender guard>                        # composed from sender_rule
        ├─ ClockDecisionsIfCaseManager           # overdue invites (CM-28-015)
        ├─ IsWithdrawableEmbargoNode             # read-only guard (CLP-10-009)
        │                                        # and redelivery (HP-01-003)
        ├─ EmbargoWithdrawalApplies (CASE_MANAGER gate)  # staged decision
        ├─ GuardedCommitCaseLedgerEntryBT        # the Leave's own entry
        └─ RecordEmbargoWithdrawal (CASE_MANAGER gate)
           └─ RecordParticipantWithdrawalNode    # each declined row's entry

    The guard refuses, with the reason, a Leave of an embargo that is not
    the one in force, from a row that is not ``AGREED``, or from the case
    owner, which ends an embargo by terminating it (CM-02-005), before the
    commit, so no replica is sent an entry it cannot replay (SYNC-12-001).
    The CASE_MANAGER also decides the withdrawal on a staged store among the
    guards, so a Leave whose entries would not apply is refused uncommitted
    too (ADR-0124).  The Leave's entry carries no row: after it, the effect
    commits each row the withdrawal declines (the sender's row for the
    embargo in force and every open proposal's row it had agreed to) as the
    CASE_MANAGER's own ``Update(EmbargoConsent)`` entry, then applies them by
    copying (CLP-07-013); it moves no register entry.

    Args:
        case_id: ID of the VulnerabilityCase (the Leave's ``context``).
        embargo_id: ID of the EmbargoEvent the Leave names.
        withdrawing_actor_id: The Leave's ``actor``: the participant
            withdrawing.  Read from the message, never from the receiving
            store (ADR-0022).
        activity_id: The Leave's own id; a Leave the ledger already records
            is a redelivery, reported ``SKIPPED`` (HP-01-003).
        sender_rule: The use case's declared sender rule; the factory
            composes the sender guard from it (HP-01-008).

    Returns:
        Root node of the ``WithdrawFromEmbargoOnCaseBT`` Sequence.
    """
    root = create_receive_activity_tree(
        name="WithdrawFromEmbargoOnCaseBT",
        case_id=case_id,
        addressee_check="Leave(EmbargoEvent)",
        sender_rule=sender_rule,
        sender_context=SenderCheckContext(
            sender_id=withdrawing_actor_id, case_id=case_id
        ),
        clock_decisions=embargo_clock_decisions(case_id),
        precondition_guards=[
            IsWithdrawableEmbargoNode(
                case_id=case_id,
                embargo_id=embargo_id,
                withdrawing_actor_id=withdrawing_actor_id,
                activity_id=activity_id,
            ),
            case_manager_admits_withdrawal_guard(
                case_id, embargo_id, withdrawing_actor_id
            ),
        ],
        manager_effects=[
            # The consent belongs to the actor who left, not to the BT
            # execution actor (the CASE_MANAGER, PCR-08).
            RecordParticipantWithdrawalNode(
                case_id=case_id,
                embargo_id=embargo_id,
                withdrawing_actor_id=withdrawing_actor_id,
            ),
        ],
        manager_case_id=case_id,
        manager_gate_name="RecordEmbargoWithdrawal",
    )
    logger.info(
        "Created WithdrawFromEmbargoOnCaseBT for case=%s embargo=%s"
        " withdrawing_actor=%s",
        case_id,
        embargo_id,
        withdrawing_actor_id,
    )
    return root


__all__ = ["withdraw_from_embargo_on_case_tree"]
