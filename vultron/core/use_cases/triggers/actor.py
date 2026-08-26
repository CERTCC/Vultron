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

"""
Class-based use cases for actor-level trigger behaviors.

No HTTP framework imports permitted here.
"""

import logging
from typing import Any, cast

import py_trees.behaviour

from vultron.core.behaviors.case.actor_trigger_trees import (
    accept_actor_recommendation_trigger_bt,
    accept_case_invite_trigger_bt,
    accept_case_ownership_transfer_trigger_bt,
    invite_actor_to_case_trigger_bt,
    offer_case_ownership_transfer_trigger_bt,
    reject_case_invite_trigger_bt,
    suggest_actor_to_case_trigger_bt,
)
from vultron.core.models._helpers import _as_id
from vultron.core.use_cases._helpers import _find_case_actor_id
from vultron.core.use_cases.triggers._base import SvcBTTriggerBase
from vultron.core.use_cases.triggers._helpers import (
    _prepare_delegated_context,
    resolve_actor,
    resolve_case,
)
from vultron.core.use_cases.triggers.requests import (
    AcceptActorRecommendationTriggerRequest,
    AcceptCaseInviteTriggerRequest,
    AcceptCaseOwnershipTransferTriggerRequest,
    InviteActorToCaseTriggerRequest,
    OfferCaseOwnershipTransferTriggerRequest,
    OfferCaseParticipantRoleTriggerRequest,
    RejectCaseInviteTriggerRequest,
    SuggestActorToCaseTriggerRequest,
)
from vultron.errors import VultronNotFoundError

logger = logging.getLogger(__name__)


class SvcSuggestActorToCaseUseCase(SvcBTTriggerBase):
    """Recommend another actor for participation in an existing case.

    Emits a RecommendActorActivity routed through the Case Manager
    (SenderSideBT / PCR-08-001).
    """

    def _prepare(self) -> None:
        request = cast(SuggestActorToCaseTriggerRequest, self._request)
        actor = resolve_actor(request.actor_id, self._dl)
        self._actor_id = actor.id_
        self._case = resolve_case(request.case_id, self._dl)

        suggested_raw = self._dl.read(request.suggested_actor_id)
        if suggested_raw is None:
            raise VultronNotFoundError("Actor", request.suggested_actor_id)

        self._suggested_actor_id = request.suggested_actor_id
        self._suggested_roles = (
            [r.value for r in request.roles] if request.roles else None
        )

    def _build_tree(self) -> py_trees.behaviour.Behaviour:
        def _build_activities(case_manager_id: str) -> list[str]:
            activity_id, activity_dict = self._factory.suggest_actor_to_case(
                recommended_id=self._suggested_actor_id,
                case_id=self._case.id_,
                actor=self._actor_id,
                to=[case_manager_id],
                roles=self._suggested_roles,
            )
            self._captured["activity"] = activity_dict
            return [activity_id]

        return suggest_actor_to_case_trigger_bt(
            case_id=self._case.id_,
            activity_builder=_build_activities,
        )

    def _handle_result(self) -> None:
        logger.info(
            "Actor '%s' suggested actor '%s' for case '%s'",
            self._actor_id,
            self._suggested_actor_id,
            self._case.id_,
        )


class SvcAcceptActorRecommendationUseCase(SvcBTTriggerBase):
    """Accept an actor recommendation on behalf of the Case Owner.

    Emits Accept(Offer(CaseParticipant)) queued in the Case Owner's outbox for
    delivery to the CaseActor, completing ADR-0026 CM-16-006.
    """

    def _prepare(self) -> None:
        request = cast(AcceptActorRecommendationTriggerRequest, self._request)
        actor = resolve_actor(request.actor_id, self._dl)
        self._actor_id = actor.id_
        self._cp_offer_id = request.cp_offer_id
        self._case_actor_id = request.case_actor_id

    def _build_tree(self) -> py_trees.behaviour.Behaviour:
        return accept_actor_recommendation_trigger_bt(
            cp_offer_id=self._cp_offer_id,
            case_actor_id=self._case_actor_id,
            captured=self._captured,
        )

    def _handle_result(self) -> None:
        logger.info(
            "Actor '%s' accepted actor recommendation offer '%s' → CaseActor '%s'",
            self._actor_id,
            self._cp_offer_id,
            self._case_actor_id,
        )


