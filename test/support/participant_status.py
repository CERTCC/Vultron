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

"""Test-side participant RM arrange helper (ADR-0089 AC-2, issue #3207).

Production code advances a participant's RM state only through the sole writer,
:class:`~vultron.core.behaviors.case.nodes.participant.status.CreateParticipantStatusNode`.
The model no longer carries an ``append_rm_state`` mutator.  Tests that just
need to *arrange* a participant at a given RM state use ``advance_participant_rm``
below, which goes through the public, validated
:meth:`~vultron.core.models.case_participant.CaseParticipant.add_participant_status`
door (PRM-03-003) rather than mutating ``participant_statuses`` directly.

It reproduces the vendor/deployer carry-forward the old mutator performed
(#2264, #3134): an RM-only append must not silently rewind ``vf``/``d`` that the
role-dimension seeding validator would re-seed at their initial state.
"""

from __future__ import annotations

import logging

from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.dimensions import (
    DDimension,
    PecDimension,
    RmDimension,
    VfDimension,
)
from vultron.core.models.participant_status import (
    ParticipantStatus,
    coerce_cvd_roles,
    coerce_em_consent_state,
    participant_status_d_state,
    participant_status_vf_state,
)
from vultron.core.predicates.roles import has_deployer_role, has_vendor_role
from vultron.core.states.rm import RM, is_valid_rm_transition

logger = logging.getLogger(__name__)


def advance_participant_rm(
    participant: CaseParticipant, rm_state: RM, actor: str, context: str
) -> bool:
    """Append a ParticipantStatus at *rm_state*, carrying vf/d forward.

    Test-only stand-in for the retired ``CaseParticipant.append_rm_state``.
    Validates the RM transition against the state machine; on an invalid
    transition it logs a warning and returns ``False`` without appending
    (matching the old mutator's contract so arrange sites that asserted the
    boolean still hold).

    Args:
        participant: The participant to advance.
        rm_state: Target RM state.
        actor: URI of the actor asserting the transition.
        context: URI of the case context.

    Returns:
        ``True`` when a status was appended, ``False`` when the transition was
        blocked.
    """
    latest = participant.participant_status
    current = latest.rm.state if latest is not None else RM.START
    if not is_valid_rm_transition(current, rm_state):
        logger.warning(
            "Invalid RM transition %s → %s for participant %s; skipping",
            current,
            rm_state,
            participant.id_,
        )
        return False
    consent_state = coerce_em_consent_state(participant.embargo_consent_state)
    roles = coerce_cvd_roles(participant.case_roles)
    # Carry the vendor and deployer paths forward, but only while their role is
    # still held (ADR-0075) — omitting a dimension re-seeds it at its initial
    # state (#2264, #3134), which would silently rewind a vendor or deployer.
    current_vf = (
        participant_status_vf_state(latest)
        if latest is not None and has_vendor_role(roles)
        else None
    )
    current_d = (
        participant_status_d_state(latest)
        if latest is not None and has_deployer_role(roles)
        else None
    )
    participant.add_participant_status(
        ParticipantStatus(
            rm=RmDimension(state=rm_state),
            vf=(
                VfDimension(state=current_vf)
                if current_vf is not None
                else None
            ),
            d=DDimension(state=current_d) if current_d is not None else None,
            context=context,
            attributed_to=actor,
            consent=(
                PecDimension(state=consent_state)
                if consent_state is not None
                else None
            ),
            cvd_role=roles,
        )
    )
    return True
