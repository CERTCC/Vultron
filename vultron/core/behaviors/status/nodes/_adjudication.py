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

"""Per-dimension adjudication helpers for received ParticipantStatus.

Extracted from ``dimension_filter`` to keep that module under the 500-line
BTND-07-004 limit.  All public names are re-exported from ``dimension_filter``
and should be imported from there, not from this module directly.
"""

import logging
from typing import Any, TypeVar

from vultron.core.models.dimensions import (
    DDimension,
    PxaDimension,
    RmDimension,
    VfDimension,
)
from vultron.core.models.participant_status import ParticipantStatus
from vultron.core.states.cross_machine_invariants import (
    EntailmentViolation,
    cross_machine_violations,
)
from vultron.core.states.cs import (
    CS_d,
    CS_vf,
    is_monotonic_d_forward,
    is_monotonic_pxa_forward,
    is_monotonic_vf_forward,
)
from vultron.core.states.rm import (
    RM,
    is_monotonic_rm_forward,
    is_valid_rm_transition,
)
from vultron.enums.roles import CVDRole

logger = logging.getLogger(__name__)

# `vf` and `d` are the only dimensions the cross-machine entailment pass can
# refuse, which bounds how many rounds it can need (see
# `_adjudicate_cross_machine_entailments`).
_REFUSABLE_DIMENSIONS = 2

# The two per-dimension state types `_effective_state` reads.  A value-restricted
# TypeVar keeps the return type tied to the dimension asked for, so callers get
# `CS_vf | None` or `CS_d | None` rather than a union of both (CS-11-001).
_DimState = TypeVar("_DimState", CS_vf, CS_d)


def _rm_is_acceptable(current: RM, asserted: RM) -> bool:
    """Return True if *asserted* is an acceptable RM value given *current*.

    ``RM.CLOSED`` is terminal (DEMOMA-07-003): once a participant has closed,
    no further RM value — not even ``CLOSED`` again — is acceptable.  Otherwise
    a status confirmation (no change), a valid adjacent transition, or a
    non-adjacent but monotone forward jump are all acceptable; the sender is
    authoritative about its own RM progress.
    """
    if current == RM.CLOSED:
        return False
    if asserted == current:
        return True
    return is_valid_rm_transition(
        current, asserted
    ) or is_monotonic_rm_forward(current, asserted)


def _vf_carry(current_vf: CS_vf | None) -> VfDimension | None:
    """Return the VF value to write back, or ``None`` to clear the dimension.

    The single ``VfDimension`` construction site in this module: every carry —
    role refusal, omitted assertion, non-monotone refusal, entailment refusal —
    means the same thing, so it is spelled once (ARCH-15-004).  ``None`` is
    returned when the participant has no VF history to carry (RSH-05-002).
    """
    return VfDimension(state=current_vf) if current_vf is not None else None


def _d_carry(current_d: CS_d | None) -> DDimension | None:
    """Return the D value to write back, or ``None`` to clear the dimension.

    The single ``DDimension`` construction site in this module; see
    :func:`_vf_carry`.
    """
    return DDimension(state=current_d) if current_d is not None else None


def _adjudicate_vf(
    current_vf: CS_vf | None,
    asserted_vf: CS_vf | None,
    roles: list[CVDRole] | None,
) -> tuple[bool, VfDimension | None]:
    """Return (refused, carry) for the VF dimension.

    Refuses if the sender lacks VENDOR role or the transition is not monotone
    forward.  ``carry`` is the dimension value to write back (``None`` means
    clear the dimension; used when refused with no prior history).

    ``current_vf is None`` is a **first observation**, and it is accepted as
    asserted.  Two things make that the right answer rather than an unchecked
    gap: absence is structural — a participant with no vendor path has no
    baseline to advance *from*, not a baseline of ``CS_vf.vf`` (ADR-0075) — and
    even reading it as ``CS_vf.vf`` would refuse nothing, because every value
    is a monotone advance on the bottom of the ladder.  Non-adjacent forward
    jumps are deliberately legal here: a peer may have advanced several steps
    between status messages, and strict adjacency belongs to local write nodes
    only (CSB-16-001).  What *does* constrain a first observation is the
    cross-machine entailment pass in
    :func:`_adjudicate_cross_machine_entailments` — a ready fix still requires
    an accepted report (#2906).
    """
    if (
        asserted_vf is not None
        and roles is not None
        and CVDRole.VENDOR not in roles
    ):
        return True, _vf_carry(current_vf)
    if asserted_vf is None and current_vf is not None:
        return False, _vf_carry(current_vf)
    if (
        current_vf is not None
        and asserted_vf is not None
        and asserted_vf != current_vf
        and not is_monotonic_vf_forward(current_vf, asserted_vf)
    ):
        return True, _vf_carry(current_vf)
    return False, None


