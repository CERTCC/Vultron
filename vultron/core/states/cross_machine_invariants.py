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

"""Cross-machine entailment invariants for the Vultron composite state.

Validates that combinations of RM, VFD, and EM states are mutually consistent.

:func:`violation_rm_vfd_entailment` is enforced at emit time via
:class:`~vultron.core.behaviors.case.nodes.participant.trigger_validation\
.ValidateTriggerTransitionsNode` in the trigger path.  Both RM and VFD are
per-actor attributes, so a contradictory combination is an error at the source.

:func:`violation_pxa_em_entailment` expresses the PXA→EM consistency rules
but is NOT enforced on the emit path: asserting P CAUSES the embargo to
terminate (the embargo teardown is a consequence, not a prerequisite).  These
constraints belong on the receive path and are provided here for future use.

:func:`cross_machine_violations` composes the RM↔VF, RM↔D and VF↔D rules into
the single evaluator that *both* protocol paths use — the emit path via
:class:`~vultron.core.behaviors.case.nodes.participant.trigger_validation\
.ValidateTriggerTransitionsNode` and the receive path via
``vultron.core.behaviors.status.nodes._adjudication``.  Before #2906 the
receive path composed only VF↔D by hand, so a peer could have an impossible
RM/VF pair recorded as canonical that the same actor would have refused to
emit.  Composing once is what keeps the two from drifting apart again
(RSH-05-020).

Source: docs/topics/process_models/model_interactions/rm_em_cs.md
Spec: CSB-18-001 (emit and receive paths), CSB-18-002..004 (receive path, future)
Closes #2236.
"""

from typing import NamedTuple

from vultron.core.states.cs import (
    CS_d,
    CS_pxa,
    CS_vf,
    CS_vfd,
    D_FIX_DEPLOYED,
    PXA_ATTACKS_OBSERVED,
    PXA_EXPLOIT_PUBLIC,
    PXA_PUBLIC_AWARE,
    VF_FIX_READY,
    VFD_FIX_READY,
)
from vultron.core.states.em import EM, EM_EMBARGO_ACTIVE
from vultron.core.states.rm import RM

# RM states consistent with asserting fix readiness or deployment.
# The fix-ready event (F) can occur only when the vendor has passed through
# RM.ACCEPTED; since RM is monotonic, DEFERRED and CLOSED are also consistent
# with F having been reached.
# Source: rm_em_cs.md § "Fix Readiness", § "Fix Deployment"
RM_STATES_CONSISTENT_WITH_FIX: frozenset[RM] = frozenset(
    {RM.ACCEPTED, RM.DEFERRED, RM.CLOSED}
)


def violation_rm_vf_entailment(rm: RM, vf: CS_vf) -> str | None:
    """Return an error string if (rm, vf) violates the fix-readiness entailment.

    Fix readiness (F bit set: CS_vf.VF) can only be asserted when the vendor
    has accepted the report (RM ∈ {ACCEPTED, DEFERRED, CLOSED}).

    Returns:
        None when the combination is valid.
        A descriptive error string when the entailment is violated.

    Source: rm_em_cs.md § "Fix Readiness"
    Spec: CSB-18-001
    """
    if vf not in VF_FIX_READY:
        return None
    if rm in RM_STATES_CONSISTENT_WITH_FIX:
        return None
    return (
        f"Cross-machine entailment violated: VF={vf.name!r} (F bit set)"
        f" requires RM ∈ {{ACCEPTED, DEFERRED, CLOSED}},"
        f" but RM={rm.name!r}."
        " Fix readiness cannot precede RM.ACCEPTED"
        " (rm_em_cs.md § Fix Readiness)."
    )


def violation_rm_d_entailment(rm: RM, d: CS_d) -> str | None:
    """Return an error string if (rm, d) violates the fix-deployment entailment.

    Fix deployment (D bit set: CS_d.D) implies fix readiness, which requires
    RM ∈ {ACCEPTED, DEFERRED, CLOSED}.

    Returns:
        None when the combination is valid.
        A descriptive error string when the entailment is violated.

    Source: rm_em_cs.md § "Fix Deployment"
    Spec: CSB-18-001
    """
    if d not in D_FIX_DEPLOYED:
        return None
    if rm in RM_STATES_CONSISTENT_WITH_FIX:
        return None
    return (
        f"Cross-machine entailment violated: D={d.name!r} (D bit set)"
        f" requires RM ∈ {{ACCEPTED, DEFERRED, CLOSED}},"
        f" but RM={rm.name!r}."
        " Fix deployment cannot precede RM.ACCEPTED"
        " (rm_em_cs.md § Fix Deployment)."
    )


def violation_rm_vfd_entailment(rm: RM, vfd: CS_vfd) -> str | None:
    """Return an error string if (rm, vfd) violates the Fix Readiness entailment.

    Fix readiness (F bit set: CS_vfd.VFd or CS_vfd.VFD) can only be asserted
    when the vendor has accepted the report (RM ∈ {ACCEPTED, DEFERRED, CLOSED}).
    RM is monotonic, so once ACCEPTED the vendor may later be at DEFERRED or
    CLOSED; all three are consistent with the F/D bits being set.

    Returns:
        None when the combination is valid.
        A descriptive error string when the entailment is violated.

    Source: rm_em_cs.md § "Fix Readiness", § "Fix Deployment"
    Spec: CSB-18-001
    """
    if vfd not in VFD_FIX_READY:
        return None  # F bit not set — no RM constraint from this rule
    if rm in RM_STATES_CONSISTENT_WITH_FIX:
        return None
    return (
        f"Cross-machine entailment violated: VFD={vfd.name!r} (F bit set)"
        f" requires RM ∈ {{ACCEPTED, DEFERRED, CLOSED}},"
        f" but RM={rm.name!r}."
        " Fix readiness cannot precede RM.ACCEPTED"
        " (rm_em_cs.md § Fix Readiness)."
    )


