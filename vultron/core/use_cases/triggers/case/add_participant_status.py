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

import logging
from typing import TYPE_CHECKING, Any

from py_trees.common import Status

from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.case.add_participant_status_trigger_tree import (
    add_participant_status_trigger_bt,
)
from vultron.core.ports.case_persistence import CaseOutboxPersistence
from vultron.core.states.cs import CS_vfd
from vultron.core.states.rm import RM
from vultron.core.use_cases.triggers._helpers import (
    resolve_actor,
    resolve_case,
)
from vultron.core.use_cases.triggers.requests import (
    AddParticipantStatusTriggerRequest,
)
from vultron.errors import VultronValidationError

if TYPE_CHECKING:
    from vultron.core.ports.trigger_activity import TriggerActivityPort

logger = logging.getLogger(__name__)


class SvcAddParticipantStatusUseCase:
    """Self-report actor RM/VFD/PXA state to the Case Manager.

    Delegates ParticipantStatus record creation to
    :class:`~vultron.core.behaviors.case.nodes.participant\
.CreateParticipantStatusNode` via BTBridge (BT-15-001), then emits an
    ``Add(ParticipantStatus, target=CaseParticipant)`` activity addressed
    to the Case Manager (DEMOMA-07-001).

    BT-15-001 audit: ``ParticipantStatus`` writes with explicit
    ``rm_state``/``vfd_state`` are protocol-significant behavior and are
    performed inside the BT, not directly in ``execute()``.  The
    ``rm_state``/``vfd_state`` values represent the actor's current
    (already-transitioned) state; no RM state-machine transition is
    performed here.
    """

    def __init__(
        self,
        dl: CaseOutboxPersistence,
        request: AddParticipantStatusTriggerRequest,
        trigger_activity: "TriggerActivityPort | None" = None,
    ) -> None:
        self._dl = dl
        self._request = request
        self._trigger_activity = trigger_activity

    def _resolve_current_participant_state(
        self,
        dl: CaseOutboxPersistence,
        participant_id: str,
    ) -> tuple[RM, CS_vfd]:
        """Return (current_rm, current_vfd) from the participant's latest status.

        Preserved for backward compatibility; delegates to
        :func:`~vultron.core.behaviors.case.nodes.participant\
.resolve_participant_state_from_dl`.
        """
        from vultron.core.behaviors.case.nodes.participant import (
            resolve_participant_state_from_dl,
        )
        from typing import cast
        from vultron.core.ports.case_persistence import CasePersistence

        return resolve_participant_state_from_dl(
            cast(CasePersistence, dl), participant_id
        )

    def execute(self) -> dict[str, Any]:
        request = self._request
        actor_id = request.actor_id
        case_id = request.case_id
        dl = self._dl

        actor = resolve_actor(actor_id, dl)
        actor_id = actor.id_

        resolve_case(case_id, dl)

        if self._trigger_activity is None:
            raise RuntimeError(
                "SvcAddParticipantStatusUseCase requires a TriggerActivityPort"
            )

        factory = self._trigger_activity
        result_data: dict = {}

        def _build_activities(case_manager_id: str) -> list[str]:
            status_id = result_data.get("status_id")
            participant_id = result_data.get("participant_id")
            if not isinstance(status_id, str) or not isinstance(
                participant_id, str
            ):
                raise RuntimeError(
                    "CreateParticipantStatusNode did not populate result_data"
                    " before activity_builder was called"
                )
            activity_id = factory.add_participant_status_to_participant(
                status_id=status_id,
                participant_id=participant_id,
                actor=actor_id,
                to=[case_manager_id],
            )
            result_data["activity_id"] = activity_id
            return [activity_id]

        bridge = BTBridge(datalayer=dl, trigger_activity=factory)
        tree = add_participant_status_trigger_bt(
            case_id=case_id,
            actor_id=actor_id,
            rm_state=request.rm_state,
            vfd_state=request.vfd_state,
            pxa_state=request.pxa_state,
            result_out=result_data,
            activity_builder=_build_activities,
        )
        result = bridge.execute_with_setup(tree, actor_id=actor_id)

        if result.status != Status.SUCCESS:
            raise VultronValidationError(
                f"AddParticipantStatus failed:"
                f" {BTBridge.get_failure_reason(tree)}"
            )

        logger.info(
            "Actor '%s' reported status in case '%s'",
            actor_id,
            case_id,
        )

        return {
            "activity_id": result_data.get("activity_id"),
            "status_id": result_data.get("status_id"),
        }