def _adjudicate_d(
    current_d: CS_d | None,
    asserted_d: CS_d | None,
    roles: list[CVDRole] | None,
) -> tuple[bool, DDimension | None]:
    """Return (refused, carry) for the D dimension.

    Refuses if the sender lacks DEPLOYER role or the transition is not monotone
    forward.  ``carry`` is the dimension value to write back (``None`` means
    clear the dimension; used when refused with no prior history).

    ``current_d is None`` is a first observation and is accepted as asserted,
    for the reasons given in :func:`_adjudicate_vf`; the entailment pass is
    what refuses a deployment the participant's RM or VF state cannot support.
    """
    if (
        asserted_d is not None
        and roles is not None
        and CVDRole.DEPLOYER not in roles
    ):
        return True, _d_carry(current_d)
    if asserted_d is None and current_d is not None:
        return False, _d_carry(current_d)
    if (
        current_d is not None
        and asserted_d is not None
        and asserted_d != current_d
        and not is_monotonic_d_forward(current_d, asserted_d)
    ):
        return True, _d_carry(current_d)
    return False, None


def _effective_state(
    update_fields: dict[str, Any],
    dimension: str,
    asserted_state: _DimState | None,
) -> _DimState | None:
    """Return the state that *will be recorded* for *dimension*.

    A dimension named in *update_fields* was adjudicated, and its carry value
    is what gets recorded — including when that value is ``None``, which
    clears the dimension because there was no prior history to fall back to.
    Membership is therefore the test, not truthiness: ``update_fields[dim]``
    is ``None`` both for "refused, no history" and for "never adjudicated",
    and those two mean opposite things (ISSUE-2893).

    A dimension nobody adjudicated records the sender's assertion unchanged.
    """
    if dimension not in update_fields:
        return asserted_state
    carry = update_fields[dimension]
    return None if carry is None else carry.state


def _asserts_new_value(
    dimension: str,
    current_vf: CS_vf | None,
    current_d: CS_d | None,
    asserted_vf: CS_vf | None,
    asserted_d: CS_d | None,
) -> bool:
    """Return True if the sender made a *new* claim about *dimension*.

    A dimension the sender omitted, or restated at the value the receiver
    already holds, is not a claim this receiver can refuse: carrying the current
    value forward would write back the value that is already there.  Only a
    moved dimension is refusable.
    """
    if dimension == "vf":
        return asserted_vf is not None and asserted_vf != current_vf
    return asserted_d is not None and asserted_d != current_d


def _refusal_target(
    violation: EntailmentViolation,
    refused: list[str],
    current_vf: CS_vf | None,
    current_d: CS_d | None,
    asserted_vf: CS_vf | None,
    asserted_d: CS_d | None,
) -> str | None:
    """Return the dimension to refuse for *violation*, or ``None`` for neither.

    Walks the violation's candidates in preference order and picks the first one
    that is both still un-refused and carrying a *new* claim.  Two rejections
    matter:

    * **Already refused.** That dimension has been carried forward once; naming
      it again cannot change the recorded value, and would name it twice in the
      audit trail.  Try the next candidate rather than giving up — for VF↔D the
      other side may still be refusable.
    * **Not a new claim.** Refusing an incumbent value carries it straight back,
      so the refusal would be a no-op that misreports the audit trail as a
      rewrite (see ``notes/received-status-authorization.md`` § "A blocked
      dimension is not always a rewritten one").

    ``None`` therefore means the contradiction lives entirely in the state the
    receiver already holds, which no per-dimension refusal on this path can
    repair — see :func:`_adjudicate_cross_machine_entailments`.
    """
    for candidate in (violation.dimension, *violation.alternatives):
        if candidate in refused:
            continue
        if _asserts_new_value(
            candidate, current_vf, current_d, asserted_vf, asserted_d
        ):
            return candidate
    return None


def _carry_current_dimension(
    dimension: str, current_vf: CS_vf | None, current_d: CS_d | None
) -> VfDimension | DDimension | None:
    """Return the carry-forward value for a refused *dimension*, by name.

    Dispatches to :func:`_vf_carry` / :func:`_d_carry` so the entailment pass,
    which learns which dimension to refuse only at runtime, shares their
    construction sites rather than repeating them.
    """
    if dimension == "vf":
        return _vf_carry(current_vf)
    return _d_carry(current_d)


