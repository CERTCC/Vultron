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
from vultron.core.behaviors.helpers import DataLayerActionWithPorts
from vultron.core.behaviors.narrative_log import (
    log_cs_transition,
    log_rm_transition,
)
from vultron.core.models.case_status import CaseStatus
from vultron.core.models.participant_status import (
    ParticipantStatus,
    coerce_cvd_roles,
    coerce_em_consent_state,
)
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.dimensions import (
    DDimension,
    EmDimension,
    PecDimension,
    PxaDimension,
    RmDimension,
    VfDimension,
)
from vultron.core.states.cs import (
    CS_d,
    CS_pxa,
    CS_vf,
    is_valid_d_transition,
    is_valid_pxa_transition,
    is_valid_vf_transition,
)
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


def _pxa_from_case(case: object) -> CS_pxa | None:
    """Return the case-level PXA state, or ``None`` when unavailable."""
    try:
        current_status = case.current_status  # type: ignore[attr-defined]
    except (AttributeError, ValueError):
        return None
    pxa_state = getattr(getattr(current_status, "pxa", None), "state", None)
    return pxa_state if isinstance(pxa_state, CS_pxa) else None


def _resolve_pxa_state(case: object, participant: object) -> CS_pxa:
    """Return the PXA state in force before this node writes a new snapshot.

    The participant's own latest ``ParticipantStatus.case_status.pxa`` is
    authoritative: this node records PXA on the *participant* snapshot and
    does not append to ``case.case_statuses``, so ``case.current_status``
    would report a stale ``pxa`` and make every repeat write look like a fresh
    public-disclosure event.

    Falls back to the case-level PXA (then ``CS_pxa.pxa``) when the
    participant has no PXA-bearing snapshot yet.
    """
    statuses = getattr(participant, "participant_statuses", None) or []
    for status in reversed(statuses):
        pxa_state = getattr(
            getattr(getattr(status, "case_status", None), "pxa", None),
            "state",
            None,
        )
        if isinstance(pxa_state, CS_pxa):
            return pxa_state
    return _pxa_from_case(case) or CS_pxa.pxa


