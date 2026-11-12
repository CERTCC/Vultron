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


"""Use case for the CASE_MANAGER's offer of a participant role.

No HTTP framework imports permitted here.
"""

import json
import logging
from datetime import datetime

from vultron.core.behaviors.bridge.act_instant import open_act
from vultron.core.models.use_case_result import RoleOfferResult
from vultron.core.participants.authority import resolve_case_manager_id
from vultron.core.ports.case_outbox import CaseOutboxPersistence
from vultron.core.ports.clock import ClockPort
from vultron.core.ports.trigger_activity import TriggerActivityPort
from vultron.core.use_cases.triggers._helpers import (
    resolve_case,
    send_case_actor_activity,
)
from vultron.core.use_cases.triggers.requests import (
    OfferCaseParticipantRoleTriggerRequest,
)
from vultron.errors import (
    VultronNotFoundError,
)

logger = logging.getLogger(__name__)


class SvcOfferCaseParticipantRoleUseCase:
    """The Case Owner offers a CVDRole to a target Actor (ADR-0039, CM-33-001).

    Builds ``Offer(CaseParticipantRole)[context=VulnerabilityCase]``
    from the requesting actor, addressed to the case's CASE_MANAGER only, and
    queues it in the requesting actor's outbox through the SenderSideBT
    (PCR-08-001).  The CASE_MANAGER checks the Offer, records it and forwards
    it to the target (CM-33-002, CM-33-003); the target never receives the
    Case Owner's own Offer (CM-33-001).  The ``trigger_activity`` adapter's
    ``offer_case_participant_role`` method handles wire construction and
    persistence.  It is not a ``SvcBTTriggerBase`` subclass, so its result
    carries no ``emitting_actor_id`` (ADR-0110).

    Raises ``VultronNotFoundError`` before anything is built when the case is
    not held, or names no CASE_MANAGER (PCR-08-011): a case always has one
    (CM-02-014), so its absence is a fault, never a direct send to the target
    (CM-24-014).

    See SE-08-003, ADR-0039.
    """

    def __init__(
        self,
        dl: CaseOutboxPersistence,
        request: OfferCaseParticipantRoleTriggerRequest,
        trigger_activity: TriggerActivityPort | None = None,
        *,
        clock: ClockPort,
    ) -> None:
        self._dl = dl
        self._request = request
        self._trigger_activity = trigger_activity
        # The act clock, read once by execute() after it takes the tree lock
        # (ADR-0176).
        self._clock = clock

    def execute(self) -> RoleOfferResult:
        """Run the trigger as one act: lock, read the clock once, then run."""
        with open_act(self._clock) as at:
            return self._execute_act(at)

    def _execute_act(self, at: datetime) -> RoleOfferResult:
        if self._trigger_activity is None:
            raise RuntimeError(
                "SvcOfferCaseParticipantRoleUseCase requires a TriggerActivityPort"
            )
        factory = self._trigger_activity
        req = self._request
        case = resolve_case(req.case_id, self._dl)
        # The Offer goes to the CASE_MANAGER or nowhere (CM-33-001,
        # PCR-08-011).
        if resolve_case_manager_id(case, self._dl) is None:
            raise VultronNotFoundError(
                "CASE_MANAGER", f"(for case '{case.id_}')"
            )
        built: dict[str, str] = {}

        def _build_offer(case_manager_id: str) -> list[str]:
            activity_id, activity_dict = factory.offer_case_participant_role(
                case_id=case.id_,
                role=req.role,
                target_actor_id=req.target_actor_id,
                actor=req.actor_id,
                to=[case_manager_id],
                at=at,
            )
            built.update(
                activity_id=activity_id,
                activity=activity_dict,
                case_manager_id=case_manager_id,
            )
            return [activity_id]

        send_case_actor_activity(
            dl=self._dl,
            case_id=case.id_,
            actor_id=req.actor_id,
            trigger_activity=factory,
            failure_label="SvcOfferCaseParticipantRoleUseCase",
            activity_builder=_build_offer,
            at=at,
        )
        activity_id, activity_dict = built["activity_id"], built["activity"]
        logger.info(
            "SvcOfferCaseParticipantRoleUseCase: queued Offer(CaseParticipantRole)"
            " '%s' for case '%s' role '%s' → actor '%s', sent to the"
            " CASE_MANAGER '%s'",
            activity_id,
            case.id_,
            req.role,
            req.target_actor_id,
            built["case_manager_id"],
        )
        return RoleOfferResult(
            activity_id=activity_id,
            activity=json.loads(activity_dict),
        )
