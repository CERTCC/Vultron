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

"""Trigger-side behavior trees for actor-participation workflows.

Trigger trees provided here include:

- ``suggest_actor_to_case_trigger_bt`` — SenderSideBT wrapper for
  Offer(Actor, Case) routed through the Case Manager (PCR-08-001).  The Case
  Owner's direct invite uses it too: the owner asks the CASE_MANAGER to
  invite, and the CASE_MANAGER emits the Invite from its own received tree
  (CM-17-007, ADR-0109).  No trigger tree emits an Invite.
- ``accept_case_invite_trigger_bt`` — Sequence for Accept(Invite)
  sent by the invitee.
- ``accept_actor_recommendation_trigger_bt`` and
  ``reject_actor_recommendation_trigger_bt`` — the Case Owner's answer to a
  forwarded Offer(CaseParticipant) (CM-16-006, CM-16-007).

Per specs/behavior-tree-integration.yaml BT-15-001, BT-15-002.
"""

import logging
from collections.abc import Callable
from datetime import datetime

import py_trees

from vultron.core.behaviors.case.nodes.invite_received import (
    FixInviteTrustAnchorNode,
)
from vultron.core.behaviors.case.nodes.invite_response import (
    EmitAcceptCaseInviteNode,
    EmitAcceptFullCaseInviteNode,
    EmitRejectCaseInviteNode,
    EmitRejectFullCaseInviteNode,
    EmitTentativeRejectFullCaseInviteNode,
)
from vultron.core.behaviors.case.nodes.ownership_transfer import (
    EmitAcceptCaseOwnershipTransferNode,
    EmitProposeCaseOwnershipTransferNode,
    EmitRejectCaseOwnershipTransferNode,
    EmitWithdrawCaseOwnershipTransferNode,
)
from vultron.core.behaviors.case.nodes.suggest_actor.accept_offer import (
    EmitAcceptCaseParticipantOfferNode,
    EmitRejectCaseParticipantOfferNode,
)
from vultron.core.behaviors.sender.send_tree import sender_side_bt
from vultron.core.models.ledger_position import LedgerPosition

logger = logging.getLogger(__name__)


def suggest_actor_to_case_trigger_bt(
    case_id: str,
    activity_builder: Callable[[str], list[str]],
) -> py_trees.behaviour.Behaviour:
    """Return the trigger-side BT for the suggest-actor workflow.

    Routes Offer(Actor, Case) through the Case Manager via
    :func:`~vultron.core.behaviors.sender.send_tree.sender_side_bt`
    (PCR-08-001).

    Args:
        case_id: ID of the VulnerabilityCase.
        activity_builder: Closure called with the resolved Case Manager ID;
            returns the list of outbound activity IDs.

    Returns:
        SenderSideBT Sequence.
    """
    return sender_side_bt(case_id=case_id, activity_builder=activity_builder)


def accept_case_invite_trigger_bt(
    invite_id: str,
    captured: dict | None = None,
) -> py_trees.behaviour.Behaviour:
    """Return the trigger-side BT for the accept-case-invite workflow.

    Emits Accept(Invite) from the invitee's identity; the factory derives
    the recipient from the persisted invite object.  Once the Accept is
    queued, the trust anchor that Invite set is fixed, so a later Invite
    naming another CaseActor can no longer replace it (PCR-03-004).

    Args:
        invite_id: ID of the RmInviteToCaseActivity being accepted.
        captured: Optional dict; ``captured["activity"]`` is set on success.

    Returns:
        Sequence of EmitAcceptCaseInviteNode then FixInviteTrustAnchorNode.
    """
    root = py_trees.composites.Sequence(
        name="AcceptCaseInviteTriggerBT",
        memory=False,
        children=[
            EmitAcceptCaseInviteNode(
                invite_id=invite_id,
                captured=captured,
            ),
            FixInviteTrustAnchorNode(invite_id=invite_id),
        ],
    )
    logger.debug("Created AcceptCaseInviteTriggerBT for invite=%s", invite_id)
    return root


def reject_case_invite_trigger_bt(
    invite_id: str,
    captured: dict | None = None,
) -> py_trees.behaviour.Behaviour:
    """Return the trigger-side BT for the reject-case-invite workflow.

    Emits Reject(Invite) from the invitee's identity; the factory derives
    the recipient from the persisted invite object.

    Args:
        invite_id: ID of the RmInviteToCaseActivity being rejected.
        captured: Optional dict; ``captured["activity"]`` is set on success.

    Returns:
        Sequence containing a single EmitRejectCaseInviteNode.
    """
    root = py_trees.composites.Sequence(
        name="RejectCaseInviteTriggerBT",
        memory=False,
        children=[
            EmitRejectCaseInviteNode(
                invite_id=invite_id,
                captured=captured,
            ),
        ],
    )
    logger.debug("Created RejectCaseInviteTriggerBT for invite=%s", invite_id)
    return root


