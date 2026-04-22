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

from vultron.core.ports.datalayer import DataLayer
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
from vultron.wire.as2.vocab.activities.actor import RecommendActorActivity
from vultron.wire.as2.vocab.activities.case import (
    RmAcceptInviteToCaseActivity,
    RmInviteToCaseActivity,
)
from vultron.wire.as2.vocab.base.objects.actors import as_Actor
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    VulnerabilityCase,
    VulnerabilityCaseStub,
)

logger = logging.getLogger(__name__)


class SvcSuggestActorToCaseUseCase:
    """Recommend another actor for participation in an existing case.

    Emits a RecommendActorActivity addressed to the case owner (typically
    the CaseActor), which then autonomously invites the suggested actor.
    The originating actor is the ``actor`` field; ``object_`` is the actor
    being suggested; ``target`` is the case.
    """

    def __init__(
        self, dl: DataLayer, request: SuggestActorToCaseTriggerRequest
    ) -> None:
        self._dl = dl
        self._request = request

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

        activity = RecommendActorActivity(
            actor=actor_id,
            object_=cast(as_Actor, suggested_raw),
            target=cast(VulnerabilityCase, case),
        )
        self._dl.create(activity)

        add_activity_to_outbox(actor_id, activity.id_, self._dl)

        logger.info(
            "Actor '%s' suggested actor '%s' for case '%s'",
            actor_id,
            self._request.suggested_actor_id,
            case.id_,
        )

        return {
            "activity": activity.model_dump(by_alias=True, exclude_none=True)
        }


class SvcInviteActorToCaseUseCase:
    """Directly invite an actor to a case (case-owner action).

    Emits an RmInviteToCaseActivity addressed to the invitee, queued in the
    actor's outbox for delivery.
    """

    def __init__(
        self, dl: DataLayer, request: InviteActorToCaseTriggerRequest
    ) -> None:
        self._dl = dl
        self._request = request

    def execute(self) -> dict[str, Any]:
        actor_id = self._request.actor_id
        actor = resolve_actor(actor_id, self._dl)
        actor_id = actor.id_
        case = resolve_case(self._request.case_id, self._dl)

        invitee_raw = self._dl.read(self._request.invitee_id)
        if invitee_raw is None:
            raise VultronNotFoundError("Actor", self._request.invitee_id)

        activity = RmInviteToCaseActivity(
            actor=actor_id,
            object_=cast(as_Actor, invitee_raw),
            target=VulnerabilityCaseStub(id_=case.id_),
            to=[self._request.invitee_id],
        )
        self._dl.create(activity)

        add_activity_to_outbox(actor_id, activity.id_, self._dl)

        logger.info(
            "Actor '%s' invited actor '%s' to case '%s'",
            actor_id,
            self._request.invitee_id,
            case.id_,
        )

        return {
            "activity": activity.model_dump(by_alias=True, exclude_none=True)
        }


class SvcAcceptCaseInviteUseCase:
    """Accept a case invitation by emitting RmAcceptInviteToCaseActivity.

    The invitee actor reads the invite from the DataLayer, coerces it to
    the expected typed class if needed, and queues the accept activity in
    their outbox for delivery to the case owner.
    """

    def __init__(
        self, dl: DataLayer, request: AcceptCaseInviteTriggerRequest
    ) -> None:
        self._dl = dl
        self._request = request

    def execute(self) -> dict[str, Any]:
        actor_id = self._request.actor_id
        actor = resolve_actor(actor_id, self._dl)
        actor_id = actor.id_

        raw_invite = self._dl.read(self._request.invite_id)
        if raw_invite is None:
            raise VultronNotFoundError(
                "RmInviteToCaseActivity", self._request.invite_id
            )

        if not isinstance(raw_invite, RmInviteToCaseActivity):
            try:
                invite = RmInviteToCaseActivity.model_validate(
                    raw_invite.model_dump(by_alias=True)
                )
            except Exception as exc:
                raise VultronValidationError(
                    f"'{self._request.invite_id}' cannot be coerced to"
                    " RmInviteToCaseActivity"
                ) from exc
        else:
            invite = raw_invite

        activity = RmAcceptInviteToCaseActivity(
            actor=actor_id,
            object_=invite,
        )
        self._dl.create(activity)

        add_activity_to_outbox(actor_id, activity.id_, self._dl)

        logger.info(
            "Actor '%s' accepted case invite '%s'",
            actor_id,
            invite.id_,
        )

        return {
            "activity": activity.model_dump(by_alias=True, exclude_none=True)
        }
