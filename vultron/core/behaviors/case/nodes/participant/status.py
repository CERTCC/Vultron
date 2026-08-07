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
    EmDimension,
    PecDimension,
    PxaDimension,
    RmDimension,
    VfdDimension,
)
from vultron.core.states.cs import (
    CS_pxa,
    CS_vfd,
    is_valid_pxa_transition,
    is_valid_vfd_transition,
)
from vultron.core.states.em import EM
from vultron.core.states.rm import RM, is_valid_rm_transition


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
        skip_transition_validation: bool = False,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self._case_id = case_id
        self._actor_id = actor_id
        self._rm_state = rm_state
        self._vfd_state = vfd_state
        self._pxa_state = pxa_state
        self._result_out = result_out
        self._skip_transition_validation = skip_transition_validation

    def _build_status(
        self,
        case: VulnerabilityCase,
        participant_obj: object,
        current_rm: "RM",
        current_vfd: "CS_vfd",
        pxa_before: "CS_pxa",
    ) -> "ParticipantStatus":
        """Construct the ParticipantStatus record to persist."""
        case_status: CaseStatus | None = None
        if self._pxa_state is not None:
            case_status = CaseStatus(
                context=self._case_id,
                attributed_to=self._actor_id,
                em=EmDimension(state=_resolve_em_state(case)),
                pxa=PxaDimension(state=self._pxa_state),
            )

        participant_roles = (
            participant_obj.roles  # type: ignore[union-attr]
            if isinstance(participant_obj, CaseParticipant)
            else []
        )
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

        return ParticipantStatus(
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
            cvd_role=coerce_cvd_roles(participant_roles),
            case_status=case_status,
        )

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

        current_rm, current_vfd = resolve_participant_state_from_dl(
            dl, participant_id
        )
        participant_obj = dl.read(participant_id)

        pxa_before = _resolve_pxa_state(case, participant_obj)
        if not self._skip_transition_validation:
            err = self._validate_transitions(
                current_rm, current_vfd, pxa_before
            )
            if err is not None:
                self.feedback_message = err
                self.logger.info("%s: %s", self.name, err)
                return Status.FAILURE

        status = self._build_status(
            case, participant_obj, current_rm, current_vfd, pxa_before
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

        self.logger.debug(
            "%s: Created ParticipantStatus '%s' for actor '%s' in case '%s'",
            self.name,
            status.id_,
            self._actor_id,
            self._case_id,
        )
        self._log_transitions(current_rm, current_vfd, pxa_before)
        return Status.SUCCESS

    def _validate_transitions(
        self,
        current_rm: RM,
        current_vfd: CS_vfd,
        pxa_before: CS_pxa,
    ) -> str | None:
        """Return an error string if any requested transition is invalid, else None."""
        if self._rm_state is not None and self._rm_state != current_rm:
            if not is_valid_rm_transition(current_rm, self._rm_state):
                return f"Invalid RM transition {current_rm!r} → {self._rm_state!r}"
        if self._vfd_state is not None and self._vfd_state != current_vfd:
            if not is_valid_vfd_transition(current_vfd, self._vfd_state):
                return (
                    f"Invalid VFD transition"
                    f" {current_vfd!r} → {self._vfd_state!r}"
                )
        if (
            self._pxa_state is not None
            and self._pxa_state != pxa_before
            and not is_valid_pxa_transition(pxa_before, self._pxa_state)
        ):
            return (
                f"Invalid PXA transition {pxa_before!r} → {self._pxa_state!r}"
            )
        return None

    def _log_transitions(
        self,
        rm_before: RM,
        vfd_before: CS_vfd,
        pxa_before: CS_pxa | None,
    ) -> None:
        """Emit narrative INFO lines for the dimensions this node advanced.

        The RM/CS dimension changes carried by the snapshot are the protocol
        story (SL-04-001); the helpers suppress no-op writes.

        This node is a second per-participant RM write path alongside
        ``update_participant_rm_state()`` (used by e.g. the leave-case
        RM → CLOSED nodes), so it must log the RM line itself.
        """
        if self._rm_state is not None:
            log_rm_transition(
                self.logger,
                self._actor_id,
                self._case_id,
                rm_before,
                self._rm_state,
            )
        if self._vfd_state is not None:
            log_cs_transition(
                self.logger,
                self._actor_id,
                self._case_id,
                vfd_before,
                self._vfd_state,
            )
        if self._pxa_state is not None and pxa_before is not None:
            log_cs_transition(
                self.logger,
                self._actor_id,
                self._case_id,
                pxa_before,
                self._pxa_state,
            )