def full_case_invite_reply_trigger_bt(
    emit_node: type[
        EmitAcceptFullCaseInviteNode
        | EmitTentativeRejectFullCaseInviteNode
        | EmitRejectFullCaseInviteNode
    ],
    invite_id: str,
    position: LedgerPosition,
    captured: dict | None = None,
) -> py_trees.behaviour.Behaviour:
    """Return the trigger-side BT for a reply to the full-case Invite.

    Emits the reply (RV, RI or RC, by *emit_node*) from the participant's
    identity, carrying its own ledger *position* (CM-11-011); the factory
    derives the recipient from the persisted Invite.

    Args:
        emit_node: The emit node class naming the reply.
        invite_id: ID of the full-case Invite being answered.
        position: The participant's own ledger position.
        captured: Optional dict; ``captured["activity"]`` is set on success.

    Returns:
        Sequence containing a single emit node.
    """
    root = py_trees.composites.Sequence(
        name=f"{emit_node.__name__}TriggerBT",
        memory=False,
        children=[
            emit_node(
                invite_id=invite_id, position=position, captured=captured
            )
        ],
    )
    logger.debug("Created %s for invite=%s", root.name, invite_id)
    return root


def _actor_recommendation_answer_trigger_bt(
    name: str,
    emit_node: py_trees.behaviour.Behaviour,
    cp_offer_id: str,
    case_actor_id: str,
) -> py_trees.behaviour.Behaviour:
    """Return a Sequence *name* holding *emit_node*, which answers *cp_offer_id*.

    Shared by the Case Owner's Accept (CM-16-006) and Reject (CM-16-007) of
    the ``Offer(CaseParticipant)`` the CaseActor forwarded (ADR-0026).
    """
    root = py_trees.composites.Sequence(
        name=name,
        memory=False,
        children=[emit_node],
    )
    logger.debug(
        "Created %s for offer=%s case_actor=%s",
        root.name,
        cp_offer_id,
        case_actor_id,
    )
    return root


def accept_actor_recommendation_trigger_bt(
    cp_offer_id: str,
    case_actor_id: str,
    captured: dict | None = None,
) -> py_trees.behaviour.Behaviour:
    """Return the trigger-side BT for the accept-actor-recommendation workflow.

    Emits Accept(Offer(CaseParticipant)) from the Case Owner's identity to
    the CaseActor, completing the ADR-0026 CM-16-006 approval step.

    Args:
        cp_offer_id: ID of the ``Offer(CaseParticipant)`` forwarded by CaseActor.
        case_actor_id: URI of the CaseActor to route the Accept to.
        captured: Optional dict; ``captured["activity"]`` is set on success.

    Returns:
        Sequence containing a single EmitAcceptCaseParticipantOfferNode.
    """
    return _actor_recommendation_answer_trigger_bt(
        "AcceptActorRecommendationTriggerBT",
        EmitAcceptCaseParticipantOfferNode(
            cp_offer_id=cp_offer_id,
            case_actor_id=case_actor_id,
            captured=captured,
        ),
        cp_offer_id,
        case_actor_id,
    )


def reject_actor_recommendation_trigger_bt(
    cp_offer_id: str,
    case_actor_id: str,
    captured: dict | None = None,
) -> py_trees.behaviour.Behaviour:
    """Return the trigger-side BT for the reject-actor-recommendation workflow.

    Emits Reject(Offer(CaseParticipant)) from the Case Owner's identity to
    the CaseActor, which ledgers it and answers the recommender (ADR-0026,
    CM-16-007).

    Args:
        cp_offer_id: ID of the ``Offer(CaseParticipant)`` forwarded by CaseActor.
        case_actor_id: URI of the CaseActor to route the Reject to.
        captured: Optional dict; ``captured["activity"]`` is set on success.

    Returns:
        Sequence containing a single EmitRejectCaseParticipantOfferNode.
    """
    return _actor_recommendation_answer_trigger_bt(
        "RejectActorRecommendationTriggerBT",
        EmitRejectCaseParticipantOfferNode(
            cp_offer_id=cp_offer_id,
            case_actor_id=case_actor_id,
            captured=captured,
        ),
        cp_offer_id,
        case_actor_id,
    )


