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

Both RM and the vendor/deployer paths are per-actor attributes, so a
contradictory combination is an error at the source.  The RM↔fix rule is stated
per dimension — :func:`violation_rm_vf_entailment` and
:func:`violation_rm_d_entailment` — since ADR-0075 split the compound ``CS_vfd``
into independent ``CS_vf`` and ``CS_d`` dimensions.  A compound
``violation_rm_vfd_entailment`` existed alongside them until ISSUE-3016; it was a
second implementation of the same F-bit rule (ARCH-15-004) with no callers, and
callers holding a ``CS_vfd`` should split it via
:func:`~vultron.core.states.cs_invariants.cs_dimensions` and use the pair.

:func:`violation_pxa_em_entailment` expresses the PXA→EM consistency rules
but is NOT enforced on the emit path: asserting P CAUSES the embargo to
terminate (the embargo teardown is a consequence, not a prerequisite).  These
constraints belong on the receive path and are provided here for future use.

:func:`cross_machine_violations` composes the RM↔VF, RM↔D and VF↔D rules into
the single evaluator that *both* protocol paths use — the emit path via
:func:`~vultron.core.states.participant_transitions\
.participant_transition_violations`, which folds these rules in alongside the
per-dimension and role rules for both the trigger guard and the write node
(ADR-0086), and the receive path via
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
    D_FIX_DEPLOYED,
    PXA_ATTACKS_OBSERVED,
    PXA_EXPLOIT_PUBLIC,
    PXA_PUBLIC_AWARE,
    VF_FIX_READY,
)
from vultron.core.states.em import EM, EM_EMBARGO_ACTIVE
from vultron.core.states.rm import RM

# RM states consistent with asserting fix readiness or deployment.
#
# The underlying rule is a *history* property: the fix-ready event (F) can occur
# only in RM.ACCEPTED, so an actor carrying the F bit must have "passed through
# q^rm = Accepted at some point" (rm_em_cs.md § Fix Ready, § Fix Deployment).
# A ParticipantStatus carries only the *current* RM value, so this set is the
# tightest sound approximation available from it: exactly the states reachable
# from RM.ACCEPTED, i.e. those in which the history property *may* hold.
# `test_consistent_with_fix_is_the_post_acceptance_reachable_set` derives it from
# the RM transition graph so it cannot drift.
#
# It is deliberately sound-but-not-complete.  DEFERRED and CLOSED are each also
# reachable without ever visiting ACCEPTED (VALID→DEFERRED, INVALID→CLOSED), so
# neither *proves* acceptance — but excluding them would refuse the legitimate
# batched update in which a peer advances through ACCEPTED and reports fix
# readiness in one message, which the received path explicitly permits
# (CSB-16-001).  Narrowing to {ACCEPTED} is the only alternative that would be
# complete, and it would refuse far more real traffic than it caught.  Closing
# the gap properly needs the participant's RM *history*, not a better predicate
# over one snapshot; RSH-05-020's note records that.
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

    ``dimension`` is the *preferred* disqualified dimension, not merely a
    participant in the rule: RM↔VF names ``"vf"`` and both RM↔D and VF↔D name
    ``"d"``, because RM progress is the participant's own report-handling
    history and is never the claim these rules refuse.  The emit path refuses
    the whole snapshot and uses only the message.

    ``alternatives`` names the *other* dimensions whose claim could be refused
    to resolve the same contradiction, in descending preference.  Only VF↔D has
    one: it constrains a pair, so either side can be the offending claim.  The
    receive path refuses per dimension (RSH-05-001) and must refuse whichever
    side actually moved — refusing an incumbent value carries it straight back
    and resolves nothing — so it needs the full candidate list, not just the
    preferred name.  See
    ``vultron.core.behaviors.status.nodes._adjudication._refusal_target``.

    ``reads`` names *every* dimension the rule inspects, which is a different
    question from which one it refuses: RM↔VF reads ``("rm", "vf")`` but never
    refuses ``rm``.  The emit path classifies a violation as derived when a
    dimension it reads already carries a single-dimension violation
    (EH-07-002), so it needs the read set rather than the refusal candidates.
    """

    dimension: str
    message: str
    alternatives: tuple[str, ...] = ()
    reads: tuple[str, ...] = ()


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

    The order is stable, so the rules are always reported in the same
    sequence.  Note that reporting only ``violations[0]`` is *not* a licensed
    reduction: rejecting the whole write is a statement about what gets
    persisted, not about how much of the diagnosis the caller is owed
    (EH-07-001, ADR-0086).

    This function answers only "which rules does this combination violate".
    Deciding *which dimension to refuse* is the caller's, because the answer
    differs by path: the emit path refuses the whole snapshot, while the receive
    path must refuse the side that actually moved (see
    :class:`EntailmentViolation` on ``alternatives``).

    Args:
        rm: The RM state being asserted or recorded.
        vf: The vendor-path state, or ``None`` when the dimension is absent.
        d: The deployer-path state, or ``None`` when the dimension is absent.

    Returns:
        One :class:`EntailmentViolation` per violated rule, empty when the
        combination is consistent.  ``d`` is the preferred name for two of the
        three rules, so it can appear twice — by RM↔D and by VF↔D — when the
        combination violates both.
    """
    violations: list[EntailmentViolation] = []
    if vf is not None:
        if (msg := violation_rm_vf_entailment(rm, vf)) is not None:
            violations.append(
                EntailmentViolation("vf", msg, reads=("rm", "vf"))
            )
    if d is not None:
        if (msg := violation_rm_d_entailment(rm, d)) is not None:
            violations.append(EntailmentViolation("d", msg, reads=("rm", "d")))
    if (msg := violation_vf_d_entailment(vf, d)) is not None:
        # VF↔D constrains a pair: `d` is preferred (deployment is the dependent
        # claim), but refusing `vf` resolves the same contradiction when `vf` is
        # the side that moved.
        violations.append(
            EntailmentViolation(
                "d", msg, alternatives=("vf",), reads=("vf", "d")
            )
        )
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
