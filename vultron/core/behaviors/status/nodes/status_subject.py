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

"""What an on-behalf ``Add(ParticipantStatus)`` may assert (RSH-08-007).

Participant status is self-declared: a received ``Add(ParticipantStatus)``
asserts a status onto the sender's own participant record.  The one exception
is the on-behalf assertion of PRM-06-003/004: a CASE_MANAGER or Case Owner may
assert v→V for a Vendor-role participant, or d→D for a Deployer-role one, and
nothing else (ADR-0121).

Who may send the status is the use case's declared sender rule (HP-01-007,
HP-01-008): at the CASE_MANAGER, the participant the target record names
(``AUTHOR``), or the CASE_MANAGER or Case Owner.  The sender guard refuses
anyone else, with no refusal notice (HP-01-006, CLP-05-001).  This module
holds what remains once the sender is entitled: when the record is not the
sender's own, the status must be an on-behalf assertion.  That is a check of
what the status asserts, so an entitled sender that asserts more is refused
by a precondition guard and answered with the refusal notice (CLP-10-022).

:func:`on_behalf_status_guard` composes it, and the tree composes it only
when the target record names an actor other than the sender::

    OnBehalfStatusGuard (Selector)
    ├─ NotCaseManager (Inverter(CheckIsCaseManagerNode))  # the CASE_MANAGER judges
    └─ OnBehalfAssertion (Sequence)                       # PRM-06-003/004
        ├─ CheckOnBehalfStatusShapeNode        # v→V and/or d→D, nothing else
        └─ CheckOnBehalfTargetIsParticipantNode  # target holds the role

Only the CASE_MANAGER judges the assertion.  At any other receiver the guard
passes, and that is safe: the sender guard admits only the CASE_MANAGER
there (PCR-03-001), and the CASE_MANAGER gate keeps a replica from appending
or committing the copy (RSH-08-003, BT-17-001).  The same holds when the
CASE_MANAGER check fails because this store holds no such case: the sender
guard has already refused for want of one.

The causal gate the on-behalf trigger adds for d→D (CSB-15-004: some vendor
is at VF) is a trigger-side precondition, which the receive side does not
repeat for an on-behalf assertion, as it does not for a self-declared one.

Every node is a pure read that runs before the commit, so a refused status
leaves no entry and no append (CLP-10-006).
"""

import py_trees
from py_trees.common import Status

from vultron.core.behaviors.case.nodes.conditions import CheckIsCaseManagerNode
from vultron.core.behaviors.case.nodes.on_behalf_guards import (
    CheckOnBehalfTargetIsParticipantNode,
    on_behalf_required_roles,
)
from vultron.core.behaviors.case.nodes.participant.common import (
    resolve_participant_state_from_dl,
)
from vultron.core.behaviors.helpers import DataLayerConditionWithPorts
from vultron.core.models.case import VulnerabilityCase
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