def offer_case_ownership_transfer_trigger_bt(
    case_id: str,
    transferee_id: str,
    content: str | None = None,
    captured: dict | None = None,
    end_time: datetime | None = None,
) -> py_trees.behaviour.Behaviour:
    """Return the trigger-side BT for the offer-case-ownership-transfer workflow.

    Emits the Case Owner's proposal, ``Offer(Offer(VulnerabilityCase))``, to
    the case's CASE_MANAGER (CM-21-005, TRIG-11-001).  The CASE_MANAGER's
    received tree makes the one ``Offer(VulnerabilityCase)`` the transferee
    answers; no trigger tree emits as the CASE_MANAGER (CM-24-004,
    ADR-0109, ADR-0148).

    Args:
        case_id: ID of the VulnerabilityCase whose ownership is being offered.
        transferee_id: Actor URI of the intended new owner.
        content: Optional human-readable message included in the offer.
        captured: Optional dict; ``captured["activity"]`` is set on success.
        end_time: Optional deadline to answer the Offer, set as the inner
            Offer's ``end_time`` (TRIG-11-007, CM-21-016).

    Returns:
        Sequence containing a single EmitProposeCaseOwnershipTransferNode.
    """
    root = py_trees.composites.Sequence(
        name="OfferCaseOwnershipTransferTriggerBT",
        memory=False,
        children=[
            EmitProposeCaseOwnershipTransferNode(
                case_id=case_id,
                transferee_id=transferee_id,
                content=content,
                captured=captured,
                end_time=end_time,
            ),
        ],
    )
    logger.debug(
        "Created OfferCaseOwnershipTransferTriggerBT case=%s transferee=%s",
        case_id,
        transferee_id,
    )
    return root


def _ownership_answer_trigger_bt(
    name: str,
    emit_node: (
        type[EmitAcceptCaseOwnershipTransferNode]
        | type[EmitRejectCaseOwnershipTransferNode]
        | type[EmitWithdrawCaseOwnershipTransferNode]
    ),
    offer_id: str,
    case_id: str,
    captured: dict | None,
) -> py_trees.behaviour.Behaviour:
    """The trigger-side tree shared by every reply to an ownership Offer.

    The transferee's Accept and Reject, and the offerer's withdrawal.
    """
    root = py_trees.composites.Sequence(
        name=name,
        memory=False,
        children=[
            emit_node(offer_id=offer_id, case_id=case_id, captured=captured),
        ],
    )
    logger.debug("Created %s for offer=%s case=%s", name, offer_id, case_id)
    return root


def accept_case_ownership_transfer_trigger_bt(
    offer_id: str,
    case_id: str,
    captured: dict | None = None,
) -> py_trees.behaviour.Behaviour:
    """Return the trigger-side BT for the accept-case-ownership-transfer workflow.

    Emits ``Accept(Offer(VulnerabilityCase))`` addressed to the CaseActor
    (TRIG-11-002, CM-21-006).

    Args:
        offer_id: ID of the ``_OfferCaseOwnershipTransferActivity`` being accepted.
        case_id: ID of the VulnerabilityCase; used to resolve the CaseActor.
        captured: Optional dict; ``captured["activity"]`` is set on success.

    Returns:
        Sequence containing a single EmitAcceptCaseOwnershipTransferNode.
    """
    return _ownership_answer_trigger_bt(
        "AcceptCaseOwnershipTransferTriggerBT",
        EmitAcceptCaseOwnershipTransferNode,
        offer_id,
        case_id,
        captured,
    )


def reject_case_ownership_transfer_trigger_bt(
    offer_id: str,
    case_id: str,
    captured: dict | None = None,
) -> py_trees.behaviour.Behaviour:
    """Return the trigger-side BT for the reject-case-ownership-transfer workflow.

    Emits ``Reject(Offer(VulnerabilityCase))`` addressed to the case's
    CASE_MANAGER (TRIG-11-005, CM-21-010).

    Args:
        offer_id: ID of the ``_OfferCaseOwnershipTransferActivity`` declined.
        case_id: ID of the VulnerabilityCase; used to resolve the
            CASE_MANAGER.
        captured: Optional dict; ``captured["activity"]`` is set on success.

    Returns:
        Sequence containing a single EmitRejectCaseOwnershipTransferNode.
    """
    return _ownership_answer_trigger_bt(
        "RejectCaseOwnershipTransferTriggerBT",
        EmitRejectCaseOwnershipTransferNode,
        offer_id,
        case_id,
        captured,
    )


def withdraw_case_ownership_transfer_trigger_bt(
    offer_id: str,
    case_id: str,
    captured: dict | None = None,
) -> py_trees.behaviour.Behaviour:
    """Return the trigger-side BT for the withdraw-case-ownership-transfer workflow.

    Emits ``Undo(Offer(Offer(VulnerabilityCase)))`` from the Case Owner,
    addressed to the case's CASE_MANAGER (TRIG-11-006, CM-21-015): the owner
    withdraws its own proposal, and the CASE_MANAGER the Offer it made from
    it (ADR-0148).

    Args:
        offer_id: ID of the ``_ProposeCaseOwnershipTransferActivity``
            withdrawn, the owner's own proposal.
        case_id: ID of the VulnerabilityCase; used to resolve the
            CASE_MANAGER.
        captured: Optional dict; ``captured["activity"]`` is set on success.

    Returns:
        Sequence containing a single EmitWithdrawCaseOwnershipTransferNode.
    """
    return _ownership_answer_trigger_bt(
        "WithdrawCaseOwnershipTransferTriggerBT",
        EmitWithdrawCaseOwnershipTransferNode,
        offer_id,
        case_id,
        captured,
    )
