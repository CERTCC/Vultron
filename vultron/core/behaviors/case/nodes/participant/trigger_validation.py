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

import py_trees
from py_trees.common import Status

from vultron.core.behaviors.case.nodes.participant.common import (
    context_after_followed,
    resolve_transition_context_or_report,
    validate_participant_status_write,
)
from vultron.core.behaviors.helpers import DataLayerCondition
from vultron.core.models.case import VulnerabilityCase
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.states.cs import CS_d, CS_pxa, CS_vf
from vultron.core.states.rm import RM

logger = logging.getLogger(__name__)


def check_participant_status_move(
    node: py_trees.behaviour.Behaviour,
    dl: CasePersistence,
    case: VulnerabilityCase,
    participant_id: str,
    *,
    actor_id: str,
    rm_state: "RM | None",
    vf_state: "CS_vf | None" = None,
    d_state: "CS_d | None" = None,
    pxa_state: "CS_pxa | None" = None,
    result_out: dict | None = None,
    follows: list[str] | None = None,
) -> Status | None:
    """Check a status move against the shared rule set; ``None`` when legal.

    The check a trigger runs before it sends a declaration it does not write
    (RSH-08-006): the same evaluator the write node uses (BTND-10-002), run
    against the participant's current state, or the state the last of
    *follows* leaves.  On a refusal it returns ``FAILURE`` with the
    violations reported on *node* and in ``result_out["error"]``.
    """
    context = resolve_transition_context_or_report(
        node, dl, case, participant_id
    )
    if isinstance(context, Status):
        return context
    context = context_after_followed(dl, context, follows)
    return validate_participant_status_write(
        node,
        context,
        case_id=str(case.id_),
        actor_id=actor_id,
        rm_state=rm_state,
        vf_state=vf_state,
        d_state=d_state,
        pxa_state=pxa_state,
        result_out=result_out,
    )


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

    When the participant has no current status (first write) the baseline is
    ``RM.START``, ``CS_pxa.pxa``, and **absent** VF and D — ``None``, not an
    initial value (ADR-0075).  Absence means there is no transition to measure,
    so no per-dimension VF/D rule can fire; the role gate is what refuses an
    assertion on a path the participant does not have (#2906).

    This node writes ``result_out["error"]`` when it refuses, which is a
    deliberate exception to :class:`DataLayerCondition`'s otherwise
    side-effect-free contract.  The aggregate exception has to reach
    ``SvcBTTriggerBase.execute()`` for the FastAPI layer to project it into the
    422 ``details`` array (EH-05-002, EH-07-003), and ``result_out`` is the
    existing channel for that.  It carries diagnostics only — no protocol state.

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
        require_participant: bool = False,
        follows: list[str] | None = None,
    ) -> None:
        """Create the node.

        *require_participant* fails the check when the case or the actor's
        participant record is missing.  A tree with no
        ``CreateParticipantStatusNode`` after this node to report that
        absence passes it, so a decision the actor has no standing to make
        is refused before it is sent.

        *follows* names statuses already stored for the actor but not
        appended to its record; the move is checked as the step after the
        last of them (:func:`~vultron.core.behaviors.case.nodes.participant\
.common.context_after_followed`).
        """
        super().__init__(name=name or self.__class__.__name__)
        self._require_participant = require_participant
        self._follows = follows
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

        # Regime 2 / defer-downstream (ADR-0087): this validation pre-stage runs
        # ahead of CreateParticipantStatusNode, which authoritatively reports a
        # missing case/participant. Passing through as SUCCESS here avoids a
        # duplicate failure and lets the canonical reporter own it (allowlist).
        case = dl.read_case(self._case_id)
        participant_id = (
            case.actor_participant_index.get(self._actor_id) if case else None
        )
        if case is None or participant_id is None:
            if not self._require_participant:
                # CreateParticipantStatusNode will report this; pass through.
                return Status.SUCCESS
            self.feedback_message = (
                f"No participant record for actor '{self._actor_id}'"
                f" in case '{self._case_id}'"
            )
            self.logger.warning("%s: %s", self.name, self.feedback_message)
            return Status.FAILURE

        failure = check_participant_status_move(
            self,
            dl,
            case,
            participant_id,
            actor_id=self._actor_id,
            rm_state=self._rm_state,
            vf_state=self._vf_state,
            d_state=self._d_state,
            pxa_state=self._pxa_state,
            result_out=self._result_out,
            follows=self._follows,
        )
        return Status.SUCCESS if failure is None else failure