class SvcInviteActorToCaseUseCase(SvcBTTriggerBase):
    """Directly invite an actor to a case (case-owner action).

    Emits RmInviteToCaseActivity from the Case Actor's identity
    (PCR-08-007).  ``self._actor_id`` is set to the Case Actor URI in
    ``_prepare()`` so the BT queues the invite in the Case Actor's outbox.
    """

    def _prepare(self) -> None:
        request = cast(InviteActorToCaseTriggerRequest, self._request)
        actor = resolve_actor(request.actor_id, self._dl)
        owner_id = actor.id_
        self._case = resolve_case(request.case_id, self._dl)

        invitee_raw = self._dl.read(request.invitee_id)
        if invitee_raw is None:
            raise VultronNotFoundError("Actor", request.invitee_id)

        self._invitee_id = request.invitee_id
        self._suggested_roles = request.roles

        # Delegated-message contract (CM-24-001..003)
        self._actor_id, self._attributed_to = _prepare_delegated_context(
            self._dl, self._case.id_, owner_id
        )
        # case_actor_id also needed for invite BT routing (ADR-0021: no
        # CaseActor → no cc: → no self-delivery → no CaseLedgerEntry commit)
        self._case_actor_id = _find_case_actor_id(self._dl, self._case.id_)

    def _build_tree(self) -> py_trees.behaviour.Behaviour:
        return invite_actor_to_case_trigger_bt(
            invitee_id=self._invitee_id,
            case_id=self._case.id_,
            case_actor_id=self._case_actor_id,
            attributed_to=self._attributed_to,
            captured=self._captured,
        )

    def _extra_execute_kwargs(self) -> dict[str, Any]:
        kwargs = super()._extra_execute_kwargs()
        if self._suggested_roles is not None:
            kwargs["suggested_roles"] = self._suggested_roles
        return kwargs

    def _handle_result(self) -> None:
        logger.info(
            "Actor '%s' invited actor '%s' to case '%s'",
            self._actor_id,
            self._invitee_id,
            self._case.id_,
        )


class SvcAcceptCaseInviteUseCase(SvcBTTriggerBase):
    """Accept a case invitation by emitting RmAcceptInviteToCaseActivity.

    The invitee actor reads the invite from the DataLayer and queues the
    Accept activity for delivery to the Case Actor.
    """

    def _prepare(self) -> None:
        request = cast(AcceptCaseInviteTriggerRequest, self._request)
        actor = resolve_actor(request.actor_id, self._dl)
        self._actor_id = actor.id_

        if self._dl.read(request.invite_id) is None:
            raise VultronNotFoundError(
                "RmInviteToCaseActivity", request.invite_id
            )

        self._invite_id = request.invite_id

    def _build_tree(self) -> py_trees.behaviour.Behaviour:
        return accept_case_invite_trigger_bt(
            invite_id=self._invite_id,
            captured=self._captured,
        )

    def _handle_result(self) -> None:
        logger.info(
            "Actor '%s' accepted case invite '%s'",
            self._actor_id,
            self._invite_id,
        )


class SvcRejectCaseInviteUseCase(SvcBTTriggerBase):
    """Reject a case invitation by emitting RmRejectInviteToCaseActivity.

    The invitee actor reads the invite from the DataLayer and queues the
    Reject activity for delivery to the Case Actor.
    """

    def _prepare(self) -> None:
        request = cast(RejectCaseInviteTriggerRequest, self._request)
        actor = resolve_actor(request.actor_id, self._dl)
        self._actor_id = actor.id_

        if self._dl.read(request.invite_id) is None:
            raise VultronNotFoundError(
                "RmInviteToCaseActivity", request.invite_id
            )

        self._invite_id = request.invite_id

    def _build_tree(self) -> py_trees.behaviour.Behaviour:
        return reject_case_invite_trigger_bt(
            invite_id=self._invite_id,
            captured=self._captured,
        )

    def _handle_result(self) -> None:
        logger.info(
            "Actor '%s' rejected case invite '%s'",
            self._actor_id,
            self._invite_id,
        )