def _adjudicate_cross_machine_entailments(
    current: ParticipantStatus,
    asserted: ParticipantStatus,
    refused: list[str],
    update_fields: dict[str, Any],
    current_vf: CS_vf | None,
    current_d: CS_d | None,
    asserted_vf: CS_vf | None,
    asserted_d: CS_d | None,
) -> None:
    """Refuse in-place any *newly claimed* dimension the effective state makes
    impossible.

    Runs after the per-dimension role and monotonicity checks, against the state
    that would actually be recorded, so a refused or carried-forward ``vf``
    cannot license the ``d`` the sender paired it with (ISSUE-2893).  ``rm`` is
    read from its effective value too, for consistency, but note that this can
    only ever *loosen*: ``rm`` is refused only when the asserted value is not a
    forward move, so the carried value ranks at or above the asserted one on the
    RM progress scale, and ``RM_STATES_CONSISTENT_WITH_FIX`` is exactly the top
    of that scale.  There is no reachable case in which a refused ``rm`` would
    have licensed a ``vf`` that the asserted ``rm`` refuses.

    These are the same rules the emit path enforces in
    :class:`~vultron.core.behaviors.case.nodes.participant.trigger_validation\
    .ValidateTriggerTransitionsNode`, composed by the shared
    :func:`~vultron.core.states.cross_machine_invariants\
    .cross_machine_violations` (CSB-17-001, CSB-18-001, RSH-05-020).  Where the
    emit path refuses the whole trigger, the receive path refuses only the
    disqualified dimension and carries the participant's current value forward
    (RSH-05-001, RSH-05-002).

    **Which dimension gets refused matters.** VF↔D constrains a pair, so the
    offending claim is whichever side *moved*; refusing the incumbent side
    carries its value straight back and leaves the contradiction recorded.
    :func:`_refusal_target` makes that choice, which is why the shared evaluator
    reports candidate dimensions rather than a single name.

    **Why it re-evaluates rather than refusing every violation in one sweep.**
    A refusal changes the effective state, which can retire a violation the
    first evaluation reported: refusing ``d`` for RM↔D clears or lowers the D
    bit, so a VF↔D violation computed alongside it no longer holds.  Acting on
    that stale violation would refuse ``vf`` for a contradiction that no longer
    exists.  Each round therefore recomputes from the current carries and
    refuses at most one dimension.  ``vf`` and ``d`` are the only refusable
    dimensions and :func:`_refusal_target` never re-refuses one, so the loop
    makes progress every round and terminates.

    **What this pass guarantees:** if the participant's current state satisfies
    the entailments, so does the recorded state.  It cannot promise more.  When
    the *incumbent* state is already impossible — reachable today because the
    replica-apply path enforces only the RM ratchet (RSH-05-007, ISSUE-3009) —
    no per-dimension refusal can repair it, since every carry-forward writes the
    offending value straight back.  That case is logged and left alone rather
    than reported as the refusal of a claim the sender never made.
    """
    for _ in range(_REFUSABLE_DIMENSIONS + 1):
        effective_rm = (
            current.rm.state if "rm" in update_fields else asserted.rm.state
        )
        effective_vf = _effective_state(update_fields, "vf", asserted_vf)
        effective_d = _effective_state(update_fields, "d", asserted_d)
        violations = cross_machine_violations(
            effective_rm, effective_vf, effective_d
        )
        if not violations:
            return

        target: str | None = None
        for violation in violations:
            target = _refusal_target(
                violation,
                refused,
                current_vf,
                current_d,
                asserted_vf,
                asserted_d,
            )
            if target is not None:
                break

        if target is None:
            logger.warning(
                "Received ParticipantStatus '%s' would record an impossible"
                " state the receiver already holds (rm=%s, vf=%s, d=%s): %s"
                " — no dimension of this assertion can be refused to repair it"
                " (RSH-05-020, ISSUE-3009)",
                asserted.id_,
                effective_rm.name,
                effective_vf.name if effective_vf is not None else None,
                effective_d.name if effective_d is not None else None,
                violations[0].message,
            )
            return

        refused.append(target)
        update_fields[target] = _carry_current_dimension(
            target, current_vf, current_d
        )
        logger.warning(
            "Refusing '%s' dimension of received ParticipantStatus '%s':"
            " %s — carrying the current value forward (RSH-05-020)",
            target,
            asserted.id_,
            violation.message,
        )


