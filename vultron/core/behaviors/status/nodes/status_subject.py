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

"""Whose status a received ``Add(ParticipantStatus)`` may assert (RSH-08-007).

Participant status is self-declared: a received ``Add(ParticipantStatus)``
asserts a status onto the sender's own participant record.  The one exception
is the on-behalf assertion of PRM-06-003/004: a CASE_MANAGER or Case Owner may
assert v→V for a Vendor-role participant, or d→D for a Deployer-role one, and
nothing else (ADR-0121).

:func:`status_subject_guard` composes the precondition guard::

    StatusSubjectGuard (Selector)
    ├─ NotCaseManager (Inverter(CheckIsCaseManagerNode))  # the CASE_MANAGER judges
    ├─ StatusTargetIsOwnRecordNode            # the asserting actor's own record
    └─ OnBehalfAssertion (Sequence)           # PRM-06-003/004
        ├─ CheckOnBehalfAuthorizedNode        # sender holds CASE_MANAGER or CASE_OWNER
        ├─ CheckOnBehalfStatusShapeNode       # v→V and/or d→D, nothing else
        └─ CheckOnBehalfTargetIsParticipantNode  # target holds the role

Only the CASE_MANAGER judges the subject: at any other receiver the guard
passes, and the CASE_MANAGER gate turns the copy away (HP-01-005, RSH-08-003).

This is a check of what the status is about, not of the sender's standing:
the declared sender rule (``PARTICIPANT``) decides whether the sender may send
an ``Add(ParticipantStatus)`` at all (HP-01-008), and this guard decides
whether the record the status names is the one the sender may write, as
HP-08-008 decides which case it names.  So a refusal is a precondition
refusal, answered with the refusal notice (CLP-05-001).

The on-behalf branch reuses the trigger side's guards
(:mod:`vultron.core.behaviors.case.nodes.on_behalf_guards`), so the sender
and the CASE_MANAGER admit the same assertions.  Every node is a pure read
that runs before the commit, so a refused status leaves no entry and no
append (CLP-10-006).
"""

import py_trees
from py_trees.common import Status

from vultron.core.behaviors.case.nodes.conditions import CheckIsCaseManagerNode
from vultron.core.behaviors.case.nodes.on_behalf_guards import (
    CheckOnBehalfAuthorizedNode,
    CheckOnBehalfTargetIsParticipantNode,
    on_behalf_required_roles,
)
from vultron.core.behaviors.case.nodes.participant.common import (
    resolve_participant_state_from_dl,
)
from vultron.core.behaviors.helpers import DataLayerConditionWithPorts
from vultron.core.models._helpers import _as_id
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.participant_status import ParticipantStatus
from vultron.core.models.protocols import PersistableModel
from vultron.core.states.cs import CS_d, CS_vf
from vultron.core.states.rm import RM
from vultron.enums.roles import CVDRole


def _asserted_vf(status: ParticipantStatus) -> CS_vf | None:
    return status.vf.state if status.vf is not None else None


def _asserted_d(status: ParticipantStatus) -> CS_d | None:
    return status.d.state if status.d is not None else None


def on_behalf_status_roles(status: ParticipantStatus) -> list[CVDRole] | None:
    """The roles an on-behalf target must hold for *status*, or ``None``.

    ``VENDOR`` when *status* asserts ``Vf`` (v→V, PRM-06-003) and ``DEPLOYER``
    when it asserts ``D`` (d→D, PRM-06-004), as
    :func:`on_behalf_required_roles` derives them.  ``None`` when it asserts
    neither, so it cannot be an on-behalf assertion at all.
    """
    vf = _asserted_vf(status)
    d = _asserted_d(status)
    try:
        return on_behalf_required_roles(
            vf if vf is CS_vf.Vf else None, d if d is CS_d.D else None
        )
    except ValueError:
        return None


def _move_violation(
    label: str,
    current: CS_vf | CS_d | None,
    asserted: CS_vf | CS_d | None,
    allowed: tuple[CS_vf, CS_vf] | tuple[CS_d, CS_d],
    cites: str,
) -> str | None:
    """Why the move *current* → *asserted* is not the one on-behalf move.

    Unchanged (or not asserted) is no move; otherwise only
    ``allowed[0]`` (or no state yet) → ``allowed[1]`` is.
    """
    if asserted is None or asserted == current:
        return None
    start, end = allowed
    if asserted == end and current in (None, start):
        return None
    return (
        f"{label}: moves {current} to {asserted}; only {start}→{end} may be"
        f" asserted on behalf ({cites})"
    )


def on_behalf_status_violations(
    current_rm: RM,
    current_vf: CS_vf | None,
    current_d: CS_d | None,
    asserted: ParticipantStatus,
) -> list[str]:
    """Every way *asserted* is more than an on-behalf v→V or d→D.

    An on-behalf assertion moves the target's VF from ``vf`` to ``Vf``, its D
    from ``d`` to ``D``, or both, and changes nothing else: RM stays as the
    target holds it, and it carries no case status, so no P, X or A
    (PRM-06-003/004, PRM-06-005).  Every violation is reported (EH-07-001);
    an empty list admits the shape.
    """
    violations: list[str] = []
    if asserted.rm.state != current_rm:
        violations.append(
            f"RM: asserts {asserted.rm.state.value} but the target is at"
            f" {current_rm.value}; RM is only the participant's own to"
            " assert"
        )
    if asserted.case_status is not None:
        violations.append(
            "PXA: carries a case status; P, X and A are only the"
            " participant's own to assert"
        )
    for violation in (
        _move_violation(
            "VF",
            current_vf,
            _asserted_vf(asserted),
            (CS_vf.vf, CS_vf.Vf),
            "PRM-06-003, PRM-06-005",
        ),
        _move_violation(
            "D",
            current_d,
            _asserted_d(asserted),
            (CS_d.d, CS_d.D),
            "PRM-06-004",
        ),
    ):
        if violation is not None:
            violations.append(violation)
    if on_behalf_status_roles(asserted) is None:
        violations.append(
            "asserts neither v→V nor d→D, the only moves a CASE_MANAGER or"
            " Case Owner may assert on behalf (PRM-06-003, PRM-06-004)"
        )
    return violations


