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

"""Participant status snapshot node for add-participant-status trigger BT.

The write boundary validates its own writes (BTND-10-001, BTND-10-003): five
production call sites reach :class:`CreateParticipantStatusNode` without passing
through :class:`~vultron.core.behaviors.case.nodes.participant\
.trigger_validation.ValidateTriggerTransitionsNode` — ``develop_fix.py``,
``deploy_fix.py``, ``close_case_effect.py`` and two in ``leave.py`` — and for
those this node's check is the only validation.  Both nodes evaluate the same
composed rule set via :func:`~vultron.core.behaviors.case.nodes.participant\
.common.validate_participant_status_write` (BTND-10-002, ADR-0086).
"""

from typing import NamedTuple

from py_trees.common import Status

from vultron.core.behaviors.case.nodes.participant.common import (
    ParticipantTransitionContext,
    resolve_participant_transition_context,
    validate_participant_status_write,
)
from vultron.core.behaviors.helpers import DataLayerActionWithPorts
from vultron.core.behaviors.narrative_log import (
    log_cs_transition,
    log_rm_transition,
)
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_status import CaseStatus
from vultron.core.models.participant_status import (
    ParticipantStatus,
    coerce_cvd_roles,
    coerce_em_consent_state,
)
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
    is_pxa_public_aware,
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