def _adjudicate_case_status(
    current_cs: Any,
    asserted_cs: Any,
    refused: list[str],
    update_fields: dict[str, Any],
) -> None:
    """Adjudicate the ``case_status`` (pxa) dimension in-place.

    A first observation — the receiver holds no ``case_status`` at all — is
    accepted as asserted.  There is no prior PXA value to regress from, and
    every value is a monotone advance on the all-lowercase baseline, so a
    monotonicity check could not refuse one anyway.
    """
    if asserted_cs is None and current_cs is not None:
        # Nothing asserted about pxa/em — carry the receiver's own view
        # forward.  Persisting the assertion as-is would blank both.
        update_fields["case_status"] = current_cs.model_copy(deep=True)
    elif asserted_cs is not None and current_cs is not None:
        current_pxa = current_cs.pxa.state
        asserted_pxa = asserted_cs.pxa.state
        if asserted_pxa != current_pxa and not is_monotonic_pxa_forward(
            current_pxa, asserted_pxa
        ):
            refused.append("pxa")
            update_fields["case_status"] = asserted_cs.model_copy(
                update={"pxa": PxaDimension(state=current_pxa)}
            )


def _adjudicate_dimensions(
    current: ParticipantStatus,
    asserted: ParticipantStatus,
    roles: list[CVDRole] | None = None,
) -> tuple[list[str], dict[str, Any]]:
    """Adjudicate ``rm``, ``vf``, ``d`` and ``pxa`` independently.

    Returns the names of the refused dimensions and the ``model_copy`` update
    that carries the current value forward for each of them.  ``em``,
    ``consent``, ``case_engagement``, ``embargo_adherence``, ``cvd_role`` and
    ``tracking_id`` are not adjudicated here — ``em`` in particular belongs to
    EmbargoTeardownAuthorizationGate (ADR-0046, ISSUE-2256).

    The two return values are deliberately not the same set.  ``refused`` names
    the dimensions whose *asserted* value was rejected; ``update_fields`` also
    carries dimensions the sender said nothing about, which must be preserved
    rather than dropped.  An inbound status with no ``case_status`` at all is
    the common case: it asserts nothing about ``pxa``/``em``, so the
    participant's current ``case_status`` is carried forward instead of letting
    the omission erase state the receiver already holds (RSH-05-002).

    When ``roles`` is provided, VF writes require ``CVDRole.VENDOR`` and D
    writes require ``CVDRole.DEPLOYER`` (ADR-0075, #2965).

    Independent adjudication cannot see a claim that is impossible only in
    combination, so a final pass evaluates the cross-machine entailments
    against the effective — post-adjudication — state and refuses whichever
    dimension they disqualify (RSH-05-020, #2906).
    """
    refused: list[str] = []
    update_fields: dict[str, Any] = {}

    if not _rm_is_acceptable(current.rm.state, asserted.rm.state):
        refused.append("rm")
        update_fields["rm"] = RmDimension(state=current.rm.state)

    current_vf = current.vf.state if current.vf is not None else None
    asserted_vf = asserted.vf.state if asserted.vf is not None else None
    vf_refused, vf_carry = _adjudicate_vf(current_vf, asserted_vf, roles)
    if vf_refused:
        refused.append("vf")
        update_fields["vf"] = (
            vf_carry  # None clears field when no prior history
        )
    elif vf_carry is not None:
        update_fields["vf"] = vf_carry  # Carry forward omitted dimension value

    current_d = current.d.state if current.d is not None else None
    asserted_d = asserted.d.state if asserted.d is not None else None
    d_refused, d_carry = _adjudicate_d(current_d, asserted_d, roles)
    if d_refused:
        refused.append("d")
        update_fields["d"] = d_carry  # None clears field when no prior history
    elif d_carry is not None:
        update_fields["d"] = d_carry  # Carry forward omitted dimension value

    # Cross-machine entailments on the effective state (CSB-17-001, CSB-18-001,
    # RSH-05-020, #2906): a claim can be individually well-formed in every
    # dimension and still describe a state no sequence of events could produce.
    _adjudicate_cross_machine_entailments(
        current,
        asserted,
        refused,
        update_fields,
        current_vf,
        current_d,
        asserted_vf,
        asserted_d,
    )

    _adjudicate_case_status(
        current.case_status, asserted.case_status, refused, update_fields
    )

    return refused, update_fields
