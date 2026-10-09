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

"""Received-side BT factories for the suggest-actor workflow (CASE_MANAGER inbox).

Three factories correspond to the three received-side protocol events defined
in ADR-0026/CM-16:

- :func:`create_recommend_actor_to_case_received_tree`  — the CASE_MANAGER
  handles ``Offer(Actor, Case)`` from a recommending participant
  (CM-16-001..004).
- :func:`create_accept_actor_recommendation_received_tree` — the CASE_MANAGER
  handles ``Accept(Offer(CaseParticipant))`` from the Case Owner (CM-16-006).
- :func:`create_reject_actor_recommendation_received_tree` — the CASE_MANAGER
  handles ``Reject(Offer(CaseParticipant))`` from the Case Owner (CM-16-007).

All three trees route through the CASE_MANAGER's inbox per ADR-0021/ADR-0026
and use
:func:`~vultron.core.behaviors.case.receive_activity_tree.create_receive_activity_tree`
to enforce CLP-10-006 ordering (ledger commit before effect nodes).

Every effect in this workflow is the CASE_MANAGER's, so each tree's effect
section is passed as ``manager_effects``, which the factory wraps in the
CASE_MANAGER gate (BT-17-001, BT-17-008, BTND-07-005).  The same handler
runs on every participant that holds a copy of the message; the gate is
what keeps a participant that is *not* the case's CASE_MANAGER from
forwarding, accepting, or inviting as itself (#3752).  The handler then
reports the skip as a refusal (HP-01-005).

BT leaf nodes for this workflow are in the
:mod:`vultron.core.behaviors.case.nodes.suggest_actor` subpackage.
"""

import logging

import py_trees

from vultron.config.actor import ActorConfig
from vultron.core.behaviors.case.nodes.actor import (
    EmitInviteActorToCaseNode,
    EvaluateDefaultRolesNode,
)
from vultron.core.behaviors.case.nodes.invite_inert_participant import (
    CreateInertInviteeParticipantNode,
)
from vultron.core.behaviors.case.nodes.stub_invite_lifetime import (
    ReinviteAwaitingNode,
    ReinviteNotToClosedParticipantNode,
)
from vultron.core.behaviors.case.nodes.suggest_actor import (
    ActorAlreadyParticipantNode,
    EmitAcceptActorRecommendationNode,
    EmitNoteDuplicateRecommendationToOwnerNode,
    EmitOfferCaseParticipantToOwnerNode,
    EmitRejectActorRecommendationNode,
    InviteInFlightNode,
    PendingOfferCaseParticipantNode,
    RecordRecommendationRecommenderNode,
    case_manager_admits_accepted_invitee_guard,
    case_manager_admits_suggested_actor_guard,
)
from vultron.core.behaviors.case.receive_activity_tree import (
    create_receive_activity_tree,
)
from vultron.core.behaviors.sender_entitlement import (
    SenderIsActiveParticipantNode,
    SenderIsCaseManagerNode,
    SenderIsCaseOwnerNode,
)

logger = logging.getLogger(__name__)


