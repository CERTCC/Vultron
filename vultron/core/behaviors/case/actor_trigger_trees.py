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

Three trigger trees are provided:

- ``suggest_actor_to_case_trigger_bt`` — SenderSideBT wrapper for
  Offer(Actor, Case) routed through the Case Manager (PCR-08-001).
- ``invite_actor_to_case_trigger_bt`` — direct-route Sequence for
  Invite(Actor, Case) sent from the Case Actor identity.
- ``accept_case_invite_trigger_bt`` — Sequence for Accept(Invite)
  sent by the invitee.

Per specs/behavior-tree-integration.yaml BT-15-001, BT-15-002.
"""

import logging
from typing import Callable

import py_trees

from vultron.core.behaviors.case.communication_tree import (
    SendOfferCaseManagerRoleNode,
)
from vultron.core.behaviors.case.nodes.actor import (
    EmitAcceptCaseInviteNode,
    EmitInviteActorToCaseNode,
)
from vultron.core.behaviors.case.nodes.suggest_actor.accept_offer import (
    EmitAcceptCaseParticipantOfferNode,
)
from vultron.core.behaviors.helpers import UpdateActorOutbox
from vultron.core.behaviors.sender.send_tree import sender_side_bt

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


def invite_actor_to_case_trigger_bt(
    invitee_id: str,
    case_id: str,
    case_actor_id: str | None = None,
    attributed_to: str | None = None,
    captured: dict | None = None,
) -> py_trees.behaviour.Behaviour:
    """Return the trigger-side BT for the invite-actor workflow.

    Emits Invite(Actor, Case) from the Case Actor's identity directly to
    the invitee (no Case Manager resolution needed — the Case Actor IS the
    routing endpoint here per PCR-08-007).  When ``case_actor_id`` is
    provided it is added to ``cc:`` so ASGI self-delivery routes a copy to
    the CaseActor's own inbox for canonical ledger archival (CLP-10-001).

    Args:
        invitee_id: Actor URI of the participant being invited.
        case_id: ID of the VulnerabilityCase.
        case_actor_id: Optional Case Actor URI added to ``cc:`` for
            self-archival (CLP-10-001).
        attributed_to: Optional original requesting actor URI.
        captured: Optional dict; ``captured["activity"]`` is set on success.

    Returns:
        Sequence containing a single EmitInviteActorToCaseNode.
    """
    root = py_trees.composites.Sequence(
        name="InviteActorToCaseTriggerBT",
        memory=False,
        children=[
            EmitInviteActorToCaseNode(
                invitee_id=invitee_id,
                case_id=case_id,
                case_actor_id=case_actor_id,
                attributed_to=attributed_to,
                captured=captured,
            ),
        ],
    )
    logger.debug(
        "Created InviteActorToCaseTriggerBT for invitee=%s case=%s",
        invitee_id,
        case_id,
    )
    return root


def accept_case_invite_trigger_bt(
    invite_id: str,
    captured: dict | None = None,
) -> py_trees.behaviour.Behaviour:
    """Return the trigger-side BT for the accept-case-invite workflow.

    Emits Accept(Invite) from the invitee's identity; the factory derives
    the recipient from the persisted invite object.

    Args:
        invite_id: ID of the RmInviteToCaseActivity being accepted.
        captured: Optional dict; ``captured["activity"]`` is set on success.

    Returns:
        Sequence containing a single EmitAcceptCaseInviteNode.
    """
    root = py_trees.composites.Sequence(
        name="AcceptCaseInviteTriggerBT",
        memory=False,
        children=[
            EmitAcceptCaseInviteNode(
                invite_id=invite_id,
                captured=captured,
            ),
        ],
    )
    logger.debug("Created AcceptCaseInviteTriggerBT for invite=%s", invite_id)
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
    root = py_trees.composites.Sequence(
        name="AcceptActorRecommendationTriggerBT",
        memory=False,
        children=[
            EmitAcceptCaseParticipantOfferNode(
                cp_offer_id=cp_offer_id,
                case_actor_id=case_actor_id,
                captured=captured,
            ),
        ],
    )
    logger.debug(
        "Created AcceptActorRecommendationTriggerBT for offer=%s case_actor=%s",
        cp_offer_id,
        case_actor_id,
    )
    return root


def offer_case_manager_role_trigger_bt(
    captured: dict | None = None,
) -> py_trees.behaviour.Behaviour:
    """Return the trigger-side BT for the offer-case-manager-role workflow.

    Emits ``Offer(CaseManagerRole)`` from the Case Actor's identity and flushes
    the activity to the Case Actor's outbox.  This is the manual trigger-side
    counterpart to the automatic path in ``receive_report_case_tree.py``
    (DEMOMA-08-007).

    The calling use case MUST pre-populate the blackboard (via
    ``_extra_execute_kwargs``) with:

    - ``case_id``: ID of the ``VulnerabilityCase``.
    - ``case_actor_id``: ID of the Case Actor Service.
    - ``case_actor_participant_id``: ID of the Case Actor's
      ``CaseParticipant`` record.

    Returns:
        Sequence containing ``SendOfferCaseManagerRoleNode`` followed by
        ``UpdateActorOutbox``.

    Per specs/multi-actor-demo.yaml DEMOMA-08-007; BT-15-001.
    """
    root = py_trees.composites.Sequence(
        name="OfferCaseManagerRoleTriggerBT",
        memory=False,
        children=[
            SendOfferCaseManagerRoleNode(captured=captured),
            UpdateActorOutbox(name="UpdateActorOutbox(Offer)"),
        ],
    )
    logger.debug("Created OfferCaseManagerRoleTriggerBT")
    return root
