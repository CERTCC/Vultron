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
from datetime import datetime

import py_trees

from vultron.config.actor import ActorConfig
from vultron.core.behaviors.case.nodes.refusal_notice import (
    EMBARGO_REFUSAL_ANSWERS,
)
from vultron.core.behaviors.case.receive_activity_tree import (
    create_receive_activity_tree,
)
from vultron.core.behaviors.embargo.embargo_clock_decisions import (
    embargo_clock_decisions,
)
from vultron.core.behaviors.embargo.expiry_tree import (
    invite_expiry_decision,
    late_accept_diversions,
)
from vultron.core.behaviors.embargo.nodes import (
    IsRejectableEmbargoNode,
    RecordParticipantAcceptanceNode,
    RecordParticipantRejectionNode,
    RejectIsNotWithdrawalNode,
    ValidateCaseExistsNode,
)
from vultron.core.behaviors.embargo.nodes.answer_record import (
    case_manager_admits_answer_change_guard,
)
from vultron.core.behaviors.embargo.nodes.answer_repeat import (
    case_manager_admits_embargo_answer_guard,
)
from vultron.core.behaviors.embargo.nodes.expiry import InviteNotExpiredNode
from vultron.core.behaviors.embargo.refusal_tree import pxa_accept_refusal
from vultron.core.behaviors.sender_entitlement import (
    SenderRule,
)
from vultron.core.behaviors.sender_guard import SenderCheckContext
from vultron.core.behaviors.sync.nodes.embargo_backfill import (
    BackfillAdmittedParticipantsNode,
)
from vultron.core.states.participant_embargo_consent import (
    EmbargoConsentState,
)

logger = logging.getLogger(__name__)


