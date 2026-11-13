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


"""Use cases for actor recommendations and case invitations, and their answers.

No HTTP framework imports permitted here.
"""

import json
import logging
from typing import ClassVar, cast

import py_trees.behaviour

from vultron.core.behaviors.call_out.bundles.actor_resolution import (
    ACTOR_RESOLUTION_DETERMINISTIC,
    ActorResolutionCallOutBundle,
)
from vultron.core.behaviors.case.actor_trigger_trees import (
    accept_actor_recommendation_trigger_bt,
    reject_actor_recommendation_trigger_bt,
    suggest_actor_to_case_trigger_bt,
)
from vultron.core.behaviors.case.stub_invite_lifetime import invitee_record
from vultron.core.ports.clock import ClockPort
from vultron.core.ports.sync_activity import SyncActivityPort
from vultron.core.ports.wire_render import WireRenderPort
from vultron.core.use_cases.triggers._base import SvcActivityTriggerBase
from vultron.core.use_cases.triggers._helpers import (
    resolve_actor,
    resolve_case,
)
from vultron.core.use_cases.triggers.actor._peers import _record_named_peer
from vultron.core.use_cases.triggers.requests import (
    AcceptActorRecommendationTriggerRequest,
    InviteActorToCaseTriggerRequest,
    RejectActorRecommendationTriggerRequest,
    SuggestActorToCaseTriggerRequest,
)
from vultron.enums.roles import CVDRole
from vultron.errors import (
    VultronInvalidStateTransitionError,
)

logger = logging.getLogger(__name__)


class _SvcRecommendActorBase(SvcActivityTriggerBase):
    """Send this actor's own ``Offer(Actor)[target=VulnerabilityCase]`` to the case's CASE_MANAGER.

    The shared emit of the suggest-actor flow (CM-16-001) and of the Case
    Owner's direct invite (CM-17-007): both name an actor the case does not
    yet have, with the roles the requester intends for it, and both reach the
    CASE_MANAGER the same way — the requester's own activity, from the
    requester's own identity and outbox, routed by the SenderSideBT
    (PCR-08-001). Neither executes a tree as the CASE_MANAGER (CM-24-011,
    ADR-0109); what the CASE_MANAGER does with the Offer is decided on its
    side, by the recommend-actor received tree.

    Subclasses implement :meth:`_prepare` and call
    :meth:`_prepare_recommendation` from it.
    """

    def __init__(
        self,
        dl: object,
        request: object,
        trigger_activity: object = None,
        call_out: ActorResolutionCallOutBundle = ACTOR_RESOLUTION_DETERMINISTIC,
        wire_render_port: WireRenderPort | None = None,
        sync_port: SyncActivityPort | None = None,
        *,
        clock: ClockPort,
    ) -> None:
        super().__init__(
            dl=dl,  # type: ignore[arg-type]
            request=request,
            trigger_activity=trigger_activity,  # type: ignore[arg-type]
            wire_render_port=wire_render_port,
            sync_port=sync_port,
            clock=clock,
        )
        self._actor_resolution_call_out = call_out

    def _prepare_recommendation(
        self,
        actor_id: str,
        case_id: str,
        recommended_id: str,
        field: str,
        roles: list[CVDRole] | None,
    ) -> None:
        """Resolve the requester and case, and record the named peer.

        Args:
            actor_id: The requesting actor, as the request names it.
            case_id: The case, as the request names it.
            recommended_id: The actor being recommended or invited.
            field: Name of the request field *recommended_id* came from.
            roles: The roles the requester intends for that actor, if any.
        """
        actor = resolve_actor(actor_id, self._dl)
        self._actor_id = actor.id_
        self._case = resolve_case(case_id, self._dl)

        # The named actor is a peer by definition — the whole point is to name
        # an actor the *case* does not yet have. Under ADR-0073 its record is in
        # the store of whoever knows it, so demanding one here refused every
        # genuinely remote candidate.
        _record_named_peer(
            self._dl,
            recommended_id,
            field,
            actor.id_,
            self._actor_resolution_call_out,
        )

        self._recommended_id = recommended_id
        self._suggested_roles = [r.value for r in roles] if roles else None

    def _build_tree(self) -> py_trees.behaviour.Behaviour:
        def _build_activities(case_manager_id: str) -> list[str]:
            activity_id, activity_dict = self._factory.suggest_actor_to_case(
                recommended_id=self._recommended_id,
                case_id=self._case.id_,
                actor=self._actor_id,
                to=[case_manager_id],
                roles=self._suggested_roles,
                at=self._at,
            )
            self._captured["activity"] = json.loads(activity_dict)
            return [activity_id]

        return suggest_actor_to_case_trigger_bt(
            case_id=self._case.id_,
            activity_builder=_build_activities,
        )


