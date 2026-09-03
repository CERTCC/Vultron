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

"""The single evaluator for a proposed ``ParticipantStatus`` write.

:func:`participant_transition_violations` composes every rule that governs a
``(rm, vf, d, pxa)`` write against a participant's current state and returns
**all** of them that the write violates:

* the per-dimension transition checks (RM, VF, D, PXA);
* the VENDOR and DEPLOYER role gates;
* the RM↔VF, RM↔D and VF↔D cross-machine entailments, by delegating to
  :func:`~vultron.core.states.cross_machine_invariants.cross_machine_violations`;
* the compound CS transition.

Every node that validates such a write calls this function rather than the
individual ``is_valid_*_transition()`` / ``violation_*`` predicates
(BTND-10-002).  Before ADR-0086 the rules were implemented twice — once in
``ValidateTriggerTransitionsNode``, once in ``CreateParticipantStatusNode`` —
with byte-identical message text for the overlap and a different subset each
(ARCH-15-004).  ISSUE-2906 established that composing the rule *set* once, not
sharing its individual members, is what keeps two paths from drifting apart.

Rejecting the write is all-or-nothing on the emit path, but that governs what
is *persisted*, not how much of the diagnosis the caller is owed: a caller told
one reason per round trip gains nothing from the trip, because nothing partial
was accepted (EH-07-001).  Reporting everything unranked has the mirror
failure, so each violation is labelled root or derived by dimension overlap
(EH-07-002) — see :func:`_classify`.

Spec: EH-07-001, EH-07-002, BTND-10-001, BTND-10-002, BTND-10-003,
CSB-15-001, CSB-15-002, CSB-16-001, CSB-16-002, CSB-17-001, CSB-18-001,
SM-09-002.  ADR: ADR-0086.
"""

from collections.abc import Sequence

from vultron.core.states.cross_machine_invariants import (
    cross_machine_violations,
)
from vultron.core.states.cs import (
    CS_d,
    CS_pxa,
    CS_vf,
    CS_vfd,
    is_valid_d_transition,
    is_valid_pxa_transition,
    is_valid_vf_transition,
)
from vultron.core.states.cs_invariants import (
    cs_from_dimensions,
    is_valid_cs_transition,
)
from vultron.core.states.rm import RM, is_valid_rm_transition
from vultron.enums.roles import CVDRole
from vultron.errors import Violation

# VF states that assert vendor awareness or fix readiness.  Both are
# VENDOR-specific: only an actor that maintains the affected product can become
# aware of the report as its vendor or produce a fix for it.
_VENDOR_ONLY_VF: dict[CS_vf, str] = {
    CS_vf.Vf: "ADR-0075",
    CS_vf.VF: "CSB-15-001",
}


def _compound_vfd(vf: CS_vf, d: CS_d) -> CS_vfd | None:
    """Map a ``(CS_vf, CS_d)`` pair to its ``CS_vfd`` member, or ``None``.

    ``None`` means the pair has no compound spelling — ``vfD`` (deployed
    without ready) is structurally impossible per CSB-17-001.
    """
    try:
        return CS_vfd[f"{vf}{d}"]
    except KeyError:
        return None


def _rm_violations(current_rm: RM, requested_rm: RM | None) -> list[Violation]:
    """CSB-16-001: the requested RM state must be an adjacent step."""
    if requested_rm is None or requested_rm == current_rm:
        return []
    if is_valid_rm_transition(current_rm, requested_rm):
        return []
    return [
        Violation(
            f"Invalid RM transition {current_rm!r} → {requested_rm!r}",
            dimensions=("rm",),
        )
    ]


def _vf_violations(
    current_vf: CS_vf | None,
    requested_vf: CS_vf | None,
    actor_roles: Sequence[CVDRole],
) -> list[Violation]:
    """CSB-15-001 / ADR-0075 / CSB-16-001: VF role gate and transition."""
    if requested_vf is None:
        return []
    violations: list[Violation] = []
    if (
        spec := _VENDOR_ONLY_VF.get(requested_vf)
    ) is not None and CVDRole.VENDOR not in actor_roles:
        violations.append(
            Violation(
                f"CVDRole.VENDOR required for VF state {requested_vf!r}"
                f" ({spec}); actor roles: {list(actor_roles)!r}",
                dimensions=("vf",),
            )
        )
    if (
        current_vf is not None
        and requested_vf != current_vf
        and not is_valid_vf_transition(current_vf, requested_vf)
    ):
        violations.append(
            Violation(
                f"Invalid VF transition {current_vf!r} → {requested_vf!r}",
                dimensions=("vf",),
            )
        )
    return violations