class CheckOnBehalfStatusShapeNode(DataLayerConditionWithPorts):
    """SUCCESS when the received status is only an on-behalf v→V or d→D.

    Reads the asserted status (the stored copy, else the one carried) and the
    target's current status, and applies :func:`on_behalf_status_violations`.
    Two more conditions keep the guard closed:

    - the status must assert the dimensions the target's roles were derived
      from when the tree was built (*expected_roles*), so the role check never
      judges a different status than this one; a status carried by reference
      has no expected roles and is refused;
    - the case's participant index must list *participant_id* for
      *target_actor_id*, so the roles checked are the target record's own
      (CM-19-003).

    FAILURE names every violation (EH-07-001, RSH-08-007).
    """

    def __init__(
        self,
        case_id: str,
        participant_id: str,
        target_actor_id: str,
        status_id: str,
        expected_roles: list[CVDRole] | None,
        status_obj_fallback: PersistableModel | None = None,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self._case_id = case_id
        self._participant_id = participant_id
        self._target_actor_id = target_actor_id
        self._status_id = status_id
        self._expected_roles = expected_roles
        self._status_obj_fallback = status_obj_fallback

    def _violations(self, case: VulnerabilityCase) -> list[str]:
        assert self.datalayer is not None
        violations: list[str] = []
        indexed = case.actor_participant_index.get(self._target_actor_id)
        if indexed != self._participant_id:
            violations.append(
                f"the case lists '{indexed}', not '{self._participant_id}',"
                f" as '{self._target_actor_id}''s participant record"
                " (CM-19-003)"
            )
        from_dl = self.datalayer.read(self._status_id)
        asserted = (
            from_dl if from_dl is not None else self._status_obj_fallback
        )
        if not isinstance(asserted, ParticipantStatus):
            violations.append(
                f"status '{self._status_id}' is not a readable"
                " ParticipantStatus"
            )
            return violations
        if self._expected_roles is None:
            violations.append(
                "the status was not carried inline, so the target's roles"
                " for an on-behalf v→V or d→D could not be checked"
            )
        elif on_behalf_status_roles(asserted) != self._expected_roles:
            violations.append(
                f"status '{self._status_id}' as stored asserts other"
                " dimensions than the status carried"
            )
        current_rm, current_vf, current_d = resolve_participant_state_from_dl(
            self.datalayer, self._participant_id
        )
        violations.extend(
            on_behalf_status_violations(
                current_rm, current_vf, current_d, asserted
            )
        )
        return violations

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        case, failure = self._require_case(self._case_id)
        if failure is not None:
            return failure  # Regime 1: the index check needs the case
        assert case is not None
        violations = self._violations(case)
        if not violations:
            return Status.SUCCESS
        self.feedback_message = (
            f"On-behalf ParticipantStatus '{self._status_id}' for"
            f" '{self._participant_id}' refused: "
            + "; ".join(violations)
            + " (RSH-08-007)"
        )
        self.logger.warning("%s: %s", self.name, self.feedback_message)
        return Status.FAILURE


def on_behalf_status_guard(
    *,
    case_id: str,
    participant_id: str,
    target_actor_id: str,
    status_id: str,
    status_obj: PersistableModel | None,
) -> py_trees.behaviour.Behaviour:
    """The RSH-08-007 guard for a status onto another participant's record.

    The tree composes it only when the target record names an actor other
    than the sender, whom the sender guard has already found to be the
    CASE_MANAGER or Case Owner.  It admits only an on-behalf v→V or d→D for
    a target holding the matching role (PRM-06-003/004).  The target's
    required roles come from the status as carried; a status carried by
    reference has none, and the shape check refuses it.

    Args:
        case_id: The target participant's case (HP-08-008).
        participant_id: The target participant record.
        target_actor_id: The actor the target record names.
        status_id: The asserted status's id.
        status_obj: The asserted status as carried, if inline.
    """
    roles = (
        on_behalf_status_roles(status_obj)
        if isinstance(status_obj, ParticipantStatus)
        else None
    )
    assertion: list[py_trees.behaviour.Behaviour] = [
        CheckOnBehalfStatusShapeNode(
            case_id=case_id,
            participant_id=participant_id,
            target_actor_id=target_actor_id,
            status_id=status_id,
            expected_roles=roles,
            status_obj_fallback=status_obj,
        )
    ]
    if roles is not None:
        assertion.append(
            CheckOnBehalfTargetIsParticipantNode(
                case_id=case_id,
                target_actor_id=target_actor_id,
                required_roles=roles,
            )
        )
    return py_trees.composites.Selector(
        name="OnBehalfStatusGuard",
        memory=False,
        children=[
            py_trees.decorators.Inverter(
                name="NotCaseManager",
                child=CheckIsCaseManagerNode(case_id=case_id),
            ),
            py_trees.composites.Sequence(
                name="OnBehalfAssertion", memory=False, children=assertion
            ),
        ],
    )