class SvcOfferCaseOwnershipTransferUseCase(SvcBTTriggerBase):
    """Offer case ownership to another actor (trigger-side path).

    Emits ``Offer(VulnerabilityCase)`` (ownership transfer variant) from the
    CaseActor's identity on behalf of the offering actor (CM-24-001, TRIG-11-001).
    """

    def _prepare(self) -> None:
        request = cast(OfferCaseOwnershipTransferTriggerRequest, self._request)
        actor = resolve_actor(request.actor_id, self._dl)
        offering_actor_id = actor.id_
        self._case = resolve_case(request.case_id, self._dl)

        if self._dl.read(request.transferee_id) is None:
            raise VultronNotFoundError("Actor", request.transferee_id)

        self._transferee_id = request.transferee_id
        self._content = request.content

        # Delegated-message contract: emit from CaseActor identity (CM-24-001..003)
        self._actor_id, self._attributed_to = _prepare_delegated_context(
            self._dl, self._case.id_, offering_actor_id
        )

    def _build_tree(self) -> py_trees.behaviour.Behaviour:
        return offer_case_ownership_transfer_trigger_bt(
            case_id=self._case.id_,
            transferee_id=self._transferee_id,
            content=self._content,
            attributed_to=self._attributed_to,
            captured=self._captured,
        )

    def _handle_result(self) -> None:
        logger.info(
            "Actor '%s' offered case ownership transfer for case '%s' to '%s'",
            self._actor_id,
            self._case.id_,
            self._transferee_id,
        )


class SvcAcceptCaseOwnershipTransferUseCase(SvcBTTriggerBase):
    """Accept a case ownership transfer offer (trigger-side path).

    Emits ``Accept(Offer(VulnerabilityCase))`` from the accepting actor back
    to the offering actor (TRIG-11-002).
    """

    def _prepare(self) -> None:
        request = cast(
            AcceptCaseOwnershipTransferTriggerRequest, self._request
        )
        actor = resolve_actor(request.actor_id, self._dl)
        self._actor_id = actor.id_

        offer = self._dl.read(request.offer_id)
        if offer is None:
            raise VultronNotFoundError(
                "VultronOwnershipTransferOfferRecord", request.offer_id
            )

        self._offer_id = request.offer_id

        # Two shapes reach this point for the same Offer: the SYNC replica path
        # stores a VultronOwnershipTransferOfferRecord (case URI in `case_id`),
        # while the HTTP-inbox path stores the wire Offer activity (case in
        # `object_`, possibly rehydrated to a typed object).  Accept either.
        raw_case_id = _as_id(
            getattr(offer, "case_id", None) or getattr(offer, "object_", None)
        )
        if not raw_case_id:
            raise VultronNotFoundError(
                "VulnerabilityCase (in Offer case reference)", request.offer_id
            )
        self._case_id = raw_case_id

    def _build_tree(self) -> py_trees.behaviour.Behaviour:
        return accept_case_ownership_transfer_trigger_bt(
            offer_id=self._offer_id,
            case_id=self._case_id,
            captured=self._captured,
        )

    def _handle_result(self) -> None:
        logger.info(
            "Actor '%s' accepted case ownership transfer offer '%s'",
            self._actor_id,
            self._offer_id,
        )


class SvcOfferCaseParticipantRoleUseCase:
    """Offer a CVDRole to a target Actor via the canonical ADR-0039 wire format.

    Emits ``Offer(CaseParticipantRole, target=Actor, context=VulnerabilityCase)``
    from the requesting actor.  The trigger_activity adapter's
    ``offer_case_participant_role`` method handles wire construction and
    DataLayer persistence.  No BT orchestration is needed on the sending side.

    See SE-08-003, ADR-0039.
    """

    def __init__(
        self,
        dl: object,
        request: object,
        trigger_activity: object = None,
    ) -> None:
        self._dl = dl
        self._request = request
        self._trigger_activity = trigger_activity

    def execute(self) -> dict[str, Any]:
        from vultron.core.ports.trigger_activity import TriggerActivityPort

        if self._trigger_activity is None:
            raise RuntimeError(
                "SvcOfferCaseParticipantRoleUseCase requires a TriggerActivityPort"
            )
        req = cast(OfferCaseParticipantRoleTriggerRequest, self._request)
        factory = cast(TriggerActivityPort, self._trigger_activity)
        activity_id, activity_dict = factory.offer_case_participant_role(
            case_id=req.case_id,
            role=req.role,
            target_actor_id=req.target_actor_id,
            actor=req.actor_id,
        )
        logger.info(
            "SvcOfferCaseParticipantRoleUseCase: queued Offer(CaseParticipantRole)"
            " '%s' for case '%s' role '%s' → actor '%s'",
            activity_id,
            req.case_id,
            req.role,
            req.target_actor_id,
        )
        return {"activity_id": activity_id, "activity": activity_dict}
