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

"""Received-side trees for an answer to an embargo Invite (EA / ER / EJ).

``accept_invite_to_embargo_tree`` handles ``Accept(Invite(EmbargoEvent))``
and ``reject_invite_to_embargo_tree`` handles ``Reject(Invite(EmbargoEvent))``.
Every answer routes through the CASE_MANAGER (PCR-08, ADR-0113), so the
effects of both trees write shared case state and are passed as
``manager_effects``, which the factory gates on the CASE_MANAGER (BT-17-001,
BT-17-008, RSH-08-003): a participant
replica learns the answer from the ``Announce(CaseLedgerEntry)`` broadcast
(EP-09-007), never from the activity itself.  A receiver the gate turns away
reports ``REFUSED`` (HP-01-005).

Split out of ``announce_teardown_tree`` to keep that module under the
CS-18-001 size cap; it re-exports both factories.
"""

import logging

import py_trees

from vultron.config.actor import ActorConfig
from vultron.core.behaviors.case.nodes.invite_actor_emit import (
    ReissueStubInvitesNode,
)
from vultron.core.behaviors.case.receive_activity_tree import (
    create_receive_activity_tree,
)
from vultron.core.behaviors.embargo.nodes import (
    DecideRejectedEmbargoProposalNode,
    IsRejectableEmbargoNode,
    OwnerRejectsRevisionAfterDisclosureNode,
    RecordParticipantAcceptanceNode,
    RecordParticipantRejectionNode,
    ValidateCaseExistsNode,
    embargo_ending_notice_nodes,
)
from vultron.core.behaviors.embargo.trigger_tree import terminate_embargo_bt
from vultron.core.behaviors.sender_entitlement import SenderIsInviteeNode
from vultron.core.behaviors.sync.nodes.embargo_backfill import (
    BackfillAdmittedParticipantsNode,
)
from vultron.core.states.embargo_register import TerminationReason

logger = logging.getLogger(__name__)


