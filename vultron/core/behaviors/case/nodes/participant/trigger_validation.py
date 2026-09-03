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

Both nodes evaluate the *same* rule set, composed once by
:func:`~vultron.core.states.participant_transitions\
.participant_transition_violations` and reached through
:func:`~vultron.core.behaviors.case.nodes.participant.common\
.validate_participant_status_write` (BTND-10-002, ADR-0086).  They cannot
double-report: this guard fails first and the enclosing ``Sequence`` aborts
before the write node ticks.

This is the trigger-path counterpart of
:class:`~vultron.core.behaviors.status.nodes.dimension_filter\
.FilterParticipantStatusDimensionsNode` (received wire path).  The two differ
in disposition: the received path uses per-dimension partial-accept (a refused
dimension carries the current value forward so other dimensions still land);
the trigger path is fail-closed (a self-reported invalid jump is rejected
outright — the actor controls its own state machine and must request valid
steps).  That asymmetry is Postel's maxim applied to the two sides of the wire,
not an inconsistency to reconcile — see `notes/domain-validation.md`.

Per specs/behavior-tree-node-design.yaml BTND-10-001, BTND-10-002,
specs/status-dimension-objects.yaml SDO-02-004,
specs/cs-behavior.yaml CSB-16-001, CSB-16-002, CSB-18-001,
specs/error-handling.yaml EH-07-001, EH-07-002.
Closes #2081 (AC-1, AC-2, AC-3, AC-6), #1903 (AC-1, AC-2, AC-3), #2236, #3050.
"""

import logging

from py_trees.common import Status

from vultron.core.behaviors.case.nodes.participant.common import (
    resolve_transition_context_or_report,
    validate_participant_status_write,
)
from vultron.core.behaviors.helpers import DataLayerCondition
from vultron.core.states.cs import CS_d, CS_pxa, CS_vf
from vultron.core.states.rm import RM

logger = logging.getLogger(__name__)


class ValidateTriggerTransitionsNode(DataLayerCondition):
    """Fail-closed transition guard for the add-participant-status trigger path.

    Validates each non-``None`` requested dimension against the participant's
    current state.  Returns ``FAILURE`` with a ``feedback_message`` naming
    **every** violated rule when the write is illegal, and ``SUCCESS``
    otherwise.

    Rules (per BTND-10-001, BTND-10-002, CSB-18-001) are composed by
    :func:`~vultron.core.states.participant_transitions\
    .participant_transition_violations` — this node evaluates none of them
    itself.  In summary:

    - ``None`` target → that dimension asserts nothing and is skipped (AC-5).
    - ``target == current`` → same-state confirmation, always valid (AC-4).
    - An illegal adjacent step in RM, VF, D or PXA (AC-1/2/3).
    - The VENDOR gate on the vendor path and the DEPLOYER gate on the deployer
      path (CSB-15-001, CSB-15-002, ADR-0075).
    - The RM↔VF, RM↔D and VF↔D cross-machine entailments (CSB-17-001,
      CSB-18-001) and the compound CS transition (SM-09-002).

    When the participant has no current status (first write) the initial states
    ``RM.START``, initial VF/D state, ``CS_pxa.pxa`` are used as the baseline, so
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

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None
        dl = self.datalayer

        case = dl.read_case(self._case_id)
        if case is None:
            # CreateParticipantStatusNode will report this; pass through.
            return Status.SUCCESS

        participant_id = case.actor_participant_index.get(self._actor_id)
        if participant_id is None:
            # CreateParticipantStatusNode will report this; pass through.
            return Status.SUCCESS

        context = resolve_transition_context_or_report(
            self, dl, case, participant_id
        )
        if isinstance(context, Status):
            return context

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
        )
        return Status.SUCCESS if failure is None else failure