class _EffectiveStates(NamedTuple):
    """The CS dimension values this node persists.

    Each is the requested value when one was asserted and the participant's
    current value otherwise, with the SM-09-001 promotions applied.  The
    promotions run *after* validation deliberately — they are a forced
    correction at the write boundary, not something the caller asked for — so
    ``vf`` and ``pxa`` can differ from what the evaluator saw.  ``d`` is never
    promoted, and this is the single derivation of it, so validation and
    persistence cannot disagree about the deployer path.
    """

    vf: CS_vf | None
    d: CS_d | None
    pxa: CS_pxa


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
        force_rm_state: bool = False,
    ) -> None:
        """Create the node.

        Args:
            force_rm_state: Skip the RM adjacency rule for this write.

                **Quarantine — do not add new users.** Set only by the three
                case-closure call sites that stamp a departing participant
                ``RM.CLOSED`` regardless of the rung its RM machine is actually
                on: ``sync/nodes/close_case_effect.py`` (the received close
                fan-out) and ``case/nodes/leave.py`` (twice).  ``RM.CLOSED`` is
                reachable only from ``ACCEPTED``, ``INVALID`` or ``DEFERRED``,
                so those writes request a transition the protocol does not have
                — a standing BTND-10-001 violation that was invisible until
                this node started validating RM at all (ADR-0086, #3050).

                The other two guard-bypassing sites (``develop_fix.py``,
                ``deploy_fix.py``) pass ``rm_state=None`` and so need no
                exemption: they assert nothing about RM.

                Whether case closure should be forcing participant RM state
                *at all* is a protocol question, deliberately not answered here;
                it is tracked as ``type:Concern`` #3106 so the design
                conversation happens before the behaviour changes.  Participants are expected
                to reach ``RM.CLOSED`` by closing their own report handling, not
                by being pushed there.

                ``test/architecture/test_participant_status_validation.py``
                pins the exempt call sites, so the list can only shrink.
        """
        super().__init__(name=name or self.__class__.__name__)
        self._case_id = case_id
        self._actor_id = actor_id
        self._rm_state = rm_state
        self._vf_state = vf_state
        self._d_state = d_state
        self._pxa_state = pxa_state
        self._result_out = result_out
        self._force_rm_state = force_rm_state

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

    def _apply_ac1_promotions(
        self,
        eff_vf: "CS_vf | None",
        eff_pxa: CS_pxa,
    ) -> "tuple[CS_vf | None, CS_pxa]":
        """Apply SM-09-001 pX→PX and vP→VP forced promotions."""
        if self._pxa_state is None:
            return eff_vf, eff_pxa
        if eff_pxa is CS_pxa.pXa:
            eff_pxa = CS_pxa.PXa
        elif eff_pxa is CS_pxa.pXA:
            eff_pxa = CS_pxa.PXA
        if eff_vf is CS_vf.vf and is_pxa_public_aware(eff_pxa):
            eff_vf = CS_vf.Vf
        return eff_vf, eff_pxa

    def _effective_states(
        self, context: ParticipantTransitionContext
    ) -> _EffectiveStates:
        """Return the post-promotion CS dimension values to persist."""
        eff_vf = (
            self._vf_state
            if self._vf_state is not None
            else context.current_vf
        )
        eff_d = (
            self._d_state if self._d_state is not None else context.current_d
        )
        eff_pxa = (
            self._pxa_state
            if self._pxa_state is not None
            else context.current_pxa
        )
        # AC-1: pX → PX and vP → VP forced promotions (SM-09-001)
        eff_vf, eff_pxa = self._apply_ac1_promotions(eff_vf, eff_pxa)
        return _EffectiveStates(vf=eff_vf, d=eff_d, pxa=eff_pxa)

    def _resolve_target(
        self, dl: object
    ) -> "tuple[VulnerabilityCase, str] | None":
        """Return (case, participant_id), or None after reporting a failure."""
        case = dl.read_case(self._case_id)  # type: ignore[attr-defined]
        if case is None:
            self.logger.error(
                "%s: Case '%s' not found in DataLayer",
                self.name,
                self._case_id,
            )
            self.feedback_message = f"Case '{self._case_id}' not found"
            return None

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
            return None
        return case, participant_id

    def _build_status(
        self,
        case: VulnerabilityCase,
        context: ParticipantTransitionContext,
        effective: _EffectiveStates,
    ) -> ParticipantStatus:
        """Return the ParticipantStatus snapshot for this write."""
        case_status: CaseStatus | None = None
        if self._pxa_state is not None:
            case_status = CaseStatus(
                context=self._case_id,
                attributed_to=self._actor_id,
                em=EmDimension(state=_resolve_em_state(case)),
                pxa=PxaDimension(state=effective.pxa),
            )

        status_roles, consent_dim = self._build_participant_metadata(
            context.participant
        )
        return ParticipantStatus(
            context=self._case_id,
            attributed_to=self._actor_id,
            rm=RmDimension(
                state=(
                    self._rm_state
                    if self._rm_state is not None
                    else context.current_rm
                )
            ),
            vf=(
                VfDimension(state=effective.vf)
                if effective.vf is not None
                else None
            ),
            d=(
                DDimension(state=effective.d)
                if effective.d is not None
                else None
            ),
            consent=consent_dim,
            cvd_role=status_roles,
            case_status=case_status,
        )

    def update(self) -> Status:
        dl = self.datalayer
        if dl is None:
            self.logger.error("%s: DataLayer not available", self.name)
            self.feedback_message = "DataLayer not available"
            return Status.FAILURE

        target = self._resolve_target(dl)
        if target is None:
            return Status.FAILURE
        case, participant_id = target

        context = resolve_participant_transition_context(
            dl, case, participant_id
        )
        failure = validate_participant_status_write(
            self,
            context,
            case_id=self._case_id,
            actor_id=self._actor_id,
            rm_state=self._rm_state,
            vf_state=self._vf_state,
            d_state=self._d_state,
            pxa_state=self._pxa_state,
            result_out=self._result_out,
            validate_rm_transition=not self._force_rm_state,
        )
        if failure is not None:
            return failure

        effective = self._effective_states(context)
        status = self._build_status(case, context, effective)
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
        self._log_transitions(context, effective)
        return Status.SUCCESS

    def _log_transitions(
        self,
        context: ParticipantTransitionContext,
        effective: _EffectiveStates,
    ) -> None:
        """Emit narrative INFO lines for the dimensions this node advanced."""
        if self._rm_state is not None:
            log_rm_transition(
                self.logger,
                self._actor_id,
                self._case_id,
                context.current_rm,
                self._rm_state,
            )
        # Log VF: if explicitly requested OR if vP promotion forced a change
        if effective.vf is not None:
            log_cs_transition(
                self.logger,
                self._actor_id,
                self._case_id,
                (
                    context.current_vf
                    if context.current_vf is not None
                    else CS_vf.vf
                ),
                effective.vf,
            )
        if self._d_state is not None:
            log_cs_transition(
                self.logger,
                self._actor_id,
                self._case_id,
                (
                    context.current_d
                    if context.current_d is not None
                    else CS_d.d
                ),
                self._d_state,
            )
        # Log PXA using the effective (possibly promoted) value
        if self._pxa_state is not None:
            log_cs_transition(
                self.logger,
                self._actor_id,
                self._case_id,
                context.current_pxa,
                effective.pxa,
            )
