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
from typing import Any, cast

import py_trees.behaviour

from vultron.core.behaviors.case.add_participant_status_trigger_tree import (
    add_participant_status_trigger_bt,
)
from vultron.core.ports.case_persistence import CaseOutboxPersistence
from vultron.core.states.cs import CS_vfd
from vultron.core.states.rm import RM
from vultron.core.use_cases.triggers._base import SvcBTTriggerBase
from vultron.core.use_cases.triggers._helpers import (
    resolve_actor,
    resolve_case,
)
from vultron.core.use_cases.triggers.requests import (
    AddParticipantStatusTriggerRequest,
)

logger = logging.getLogger(__name__)


class SvcAddParticipantStatusUseCase(SvcBTTriggerBase):
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

    def _prepare(self) -> None:
        request = cast(AddParticipantStatusTriggerRequest, self._request)
        actor = resolve_actor(request.actor_id, self._dl)
        self._actor_id = actor.id_
        self._case_id = resolve_case(request.case_id, self._dl).id_
        self._rm_state = request.rm_state
        self._vfd_state = request.vfd_state
        self._pxa_state = request.pxa_state

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
                actor=self._actor_id,
                to=[case_manager_id],
            )
            self._result_out["activity_id"] = activity_id
            return [activity_id]

        return add_participant_status_trigger_bt(
            case_id=self._case_id,
            actor_id=self._actor_id,
            rm_state=self._rm_state,
            vfd_state=self._vfd_state,
            pxa_state=self._pxa_state,
            result_out=self._result_out,
            activity_builder=_build_activities,
        )

    def _handle_result(self) -> None:
        logger.info(
            "Actor '%s' reported status in case '%s'",
            self._actor_id,
            self._case_id,
        )

    def execute(self) -> dict[str, Any]:
        super().execute()
        return {
            "activity_id": self._result_out.get("activity_id"),
            "status_id": self._result_out.get("status_id"),
        }

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
        from typing import cast as typing_cast

        from vultron.core.behaviors.case.nodes.participant import (
            resolve_participant_state_from_dl,
        )
        from vultron.core.ports.case_persistence import (
            CasePersistence,
        )

        return resolve_participant_state_from_dl(
            typing_cast(CasePersistence, dl), participant_id
        )
