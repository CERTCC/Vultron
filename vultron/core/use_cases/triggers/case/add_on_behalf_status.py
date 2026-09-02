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
#  Carnegie Mellon®, CERTⓇ and CERT Coordination CenterⓇ are registered in the
#  U.S. Patent and Trademark Office by Carnegie Mellon University

import logging
from typing import Any, cast

import py_trees.behaviour

from vultron.core.behaviors.case.add_on_behalf_status_trigger_tree import (
    add_on_behalf_status_trigger_bt,
)
from vultron.core.states.cs import CS_d, CS_vf
from vultron.core.use_cases.triggers._base import SvcBTTriggerBase
from vultron.core.use_cases.triggers._helpers import (
    resolve_actor,
    resolve_case,
)
from vultron.core.use_cases.triggers.requests import (
    AddOnBehalfStatusTriggerRequest,
)
from vultron.enums.roles import CVDRole

logger = logging.getLogger(__name__)


class SvcAddOnBehalfStatusUseCase(SvcBTTriggerBase):
    """Assert v→V or d→D on behalf of a notified-but-not-joined vendor/deployer.

    The ``actor_id`` in the request is the *asserting* actor (Case Manager or
    Case Owner); ``target_actor_id`` identifies the vendor or deployer whose
    awareness or deployment state is being recorded.

    Only ``CS_vf.Vf`` (v→V) and ``CS_d.D`` (d→D) may be asserted on behalf;
    ``CS_vf.VF`` (f→F) is rejected at the request layer (ADR-0084, PRM-06-005).

    BT-15-001: the ``ParticipantStatus`` write happens inside the BT via
    ``CreateParticipantStatusNode``, not directly in ``execute()``.
    """

    def _prepare(self) -> None:
        request = cast(AddOnBehalfStatusTriggerRequest, self._request)
        actor = resolve_actor(request.actor_id, self._dl)
        self._actor_id = actor.id_
        self._asserting_actor_id = actor.id_
        self._target_actor_id = request.target_actor_id
        self._case_id = resolve_case(request.case_id, self._dl).id_
        self._vf_state: CS_vf | None = request.vf_state
        self._d_state: CS_d | None = request.d_state
        self._required_role = (
            CVDRole.VENDOR
            if request.vf_state is not None
            else CVDRole.DEPLOYER
        )

    def _build_tree(self) -> py_trees.behaviour.Behaviour:
        def _build_activities(case_manager_id: str) -> list[str]:
            status_id = self._result_out.get("status_id")
            participant_id = self._result_out.get("participant_id")
            if not isinstance(status_id, str) or not isinstance(
                participant_id, str
            ):
                raise RuntimeError(
                    "CreateParticipantStatusNode did not populate result_out"
                    " before activity_builder was called"
                )
            activity_id = self._factory.add_participant_status_to_participant(
                status_id=status_id,
                participant_id=participant_id,
                actor=self._asserting_actor_id,
                to=[case_manager_id],
            )
            self._result_out["activity_id"] = activity_id
            return [activity_id]

        return add_on_behalf_status_trigger_bt(
            case_id=self._case_id,
            asserting_actor_id=self._asserting_actor_id,
            target_actor_id=self._target_actor_id,
            required_role=self._required_role,
            vf_state=self._vf_state,
            d_state=self._d_state,
            result_out=self._result_out,
            activity_builder=_build_activities,
        )

    def _handle_result(self) -> None:
        logger.info(
            "Actor '%s' asserted on-behalf status for '%s' in case '%s'",
            self._asserting_actor_id,
            self._target_actor_id,
            self._case_id,
        )

    def execute(self) -> dict[str, Any]:
        super().execute()
        return {
            "activity_id": self._result_out.get("activity_id"),
            "status_id": self._result_out.get("status_id"),
        }