class SvcSuggestActorToCaseUseCase(_SvcRecommendActorBase):
    """Recommend another actor for participation in an existing case.

    Emits a RecommendActorActivity routed through the Case Manager
    (SenderSideBT / PCR-08-001).
    """

    def _prepare(self) -> None:
        request = cast(SuggestActorToCaseTriggerRequest, self._request)
        self._prepare_recommendation(
            request.actor_id,
            request.case_id,
            request.suggested_actor_id,
            "suggested_actor_id",
            request.roles,
        )

    def _handle_result(self) -> None:
        logger.info(
            "Actor '%s' suggested actor '%s' for case '%s'",
            self._actor_id,
            self._recommended_id,
            self._case.id_,
        )


class SvcInviteActorToCaseUseCase(_SvcRecommendActorBase):
    """Ask the CASE_MANAGER to invite an actor to a case (case-owner action).

    The Case Owner sends its own ``Offer(Actor)[target=VulnerabilityCase]`` carrying the
    intended
    roles to the CASE_MANAGER, from the owner's identity and outbox
    (CM-17-007, CM-17-017). It executes no tree as the CASE_MANAGER and never emits in
    its name (CM-24-010, ADR-0109): the CASE_MANAGER's recommend-actor
    received tree sees that the recommender holds ``CVDRole.CASE_OWNER`` and
    emits the ``Invite`` itself, from its own store, committing it in that
    emitting tree (CM-17-006).

    The ``202`` this trigger earns therefore means the Offer was queued, not
    that the Invite was sent; the result's ``activity`` is the Offer.
    """

    def _prepare(self) -> None:
        request = cast(InviteActorToCaseTriggerRequest, self._request)
        self._prepare_recommendation(
            request.actor_id,
            request.case_id,
            request.invitee_id,
            "invitee_id",
            request.roles,
        )
        self._refuse_reinvite_of_closed(request.invitee_id)

    def _refuse_reinvite_of_closed(self, invitee_id: str) -> None:
        """Refuse before anything is queued: ``RM.CLOSED`` has no rejoin.

        A participant at ``RM.CLOSED`` cannot be re-invited (CM-11-043,
        ADR-0085), so the owner's Offer is never sent.  The CASE_MANAGER's
        received tree refuses it too, for an Offer that arrives from elsewhere.
        """
        record = invitee_record(self._dl, self._case, invitee_id)
        if record is not None and record.rm_closed:
            raise VultronInvalidStateTransitionError(
                f"Actor '{invitee_id}' is at RM.CLOSED in case"
                f" '{self._case.id_}' and cannot be re-invited (CM-11-043,"
                " ADR-0085)"
            )

    def _handle_result(self) -> None:
        logger.info(
            "Actor '%s' asked the CASE_MANAGER to invite actor '%s' to case"
            " '%s'",
            self._actor_id,
            self._recommended_id,
            self._case.id_,
        )


class _SvcActorRecommendationAnswerBase(SvcActivityTriggerBase):
    """The Case Owner's answer to a forwarded Offer(CaseParticipant) (ADR-0026).

    Shared by the Accept (CM-16-006) and the Reject (CM-16-007): both name
    the forwarded Offer and the CaseActor the answer goes to.  Subclasses
    build the tree and name the verb they log.
    """

    _verb: ClassVar[str]
    """Past-tense verb for the success log line; each subclass sets it."""

    def _prepare(self) -> None:
        request = cast(
            AcceptActorRecommendationTriggerRequest
            | RejectActorRecommendationTriggerRequest,
            self._request,
        )
        actor = resolve_actor(request.actor_id, self._dl)
        self._actor_id = actor.id_
        self._cp_offer_id = request.cp_offer_id
        self._case_actor_id = request.case_actor_id

    def _handle_result(self) -> None:
        logger.info(
            "Actor '%s' %s actor recommendation offer '%s' → CaseActor '%s'",
            self._actor_id,
            self._verb,
            self._cp_offer_id,
            self._case_actor_id,
        )


class SvcAcceptActorRecommendationUseCase(_SvcActorRecommendationAnswerBase):
    """Accept an actor recommendation on behalf of the Case Owner.

    Emits Accept(Offer(CaseParticipant)) queued in the Case Owner's outbox for
    delivery to the CaseActor, completing ADR-0026 CM-16-006.
    """

    _verb = "accepted"

    def _build_tree(self) -> py_trees.behaviour.Behaviour:
        return accept_actor_recommendation_trigger_bt(
            cp_offer_id=self._cp_offer_id,
            case_actor_id=self._case_actor_id,
            captured=self._captured,
        )


class SvcRejectActorRecommendationUseCase(_SvcActorRecommendationAnswerBase):
    """Reject an actor recommendation on behalf of the Case Owner.

    Emits Reject(Offer(CaseParticipant)) queued in the Case Owner's outbox for
    delivery to the CaseActor, which ledgers it and answers the recommender
    (ADR-0026, CM-16-007).
    """

    _verb = "rejected"

    def _build_tree(self) -> py_trees.behaviour.Behaviour:
        return reject_actor_recommendation_trigger_bt(
            cp_offer_id=self._cp_offer_id,
            case_actor_id=self._case_actor_id,
            captured=self._captured,
        )
