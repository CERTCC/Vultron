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

"""Use case for querying CVD action rules for an actor in a case.

Implements CM-07-001, CM-07-002, CM-07-003, AR-07-001, AR-07-002.
"""

from pydantic import BaseModel
from typing import cast

from vultron.core.case_states.patterns.potential_actions import (
    action as get_actions,
)
from vultron.core.models.protocols import CaseModel, ParticipantModel
from vultron.core.ports.datalayer import DataLayer
from vultron.core.scoring.utils import enum2title
from vultron.core.states.cs import CS_pxa, CS_vfd
from vultron.core.states.em import EM
from vultron.core.states.rm import RM
from vultron.core.use_cases.triggers._helpers import resolve_case
from vultron.errors import VultronNotFoundError, VultronValidationError


class ActionRulesRequest(BaseModel):
    """Request model for GetActionRulesUseCase."""

    case_id: str
    actor_id: str


def _resolve_participant_id_from_actor(
    case: CaseModel, actor_id: str, dl: DataLayer
) -> str:
    """Resolve a case-scoped participant ID from an actor ID."""
    participant_id = case.actor_participant_index.get(actor_id)
    if participant_id is not None:
        return participant_id

    for participant_ref in case.case_participants:
        resolved_participant_id = (
            participant_ref.as_id
            if hasattr(participant_ref, "as_id")
            else str(participant_ref)
        )
        participant = cast(
            ParticipantModel | None, dl.read(resolved_participant_id)
        )
        if participant is None:
            continue
        participant_actor_id = (
            participant.attributed_to
            if isinstance(participant.attributed_to, str)
            else getattr(participant.attributed_to, "as_id", None)
        )
        if participant_actor_id == actor_id:
            return resolved_participant_id

    raise VultronNotFoundError("CaseParticipant", actor_id)


class GetActionRulesUseCase:
    """Return valid CVD actions for an actor's participant record in a case.

    Resolves the selected VulnerabilityCase, finds the actor's matching
    CaseParticipant, reads their current RM/VFD state (from the latest
    ParticipantStatus) and the case EM/PXA state (from the current
    CaseStatus), then returns the set of valid CVD actions for the
    resulting combined case-state string together with the full state
    context.

    Implements: CM-07-001, CM-07-002, CM-07-003, AR-07-001, AR-07-002.
    """

    def __init__(self, dl: DataLayer, request: ActionRulesRequest) -> None:
        self._dl = dl
        self._request = request

    def execute(self) -> dict:
        dl = self._dl
        case_id = self._request.case_id
        actor_id = self._request.actor_id

        # 1. Resolve the VulnerabilityCase
        case = resolve_case(case_id, dl)

        # 2. Resolve the actor's CaseParticipant in the selected case.
        participant_id = _resolve_participant_id_from_actor(case, actor_id, dl)

        participant = cast(ParticipantModel | None, dl.read(participant_id))
        if participant is None:
            raise VultronNotFoundError("CaseParticipant", participant_id)
        participant_actor_id = (
            participant.attributed_to
            if isinstance(participant.attributed_to, str)
            else getattr(participant.attributed_to, "as_id", None)
        )
        if participant_actor_id is None:
            raise VultronValidationError(
                f"CaseParticipant {participant_id} has no associated actor."
            )

        # 3. Get per-participant states from the latest ParticipantStatus
        rm_state: RM = RM.START
        vfd_state: CS_vfd = CS_vfd.vfd
        if participant.participant_statuses:
            latest = participant.participant_statuses[-1]
            rm_state = latest.rm_state
            vfd_state = latest.vfd_state

        # 4. Get shared case states from the current CaseStatus
        em_state: EM = EM.EMBARGO_MANAGEMENT_NONE
        pxa_state: CS_pxa = CS_pxa.pxa
        if case.case_statuses:
            current_cs = case.current_status
            em_state = current_cs.em_state
            pxa_state = current_cs.pxa_state

        # 5. Build the combined 6-character CS state string (VFD + PXA)
        cs_state = vfd_state.name + pxa_state.name

        # 6. Look up valid CVD actions for the current state
        valid_actions = get_actions(cs_state)

        # 7. Collect participant roles as string names
        roles = [r.name for r in (participant.case_roles or [])]

        return {
            "participant_id": str(participant.as_id),
            "participant_actor_id": participant_actor_id,
            "case_id": case_id,
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