def _d_violations(
    current_d: CS_d | None,
    requested_d: CS_d | None,
    actor_roles: Sequence[CVDRole],
) -> list[Violation]:
    """CSB-15-002 / CSB-16-001: D role gate and transition.

    The role gate covers *any* asserted D value, not only ``CS_d.D``: the
    deployer path belongs to DEPLOYER participants, so a non-DEPLOYER actor
    asserting ``d`` is claiming a dimension it does not have (#2963).
    """
    if requested_d is None:
        return []
    violations: list[Violation] = []
    if CVDRole.DEPLOYER not in actor_roles:
        violations.append(
            Violation(
                f"CVDRole.DEPLOYER required for D state {requested_d!r}"
                f" (CSB-15-002); actor roles: {list(actor_roles)!r}",
                dimensions=("d",),
            )
        )
    if (
        current_d is not None
        and requested_d != current_d
        and not is_valid_d_transition(current_d, requested_d)
    ):
        violations.append(
            Violation(
                f"Invalid D transition {current_d!r} → {requested_d!r}",
                dimensions=("d",),
            )
        )
    return violations


def _pxa_violations(
    current_pxa: CS_pxa, requested_pxa: CS_pxa | None
) -> list[Violation]:
    """CSB-16-002: the requested PXA state must be an adjacent step."""
    if requested_pxa is None or requested_pxa == current_pxa:
        return []
    if is_valid_pxa_transition(current_pxa, requested_pxa):
        return []
    return [
        Violation(
            f"Invalid PXA transition {current_pxa!r} → {requested_pxa!r}",
            dimensions=("pxa",),
        )
    ]


def _entailment_violations(
    effective_rm: RM,
    effective_vf: CS_vf | None,
    effective_d: CS_d | None,
) -> list[Violation]:
    """CSB-17-001 / CSB-18-001: the cross-machine entailments.

    Delegates to :func:`cross_machine_violations`, which is the single place
    the RM↔VF, RM↔D and VF↔D rules are composed, so the emit and receive paths
    cannot enforce different subsets of them (#2906, RSH-05-020).
    """
    return [
        Violation(entailment.message, dimensions=entailment.reads)
        for entailment in cross_machine_violations(
            effective_rm, effective_vf, effective_d
        )
    ]


def _compound_violations(
    current_vf: CS_vf | None,
    current_d: CS_d | None,
    current_pxa: CS_pxa,
    effective_vf: CS_vf | None,
    effective_d: CS_d | None,
    effective_pxa: CS_pxa,
) -> list[Violation]:
    """SM-09-002: one CS event changes exactly one of the six dimensions.

    Skipped when there is no VF history to compare against — the per-dimension
    checks are the whole story for a participant's first VF-bearing snapshot.
    """
    if current_vf is None or effective_vf is None:
        return []
    current_vfd = _compound_vfd(current_vf, current_d or CS_d.d)
    effective_vfd = _compound_vfd(effective_vf, effective_d or CS_d.d)
    if effective_vfd is None:
        return [
            Violation(
                f"Impossible compound VF+D state"
                f" ({effective_vf!r}, {effective_d!r})",
                dimensions=("vf", "d"),
            )
        ]
    if current_vfd is None:
        # The incumbent pair has no compound spelling, so there is no valid
        # source state to measure the move from.  Repairing that is the
        # receive path's problem (RSH-05-020); refusing this write would only
        # strand the participant.
        return []
    current_cs = cs_from_dimensions(current_vfd, current_pxa)
    effective_cs = cs_from_dimensions(effective_vfd, effective_pxa)
    if is_valid_cs_transition(current_cs, effective_cs, allow_null=True):
        return []
    return [
        Violation(
            f"Invalid compound CS transition"
            f" {current_cs.name!r} → {effective_cs.name!r}",
            dimensions=("vf", "d", "pxa"),
        )
    ]


