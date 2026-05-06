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
from typing import TYPE_CHECKING, Any

from vultron.core.ports.case_persistence import CaseOutboxPersistence
from vultron.core.use_cases.triggers._helpers import (
    add_activity_to_outbox,
    resolve_actor,
    resolve_case,
)
from vultron.core.use_cases.triggers.requests import (
    AcceptCaseInviteTriggerRequest,
    InviteActorToCaseTriggerRequest,
    SuggestActorToCaseTriggerRequest,
)
from vultron.errors import VultronNotFoundError, VultronValidationError

if TYPE_CHECKING:
    from vultron.core.ports.trigger_activity import TriggerActivityPort

logger = logging.getLogger(__name__)


class SvcSuggestActorToCaseUseCase:
    """Recommend another actor for participation in an existing case.

    Emits a RecommendActorActivity addressed to the case owner (typically
    the CaseActor), which then autonomously invites the suggested actor.
    The originating actor is the ``actor`` field; ``object_`` is the actor
    being suggested; ``target`` is the case.
    """

    def __init__(
        self,
        dl: CaseOutboxPersistence,
        request: SuggestActorToCaseTriggerRequest,
        trigger_activity: "TriggerActivityPort | None" = None,
    ) -> None:
        self._dl = dl
        self._request = request
        self._trigger_activity = trigger_activity

    def execute(self) -> dict[str, Any]:
        actor_id = self._request.actor_id
        actor = resolve_actor(actor_id, self._dl)
        actor_id = actor.id_
        case = resolve_case(self._request.case_id, self._dl)

        suggested_raw = self._dl.read(self._request.suggested_actor_id)
        if suggested_raw is None:
            raise VultronNotFoundError(
                "Actor", self._request.suggested_actor_id
            )

        if self._trigger_activity is None:
            raise RuntimeError(
                "SvcSuggestActorToCaseUseCase requires a TriggerActivityPort"
            )

        activity_id, activity_dict = (
            self._trigger_activity.suggest_actor_to_case(
                recommended_id=self._request.suggested_actor_id,
                case_id=case.id_,
                actor=actor_id,
            )
        )

        add_activity_to_outbox(actor_id, activity_id, self._dl)

        logger.info(
            "Actor '%s' suggested actor '%s' for case '%s'",
            actor_id,
            self._request.suggested_actor_id,
            case.id_,
        )

        return {"activity": activity_dict}


class SvcInviteActorToCaseUseCase:
    """Directly invite an actor to a case (case-owner action).

    Emits an RmInviteToCaseActivity addressed to the invitee, queued in the
    actor's outbox for delivery.
    """

    def __init__(
        self,
        dl: CaseOutboxPersistence,
        request: InviteActorToCaseTriggerRequest,
        trigger_activity: "TriggerActivityPort | None" = None,
    ) -> None:
        self._dl = dl
        self._request = request
        self._trigger_activity = trigger_activity

    def execute(self) -> dict[str, Any]:
        actor_id = self._request.actor_id
        actor = resolve_actor(actor_id, self._dl)
        actor_id = actor.id_
        case = resolve_case(self._request.case_id, self._dl)

        invitee_raw = self._dl.read(self._request.invitee_id)
        if invitee_raw is None:
            raise VultronNotFoundError("Actor", self._request.invitee_id)

        if self._trigger_activity is None:
            raise RuntimeError(
                "SvcInviteActorToCaseUseCase requires a TriggerActivityPort"
            )

        activity_id, activity_dict = (
            self._trigger_activity.invite_actor_to_case(
                invitee_id=self._request.invitee_id,
                case_id=case.id_,
                actor=actor_id,
                to=[self._request.invitee_id],
            )
        )

        add_activity_to_outbox(actor_id, activity_id, self._dl)

        logger.info(
            "Actor '%s' invited actor '%s' to case '%s'",
            actor_id,
            self._request.invitee_id,
            case.id_,
        )

        return {"activity": activity_dict}


class SvcAcceptCaseInviteUseCase:
    """Accept a case invitation by emitting RmAcceptInviteToCaseActivity.

    The invitee actor reads the invite from the DataLayer, coerces it to
    the expected typed class if needed, and queues the accept activity in
    their outbox for delivery to the case owner.
    """

    def __init__(
        self,
        dl: CaseOutboxPersistence,
        request: AcceptCaseInviteTriggerRequest,
        trigger_activity: "TriggerActivityPort | None" = None,
    ) -> None:
        self._dl = dl
        self._request = request
        self._trigger_activity = trigger_activity

    def execute(self) -> dict[str, Any]:
        actor_id = self._request.actor_id
        actor = resolve_actor(actor_id, self._dl)
        actor_id = actor.id_

        raw_invite = self._dl.read(self._request.invite_id)
        if raw_invite is None:
            raise VultronNotFoundError(
                "RmInviteToCaseActivity", self._request.invite_id
            )

        invite_type = getattr(raw_invite, "type_", "")
        if invite_type != "Invite":
            raise VultronValidationError(
                f"'{self._request.invite_id}' is not an"
                " RmInviteToCaseActivity"
            )

        if self._trigger_activity is None:
            raise RuntimeError(
                "SvcAcceptCaseInviteUseCase requires a TriggerActivityPort"
            )

        activity_id, activity_dict = self._trigger_activity.accept_case_invite(
            invite_id=self._request.invite_id,
            actor=actor_id,
        )

        add_activity_to_outbox(actor_id, activity_id, self._dl)

        logger.info(
            "Actor '%s' accepted case invite '%s'",
            actor_id,
            self._request.invite_id,
        )

        return {"activity": activity_dict}
