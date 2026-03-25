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

"""Use case for querying CVD action rules for a case participant.

Implements CM-07-001, CM-07-002, CM-07-003, AR-07-001, AR-07-002.
"""

import logging

from pydantic import BaseModel

from vultron.core.case_states.patterns.potential_actions import (
    action as get_actions,
)
from vultron.core.ports.datalayer import DataLayer
from vultron.core.scoring.utils import enum2title
from vultron.core.states.cs import CS_pxa, CS_vfd
from vultron.core.states.em import EM
from vultron.core.states.rm import RM
from vultron.core.use_cases.triggers._helpers import resolve_case
from vultron.errors import VultronNotFoundError, VultronValidationError

logger = logging.getLogger(__name__)


class ActionRulesRequest(BaseModel):
    """Request model for GetActionRulesUseCase."""

    case_actor_id: str
    participant_actor_id: str


class GetActionRulesUseCase:
    """Return valid CVD actions for a participant in a case.

    Looks up the CaseActor, resolves its associated VulnerabilityCase,
    finds the requested participant, reads their current RM/VFD state
    (from the latest ParticipantStatus) and the case EM/PXA state
    (from the current CaseStatus), then returns the set of valid CVD
    actions for the resulting combined case-state string together with
    the full state context.

    Implements: CM-07-001, CM-07-002, CM-07-003, AR-07-001, AR-07-002.
    """

    def __init__(self, dl: DataLayer, request: ActionRulesRequest) -> None:
        self._dl = dl
        self._request = request

    def execute(self) -> dict:
        dl = self._dl
        case_actor_id = self._request.case_actor_id
        participant_actor_id = self._request.participant_actor_id

        # 1. Resolve the CaseActor
        case_actor = dl.read(case_actor_id)
        if case_actor is None:
            raise VultronNotFoundError("CaseActor", case_actor_id)

        case_id = getattr(case_actor, "context", None)
        if not case_id:
            raise VultronValidationError(
                f"CaseActor {case_actor_id} has no associated case."
            )

        # 2. Resolve the VulnerabilityCase
        case = resolve_case(str(case_id), dl)

        # 3. Find the participant by actor ID via the case index
        participant_id = case.actor_participant_index.get(participant_actor_id)
        if participant_id is None:
            raise VultronNotFoundError("CaseParticipant", participant_actor_id)

        participant = dl.read(participant_id)
        if participant is None:
            raise VultronNotFoundError("CaseParticipant", participant_id)

        # 4. Get per-participant states from the latest ParticipantStatus
        rm_state: RM = RM.START
        vfd_state: CS_vfd = CS_vfd.vfd
        if participant.participant_statuses:
            latest = participant.participant_statuses[-1]
            rm_state = latest.rm_state
            vfd_state = latest.vfd_state

        # 5. Get shared case states from the current CaseStatus
        em_state: EM = EM.EMBARGO_MANAGEMENT_NONE
        pxa_state: CS_pxa = CS_pxa.pxa
        if case.case_statuses:
            current_cs = case.current_status
            em_state = current_cs.em_state
            pxa_state = current_cs.pxa_state

        # 6. Build the combined 6-character CS state string (VFD + PXA)
        cs_state = vfd_state.name + pxa_state.name

        # 7. Look up valid CVD actions for the current state
        valid_actions = get_actions(cs_state)

        # 8. Collect participant roles as string names
        roles = [r.name for r in (participant.case_roles or [])]

        return {
            "participant_id": str(participant.as_id),
            "participant_actor_id": participant_actor_id,
            "case_actor_id": case_actor_id,
            "case_id": str(case_id),
            "role": roles,
            "rm_state": str(rm_state),
            "em_state": str(em_state),
            "vfd_state": vfd_state.name,
            "pxa_state": pxa_state.name,
            "cs_state": cs_state,
            "actions": [
                {"name": a.name, "description": enum2title(a)}
                for a in valid_actions
            ],
        }