class CreateParticipantStatusNode(DataLayerActionWithPorts):
    """Create a ParticipantStatus snapshot and append it to the participant."""

    def __init__(
        self,
        case_id: str,
        actor_id: str,
        rm_state: "RM | None",
        vf_state: "CS_vf | None",
        d_state: "CS_d | None",
        pxa_state: "CS_pxa | None",
        result_out: dict,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self._case_id = case_id
        self._actor_id = actor_id
        self._rm_state = rm_state
        self._vf_state = vf_state
        self._d_state = d_state
        self._pxa_state = pxa_state
        self._result_out = result_out

    def _persist_status(
        self, dl: object, participant_id: str, status: "ParticipantStatus"
    ) -> None:
        """Write the status to the DataLayer and link it to the participant."""
        try:
            dl.create(status)  # type: ignore[attr-defined]
        except ValueError:
            dl.save(status)  # type: ignore[attr-defined]
        participant_obj = dl.read(participant_id)  # type: ignore[attr-defined]
        wire_status = dl.read(status.id_)  # type: ignore[attr-defined]
        if isinstance(participant_obj, CaseParticipant) and isinstance(
            wire_status, ParticipantStatus
        ):
            participant_obj.add_participant_status(wire_status)
            dl.save(participant_obj)  # type: ignore[attr-defined]

    def _build_dimensions(
        self,
        current_vf: CS_vf | None,
        current_d: CS_d | None,
    ) -> "tuple[VfDimension | None, DDimension | None]":
        """Return (vf_dim, d_dim) for the new snapshot."""
        vf_dim: VfDimension | None = None
        if self._vf_state is not None:
            vf_dim = VfDimension(state=self._vf_state)
        elif current_vf is not None:
            vf_dim = VfDimension(state=current_vf)

        d_dim: DDimension | None = None
        if self._d_state is not None:
            d_dim = DDimension(state=self._d_state)
        elif current_d is not None:
            d_dim = DDimension(state=current_d)

        return vf_dim, d_dim

    def _build_participant_metadata(
        self, participant_obj: object
    ) -> "tuple[list, PecDimension | None]":
        """Return (status_roles, consent_dim) derived from participant object."""
        participant_roles = (
            participant_obj.roles  # type: ignore[union-attr]
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
        return status_roles, consent_dim

    def _check_vf_precondition(
        self, current_vf: CS_vf | None
    ) -> "Status | None":
        """CSB-16-001: validate VF transition before writing."""
        if self._vf_state is None or current_vf is None:
            return None
        if self._vf_state != current_vf and not is_valid_vf_transition(
            current_vf, self._vf_state
        ):
            self.logger.warning(
                "%s: invalid VF transition %s → %s for actor '%s'",
                self.name,
                current_vf,
                self._vf_state,
                self._actor_id,
            )
            self.feedback_message = (
                f"Invalid VF transition {current_vf!r} → {self._vf_state!r}"
            )
            return Status.FAILURE
        return None

    def _check_d_precondition(self, current_d: CS_d | None) -> "Status | None":
        """CSB-16-001: validate D transition before writing."""
        if self._d_state is None or current_d is None:
            return None
        if self._d_state != current_d and not is_valid_d_transition(
            current_d, self._d_state
        ):
            self.logger.warning(
                "%s: invalid D transition %s → %s for actor '%s'",
                self.name,
                current_d,
                self._d_state,
                self._actor_id,
            )
            self.feedback_message = (
                f"Invalid D transition {current_d!r} → {self._d_state!r}"
            )
            return Status.FAILURE
        return None

    def _check_pxa_precondition(self, pxa_before: CS_pxa) -> "Status | None":
        """CSB-16-002: validate PXA transition before writing."""
        if self._pxa_state is None:
            return None
        if self._pxa_state != pxa_before and not is_valid_pxa_transition(
            pxa_before, self._pxa_state
        ):
            self.logger.warning(
                "%s: invalid PXA transition %s → %s for actor '%s'",
                self.name,
                pxa_before,
                self._pxa_state,
                self._actor_id,
            )
            self.feedback_message = (
                f"Invalid PXA transition {pxa_before!r} → {self._pxa_state!r}"
            )
            return Status.FAILURE
        return None

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

        current_rm, current_vf, current_d = resolve_participant_state_from_dl(
            dl, participant_id
        )
        participant_obj = dl.read(participant_id)

        guard = self._check_vf_precondition(current_vf)
        if guard is not None:
            return guard

        guard = self._check_d_precondition(current_d)
        if guard is not None:
            return guard

        case_status: CaseStatus | None = None
        pxa_before: CS_pxa | None = None
        if self._pxa_state is not None:
            pxa_before = _resolve_pxa_state(case, participant_obj)
            guard = self._check_pxa_precondition(pxa_before)
            if guard is not None:
                return guard
            case_status = CaseStatus(
                context=self._case_id,
                attributed_to=self._actor_id,
                em=EmDimension(state=_resolve_em_state(case)),
                pxa=PxaDimension(state=self._pxa_state),
            )

        status_roles, consent_dim = self._build_participant_metadata(
            participant_obj
        )
        vf_dim, d_dim = self._build_dimensions(current_vf, current_d)

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
            vf=vf_dim,
            d=d_dim,
            consent=consent_dim,
            cvd_role=status_roles,
            case_status=case_status,
        )
        self._persist_status(dl, participant_id, status)

        self._result_out["status_id"] = status.id_
        self._result_out["participant_id"] = participant_id

        self.logger.debug(
            "%s: Created ParticipantStatus '%s' for actor '%s' in case '%s'",
            self.name,
            status.id_,
            self._actor_id,
            self._case_id,
        )
        self._log_transitions(current_rm, current_vf, current_d, pxa_before)
        return Status.SUCCESS

    def _log_transitions(
        self,
        rm_before: RM,
        vf_before: CS_vf | None,
        d_before: CS_d | None,
        pxa_before: CS_pxa | None,
    ) -> None:
        """Emit narrative INFO lines for the dimensions this node advanced."""
        if self._rm_state is not None:
            log_rm_transition(
                self.logger,
                self._actor_id,
                self._case_id,
                rm_before,
                self._rm_state,
            )
        if self._vf_state is not None:
            log_cs_transition(
                self.logger,
                self._actor_id,
                self._case_id,
                vf_before if vf_before is not None else CS_vf.vf,
                self._vf_state,
            )
        if self._d_state is not None:
            log_cs_transition(
                self.logger,
                self._actor_id,
                self._case_id,
                d_before if d_before is not None else CS_d.d,
                self._d_state,
            )
        if self._pxa_state is not None and pxa_before is not None:
            log_cs_transition(
                self.logger,
                self._actor_id,
                self._case_id,
                pxa_before,
                self._pxa_state,
            )