def _classify(violations: Sequence[Violation]) -> list[Violation]:
    """Label each violation root or derived by dimension overlap (EH-07-002).

    A rule reading one dimension is always root.  A rule reading more than one
    is derived when any dimension it reads already carries a single-dimension
    violation, and root otherwise — the root multi-dimension case is the
    informative one: every dimension moved legally on its own and the
    *combination* is impossible.

    The test is dimension overlap rather than a rule-to-rule dependency graph,
    so a rule added later is classified correctly by construction and the
    labelling cannot go stale.
    """
    faulted: set[str] = {
        violation.dimensions[0]
        for violation in violations
        if len(violation.dimensions) == 1
    }
    return [
        violation._replace(
            derived=len(violation.dimensions) > 1
            and any(dim in faulted for dim in violation.dimensions)
        )
        for violation in violations
    ]


def participant_transition_violations(
    *,
    current_rm: RM,
    current_vf: CS_vf | None,
    current_d: CS_d | None,
    current_pxa: CS_pxa,
    requested_rm: RM | None = None,
    requested_vf: CS_vf | None = None,
    requested_d: CS_d | None = None,
    requested_pxa: CS_pxa | None = None,
    actor_roles: Sequence[CVDRole] = (),
    validate_rm_transition: bool = True,
) -> list[Violation]:
    """Return every rule the proposed ``ParticipantStatus`` write violates.

    A ``None`` requested value asserts nothing about that dimension, so no
    per-dimension rule can be violated through it; the multi-dimension rules
    read the *effective* value instead, which is the requested value when there
    is one and the participant's current value otherwise.

    A ``None`` *current* ``vf`` or ``d`` means the dimension is **absent**, not
    at its initial state: a non-VENDOR participant has no vendor path and a
    non-DEPLOYER participant has no deployer path (ADR-0075).  There is
    therefore no baseline to measure a transition from, and the role gate is
    what refuses the assertion.

    Args:
        current_rm: The participant's current RM state.
        current_vf: The participant's current VF state, or ``None`` when absent.
        current_d: The participant's current D state, or ``None`` when absent.
        current_pxa: The PXA state in force before this write.
        requested_rm: The RM state being asserted, or ``None``.
        requested_vf: The VF state being asserted, or ``None``.
        requested_d: The D state being asserted, or ``None``.
        requested_pxa: The PXA state being asserted, or ``None``.
        actor_roles: The asserting actor's ``CVDRole`` list, for the role gates.
        validate_rm_transition: Whether to apply the RM adjacency rule.  Only
            the enumerated case-closure quarantine (#3106) sets this ``False`` — see
            ``force_rm_state`` on
            :class:`~vultron.core.behaviors.case.nodes.participant.status\
            .CreateParticipantStatusNode`.  It suppresses one *rule*, never a
            violation the evaluator has already produced (BTND-10-002).

    Returns:
        One :class:`~vultron.errors.Violation` per violated rule, each naming
        the dimensions the rule reads and labelled root or derived; empty when
        the write is legal.
    """
    effective_rm = current_rm if requested_rm is None else requested_rm
    effective_vf = current_vf if requested_vf is None else requested_vf
    effective_d = current_d if requested_d is None else requested_d
    effective_pxa = current_pxa if requested_pxa is None else requested_pxa

    violations: list[Violation] = [
        *(
            _rm_violations(current_rm, requested_rm)
            if validate_rm_transition
            else []
        ),
        *_vf_violations(current_vf, requested_vf, actor_roles),
        *_d_violations(current_d, requested_d, actor_roles),
        *_pxa_violations(current_pxa, requested_pxa),
        *_entailment_violations(effective_rm, effective_vf, effective_d),
        *_compound_violations(
            current_vf,
            current_d,
            current_pxa,
            effective_vf,
            effective_d,
            effective_pxa,
        ),
    ]
    return _classify(violations)
