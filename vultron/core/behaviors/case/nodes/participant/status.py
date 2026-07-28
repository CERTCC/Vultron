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

"""Participant status snapshot node for add-participant-status trigger BT."""

from py_trees.common import Status

from vultron.core.behaviors.case.nodes.participant.common import (
    resolve_participant_state_from_dl,
)
from vultron.core.behaviors.helpers import DataLayerAction
from vultron.core.models.case_status import CaseStatus
from vultron.core.models.participant_status import (
    ParticipantStatus,
    coerce_cvd_roles,
    coerce_em_consent_state,
)
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.dimensions import (
    EmDimension,
    PecDimension,
    PxaDimension,
    RmDimension,
    VfdDimension,
)
from vultron.core.states.cs import CS_pxa, CS_vfd
from vultron.core.states.em import EM
from vultron.core.states.rm import RM


def _resolve_em_state(case: object) -> EM:
    """Return the current em_state from a case, or EM.NONE if unavailable."""
    try:
        current_status = case.current_status  # type: ignore[attr-defined]
    except (AttributeError, ValueError):
        return EM.NONE
    em_state = (
        current_status.em.state if hasattr(current_status, "em") else None
    )
    return em_state if em_state is not None else EM.NONE


class CreateParticipantStatusNode(DataLayerAction):
    """Create a ParticipantStatus snapshot and append it to the participant."""

    def __init__(
        self,
        case_id: str,
        actor_id: str,
        rm_state: "RM | None",
        vfd_state: "CS_vfd | None",
        pxa_state: "CS_pxa | None",
        result_out: dict,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self._case_id = case_id
        self._actor_id = actor_id
        self._rm_state = rm_state
        self._vfd_state = vfd_state
        self._pxa_state = pxa_state
        self._result_out = result_out

    def update(self) -> Status:
        dl = self.datalayer
        if dl is None:
            self.logger.error("%s: DataLayer not available", self.name)
            self.feedback_message = "DataLayer not available"
            return Status.FAILURE

        case = dl.read(self._case_id)
        if not isinstance(case, VulnerabilityCase):
            self.logger.error(
                "%s: Case '%s' not found in DataLayer",
                self.name,
                self._case_id,
            )
            self.feedback_message = f"Case '{self._case_id}' not found"
            return Status.FAILURE

        participant_id = case.actor_participant_index.get(self._actor_id)
        if participant_id is None:
            self.logger.error(
                "%s: actor '%s' not in case '%s'",
                self.name,
                self._actor_id,
                self._case_id,
            )
            self.feedback_message = (
                f"Actor '{self._actor_id}' not found in"
                f" case '{self._case_id}'"
            )
            return Status.FAILURE

        case_status: CaseStatus | None = None
        if self._pxa_state is not None:
            case_status = CaseStatus(
                context=self._case_id,
                attributed_to=self._actor_id,
                em=EmDimension(state=_resolve_em_state(case)),
                pxa=PxaDimension(state=self._pxa_state),
            )

        current_rm, current_vfd = resolve_participant_state_from_dl(
            dl, participant_id
        )
        participant_obj = dl.read(participant_id)
        participant_roles = (
            participant_obj.roles
            if isinstance(participant_obj, CaseParticipant)
            else []
        )
        status_roles = coerce_cvd_roles(participant_roles)
        raw_consent = (
            getattr(participant_obj, "embargo_consent_state", None)
            if isinstance(participant_obj, CaseParticipant)
            else None
        )
        em_consent_state = coerce_em_consent_state(raw_consent)
        consent_dim = (
            PecDimension(state=em_consent_state)
            if em_consent_state is not None
            else None
        )

        status = ParticipantStatus(
            context=self._case_id,
            attributed_to=self._actor_id,
            rm=RmDimension(
                state=(
                    self._rm_state
                    if self._rm_state is not None
                    else current_rm
                )
            ),
            vfd=VfdDimension(
                state=(
                    self._vfd_state
                    if self._vfd_state is not None
                    else current_vfd
                )
            ),
            consent=consent_dim,
            cvd_role=status_roles,
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

        self._result_out["status_id"] = status.id_
        self._result_out["participant_id"] = participant_id

        self.logger.info(
            "%s: Created ParticipantStatus '%s' for actor '%s' in case '%s'",
            self.name,
            status.id_,
            self._actor_id,
            self._case_id,
        )
        return Status.SUCCESS
