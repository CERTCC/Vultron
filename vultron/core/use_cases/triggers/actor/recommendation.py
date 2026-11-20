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

from vultron.config.actor import ActorConfig
from vultron.core.behaviors.act_key_scope import with_act_keys
from vultron.core.behaviors.act_keys import CASE_ID, INVITEE_ID
from vultron.core.behaviors.call_out.bundles.actor_resolution import (
    ACTOR_RESOLUTION_DETERMINISTIC,
    ActorResolutionCallOutBundle,
)
from vultron.core.behaviors.case.actor_trigger_trees import (
    accept_actor_recommendation_trigger_bt,
    case_manager_invite_actor_trigger_bt,
    reject_actor_recommendation_trigger_bt,
    suggest_actor_to_case_trigger_bt,
)
from vultron.core.behaviors.case.nodes.suggest_actor.admission import (
    not_invitable_refusal,
    removed_participant_refusal,
)
from vultron.core.behaviors.sender.send_tree import sender_side_bt
from vultron.core.participants.role_predicate import has_role
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
    VultronValidationError,
)
from vultron.primitives import same_actor_id

logger = logging.getLogger(__name__)


class _SvcRecommendActorBase(SvcActivityTriggerBase):
    """Shared preparation of the two ways an actor is named for a case.

    A participant's suggestion, ``Offer(Actor)[target=VulnerabilityCase]``
    (CM-16-001), and the Case Owner's own Invite (CM-17-007) both name an
    actor the case does not yet have, with the roles the requester intends
    for it, and both reach the CASE_MANAGER the same way: the requester's own
    activity, from the requester's own identity and outbox, routed by the
    SenderSideBT (PCR-08-001).  Neither executes a tree as the CASE_MANAGER
    (CM-24-011, ADR-0109).

    Subclasses implement :meth:`_prepare`, call
    :meth:`_prepare_recommendation` from it, and build their own tree.
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


class SvcSuggestActorToCaseUseCase(_SvcRecommendActorBase):
    """Recommend another actor for participation in an existing case.

    Emits a RecommendActorActivity routed through the Case Manager
    (SenderSideBT / PCR-08-001).  The Case Owner is refused: its decision is
    its own Invite (:class:`SvcInviteActorToCaseUseCase`, CM-17-007).
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
        # The Case Owner decides; it does not suggest.  The CASE_MANAGER
        # refuses its Offer(Actor), so it is not sent (CM-17-007, ADR-0199).
        if has_role(
            self._actor_id, self._case.id_, CVDRole.CASE_OWNER, self._dl
        ):
            raise VultronValidationError(
                f"'{self._actor_id}' is the Case Owner of case"
                f" '{self._case.id_}': it invites an actor with"
                " invite-actor-to-case, its own Invite, not a suggestion"
                " (CM-17-007, ADR-0199)"
            )

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

    def _handle_result(self) -> None:
        logger.info(
            "Actor '%s' suggested actor '%s' for case '%s'",
            self._actor_id,
            self._recommended_id,
            self._case.id_,
        )


