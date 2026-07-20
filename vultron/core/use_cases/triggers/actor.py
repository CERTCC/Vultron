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
    invite_actor_to_case_trigger_bt,
    offer_case_manager_role_trigger_bt,
    suggest_actor_to_case_trigger_bt,
)
from vultron.core.use_cases._helpers import _find_case_actor_id
from vultron.core.use_cases.triggers._base import SvcBTTriggerBase
from vultron.core.use_cases.triggers._helpers import (
    resolve_actor,
    resolve_case,
)
from vultron.core.use_cases.triggers.requests import (
    AcceptActorRecommendationTriggerRequest,
    AcceptCaseInviteTriggerRequest,
    InviteActorToCaseTriggerRequest,
    OfferCaseManagerRoleTriggerRequest,
    SuggestActorToCaseTriggerRequest,
)
from vultron.errors import (
    VultronNotFoundError,
    VultronValidationError,
)

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

    def _build_tree(self) -> py_trees.behaviour.Behaviour:
        def _build_activities(case_manager_id: str) -> list[str]:
            activity_id, activity_dict = self._factory.suggest_actor_to_case(
                recommended_id=self._suggested_actor_id,
                case_id=self._case.id_,
                actor=self._actor_id,
                to=[case_manager_id],
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

        case_actor_id = _find_case_actor_id(self._dl, self._case.id_)
        self._actor_id = case_actor_id if case_actor_id else owner_id
        # When case_actor_id is None (no dedicated CaseActor), the Invite is
        # sent without cc: so no self-delivery occurs and no CaseLedgerEntry
        # is committed — by design (ADR-0021: no CaseActor → no canonical
        # ledger).
        self._case_actor_id = case_actor_id
        self._attributed_to = owner_id if case_actor_id else None

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

        raw_invite = self._dl.read(request.invite_id)
        if raw_invite is None:
            raise VultronNotFoundError(
                "RmInviteToCaseActivity", request.invite_id
            )

        invite_type = getattr(raw_invite, "type_", "")
        if invite_type != "Invite":
            raise VultronValidationError(
                f"'{request.invite_id}' is not an RmInviteToCaseActivity"
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


class SvcOfferCaseManagerRoleUseCase(SvcBTTriggerBase):
    """Offer the CASE_MANAGER role to the Case Actor (trigger-side path).

    Emits ``_OfferCaseManagerRoleActivity`` from the Case Actor's identity to
    itself, initiating the CASE_MANAGER delegation handshake.  This is the
    manual trigger-side counterpart to the automatic path wired into
    ``receive_report_case_tree.py`` (DEMOMA-08-007).

    The Case Actor service must already exist in the DataLayer (spawned by
    the CaseActor spawning protocol, issue #1092).
    """

    def _prepare(self) -> None:
        request = cast(OfferCaseManagerRoleTriggerRequest, self._request)
        # Validate the requesting actor exists in the DataLayer.
        resolve_actor(request.actor_id, self._dl)
        self._case = resolve_case(request.case_id, self._dl)

        case_actor_id = _find_case_actor_id(self._dl, self._case.id_)
        if case_actor_id is None:
            raise VultronNotFoundError("CaseActor", self._case.id_)

        participant_id = self._case.actor_participant_index.get(case_actor_id)
        if not participant_id:
            raise VultronNotFoundError(
                "CaseParticipant for CaseActor", case_actor_id
            )

        self._case_actor_id: str = case_actor_id
        self._case_actor_participant_id: str = participant_id
        # BT runs under the Case Actor's identity so the offer is queued in
        # the Case Actor's outbox (mirrors the automatic path in
        # receive_report_case_tree.py).
        self._actor_id = case_actor_id

    def _build_tree(self) -> py_trees.behaviour.Behaviour:
        return offer_case_manager_role_trigger_bt(captured=self._captured)

    def _extra_execute_kwargs(self) -> dict[str, Any]:
        return {
            "case_id": self._case.id_,
            "case_actor_id": self._case_actor_id,
            "case_actor_participant_id": self._case_actor_participant_id,
        }

    def _handle_result(self) -> None:
        logger.info(
            "CASE_MANAGER role offered for case '%s'",
            self._case.id_,
        )


class SvcAcceptCaseManagerRoleUseCase:
    """Stub for the manual accept-case-manager-role trigger path.

    The auto-accept path in ``OfferCaseManagerRoleReceivedUseCase`` handles
    CASE_MANAGER role acceptance automatically for the demo.  This class is
    a stub satisfying the interface contract (DEMOMA-08-008); full manual
    override is deferred until required.

    TODO(#1127): Implement when a manual override trigger is needed.
    """

    def __init__(
        self,
        dl: object,
        request: object,
        trigger_activity: object = None,
    ) -> None:
        self._dl = dl
        self._request = request

    def execute(self) -> dict:
        raise NotImplementedError(
            "SvcAcceptCaseManagerRoleUseCase.execute() is not yet implemented."
            " The auto-accept path (OfferCaseManagerRoleReceivedUseCase)"
            " handles CASE_MANAGER acceptance automatically."
        )
