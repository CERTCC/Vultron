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
from typing import cast

import py_trees.behaviour

from vultron.core.behaviors.case.actor_trigger_trees import (
    accept_case_invite_trigger_bt,
    invite_actor_to_case_trigger_bt,
    suggest_actor_to_case_trigger_bt,
)
from vultron.core.use_cases._helpers import _find_case_actor_id
from vultron.core.use_cases.triggers._base import SvcBTTriggerBase
from vultron.core.use_cases.triggers._helpers import (
    resolve_actor,
    resolve_case,
)
from vultron.core.use_cases.triggers.requests import (
    AcceptCaseInviteTriggerRequest,
    InviteActorToCaseTriggerRequest,
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

        case_actor_id = _find_case_actor_id(self._dl, self._case.id_)
        self._actor_id = case_actor_id if case_actor_id else owner_id
        self._attributed_to = owner_id if case_actor_id else None

    def _build_tree(self) -> py_trees.behaviour.Behaviour:
        return invite_actor_to_case_trigger_bt(
            invitee_id=self._invitee_id,
            case_id=self._case.id_,
            attributed_to=self._attributed_to,
            captured=self._captured,
        )

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