def violation_vf_d_entailment(vf: CS_vf | None, d: CS_d | None) -> str | None:
    """Return an error string if (vf, d) violates the fix-deployment entailment.

    Fix deployment (d=D) requires fix readiness (vf=VF).  The compound state
    ``*fD*`` (deployed without ready) is structurally impossible per CSB-17-001.
    When vf is None the check cannot be applied (no VF information available).

    Returns:
        None when the combination is valid or insufficient information exists.
        A descriptive error string when the entailment is violated.

    Source: docs/reference/glossary.md § Case State Model (Six Dimensions)
    Spec: CSB-17-001
    """
    if d not in D_FIX_DEPLOYED:
        return None
    assert (
        d is not None
    )  # D_FIX_DEPLOYED contains only CS_d members, never None
    if vf is None:
        return None
    if vf in VF_FIX_READY:
        return None
    return (
        f"Cross-machine entailment violated: D={d.name!r} (fix deployed)"
        f" requires VF={CS_vf.VF.name!r} (fix ready),"
        f" but VF={vf.name!r} (fix not ready)."
        " Fix deployment cannot precede fix readiness (CSB-17-001)."
    )


class EntailmentViolation(NamedTuple):
    """A violated cross-machine entailment and the dimension it disqualifies.

    ``dimension`` is the *disqualified* dimension, not merely a participant in
    the rule: RM↔VF names ``"vf"`` and both RM↔D and VF↔D name ``"d"``, because
    RM progress is the participant's own report-handling history and is never
    the claim these rules refuse.  The receive path refuses per dimension
    (RSH-05-001), so it needs the name; the emit path refuses the whole
    snapshot and uses only the message.
    """

    dimension: str
    message: str


def cross_machine_violations(
    rm: RM, vf: CS_vf | None, d: CS_d | None
) -> list[EntailmentViolation]:
    """Return every cross-machine entailment violated by ``(rm, vf, d)``.

    Composes the three participant-state entailments in one place so the emit
    and receive paths cannot enforce different subsets of them (#2906):

    * RM↔VF (CSB-18-001) — a fix cannot be *ready* before the report is accepted.
    * RM↔D (CSB-18-001) — a fix cannot be *deployed* before the report is accepted.
    * VF↔D (CSB-17-001) — a fix cannot be deployed before it is ready.

    A ``None`` dimension is *absent*, not at its initial state: a non-VENDOR
    participant has no vendor path and a non-DEPLOYER participant has no
    deployer path (ADR-0075).  An absent dimension asserts nothing, so no rule
    can be violated through it.

    The order is stable and matches the order the emit path enforced before
    the checks were consolidated, so a caller that reports only the first
    violation reports the same one it always did.

    Args:
        rm: The RM state being asserted or recorded.
        vf: The vendor-path state, or ``None`` when the dimension is absent.
        d: The deployer-path state, or ``None`` when the dimension is absent.

    Returns:
        One :class:`EntailmentViolation` per violated rule, empty when the
        combination is consistent.  ``d`` can be named twice — by RM↔D and by
        VF↔D — when it violates both.
    """
    violations: list[EntailmentViolation] = []
    if vf is not None:
        if (msg := violation_rm_vf_entailment(rm, vf)) is not None:
            violations.append(EntailmentViolation("vf", msg))
    if d is not None:
        if (msg := violation_rm_d_entailment(rm, d)) is not None:
            violations.append(EntailmentViolation("d", msg))
    if (msg := violation_vf_d_entailment(vf, d)) is not None:
        violations.append(EntailmentViolation("d", msg))
    return violations


def violation_pxa_em_entailment(pxa: CS_pxa, em: EM) -> str | None:
    """Return an error string if (pxa, em) violates the disclosure/embargo entailment.

    Public awareness (P), exploit publication (X), or attack observations (A)
    are logically inconsistent with an active embargo (EM.ACTIVE or EM.REVISE).

    Returns:
        None when the combination is valid.
        A descriptive error string when the entailment is violated.

    Source: rm_em_cs.md § "Public Awareness", § "Exploit Public", § "Attacks Observed"
    Spec: CSB-18-002, CSB-18-003, CSB-18-004
    """
    if em not in EM_EMBARGO_ACTIVE:
        return None  # no active embargo — all PXA values are consistent
    if pxa in PXA_PUBLIC_AWARE:
        return (
            f"Cross-machine entailment violated: PXA={pxa.name!r} (P bit set)"
            f" is incompatible with EM={em.name!r}."
            " An active embargo cannot coexist with public awareness"
            " (rm_em_cs.md § Public Awareness)."
        )
    if pxa in PXA_EXPLOIT_PUBLIC:
        return (
            f"Cross-machine entailment violated: PXA={pxa.name!r} (X bit set)"
            f" is incompatible with EM={em.name!r}."
            " An active embargo cannot coexist with exploit publication"
            " (rm_em_cs.md § Exploit Public)."
        )
    if pxa in PXA_ATTACKS_OBSERVED:
        return (
            f"Cross-machine entailment violated: PXA={pxa.name!r} (A bit set)"
            f" is incompatible with EM={em.name!r}."
            " An active embargo cannot coexist with observed attacks"
            " (rm_em_cs.md § Attacks Observed)."
        )
    return None
