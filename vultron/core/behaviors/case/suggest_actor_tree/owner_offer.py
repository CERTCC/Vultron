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

"""Received-side BTs for the ``Offer(CaseParticipant)`` round trip (CM-16).

The Case Owner's receipt of the CASE_MANAGER's ``Offer(CaseParticipant)``
(CM-16-003, CM-16-004) and the CASE_MANAGER's receipt of the Case Owner's
``Accept`` or ``Reject`` of it (CM-16-006, CM-16-007).
"""

import py_trees

from vultron.core.behaviors.case.nodes.received_path import (
    ReceivedPath,
)
from vultron.core.behaviors.case.nodes.suggest_actor import (
    EmitAcceptRecordedRecommendationNode,
    EmitRecordedInviteNode,
    EmitRejectActorRecommendationNode,
    SeatRecordedInviteeNode,
    case_manager_admits_accepted_invitee_guard,
    case_manager_requires_recorded_rejection_guard,
)
from vultron.core.behaviors.case.receive_activity_tree import (
    create_receive_activity_tree,
)
from vultron.core.behaviors.sender_entitlement import (
    SenderRule,
)
from vultron.core.behaviors.sender_guard import SenderCheckContext


def create_receive_offer_case_participant_tree(
    case_id: str,
    sender_id: str,
    *,
    sender_rule: SenderRule,
) -> py_trees.composites.Sequence:
    """Received-side BT for Offer(CaseParticipant) on the Case Owner inbox.

    Commits a canonical ``CaseLedgerEntry`` for the received
    ``Offer(CaseParticipant)`` (CM-16-003/CM-16-004, ADR-0026). No effect
    nodes are added here — the Case Owner's decision to Accept or Reject is
    a separate outbound activity.

    The Offer is the CASE_MANAGER's to send (CM-16-004), so the sender guard
    refuses one from any other actor before anything is recorded (HP-01-006,
    PCR-03-001).

    Args:
        case_id: ID of the VulnerabilityCase.
        sender_id: Actor ID of the Offer's sender.
        sender_rule: The use case's declared sender rule; the factory
            composes the sender guard from it (HP-01-025).

    Returns:
        Root ``ReceiveOfferCaseParticipantBT`` Sequence node.
    """
    return create_receive_activity_tree(
        name="ReceiveOfferCaseParticipantBT",
        case_id=case_id,
        # The Offer is addressed to the Case Owner, which may be the
        # CASE_MANAGER of its case or an ordinary participant of it: the
        # CASE_MANAGER commits the receipt, and a participant replica keeps
        # what arrived and takes the entry from the ledger (HP-01-038,
        # RSH-08-003).
        paths={ReceivedPath.CASE_MANAGER, ReceivedPath.PARTICIPANT_REPLICA},
        sender_rule=sender_rule,
        sender_context=SenderCheckContext(
            sender_id=sender_id, case_id=case_id
        ),
        precondition_guards=[],
    )


def create_accept_actor_recommendation_received_tree(
    answer_id: str,
    case_id: str,
    sender_id: str,
    *,
    sender_rule: SenderRule,
) -> py_trees.composites.Sequence:
    """Received-side BT for Accept(Offer(CaseParticipant)) on the CASE_MANAGER's inbox.

    This is the Case Owner's decision (``ACCEPT_OFFER_CASE_PARTICIPANT``).
    The recommender's receipt of the CASE_MANAGER's answer
    (``ACCEPT_ACTOR_RECOMMENDATION``) is
    :func:`create_recommendation_answer_received_tree`.

    Commits a canonical ``CaseLedgerEntry`` (CM-16-006 step 1), then fans
    out: sends ``AcceptActorRecommendation`` to the original recommender
    (CM-16-006 step 3) and ``Invite(Actor)[target=VulnerabilityCaseStub]``
    to the invitee (CM-16-006 step 4, CM-17): its stub carries the embargo,
    and the Invite carries the intended roles.

    Tree structure::

        AcceptActorRecommendationBT (Sequence, memory=False)
        ├── AcceptedInviteeAdmittedIfCaseManager — CM-16-019, CM-31-013 and
        │   │                                      CM-16-006 guards
        │   ├── RequireRecordedOfferAnswerNode
        │   ├── AcceptedInviteeIsNotRemovedNode
        │   └── SuggestedActorIsInvitableNode
        ├── GuardedCommitCaseLedgerEntryBT       — record receipt (CLP-10-006)
        └── AcceptActorRecommendationIfCaseManager (Selector)  — BT-17-001 gate
            ├── SkipIfNotCaseManager
            └── AcceptActorRecommendationEffects (Sequence, memory=False)
                ├── EmitAcceptRecordedRecommendationNode
                ├── EmitRecordedInviteNode
                └── SeatRecordedInviteeNode

    The recommender, the invitee and its roles come from the CASE_MANAGER's
    own records, never from the Accept (ISSUE-1745, CM-16-019): the first
    precondition guard looks up the ``Offer(CaseParticipant)`` the Accept
    names and the recommendation behind it, and publishes them for every
    later node.  An Accept naming an Offer or recommendation this
    CASE_MANAGER never recorded is refused there, after intake has archived
    it (CLP-10-018) and before the commit, so nothing is recorded and only
    the refusal notice is sent (CLP-10-005, CLP-10-010, CLP-05-001).

    Both emits are the CASE_MANAGER's (CM-16-006, PCR-08-007); a receiver
    that is not it does nothing (#3752).  An invitee already at
    ``RM.CLOSED`` (or joined) is refused by the precondition guard, before the
    receipt commit and before anything is sent: a closed participant is never
    re-invited (CM-11-015, ADR-0085).

    Only the Case Owner may accept (CM-16-019): the sender guard refuses any
    other sender before the case ledger is written or anything is sent.  An
    acceptance naming an actor removed since the Offer was made is refused
    the same way: a removed participant is sent no stub Invite (CM-31-013).
    So is one naming an actor that has since joined or is at ``RM.CLOSED``:
    it is sent no further stub Invite, so no second Invite entry reaches the
    ledger for it (CM-11-015, CM-16-006).

    Args:
        answer_id: ID of the received ``Accept``; namespaces the recorded
            Offer the guard publishes.
        case_id: ID of the VulnerabilityCase.
        sender_id: Actor ID of the Accept's sender, who must be the Case Owner.
        sender_rule: The use case's declared sender rule; the factory
            composes the sender guard from it (HP-01-025).

    Returns:
        Root ``AcceptActorRecommendationBT`` Sequence node.
    """
    return create_receive_activity_tree(
        name="AcceptActorRecommendationBT",
        case_id=case_id,
        # The Accept is the Case Owner's answer to the CASE_MANAGER, and
        # every step of this tree is the CASE_MANAGER's, so the manager path
        # is the only one it handles (ADR-0153, CM-16-006).
        paths={ReceivedPath.CASE_MANAGER},
        sender_rule=sender_rule,
        sender_context=SenderCheckContext(
            sender_id=sender_id, case_id=case_id
        ),
        precondition_guards=[
            case_manager_admits_accepted_invitee_guard(
                answer_id=answer_id, case_id=case_id
            )
        ],
        manager_effects=[
            EmitAcceptRecordedRecommendationNode(
                answer_id=answer_id, case_id=case_id
            ),
            # One recommendation is accepted once; a retry of this tree
            # rebuilds the same Invite (OX-06-002).
            EmitRecordedInviteNode(answer_id=answer_id, case_id=case_id),
            # AC-1: record the inert participant at invite-send time
            # (ADR-0114, CM-11-006), with the recorded Offer's roles.
            SeatRecordedInviteeNode(answer_id=answer_id, case_id=case_id),
        ],
        manager_case_id=case_id,
        manager_gate_name="AcceptActorRecommendationIfCaseManager",
        manager_body_name="AcceptActorRecommendationEffects",
    )