def accept_invite_to_embargo_tree(
    case_id: str,
    embargo_id: str,
    accepting_actor_id: str,
    invite_id: str,
    *,
    sender_rule: SenderRule,
    now: datetime,
    published: str,
    accept_id: str | None = None,
    expiry_out: dict[str, object] | None = None,
    actor_config: ActorConfig | None = None,
) -> py_trees.behaviour.Behaviour:
    """Create the BT for accepting an embargo invitation.

    Handles receipt of an ``Accept(InviteToEmbargoOnCase)`` activity: the
    sender's own consent, the case owner's included (ADR-0122).  The Accept's
    canonical entry is the accepter's row's entry: the ``AGREED`` row it
    states is applied by copying (ADR-0124), and it moves no register entry.
    Only the CASE_MANAGER records it (BT-17-001); any other receiver's gate
    turns it away and the handler reports a refusal.
    The owner's activation of a proposal is a separate activity
    (``activate_embargo_on_case_tree``), so no revision becomes active here;
    the backfill still runs because a participant that accepts the embargo in
    force becomes a signatory the fan-out of this entry withheld (CM-10-006).

    One tree for every delivery (CLP-10-005, ADR-0135)::

        AcceptInviteToEmbargoBT (Sequence)
        ├─ Intake → CaseOpenToExternalWrites
        ├─ ActivityAddressedToReceiverNode     # door: HP-01-005
        ├─ <sender guard>                       # door: the Invite's invitee
        ├─ ClockDecisionsIfCaseManager          # the Invite expiry (CM-28-009)
        ├─ ValidateCaseExistsNode
        ├─ EmbargoAnswerNotRecorded (gated)     # repeat → SKIPPED (CM-13-005)
        ├─ PxaAcceptRefusal (DiversionStage)    # P/X/A → ER (EMB-02-002)
        ├─ HonourLateAccept / ReinviteLateAccepter / AcknowledgeLateAccept
        │                                       # late Accept arms (EMB-17)
        ├─ InviteNotExpiredNode                 # a late Accept is no answer
        └─ AcceptInviteToEmbargoBTAct (ActTransaction)  # one act (ADR-0151)
           ├─ GuardedCommitCaseLedgerEntryBT
           └─ RecordEmbargoAcceptance (CaseManagerGate)

    The CASE_MANAGER first evaluates the Invite's RSVP deadline, a clock
    decision the factory runs after the door guards (CLP-10-025, CM-28-014):
    an expired invitation is ledgered ``TIMED_OUT`` (CM-28-009) before the
    Accept is judged.  A repeat of a recorded Accept then stops the tree.
    Once P/X/A is set the receiver answers with ER instead of recording the
    Accept (:func:`~vultron.core.behaviors.embargo.refusal_tree.pxa_accept_refusal`).
    A late Accept is routed by its compatibility with the case's embargo
    (:func:`~vultron.core.behaviors.embargo.expiry_tree.late_accept_diversions`,
    EMB-17-001) and is never recorded as an answer.

    Args:
        case_id: ID of the VulnerabilityCase.
        embargo_id: ID of the EmbargoEvent being accepted.
        accepting_actor_id: Actor ID of the participant accepting.
        invite_id: ID of the InviteToEmbargoOnCase activity.
        sender_rule: The use case's declared sender rule; the factory
            composes the sender guard from it (HP-01-008).
        now: The CASE_MANAGER's clock reading the RSVP deadline is compared
            against.
        published: The Accept's claimed ``published`` time, carried as
            received on the expiry entry (CLP-15-003); it decides nothing.
        accept_id: The Accept's own id; a re-invite's id derives from it,
            so a redelivery rebuilds the same Invite (OX-06-002).
        expiry_out: Receives the expiry decision's ``IS_EXPIRED_KEY`` and
            ``NEEDS_APPLY_KEY`` at the CASE_MANAGER, read by the late-Accept
            arms; a fresh dict when omitted.
        actor_config: The CASE_MANAGER's configuration: the re-invite's RSVP
            window and the stub re-issue after an honoured late Accept.

    Returns:
        Root node of the ``AcceptInviteToEmbargoBT`` Sequence.
    """
    expiry_out = {} if expiry_out is None else expiry_out
    root = create_receive_activity_tree(
        name="AcceptInviteToEmbargoBT",
        refusal_notice_exemption=EMBARGO_REFUSAL_ANSWERS,
        case_id=case_id,
        sender_rule=sender_rule,
        sender_context=SenderCheckContext(
            sender_id=accepting_actor_id, case_id=case_id, invite_id=invite_id
        ),
        clock_decisions=[
            invite_expiry_decision(
                case_id=case_id,
                invitee_id=accepting_actor_id,
                invite_id=invite_id,
                embargo_id=embargo_id,
                published=published,
                now=now,
                result_out=expiry_out,
            ),
            # Then every other overdue invitation of the case (CM-28-015).
            *embargo_clock_decisions(case_id, now),
        ],
        precondition_guards=[
            ValidateCaseExistsNode(case_id=case_id),
            # A repeat of an Accept already recorded commits nothing and
            # announces nothing (CM-13-005, HP-01-003).
            case_manager_admits_embargo_answer_guard(
                case_id=case_id,
                embargo_id=embargo_id,
                answering_actor_id=accepting_actor_id,
                answer=EmbargoConsentState.AGREED,
            ),
            # EMB-02-002: with P/X/A set the Accept moves nothing; ER.
            pxa_accept_refusal(
                case_id=case_id,
                invite_id=invite_id,
                accepting_actor_id=accepting_actor_id,
            ),
            # A late Accept is routed by its compatibility with the case's
            # embargo (EMB-17-001).
            *late_accept_diversions(
                case_id=case_id,
                embargo_id=embargo_id,
                accepting_actor_id=accepting_actor_id,
                invite_id=invite_id,
                published=published,
                answers=accept_id,
                result_out=expiry_out,
                actor_config=actor_config,
            ),
            # Backstop: a late Accept is never recorded as an answer.
            InviteNotExpiredNode(
                result_out=expiry_out,
                invitee_id=accepting_actor_id,
                case_id=case_id,
            ),
            # The Accept's entry carries the row it states (ADR-0122), so an
            # Accept that records nothing the case can take is refused before
            # it is committed.
            case_manager_admits_answer_change_guard(
                case_id, embargo_id, accepting_actor_id, accept=True
            ),
        ],
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
        # The Accept's own entry, its row and the backfill are one act
        # (CLP-07-015, ADR-0151).
        as_one_act=True,
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
    *,
    sender_rule: SenderRule,
) -> py_trees.behaviour.Behaviour:
    """Create the BT for rejecting an embargo invitation.

    Handles receipt of a ``Reject(InviteToEmbargoOnCase)`` activity: the
    sender's own consent, the case owner's included (ADR-0122)::

        RejectInviteToEmbargoBT (Sequence)
        ├─ IntakeReceivedActivityNode
        ├─ CaseOpenToExternalWrites           # door: post-close (CM-23-013)
        ├─ ActivityAddressedToReceiverNode    # door: addressee (HP-01-005)
        ├─ SenderIsInviteeNode                # sender guard (ADR-0115)
        ├─ ClockDecisionsIfCaseManager        # overdue invites (CM-28-015)
        ├─ IsRejectableEmbargoNode            # read-only guard (CLP-10-009)
        ├─ EmbargoAnswerNotRecorded (CASE_MANAGER gate)  # repeat guard
        ├─ RejectIsNotWithdrawalNode          # read-only guard (MSM-07-004)
        ├─ EmbargoAnswerApplies (CASE_MANAGER gate)  # the row can be written
        └─ RejectInviteToEmbargoBTAct (ActTransaction)  # one act (ADR-0151)
           ├─ GuardedCommitCaseLedgerEntryBT
           └─ AnswerRejectedEmbargo (CASE_MANAGER gate)
              └─ RecordParticipantRejectionNode  # the row the Reject states

    The guard refuses a Reject naming an embargo that is neither active nor
    an open proposal (a late Reject of a decided proposal, or an unknown
    embargo) *before* the commit, so no replica is sent an entry it cannot
    replay (SYNC-12-001).  The second guard refuses a Reject of the embargo
    in force from an ``AGREED`` row: that would be a withdrawal, and
    withdrawal is ``Leave(EmbargoEvent)`` (MSM-07-004, MSM-07-010).
    :class:`RecordParticipantRejectionNode` records the rejecting actor's
    consent under the MSM-07-004 rule: the named embargo's row becomes
    ``DECLINED`` and nothing else moves.  It decides no proposal: the owner's
    rejection for the case is
    ``Reject(EmbargoEvent, target=Case)``
    (``reject_embargo_proposal_on_case_tree``).

    Args:
        case_id: ID of the VulnerabilityCase.
        rejecting_actor_id: Actor ID of the participant rejecting.
        invite_id: ID of the InviteToEmbargoOnCase activity.
        embargo_id: ID of the EmbargoEvent the Reject names (required: which
            terms are refused decides the consent effect, MSM-07-004).
        sender_rule: The use case's declared sender rule; the factory
            composes the sender guard from it (HP-01-008).

    Returns:
        Root node of the ``RejectInviteToEmbargoBT`` Sequence.
    """
    root = create_receive_activity_tree(
        name="RejectInviteToEmbargoBT",
        refusal_notice_exemption=EMBARGO_REFUSAL_ANSWERS,
        case_id=case_id,
        sender_rule=sender_rule,
        sender_context=SenderCheckContext(
            sender_id=rejecting_actor_id, case_id=case_id, invite_id=invite_id
        ),
        clock_decisions=embargo_clock_decisions(case_id),
        precondition_guards=[
            IsRejectableEmbargoNode(case_id=case_id, embargo_id=embargo_id),
            # A repeat of a Reject already recorded commits nothing and
            # announces nothing (CM-13-005, HP-01-003).
            case_manager_admits_embargo_answer_guard(
                case_id=case_id,
                embargo_id=embargo_id,
                answering_actor_id=rejecting_actor_id,
                answer=EmbargoConsentState.DECLINED,
            ),
            RejectIsNotWithdrawalNode(
                case_id=case_id,
                embargo_id=embargo_id,
                rejecting_actor_id=rejecting_actor_id,
            ),
            # The Reject's entry carries the row it states (ADR-0122).
            case_manager_admits_answer_change_guard(
                case_id, embargo_id, rejecting_actor_id, accept=False
            ),
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
        # The Reject's own entry and its row are one act (CLP-07-015,
        # ADR-0151).
        as_one_act=True,
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