def create_receive_offer_case_participant_tree(
    case_id: str,
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

    Returns:
        Root ``ReceiveOfferCaseParticipantBT`` Sequence node.
    """
    return create_receive_activity_tree(
        name="ReceiveOfferCaseParticipantBT",
        case_id=case_id,
        sender_guard=SenderIsCaseManagerNode(case_id=case_id),
        precondition_guards=[],
    )


def create_recommend_actor_to_case_received_tree(
    recommendation_id: str,
    recommender_id: str,
    recommended_id: str,
    case_id: str,
    offer_content: str | None = None,
    suggested_roles: list[str] | None = None,
    actor_config: ActorConfig | None = None,
) -> py_trees.composites.Sequence:
    """Received-side BT for Offer(Actor, Case) on the CASE_MANAGER's inbox.

    Refuses, before any commit, the recommendation of a removed participant:
    it is sent no stub Invite, and only the Case Owner's
    ``Add(CaseParticipant)`` reinstates it (CM-31-013, CM-31-011).  Otherwise
    commits a canonical ``CaseLedgerEntry`` for the received Offer
    (CM-16-002), then routes to one of six branches via a Selector:

    0. **Re-invite** — the recommender holds ``CVDRole.CASE_OWNER`` and the
       recommended actor has an inert record that has not answered (or whose
       stub Invite expired): send a fresh stub Invite on that record with a
       new deadline, ahead of every duplicate arm (CM-11-015).  Before any
       arm, an owner's re-invite of a participant at ``RM.CLOSED`` is refused
       (CM-11-015, ADR-0085).
    1. **AC-7b** — already participant: auto-accept to recommender (CM-16-009).
    2. **AC-7a** — invite in-flight: auto-accept to recommender (CM-16-009).
    3. **AC-6** — pending Case Owner decision: send Note DM, no second Offer
       (CM-16-008).
    4. **Owner-direct** — the recommender holds ``CVDRole.CASE_OWNER``: the
       recommender is also the decider, so evaluate roles (the offered ones
       when the Offer carries any) and emit the ``Invite`` directly, committed
       in this tree (CM-17-006, CM-17-007, ADR-0109).  Forwarding the Offer to
       the owner would only ask the owner a question it has already answered.
    5. **Fresh path** — evaluate default roles and forward
       ``Offer(CaseParticipant)`` to the Case Owner (CM-16-003, CM-16-004).

    Tree structure::

        RecommendActorToCaseBT (Sequence, memory=False)
        ├── SuggestedActorNotRemovedIfCaseManager — CM-31-013 guard
        ├── GuardedCommitCaseLedgerEntryBT       — record receipt (CLP-10-006)
        └── RecommendActorToCaseIfCaseManager (Selector)   — BT-17-001 gate
            ├── SkipIfNotCaseManager                — Inverter(CheckIsCaseManagerNode)
            └── RecommendActorToCaseEffects (Sequence, memory=False)
                ├── RecordRecommendationRecommenderNode
                └── DuplicateOrFreshSelector (Selector, memory=False)
                    ├── AC-7b: Sequence(ActorAlreadyParticipantNode,
                    │                   EmitAcceptActorRecommendationNode)
                    ├── AC-7a: Sequence(InviteInFlightNode,
                    │                   EmitAcceptActorRecommendationNode)
                    ├── AC-6:  Sequence(PendingOfferCaseParticipantNode,
                    │                   EmitNoteDuplicateRecommendationToOwnerNode)
                    ├── Owner: Sequence(SenderIsCaseOwnerNode(recommender),
                    │                   EvaluateDefaultRolesNode,
                    │                   EmitInviteActorToCaseNode)
                    └── Fresh: Sequence(Inverter(SenderIsCaseOwnerNode),
                                        EvaluateDefaultRolesNode,
                                        EmitOfferCaseParticipantToOwnerNode)

    A receiver that is not the case's CASE_MANAGER passes the gate's skip arm
    and does nothing: no recommender index write, no emit (#3752).

    Only a participant may suggest an actor (CM-16-001): the sender guard
    refuses a suggestion from anyone the case does not list, before the
    case ledger is written or anything is forwarded (HP-01-006, #3668).

    Args:
        recommendation_id: ID of the incoming ``Offer(Actor, Case)`` activity.
        recommender_id: Actor ID of the recommending participant.
        recommended_id: Actor ID of the suggested new participant.
        case_id: ID of the VulnerabilityCase.
        offer_content: Optional ``content`` field from the inbound Offer
            activity; forwarded to the duplicate-recommendation Note per
            CM-16-008.
        suggested_roles: Role strings the received Offer carries
            (``suggestedRoles``), as the CASE_MANAGER stored it.  Injected
            into the role Evaluator on both the owner-direct and fresh paths;
            ``None`` leaves the choice to the Evaluator's default
            (CM-16-003).
        actor_config: The CASE_MANAGER's configuration; its RSVP windows set
            the reply deadline of every stub Invite it sends (CM-11-014,
            CM-28-012).  ``None`` applies the ``ActorConfig`` defaults.

    Returns:
        Root ``RecommendActorToCaseBT`` Sequence node.
    """
    ac7b_already_participant = py_trees.composites.Sequence(
        name="AC7b_AlreadyParticipant",
        memory=False,
        children=[
            ActorAlreadyParticipantNode(
                recommended_id=recommended_id,
                case_id=case_id,
            ),
            EmitAcceptActorRecommendationNode(
                recommender_id=recommender_id,
                recommendation_id=recommendation_id,
                recommended_id=recommended_id,
                case_id=case_id,
            ),
        ],
    )

    ac7a_invite_in_flight = py_trees.composites.Sequence(
        name="AC7a_InviteInFlight",
        memory=False,
        children=[
            InviteInFlightNode(
                recommended_id=recommended_id,
                case_id=case_id,
            ),
            EmitAcceptActorRecommendationNode(
                recommender_id=recommender_id,
                recommendation_id=recommendation_id,
                recommended_id=recommended_id,
                case_id=case_id,
            ),
        ],
    )

    ac6_pending_offer = py_trees.composites.Sequence(
        name="AC6_PendingOffer",
        memory=False,
        children=[
            PendingOfferCaseParticipantNode(
                recommended_id=recommended_id,
                case_id=case_id,
            ),
            EmitNoteDuplicateRecommendationToOwnerNode(
                recommendation_id=recommendation_id,
                recommender_id=recommender_id,
                recommended_id=recommended_id,
                case_id=case_id,
                offer_content=offer_content,
            ),
        ],
    )

    reinvite = py_trees.composites.Sequence(
        name="OwnerReinvite",
        memory=False,
        children=[
            SenderIsCaseOwnerNode(
                sender_actor_id=recommender_id,
                case_id=case_id,
                name="RecommenderIsCaseOwnerForReinvite",
            ),
            ReinviteAwaitingNode(invitee_id=recommended_id, case_id=case_id),
            EvaluateDefaultRolesNode(
                suggested_actor_id=recommended_id,
                case_id=case_id,
                recommendation_id=recommendation_id,
                injected_roles=suggested_roles,
                require_explicit_roles=True,
            ),
            # The record already exists and is on the roster, so only the
            # Invite goes out: no new participant, no Add(CaseParticipant).
            EmitInviteActorToCaseNode(
                invitee_id=recommended_id,
                case_id=case_id,
                attributed_to=recommender_id,
                recommendation_id=recommendation_id,
                # CM-11-015: the fresh stub replaces the earlier one, so
                # there is one live stub per invitee.
                replaces_previous_stub=True,
                actor_config=actor_config,
            ),
        ],
    )

    # CM-11-015: the owner may not re-invite a participant at RM.CLOSED.
    # Anyone else's suggestion is answered as before.
    closed_is_not_reinvited = py_trees.composites.Selector(
        name="ReinviteIsNotToClosedParticipant",
        memory=False,
        children=[
            py_trees.decorators.Inverter(
                name="RecommenderIsNotCaseOwnerForReinvite",
                child=SenderIsCaseOwnerNode(
                    sender_actor_id=recommender_id,
                    case_id=case_id,
                ),
            ),
            ReinviteNotToClosedParticipantNode(
                invitee_id=recommended_id, case_id=case_id
            ),
        ],
    )

    owner_direct_invite = py_trees.composites.Sequence(
        name="OwnerDirectInvite",
        memory=False,
        children=[
            SenderIsCaseOwnerNode(
                sender_actor_id=recommender_id,
                case_id=case_id,
                name="RecommenderIsCaseOwner",
            ),
            EvaluateDefaultRolesNode(
                suggested_actor_id=recommended_id,
                case_id=case_id,
                recommendation_id=recommendation_id,
                injected_roles=suggested_roles,
                # CM-11-019: the Case Owner's direct invite MUST give explicit
                # roles; no VENDOR default for the owner-direct path.
                require_explicit_roles=True,
            ),
            EmitInviteActorToCaseNode(
                invitee_id=recommended_id,
                case_id=case_id,
                attributed_to=recommender_id,
                recommendation_id=recommendation_id,
                actor_config=actor_config,
            ),
            # AC-1: record the inert participant at invite-send time
            # (ADR-0114, CM-11-006).
            CreateInertInviteeParticipantNode(
                invitee_id=recommended_id,
                case_id=case_id,
                recommendation_id=recommendation_id,
            ),
        ],
    )

    # The fresh path re-checks that the recommender is *not* the owner, so an
    # owner-direct emit that fails does not fall through to forwarding the
    # owner's own Offer back to it: the failure surfaces instead.
    fresh_path = py_trees.composites.Sequence(
        name="FreshRecommendation",
        memory=False,
        children=[
            py_trees.decorators.Inverter(
                name="RecommenderIsNotCaseOwner",
                child=SenderIsCaseOwnerNode(
                    sender_actor_id=recommender_id,
                    case_id=case_id,
                ),
            ),
            EvaluateDefaultRolesNode(
                suggested_actor_id=recommended_id,
                case_id=case_id,
                recommendation_id=recommendation_id,
                injected_roles=suggested_roles,
            ),
            EmitOfferCaseParticipantToOwnerNode(
                recommendation_id=recommendation_id,
                recommender_id=recommender_id,
                recommended_id=recommended_id,
                case_id=case_id,
            ),
        ],
    )

    duplicate_or_fresh_selector = py_trees.composites.Selector(
        name="DuplicateOrFreshSelector",
        memory=False,
        children=[
            reinvite,
            ac7b_already_participant,
            ac7a_invite_in_flight,
            ac6_pending_offer,
            owner_direct_invite,
            fresh_path,
        ],
    )

    return create_receive_activity_tree(
        name="RecommendActorToCaseBT",
        case_id=case_id,
        sender_guard=SenderIsActiveParticipantNode(
            status_id="",
            sender_actor_id=recommender_id,
            case_id=case_id,
            name="RecommenderIsParticipant",
        ),
        precondition_guards=[
            case_manager_admits_suggested_actor_guard(
                recommended_id=recommended_id, case_id=case_id
            )
        ],
        manager_effects=[
            closed_is_not_reinvited,
            RecordRecommendationRecommenderNode(
                recommendation_id=recommendation_id,
                recommender_id=recommender_id,
                case_id=case_id,
            ),
            duplicate_or_fresh_selector,
        ],
        manager_case_id=case_id,
        manager_gate_name="RecommendActorToCaseIfCaseManager",
        manager_body_name="RecommendActorToCaseEffects",
    )


def create_accept_actor_recommendation_received_tree(
    recommendation_id: str,
    recommender_id: str,
    invitee_id: str,
    case_id: str,
    sender_id: str,
    roles: list[str] | None = None,
) -> py_trees.composites.Sequence:
    """Received-side BT for Accept(Offer(CaseParticipant)) on the CASE_MANAGER's inbox.

    Commits a canonical ``CaseLedgerEntry`` (CM-16-006 step 1), then fans
    out: sends ``AcceptActorRecommendation`` to the original recommender
    (CM-16-006 step 3) and ``Invite(CaseStub+embargo+roles)`` to the
    invitee (CM-16-006 step 4, CM-17).

    Tree structure::

        AcceptActorRecommendationBT (Sequence, memory=False)
        ├── AcceptedInviteeAdmittedIfCaseManager — CM-31-013 + CM-16-006 guards
        ├── GuardedCommitCaseLedgerEntryBT       — record receipt (CLP-10-006)
        └── AcceptActorRecommendationIfCaseManager (Selector)  — BT-17-001 gate
            ├── SkipIfNotCaseManager
            └── AcceptActorRecommendationEffects (Sequence, memory=False)
                ├── ReinviteNotToClosedParticipantNode — CM-11-015 refusal
                ├── EmitAcceptActorRecommendationNode
                ├── EmitInviteActorToCaseNode
                └── CreateInertInviteeParticipantNode

    Both emits are the CASE_MANAGER's (CM-16-006, PCR-08-007); a receiver
    that is not it does nothing (#3752).  An invitee already at
    ``RM.CLOSED`` is refused before anything is sent, as in the
    recommend-actor tree: a closed participant is never re-invited
    (CM-11-015, ADR-0085).

    ``roles`` and ``invitee_id`` must come from the stored
    ``Offer(CaseParticipant)`` in the DataLayer (ISSUE-1745, CM-16-019): the
    blackboard is empty in this separate BT execution, so the use case is
    responsible for reading them from the stored Offer before calling this
    factory, never from the Accept.

    Only the Case Owner may accept (CM-16-019): the sender guard refuses any
    other sender before the case ledger is written or anything is sent.  An
    acceptance naming an actor removed since the Offer was made is refused
    the same way: a removed participant is sent no stub Invite (CM-31-013).
    So is one naming an actor that has since joined or is at ``RM.CLOSED``:
    it is sent no further stub Invite, so no second Invite entry reaches the
    ledger for it (CM-11-015, CM-16-006).

    Args:
        recommendation_id: ID of the original ``Offer(Actor, Case)`` from the
            recommender (carried in the ``origin`` field of the transformed Offer).
        recommender_id: Actor ID of the original recommender.
        invitee_id: Actor ID of the suggested new participant, from the
            recorded ``Offer(CaseParticipant)``.
        case_id: ID of the VulnerabilityCase.
        sender_id: Actor ID of the Accept's sender, who must be the Case Owner.
        roles: Serialized CVD role strings from the stored
            ``Offer(CaseParticipant)``; passed directly to
            ``EmitInviteActorToCaseNode`` so the Invite carries the correct
            roles without relying on the blackboard.

    Returns:
        Root ``AcceptActorRecommendationBT`` Sequence node.
    """
    return create_receive_activity_tree(
        name="AcceptActorRecommendationBT",
        case_id=case_id,
        sender_guard=SenderIsCaseOwnerNode(
            sender_actor_id=sender_id, case_id=case_id
        ),
        precondition_guards=[
            case_manager_admits_accepted_invitee_guard(
                recommended_id=invitee_id, case_id=case_id
            )
        ],
        manager_effects=[
            # CM-11-015: refuse a closed invitee before anything is sent.
            ReinviteNotToClosedParticipantNode(
                invitee_id=invitee_id, case_id=case_id
            ),
            EmitAcceptActorRecommendationNode(
                recommender_id=recommender_id,
                recommendation_id=recommendation_id,
                recommended_id=invitee_id,
                case_id=case_id,
            ),
            EmitInviteActorToCaseNode(
                invitee_id=invitee_id,
                case_id=case_id,
                roles=roles,
            ),
            # AC-1: record the inert participant at invite-send time
            # (ADR-0114, CM-11-006). Roles from the stored Offer are
            # passed in directly; the blackboard is empty in this BT
            # execution (create_accept_actor_recommendation_received_tree
            # docstring, ISSUE-1745).
            CreateInertInviteeParticipantNode(
                invitee_id=invitee_id,
                case_id=case_id,
                recommendation_id=recommendation_id,
                roles=roles,
            ),
        ],
        manager_case_id=case_id,
        manager_gate_name="AcceptActorRecommendationIfCaseManager",
        manager_body_name="AcceptActorRecommendationEffects",
    )


def create_reject_actor_recommendation_received_tree(
    recommendation_id: str,
    recommender_id: str,
    recommended_id: str,
    case_id: str,
    sender_id: str,
) -> py_trees.composites.Sequence:
    """Received-side BT for Reject(Offer(CaseParticipant)) on the CASE_MANAGER's inbox.

    Commits a canonical ``CaseLedgerEntry`` (CM-16-007 step 1), then sends
    ``RejectActorRecommendation`` to the original recommender
    (CM-16-007 step 3).

    Tree structure::

        RejectActorRecommendationBT (Sequence, memory=False)
        ├── GuardedCommitCaseLedgerEntryBT       — record receipt (CLP-10-006)
        └── RejectActorRecommendationIfCaseManager (Selector)  — BT-17-001 gate
            ├── SkipIfNotCaseManager
            └── EmitRejectActorRecommendationNode

    The emit is the CASE_MANAGER's (CM-16-007); a receiver that is not it
    does nothing (#3752).
    Only the Case Owner may reject (CM-16-019): the sender guard refuses any
    other sender before the case ledger is written or anything is sent.

    Args:
        recommendation_id: ID of the original ``Offer(Actor, Case)`` from the
            recommender (carried in the ``origin`` field of the transformed Offer).
        recommender_id: Actor ID of the original recommender.
        recommended_id: Actor ID of the suggested new participant, from the
            recorded ``Offer(CaseParticipant)``.
        case_id: ID of the VulnerabilityCase.
        sender_id: Actor ID of the Reject's sender, who must be the Case Owner.

    Returns:
        Root ``RejectActorRecommendationBT`` Sequence node.
    """
    return create_receive_activity_tree(
        name="RejectActorRecommendationBT",
        case_id=case_id,
        sender_guard=SenderIsCaseOwnerNode(
            sender_actor_id=sender_id, case_id=case_id
        ),
        precondition_guards=[],
        manager_effects=[
            EmitRejectActorRecommendationNode(
                recommender_id=recommender_id,
                recommendation_id=recommendation_id,
                recommended_id=recommended_id,
                case_id=case_id,
            ),
        ],
        manager_case_id=case_id,
        manager_gate_name="RejectActorRecommendationIfCaseManager",
    )


__all__ = [
    # node classes live in nodes.suggest_actor; re-exported here for backward compat
    "ActorAlreadyParticipantNode",
    "EmitAcceptActorRecommendationNode",
    "EmitNoteDuplicateRecommendationToOwnerNode",
    "EmitOfferCaseParticipantToOwnerNode",
    "EmitRejectActorRecommendationNode",
    "InviteInFlightNode",
    "PendingOfferCaseParticipantNode",
    "create_accept_actor_recommendation_received_tree",
    "create_receive_offer_case_participant_tree",
    "create_recommend_actor_to_case_received_tree",
    "create_reject_actor_recommendation_received_tree",
]