class SvcInviteActorToCaseUseCase(_SvcRecommendActorBase):
    """Invite an actor to a case (the Case Owner's decision).

    The Case Owner decides whom the case invites, and says so with its own
    ``Invite(<case preview>)[target=<invitee>]`` carrying the roles, sent to
    the CASE_MANAGER only, from the Owner's identity and outbox (CM-17-007,
    ADR-0199).  It executes no tree as the CASE_MANAGER and never emits in
    its name (CM-17-017, CM-24-010, ADR-0109): the CASE_MANAGER's received
    tree commits the Owner's Invite and sends its own stub Invite to the
    invitee, crediting the Owner (PCR-08-007, CM-17-006).  The ``202`` this
    trigger earns therefore means the Owner's Invite was queued, not that
    the stub Invite was sent; the result's ``activity`` is the Owner's.

    An Owner that holds the CASE_MANAGER role has no one to ask: it sends
    the stub Invite straight to the invitee, as its own act with neither
    ``attributedTo`` nor ``inReplyTo`` (CM-24-021), committed with the inert
    participant it creates (CM-11-006, CM-17-006); the result's
    ``activity`` is that stub Invite.

    Refused before anything is queued (TRIG-03, RSH-09): an Invite from an
    actor that is not the Case Owner, one with no
    roles (CM-11-019, CM-11-050), and one whose invitee is the Owner, the
    CASE_MANAGER, or a participant that was removed (CM-31-013), has joined
    or is at ``RM.CLOSED`` (CM-11-043, ADR-0085).  The CASE_MANAGER refuses
    the same Invite for
    the same reasons, for an Invite that arrives from elsewhere.
    """

    def __init__(
        self,
        dl: object,
        request: object,
        trigger_activity: object = None,
        call_out: ActorResolutionCallOutBundle = ACTOR_RESOLUTION_DETERMINISTIC,
        wire_render_port: WireRenderPort | None = None,
        sync_port: SyncActivityPort | None = None,
        actor_config: ActorConfig | None = None,
        *,
        clock: ClockPort,
    ) -> None:
        super().__init__(
            dl,
            request,
            trigger_activity,
            call_out,
            wire_render_port,
            sync_port,
            clock=clock,
        )
        # The RSVP window of the stub Invite an Owner that is the
        # CASE_MANAGER sends itself (CM-11-014, CM-28-012).
        self._actor_config = actor_config

    def _prepare(self) -> None:
        request = cast(InviteActorToCaseTriggerRequest, self._request)
        self._prepare_recommendation(
            request.actor_id,
            request.case_id,
            request.invitee_id,
            "invitee_id",
            request.roles,
        )
        self._refuse_unaskable_invite()
        self._is_case_manager = has_role(
            self._actor_id, self._case.id_, CVDRole.CASE_MANAGER, self._dl
        )

    def _refuse_unaskable_invite(self) -> None:
        """Refuse an Invite the CASE_MANAGER would refuse, before it is sent.

        Raises:
            VultronValidationError: The requester is not the Case Owner, or
                the Invite names no role, or names the Owner or the case's
                CASE_MANAGER as the invitee.
            VultronInvalidStateTransitionError: The invitee was removed
                (CM-31-013), has joined the case, or is at ``RM.CLOSED``,
                which has no rejoin.
        """
        invitee_id = self._recommended_id
        case_id = self._case.id_
        if not has_role(self._actor_id, case_id, CVDRole.CASE_OWNER, self._dl):
            raise VultronValidationError(
                f"'{self._actor_id}' does not hold CASE_OWNER in case"
                f" '{case_id}': only the Case Owner invites; a participant"
                " suggests an actor with suggest-actor-to-case (CM-17-007,"
                " CM-16-001)"
            )
        if not self._suggested_roles:
            raise VultronValidationError(
                f"the Invite of '{invitee_id}' to case '{case_id}' names no"
                " role; the Case Owner names at least one (CM-11-019,"
                " CM-11-050)"
            )
        if same_actor_id(invitee_id, self._actor_id) or has_role(
            invitee_id, case_id, CVDRole.CASE_MANAGER, self._dl
        ):
            raise VultronValidationError(
                f"'{invitee_id}' is the Case Owner or the CASE_MANAGER of"
                f" case '{case_id}' and is sent no stub Invite (CM-17-015)"
            )
        refusal = removed_participant_refusal(
            self._dl, self._case, invitee_id, case_id
        ) or not_invitable_refusal(self._dl, self._case, invitee_id)
        if refusal is not None:
            raise VultronInvalidStateTransitionError(refusal)

    def _build_tree(self) -> py_trees.behaviour.Behaviour:
        roles = list(self._suggested_roles or [])
        if self._is_case_manager:
            return with_act_keys(
                case_manager_invite_actor_trigger_bt(
                    offered_roles=roles,
                    actor_config=self._actor_config,
                    captured=self._captured,
                ),
                {CASE_ID: self._case.id_, INVITEE_ID: self._recommended_id},
            )

        def _build_activities(case_manager_id: str) -> list[str]:
            activity_id, activity_blob = self._factory.invite_actor_to_case(
                invitee_id=self._recommended_id,
                case_id=self._case.id_,
                actor=self._actor_id,
                to=[case_manager_id],
                roles=roles,
                case=self._case,
                at=self._at,
            )
            self._captured["activity"] = json.loads(activity_blob)
            return [activity_id]

        return sender_side_bt(
            case_id=self._case.id_, activity_builder=_build_activities
        )

    def _handle_result(self) -> None:
        if self._is_case_manager:
            logger.info(
                "Actor '%s', the CASE_MANAGER, invited actor '%s' to case"
                " '%s'",
                self._actor_id,
                self._recommended_id,
                self._case.id_,
            )
            return
        logger.info(
            "Actor '%s' sent the CASE_MANAGER its Invite of actor '%s' to"
            " case '%s'",
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
