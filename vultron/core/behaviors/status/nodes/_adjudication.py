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

from typing import Any

from vultron.core.models.dimensions import (
    DDimension,
    PxaDimension,
    RmDimension,
    VfDimension,
)
from vultron.core.models.participant_status import ParticipantStatus
from vultron.core.states.cross_machine_invariants import (
    violation_vf_d_entailment,
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


def _adjudicate_vf(
    current_vf: CS_vf | None,
    asserted_vf: CS_vf | None,
    roles: list[CVDRole] | None,
) -> tuple[bool, VfDimension | None]:
    """Return (refused, carry) for the VF dimension.

    Refuses if the sender lacks VENDOR role or the transition is not monotone
    forward.  ``carry`` is the dimension value to write back (``None`` means
    clear the dimension; used when refused with no prior history).
    """
    if (
        asserted_vf is not None
        and roles is not None
        and CVDRole.VENDOR not in roles
    ):
        carry = (
            VfDimension(state=current_vf) if current_vf is not None else None
        )
        return True, carry
    if asserted_vf is None and current_vf is not None:
        return False, VfDimension(state=current_vf)
    if (
        current_vf is not None
        and asserted_vf is not None
        and asserted_vf != current_vf
        and not is_monotonic_vf_forward(current_vf, asserted_vf)
    ):
        return True, VfDimension(state=current_vf)
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
    """
    if (
        asserted_d is not None
        and roles is not None
        and CVDRole.DEPLOYER not in roles
    ):
        carry = DDimension(state=current_d) if current_d is not None else None
        return True, carry
    if asserted_d is None and current_d is not None:
        return False, DDimension(state=current_d)
    if (
        current_d is not None
        and asserted_d is not None
        and asserted_d != current_d
        and not is_monotonic_d_forward(current_d, asserted_d)
    ):
        return True, DDimension(state=current_d)
    return False, None


def _adjudicate_case_status(
    current_cs: Any,
    asserted_cs: Any,
    refused: list[str],
    update_fields: dict[str, Any],
) -> None:
    """Adjudicate the ``case_status`` (pxa) dimension in-place."""
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

    # Cross-dimension VF↔D check (CSB-17-001, #2893 received path).
    # After individual dimension adjudication, verify the effective VF+D
    # combination is not the structurally impossible *fD* state.
    if not d_refused:
        if "vf" in update_fields:
            vf_in_fields = update_fields["vf"]
            effective_vf = (
                vf_in_fields.state
                if isinstance(vf_in_fields, VfDimension)
                else None
            )
        else:
            effective_vf = asserted_vf
        d_in_fields = update_fields.get("d")
        effective_d = (
            d_in_fields.state
            if isinstance(d_in_fields, DDimension)
            else asserted_d
        )
        if violation_vf_d_entailment(effective_vf, effective_d) is not None:
            refused.append("d")
            update_fields["d"] = (
                DDimension(state=current_d) if current_d is not None else None
            )

    _adjudicate_case_status(
        current.case_status, asserted.case_status, refused, update_fields
    )

    return refused, update_fields