def accept_invite_to_embargo_tree(
    case_id: str,
    embargo_id: str,
    accepting_actor_id: str,
    invite_id: str,
    actor_config: ActorConfig | None = None,
) -> py_trees.behaviour.Behaviour:
    """Create the BT for accepting embargo invitation (protocol EA).

    Handles receipt of an ``Accept(InviteToEmbargoOnCase)`` activity.
    Records the acceptance via EmbargoLifecycle and commits a canonical
    ledger entry.  Only the CASE_MANAGER records it (BT-17-001); any other
    receiver's gate turns it away and the handler reports a refusal.  The
    CASE_MANAGER then backfills any participant the acceptance admitted
    (CM-10-006).

    Args:
        case_id: ID of the VulnerabilityCase.
        embargo_id: ID of the EmbargoEvent being accepted.
        accepting_actor_id: Actor ID of the participant accepting.
        invite_id: ID of the InviteToEmbargoOnCase activity.
        actor_config: The CASE_MANAGER's configuration; its RSVP windows set
            the deadline of a stub Invite the owner's acceptance re-issues.

    Returns:
        Root node of the ``AcceptInviteToEmbargoBT`` Sequence.
    """
    # The owner's acceptance of a shorter revision activates it; the bound
    # signatories the ledger no longer reaches are told (CM-31-009).
    capture, notices = embargo_ending_notice_nodes(
        case_id, requested_by=accepting_actor_id
    )
    root = create_receive_activity_tree(
        name="AcceptInviteToEmbargoBT",
        case_id=case_id,
        sender_guard=SenderIsInviteeNode(
            invite_id=invite_id, sender_actor_id=accepting_actor_id
        ),
        precondition_guards=[ValidateCaseExistsNode(case_id=case_id)],
        manager_effects=[
            capture,
            RecordParticipantAcceptanceNode(
                case_id=case_id,
                embargo_id=embargo_id,
                accepting_actor_id=accepting_actor_id,
            ),
            notices,
            # The acceptance can admit the participant (or, as the
            # owner's, activate the revision) after its entry was
            # fanned out; send what the gate withheld (CM-10-006).
            BackfillAdmittedParticipantsNode(case_id=case_id),
            # The owner's accept of a revision changes the active embargo
            # under any stub Invite still outstanding (CM-11-016); a
            # participant's accept changes nothing.
            ReissueStubInvitesNode(case_id=case_id, actor_config=actor_config),
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


def _decide_owner_rejection(
    case_id: str,
    embargo_id: str,
    rejecting_actor_id: str,
    actor_config: ActorConfig | None = None,
) -> py_trees.behaviour.Behaviour:
    """The owner's Reject decides the proposal; with P/X/A set it ends the embargo.

    ``Selector``: when the owner rejects the last open revision after CS has
    gone public, exploited or attacked, returning to the prior terms is not
    allowed (EMB-04-002), so the CASE_MANAGER terminates the embargo through
    the shared ``terminate_embargo_bt`` and announces ET to every other
    participant — the same path the public-disclosure cascade takes.  Any
    other Reject is decided by :class:`DecideRejectedEmbargoProposalNode`
    (ER / EJ, or nothing for a participant's consent).  Once the condition
    holds, a termination failure fails the tree: it is not a reason to
    revert to the prior terms instead.

    The whole decision sits behind the CASE_MANAGER gate, so the
    non-manager ask arm inside ``terminate_embargo_bt`` never runs here.  It
    stays rather than a manager-only variant: every path ends an embargo
    through the one shared composition (BT-19-002).
    """
    return py_trees.composites.Selector(
        name="DecideRejectedProposal",
        memory=False,
        children=[
            py_trees.composites.Sequence(
                name="TerminateOnRejectedRevision",
                memory=False,
                children=[
                    OwnerRejectsRevisionAfterDisclosureNode(
                        case_id=case_id,
                        embargo_id=embargo_id,
                        rejecting_actor_id=rejecting_actor_id,
                    ),
                    terminate_embargo_bt(
                        case_id=case_id,
                        result_out={},
                        requested_by=rejecting_actor_id,
                        reason=TerminationReason.THREAT_SIGNAL,
                        actor_config=actor_config,
                    ),
                ],
            ),
            py_trees.decorators.Inverter(
                name="UnlessTerminating",
                child=OwnerRejectsRevisionAfterDisclosureNode(
                    case_id=case_id,
                    embargo_id=embargo_id,
                    rejecting_actor_id=rejecting_actor_id,
                    name="CheckOwnerRejectsRevisionAfterDisclosure",
                ),
            ),
        ],
    )


def reject_invite_to_embargo_tree(
    case_id: str,
    rejecting_actor_id: str,
    invite_id: str,
    embargo_id: str,
    actor_config: ActorConfig | None = None,
) -> py_trees.behaviour.Behaviour:
    """Create the BT for rejecting embargo invitation (protocol ER / EJ).

    Handles receipt of a ``Reject(InviteToEmbargoOnCase)`` activity::

        RejectInviteToEmbargoBT (Sequence)
        ├─ IntakeReceivedActivityNode
        ├─ SenderIsInviteeNode                # sender guard (ADR-0115)
        ├─ IsRejectableEmbargoNode            # read-only guard (CLP-10-009)
        ├─ GuardedCommitCaseLedgerEntryBT
        └─ AnswerRejectedEmbargo (CASE_MANAGER gate)
           ├─ RecordParticipantRejectionNode  # consent (MSM-07-004)
           ├─ DecideRejectedProposal (Selector)
           │  ├─ TerminateOnRejectedRevision  # owner EJ with P/X/A → ET
           │  └─ UnlessTerminating (Inverter)
           └─ DecideRejectedEmbargoProposalNode  # owner ER / EJ

    The guard refuses a Reject naming an embargo that is neither active nor
    an open proposal (a late Reject of a decided proposal, or an unknown
    embargo) *before* the commit, so no replica is sent an entry it cannot
    replay (SYNC-12-001).  :class:`RecordParticipantRejectionNode` records
    the rejecting actor's consent under the MSM-07-004 rule
    (ADR-0093): a Reject naming the *active* embargo is consent withdrawal,
    one naming a *proposed* embargo declines that embargo's row only,
    and the owner's EJ changes nobody's record.  When the
    rejecting actor is the case owner the Reject *decides* the proposal
    (EP-08-003): ``PROPOSED → NONE`` or ``REVISE → ACTIVE`` when it was the
    last one open, or ET when P/X/A is set (EMB-04-002).

    Args:
        case_id: ID of the VulnerabilityCase.
        rejecting_actor_id: Actor ID of the participant rejecting.
        invite_id: ID of the InviteToEmbargoOnCase activity.
        embargo_id: ID of the EmbargoEvent the Reject names (required: which
            terms are refused decides the consent effect, MSM-07-004).
        actor_config: The CASE_MANAGER's configuration; its RSVP windows set
            the deadline of a stub Invite re-issued after an ET.  ``None``
            applies the ``ActorConfig`` defaults.

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
            # The consent belongs to the actor who rejected, not to
            # the BT execution actor (the CASE_MANAGER, PCR-08).
            RecordParticipantRejectionNode(
                case_id=case_id,
                embargo_id=embargo_id,
                rejecting_actor_id=rejecting_actor_id,
            ),
            _decide_owner_rejection(
                case_id, embargo_id, rejecting_actor_id, actor_config
            ),
            # The owner's Reject decides the proposal (ER / EJ); a
            # participant's is consent and decides nothing (#3470).
            # After an ET the proposal is already gone, so this is a
            # no-op.
            DecideRejectedEmbargoProposalNode(
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
