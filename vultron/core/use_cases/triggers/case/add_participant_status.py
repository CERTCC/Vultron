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

from vultron.core.ports.case_persistence import CaseOutboxPersistence
from vultron.core.states.cs import CS_vfd
from vultron.core.states.rm import RM
from vultron.core.use_cases._helpers import _resolve_case_manager_id
from vultron.core.use_cases.triggers._helpers import (
    add_activity_to_outbox,
    resolve_actor,
    resolve_case,
)
from vultron.core.use_cases.triggers.requests import (
    AddParticipantStatusTriggerRequest,
)
from vultron.errors import VultronNotFoundError

if TYPE_CHECKING:
    from vultron.core.ports.trigger_activity import TriggerActivityPort

logger = logging.getLogger(__name__)


class SvcAddParticipantStatusUseCase:
    """Self-report actor RM/VFD/PXA state to the Case Manager.

    Creates a ParticipantStatus object, saves it, then emits an
    Add(ParticipantStatus, target=CaseParticipant) activity addressed to the
    Case Manager (DEMOMA-07-001).
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
        """Return (current_rm, current_vfd) from the participant's latest status."""
        participant_obj = dl.read(participant_id)
        if participant_obj is not None and hasattr(
            participant_obj, "participant_statuses"
        ):
            statuses = getattr(participant_obj, "participant_statuses")
            if statuses:
                latest = statuses[-1]
                raw_rm = getattr(latest, "rm_state", RM.START)
                raw_vfd = getattr(latest, "vfd_state", CS_vfd.vfd)
                rm_state = raw_rm if isinstance(raw_rm, RM) else RM.START
                vfd_state = (
                    raw_vfd if isinstance(raw_vfd, CS_vfd) else CS_vfd.vfd
                )
                return rm_state, vfd_state
        return RM.START, CS_vfd.vfd

    def execute(self) -> dict[str, Any]:
        from vultron.core.models.case_status import CaseStatus
        from vultron.core.models.participant_status import ParticipantStatus
        from vultron.core.states.em import EM

        request = self._request
        actor_id = request.actor_id
        case_id = request.case_id
        dl = self._dl

        actor = resolve_actor(actor_id, dl)
        actor_id = actor.id_

        case = resolve_case(case_id, dl)

        if self._trigger_activity is None:
            raise RuntimeError(
                "SvcAddParticipantStatusUseCase requires a TriggerActivityPort"
            )

        participant_id = case.actor_participant_index.get(actor_id)
        if participant_id is None:
            raise VultronNotFoundError(
                "CaseParticipant",
                f"actor '{actor_id}' not in case '{case_id}'",
            )

        case_status: CaseStatus | None = None
        if request.pxa_state is not None:
            current_em = getattr(
                getattr(case, "current_status", None), "em_state", None
            )
            case_status = CaseStatus(
                context=case_id,
                attributed_to=actor_id,
                em_state=current_em if current_em is not None else EM.NONE,
                pxa_state=request.pxa_state,
            )

        current_rm, current_vfd = self._resolve_current_participant_state(
            dl, participant_id
        )

        status = ParticipantStatus(
            context=case_id,
            attributed_to=actor_id,
            rm_state=(
                request.rm_state
                if request.rm_state is not None
                else current_rm
            ),
            vfd_state=(
                request.vfd_state
                if request.vfd_state is not None
                else current_vfd
            ),
            case_status=case_status,
        )
        try:
            dl.create(status)
        except ValueError:
            dl.save(status)

        participant_obj = dl.read(participant_id)
        wire_status = dl.read(status.id_)
        participant_statuses = (
            getattr(participant_obj, "participant_statuses", None)
            if participant_obj is not None
            else None
        )
        if participant_statuses is not None and wire_status is not None:
            participant_statuses.append(wire_status)
            if participant_obj is not None:
                dl.save(participant_obj)

        case_manager_id = _resolve_case_manager_id(case, dl)
        if case_manager_id is None:
            raise VultronNotFoundError(
                "CaseParticipant",
                f"no CASE_MANAGER found in case '{case_id}'"
                " — cannot send status update",
            )

        activity_id = (
            self._trigger_activity.add_participant_status_to_participant(
                status_id=status.id_,
                participant_id=participant_id,
                actor=actor_id,
                to=[case_manager_id],
            )
        )

        add_activity_to_outbox(actor_id, activity_id, dl)

        logger.info(
            "Actor '%s' reported status to participant '%s' in case '%s'",
            actor_id,
            participant_id,
            case_id,
        )

        return {"activity_id": activity_id, "status_id": status.id_}
