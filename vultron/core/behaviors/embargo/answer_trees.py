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

"""Received-side trees for an answer to an embargo Invite.

``accept_invite_to_embargo_tree`` handles ``Accept(Invite(EmbargoEvent))``
and ``reject_invite_to_embargo_tree`` handles ``Reject(Invite(EmbargoEvent))``.
Each is the sender's own consent, the case owner's included (ADR-0122); the
owner's decision for the case has activities of its own
(``owner_decision_tree``).  Every answer routes through the CASE_MANAGER
(PCR-08, ADR-0113), so the effects of both trees write shared case state and
are passed as ``manager_effects``, which the factory gates on the CASE_MANAGER
(BT-17-001, BT-17-008, RSH-08-003): a participant replica learns the answer
from the ``Announce(CaseLedgerEntry)`` broadcast (EP-09-007), never from the
activity itself.  A receiver the gate turns away reports ``REFUSED``
(HP-01-005).

Split out of ``announce_teardown_tree`` to keep that module under the
CS-18-001 size cap; it re-exports both factories.
"""

import logging

import py_trees

from vultron.core.behaviors.case.receive_activity_tree import (
    create_receive_activity_tree,
)
from vultron.core.behaviors.embargo.nodes import (
    IsRejectableEmbargoNode,
    RecordParticipantAcceptanceNode,
    RecordParticipantRejectionNode,
    ValidateCaseExistsNode,
)
from vultron.core.behaviors.sender_entitlement import SenderIsInviteeNode
from vultron.core.behaviors.sync.nodes.embargo_backfill import (
    BackfillAdmittedParticipantsNode,
)

logger = logging.getLogger(__name__)


def accept_invite_to_embargo_tree(
    case_id: str,
    embargo_id: str,
    accepting_actor_id: str,
    invite_id: str,
) -> py_trees.behaviour.Behaviour:
    """Create the BT for accepting an embargo invitation.

    Handles receipt of an ``Accept(InviteToEmbargoOnCase)`` activity: the
    sender's own consent, the case owner's included (ADR-0122).  Records the
    acceptance via EmbargoLifecycle, moving no register entry, and commits a
    canonical ledger entry.  Only the CASE_MANAGER records it (BT-17-001); any
    other receiver's gate turns it away and the handler reports a refusal.
    The owner's activation of a proposal is a separate activity
    (``activate_embargo_on_case_tree``), so no revision becomes active here;
    the backfill still runs because a participant that accepts the embargo in
    force becomes a signatory the fan-out of this entry withheld (CM-10-006).

    Args:
        case_id: ID of the VulnerabilityCase.
        embargo_id: ID of the EmbargoEvent being accepted.
        accepting_actor_id: Actor ID of the participant accepting.
        invite_id: ID of the InviteToEmbargoOnCase activity.

    Returns:
        Root node of the ``AcceptInviteToEmbargoBT`` Sequence.
    """
    root = create_receive_activity_tree(
        name="AcceptInviteToEmbargoBT",
        case_id=case_id,
        sender_guard=SenderIsInviteeNode(
            invite_id=invite_id, sender_actor_id=accepting_actor_id
        ),
        precondition_guards=[ValidateCaseExistsNode(case_id=case_id)],
        manager_effects=[
            RecordParticipantAcceptanceNode(
                case_id=case_id,
                embargo_id=embargo_id,
                accepting_actor_id=accepting_actor_id,
            ),
            # Accepting the embargo in force can admit the participant after
            # its entry was fanned out; send what the gate withheld
            # (CM-10-006).
            BackfillAdmittedParticipantsNode(case_id=case_id),
        ],
        manager_case_id=case_id,
        manager_gate_name="RecordEmbargoAcceptance",
    )
    logger.info(
        "Created AcceptInviteToEmbargoBT for case=%s embargo=%s"
        " accepting_actor=%s",
        case_id,
        embargo_id,
        accepting_actor_id,
    )
    return root


def reject_invite_to_embargo_tree(
    case_id: str,
    rejecting_actor_id: str,
    invite_id: str,
    embargo_id: str,
) -> py_trees.behaviour.Behaviour:
    """Create the BT for rejecting an embargo invitation.

    Handles receipt of a ``Reject(InviteToEmbargoOnCase)`` activity: the
    sender's own consent, the case owner's included (ADR-0122)::

        RejectInviteToEmbargoBT (Sequence)
        ├─ IntakeReceivedActivityNode
        ├─ SenderIsInviteeNode                # sender guard (ADR-0115)
        ├─ IsRejectableEmbargoNode            # read-only guard (CLP-10-009)
        ├─ GuardedCommitCaseLedgerEntryBT
        └─ AnswerRejectedEmbargo (CASE_MANAGER gate)
           └─ RecordParticipantRejectionNode  # consent (MSM-07-004)

    The guard refuses a Reject naming an embargo that is neither active nor
    an open proposal (a late Reject of a decided proposal, or an unknown
    embargo) *before* the commit, so no replica is sent an entry it cannot
    replay (SYNC-12-001).  :class:`RecordParticipantRejectionNode` records
    the rejecting actor's consent under the MSM-07-004 rule (ADR-0093): a
    Reject naming the *active* embargo is consent withdrawal, one naming a
    *proposed* embargo declines that embargo's row only.  It decides no
    proposal: the owner's rejection for the case is
    ``Reject(EmbargoEvent, target=Case)``
    (``reject_embargo_proposal_on_case_tree``).

    Args:
        case_id: ID of the VulnerabilityCase.
        rejecting_actor_id: Actor ID of the participant rejecting.
        invite_id: ID of the InviteToEmbargoOnCase activity.
        embargo_id: ID of the EmbargoEvent the Reject names (required: which
            terms are refused decides the consent effect, MSM-07-004).

    Returns:
        Root node of the ``RejectInviteToEmbargoBT`` Sequence.
    """
    root = create_receive_activity_tree(
        name="RejectInviteToEmbargoBT",
        case_id=case_id,
        sender_guard=SenderIsInviteeNode(
            invite_id=invite_id, sender_actor_id=rejecting_actor_id
        ),
        precondition_guards=[
            IsRejectableEmbargoNode(case_id=case_id, embargo_id=embargo_id),
        ],
        manager_effects=[
            # The consent belongs to the actor who rejected, not to the BT
            # execution actor (the CASE_MANAGER, PCR-08).
            RecordParticipantRejectionNode(
                case_id=case_id,
                embargo_id=embargo_id,
                rejecting_actor_id=rejecting_actor_id,
            ),
        ],
        manager_case_id=case_id,
        manager_gate_name="AnswerRejectedEmbargo",
    )
    logger.info(
        "Created RejectInviteToEmbargoBT for case=%s rejecting_actor=%s"
        " invite=%s",
        case_id,
        rejecting_actor_id,
        invite_id,
    )
    return root


__all__ = [
    "accept_invite_to_embargo_tree",
    "reject_invite_to_embargo_tree",
]