def create_reject_actor_recommendation_received_tree(
    answer_id: str,
    case_id: str,
    sender_id: str,
    *,
    sender_rule: SenderRule,
) -> py_trees.composites.Sequence:
    """Received-side BT for Reject(Offer(CaseParticipant)) on the CASE_MANAGER's inbox.

    This is the Case Owner's decision (``REJECT_OFFER_CASE_PARTICIPANT``).
    The recommender's receipt of the CASE_MANAGER's answer
    (``REJECT_ACTOR_RECOMMENDATION``) is
    :func:`create_recommendation_answer_received_tree`.

    Commits a canonical ``CaseLedgerEntry`` (CM-16-007 step 1), then sends
    ``RejectActorRecommendation`` to the original recommender
    (CM-16-007 step 3).

    Tree structure::

        RejectActorRecommendationBT (Sequence, memory=False)
        ├── RejectedOfferRecordedIfCaseManager   — CM-16-019 guard
        │   └── RequireRecordedOfferAnswerNode
        ├── GuardedCommitCaseLedgerEntryBT       — record receipt (CLP-10-006)
        └── RejectActorRecommendationIfCaseManager (Selector)  — BT-17-001 gate
            ├── SkipIfNotCaseManager
            └── EmitRejectActorRecommendationNode

    The recommender and the recommended actor come from the CASE_MANAGER's
    own records, never from the Reject (CM-16-019): the precondition guard
    looks up the ``Offer(CaseParticipant)`` the Reject names and the
    recommendation behind it, and a Reject naming either unrecorded is
    refused there, after intake has archived it (CLP-10-018) and before the
    commit, so nothing is recorded and only the refusal notice is sent
    (CLP-10-005, CLP-10-010, CLP-05-001).

    The emit is the CASE_MANAGER's (CM-16-007); a receiver that is not it
    does nothing (#3752).
    Only the Case Owner may reject (CM-16-019): the sender guard refuses any
    other sender before the case ledger is written or anything is sent.

    Args:
        answer_id: ID of the received ``Reject``; namespaces the recorded
            Offer the guard publishes.
        case_id: ID of the VulnerabilityCase.
        sender_id: Actor ID of the Reject's sender, who must be the Case Owner.
        sender_rule: The use case's declared sender rule; the factory
            composes the sender guard from it (HP-01-025).

    Returns:
        Root ``RejectActorRecommendationBT`` Sequence node.
    """
    return create_receive_activity_tree(
        name="RejectActorRecommendationBT",
        case_id=case_id,
        # As for the Accept: the Reject is answered only by the
        # CASE_MANAGER (ADR-0153, CM-16-007).
        paths={ReceivedPath.CASE_MANAGER},
        sender_rule=sender_rule,
        sender_context=SenderCheckContext(
            sender_id=sender_id, case_id=case_id
        ),
        precondition_guards=[
            case_manager_requires_recorded_rejection_guard(
                answer_id=answer_id, case_id=case_id
            )
        ],
        manager_effects=[
            EmitRejectActorRecommendationNode(
                answer_id=answer_id, case_id=case_id
            ),
        ],
        manager_case_id=case_id,
        manager_gate_name="RejectActorRecommendationIfCaseManager",
    )
