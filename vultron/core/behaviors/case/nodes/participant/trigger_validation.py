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

"""Fail-closed transition guard for the add-participant-status trigger path.

When an actor self-reports a new RM/VFD/PXA state via an HTTP trigger, the
requested state must be a valid adjacent step from the actor's current state.
:class:`ValidateTriggerTransitionsNode` enforces this before
:class:`~vultron.core.behaviors.case.nodes.participant.status\
.CreateParticipantStatusNode` writes anything to the DataLayer.

This is the trigger-path counterpart of
:class:`~vultron.core.behaviors.status.nodes.dimension_filter\
.FilterParticipantStatusDimensionsNode` (received wire path).  The two differ
in disposition: the received path uses per-dimension partial-accept (a refused
dimension carries the current value forward so other dimensions still land);
the trigger path is fail-closed (a self-reported invalid jump is rejected
outright — the actor controls its own state machine and must request valid
steps).

Per specs/behavior-tree-node-design.yaml BTND-10-001,
specs/status-dimension-objects.yaml SDO-02-004,
specs/cs-behavior.yaml CSB-16-001, CSB-16-002, CSB-18-001.
Closes #2081 (AC-1, AC-2, AC-3, AC-6), #1903 (AC-1, AC-2, AC-3), #2236.
"""

import logging

from py_trees.common import Status

from vultron.core.behaviors.case.nodes.participant.common import (
    resolve_participant_state_from_dl,
)
from vultron.core.behaviors.helpers import DataLayerCondition
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.states.cross_machine_invariants import (
    violation_rm_vfd_entailment,
)
from vultron.core.states.cs import (
    CS_pxa,
    CS_vfd,
    is_valid_pxa_transition,
    is_valid_vfd_transition,
)
from vultron.core.states.rm import RM, is_valid_rm_transition

logger = logging.getLogger(__name__)


def _resolve_current_pxa(case: object, participant: object) -> CS_pxa:
    """Return the participant's current PXA state before a new snapshot lands.

    Reads the participant's own status history first (authoritative for PXA
    because this node records PXA on the participant snapshot, not on
    ``case.case_statuses``).  Falls back to case-level PXA then ``CS_pxa.pxa``
    when the participant has no PXA-bearing snapshot yet.
    """
    statuses = getattr(participant, "participant_statuses", None) or []
    for status in reversed(statuses):
        pxa_dim = getattr(getattr(status, "case_status", None), "pxa", None)
        pxa_state = getattr(pxa_dim, "state", None)
        if isinstance(pxa_state, CS_pxa):
            return pxa_state
    # Fall back to case-level PXA.
    try:
        current_status = case.current_status  # type: ignore[attr-defined]
    except (AttributeError, ValueError):
        return CS_pxa.pxa
    pxa_dim = getattr(getattr(current_status, "pxa", None), "state", None)
    return pxa_dim if isinstance(pxa_dim, CS_pxa) else CS_pxa.pxa


class ValidateTriggerTransitionsNode(DataLayerCondition):
    """Fail-closed transition guard for the add-participant-status trigger path.

    Validates each non-``None`` requested dimension against the participant's
    current state using strict-adjacency checks.  Returns ``FAILURE`` with a
    descriptive ``feedback_message`` when any dimension would be an illegal
    jump; returns ``SUCCESS`` otherwise.

    Rules (per BTND-10-001, CSB-18-001):

    - ``None`` target → skip that dimension (AC-5).
    - ``target == current`` → same-state confirmation, always valid (AC-4).
    - ``target != current`` and invalid adjacent step → ``FAILURE`` (AC-1/2/3).
    - VFD has F bit (VFd/VFD) and effective RM ∉ {ACCEPTED, DEFERRED, CLOSED}
      → ``FAILURE`` (CSB-18-001, #2236).

    When the participant has no current status (first write) the initial states
    ``RM.START``, ``CS_vfd.vfd``, ``CS_pxa.pxa`` are used as the baseline, so
    the first valid transition from each initial state always passes.

    Returns ``SUCCESS`` without validation when the participant or case cannot
    be read from the DataLayer — ``CreateParticipantStatusNode`` downstream
    handles missing-entity failures with its own error returns.
    """

    def __init__(
        self,
        case_id: str,
        actor_id: str,
        rm_state: "RM | None",
        vfd_state: "CS_vfd | None",
        pxa_state: "CS_pxa | None",
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self._case_id = case_id
        self._actor_id = actor_id
        self._rm_state = rm_state
        self._vfd_state = vfd_state
        self._pxa_state = pxa_state

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None
        dl = self.datalayer

        case = dl.read(self._case_id)
        if not isinstance(case, VulnerabilityCase):
            # CreateParticipantStatusNode will report this; pass through.
            return Status.SUCCESS

        participant_id = case.actor_participant_index.get(self._actor_id)
        if participant_id is None:
            # CreateParticipantStatusNode will report this; pass through.
            return Status.SUCCESS

        current_rm, current_vfd = resolve_participant_state_from_dl(
            dl, participant_id
        )
        participant_obj = dl.read(participant_id)

        # --- RM dimension ---
        if (
            self._rm_state is not None
            and self._rm_state != current_rm
            and not is_valid_rm_transition(current_rm, self._rm_state)
        ):
            self.feedback_message = (
                f"Invalid RM transition {current_rm!r} → {self._rm_state!r}"
            )
            self.logger.info("%s: %s", self.name, self.feedback_message)
            return Status.FAILURE

        # --- VFD dimension ---
        if (
            self._vfd_state is not None
            and self._vfd_state != current_vfd
            and not is_valid_vfd_transition(current_vfd, self._vfd_state)
        ):
            self.feedback_message = (
                f"Invalid VFD transition"
                f" {current_vfd!r} → {self._vfd_state!r}"
            )
            self.logger.info("%s: %s", self.name, self.feedback_message)
            return Status.FAILURE

        # --- PXA dimension ---
        if self._pxa_state is not None and isinstance(
            participant_obj, CaseParticipant
        ):
            current_pxa = _resolve_current_pxa(case, participant_obj)
            if self._pxa_state != current_pxa and not is_valid_pxa_transition(
                current_pxa, self._pxa_state
            ):
                self.feedback_message = (
                    f"Invalid PXA transition"
                    f" {current_pxa!r} → {self._pxa_state!r}"
                )
                self.logger.info("%s: %s", self.name, self.feedback_message)
                return Status.FAILURE

        # --- Cross-machine: RM ↔ VFD entailment (CSB-18-001, #2236) ---
        # Fix readiness (F bit) requires RM ∈ {ACCEPTED, DEFERRED, CLOSED}.
        # Both RM and VFD are per-actor attributes, so a contradictory
        # combination is an error at the emitter.
        effective_rm = (
            self._rm_state if self._rm_state is not None else current_rm
        )
        effective_vfd = (
            self._vfd_state if self._vfd_state is not None else current_vfd
        )
        if (
            msg := violation_rm_vfd_entailment(effective_rm, effective_vfd)
        ) is not None:
            self.feedback_message = msg
            self.logger.info("%s: %s", self.name, self.feedback_message)
            return Status.FAILURE

        return Status.SUCCESS