class StatusTargetIsOwnRecordNode(DataLayerConditionWithPorts):
    """SUCCESS when the target participant record is the asserting actor's.

    The record's ``attributed_to`` names its participant; a received status
    is the asserting actor's statement about itself (RSH-08-007,
    RSH-08-001).  A pure read: FAILURE names the record's participant and
    the asserting actor.
    """

    def __init__(
        self,
        participant_id: str,
        sender_actor_id: str,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self._participant_id = participant_id
        self._sender_actor_id = sender_actor_id

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None

        record = self.datalayer.read(self._participant_id)
        owner = (
            _as_id(record.attributed_to)
            if isinstance(record, CaseParticipant)
            else None
        )
        if owner is not None and owner == self._sender_actor_id:
            return Status.SUCCESS
        self.feedback_message = (
            f"Participant record '{self._participant_id}' belongs to"
            f" '{owner or 'no actor'}', not to the sender"
            f" '{self._sender_actor_id}': a participant asserts only its own"
            " status (RSH-08-007)"
        )
        self.logger.debug("%s: %s", self.name, self.feedback_message)
        return Status.FAILURE


class CheckOnBehalfStatusShapeNode(DataLayerConditionWithPorts):
    """SUCCESS when the received status is only an on-behalf v→V or d→D.

    Reads the target's current status and the asserted one and applies
    :func:`on_behalf_status_violations`; FAILURE names every violation
    (EH-07-001, RSH-08-007).
    """

    def __init__(
        self,
        participant_id: str,
        status_id: str,
        status_obj_fallback: PersistableModel | None = None,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self._participant_id = participant_id
        self._status_id = status_id
        self._status_obj_fallback = status_obj_fallback

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None

        from_dl = self.datalayer.read(self._status_id)
        asserted = (
            from_dl if from_dl is not None else self._status_obj_fallback
        )
        if not isinstance(asserted, ParticipantStatus):
            violations = [
                f"status '{self._status_id}' is not a readable"
                " ParticipantStatus"
            ]
        else:
            current_rm, current_vf, current_d = (
                resolve_participant_state_from_dl(
                    self.datalayer, self._participant_id
                )
            )
            violations = on_behalf_status_violations(
                current_rm, current_vf, current_d, asserted
            )
        if not violations:
            return Status.SUCCESS
        self.feedback_message = (
            f"On-behalf ParticipantStatus '{self._status_id}' for"
            f" '{self._participant_id}' refused: " + "; ".join(violations)
        )
        self.logger.warning("%s: %s", self.name, self.feedback_message)
        return Status.FAILURE


def status_subject_guard(
    *,
    case_id: str,
    participant_id: str,
    sender_actor_id: str,
    target_actor_id: str | None,
    status_id: str,
    status_obj: PersistableModel | None,
) -> py_trees.behaviour.Behaviour:
    """The RSH-08-007 precondition guard for a received ``Add(ParticipantStatus)``.

    Admits a status on the sender's own record, or an on-behalf v→V or d→D
    the guards of PRM-06-003/004 admit.  The on-behalf branch is composed
    only when the target's participant is known and *status_obj* is a
    ``ParticipantStatus`` asserting ``Vf`` or ``D``, since the target's
    required roles come from what the status asserts; otherwise the record
    must be the sender's own.

    Args:
        case_id: The target participant's case (HP-08-008).
        participant_id: The target participant record.
        sender_actor_id: The activity's actor.
        target_actor_id: The actor the target record names, or ``None``.
        status_id: The asserted status's id.
        status_obj: The asserted status as carried, if inline.
    """
    own_record = StatusTargetIsOwnRecordNode(
        participant_id=participant_id, sender_actor_id=sender_actor_id
    )
    not_case_manager = py_trees.decorators.Inverter(
        name="NotCaseManager",
        child=CheckIsCaseManagerNode(case_id=case_id),
    )
    roles = (
        on_behalf_status_roles(status_obj)
        if isinstance(status_obj, ParticipantStatus)
        else None
    )
    children: list[py_trees.behaviour.Behaviour] = [
        not_case_manager,
        own_record,
    ]
    if roles is not None and target_actor_id is not None:
        children.append(
            py_trees.composites.Sequence(
                name="OnBehalfAssertion",
                memory=False,
                children=[
                    CheckOnBehalfAuthorizedNode(
                        case_id=case_id, asserting_actor_id=sender_actor_id
                    ),
                    CheckOnBehalfStatusShapeNode(
                        participant_id=participant_id,
                        status_id=status_id,
                        status_obj_fallback=status_obj,
                    ),
                    CheckOnBehalfTargetIsParticipantNode(
                        case_id=case_id,
                        target_actor_id=target_actor_id,
                        required_roles=roles,
                    ),
                ],
            )
        )
    return py_trees.composites.Selector(
        name="StatusSubjectGuard", memory=False, children=children
    )
