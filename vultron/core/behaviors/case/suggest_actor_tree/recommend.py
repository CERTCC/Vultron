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

"""Received-side BT for a participant's actor recommendation (ADR-0026, CM-16).

The CASE_MANAGER handles ``Offer(Actor)[target=VulnerabilityCase]`` from a
recommending participant (CM-16-001..004).
"""

import py_trees

from vultron.config.actor import ActorConfig
from vultron.core.behaviors.case.nodes.actor import (
    EmitInviteActorToCaseNode,
    EvaluateDefaultRolesNode,
)
from vultron.core.behaviors.case.nodes.invite_inert_participant import (
    CreateInertInviteeParticipantNode,
)
from vultron.core.behaviors.case.nodes.path_branch import OnPaths
from vultron.core.behaviors.case.nodes.received_path import ReceivedPath
from vultron.core.behaviors.case.nodes.stub_invite_lifetime import (
    ReinviteAwaitingNode,
    ReinviteNotToClosedParticipantNode,
)
from vultron.core.behaviors.case.nodes.suggest_actor import (
    ActorAlreadyParticipantNode,
    EmitAcceptActorRecommendationNode,
    EmitNoteDuplicateRecommendationToOwnerNode,
    EmitOfferCaseParticipantToOwnerNode,
    InviteInFlightNode,
    PendingOfferCaseParticipantNode,
    RecordRecommendationRecommenderNode,
    case_manager_admits_suggested_actor_guard,
)
from vultron.core.behaviors.case.receive_activity_tree import (
    create_receive_activity_tree,
)
from vultron.core.behaviors.case_id_scope import with_case_id
from vultron.core.behaviors.sender_entitlement import (
    SenderIsCaseOwnerNode,
    SenderRule,
)
from vultron.core.behaviors.sender_guard import SenderCheckContext


def create_recommend_actor_to_case_received_tree(
    recommendation_id: str,
    recommender_id: str,
    recommended_id: str,
    case_id: str,
    offer_content: str | None = None,
    suggested_roles: list[str] | None = None,
    actor_config: ActorConfig | None = None,
    *,
    sender_rule: SenderRule,
) -> py_trees.composites.Sequence:
    """Received-side BT for Offer(Actor)[target=VulnerabilityCase] on the CASE_MANAGER's
    inbox.

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
    3. **AC-6** — pending Case Owner decision: record the reinforcing note
       as the CASE_MANAGER's own ``add_note_to_case`` entry, no second Offer
       (CM-16-008, CM-16-016).
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
        recommendation_id: ID of the incoming ``Offer(Actor)[target=VulnerabilityCase]``
        activity.
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
        sender_rule: The use case's declared sender rule; the factory
            composes the sender guard from it (HP-01-025).

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
            with_case_id(
                SenderIsCaseOwnerNode(
                    sender_actor_id=recommender_id,
                    name="RecommenderIsCaseOwnerForReinvite",
                ),
                case_id,
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
                # A retry for the same Offer rebuilds the same Invite
                # (OX-06-002).
                answers=recommendation_id,
            ),
        ],
    )

    # CM-11-043: the owner may not re-invite a participant at RM.CLOSED.
    # Anyone else's suggestion is answered as before.
    closed_is_not_reinvited = py_trees.composites.Selector(
        name="ReinviteIsNotToClosedParticipant",
        memory=False,
        children=[
            py_trees.decorators.Inverter(
                name="RecommenderIsNotCaseOwnerForReinvite",
                child=with_case_id(
                    SenderIsCaseOwnerNode(
                        sender_actor_id=recommender_id,
                    ),
                    case_id,
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
            with_case_id(
                SenderIsCaseOwnerNode(
                    sender_actor_id=recommender_id,
                    name="RecommenderIsCaseOwner",
                ),
                case_id,
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
                # A retry for the same Offer rebuilds the same Invite
                # (OX-06-002).
                answers=recommendation_id,
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
                child=with_case_id(
                    SenderIsCaseOwnerNode(
                        sender_actor_id=recommender_id,
                    ),
                    case_id,
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
        # The Offer reaches two stores: the recommending participant
        # addresses it to the case's CASE_MANAGER, which admits it, commits
        # it and forwards an Offer(CaseParticipant) to the Case Owner, and
        # the CASE_MANAGER's copy reaches a participant replica, which takes
        # it from the CASE_MANAGER alone and does nothing with it
        # (CM-16-001, CM-16-002, PCR-03-001, HP-01-038, #4646).
        paths={
            ReceivedPath.CASE_MANAGER,
            ReceivedPath.PARTICIPANT_REPLICA,
        },
        sender_rule=sender_rule,
        # A replica takes the Offer from the CASE_MANAGER alone, so with no
        # CASE_MANAGER to check against it refuses (PCR-03-001, #4646).
        sender_context=SenderCheckContext(
            sender_id=recommender_id,
            case_id=case_id,
            case_manager_required=True,
        ),
        precondition_guards=[
            # The admission check is the CASE_MANAGER's adjudication, so it
            # is declared on that path rather than run at both (HP-01-038).
            OnPaths.at_case_manager(
                "SuggestedActorAdmitted",
                case_manager_admits_suggested_actor_guard(
                    recommended_id=recommended_id, case_id=case_id
                ),
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
