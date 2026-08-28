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

Source: docs/topics/process_models/model_interactions/rm_em_cs.md
Spec: CSB-18-001 (emit path), CSB-18-002..004 (receive path, future)
Closes #2236.
"""

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
