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
from vultron.core.states.cs import (
    is_monotonic_d_forward,
    is_monotonic_pxa_forward,
    is_monotonic_vf_forward,
)
from vultron.core.states.rm import (
    RM,
    is_monotonic_rm_forward,
    is_valid_rm_transition,
)


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


def _adjudicate_dimensions(
    current: ParticipantStatus, asserted: ParticipantStatus
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
    """
    refused: list[str] = []
    update_fields: dict[str, Any] = {}

    if not _rm_is_acceptable(current.rm.state, asserted.rm.state):
        refused.append("rm")
        update_fields["rm"] = RmDimension(state=current.rm.state)

    # VF dimension (vendor-path: vendor awareness + fix readiness).
    # Intentionally uses the weaker monotone check rather than strict adjacency:
    # a remote peer may have advanced through multiple steps between messages.
    # An omitted vf (None) carries forward the current value — absence is not
    # an assertion that the dimension is unknown (RSH-05-002).
    current_vf = current.vf.state if current.vf is not None else None
    asserted_vf = asserted.vf.state if asserted.vf is not None else None
    if asserted_vf is None and current_vf is not None:
        update_fields["vf"] = VfDimension(state=current_vf)
    elif (
        current_vf is not None
        and asserted_vf is not None
        and asserted_vf != current_vf
        and not is_monotonic_vf_forward(current_vf, asserted_vf)
    ):
        refused.append("vf")
        update_fields["vf"] = VfDimension(state=current_vf)

    # D dimension (deployer-path: fix deployment).
    # Same omission semantics as vf (RSH-05-002).
    current_d = current.d.state if current.d is not None else None
    asserted_d = asserted.d.state if asserted.d is not None else None
    if asserted_d is None and current_d is not None:
        update_fields["d"] = DDimension(state=current_d)
    elif (
        current_d is not None
        and asserted_d is not None
        and asserted_d != current_d
        and not is_monotonic_d_forward(current_d, asserted_d)
    ):
        refused.append("d")
        update_fields["d"] = DDimension(state=current_d)

    asserted_cs = asserted.case_status
    current_cs = current.case_status
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

    return refused, update_fields
