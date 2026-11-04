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


"""The six CS transition events and the CS compound-state dimensions.

Spec: `specs/cs-behavior.yaml` CSB-17.  Decision: ADR-0060.
"""

from enum import StrEnum

from vultron.core.states.cs import (
    CS,
    CS_d,
    CS_pxa,
    CS_vf,
    PXA_Trigger,
)


class CSEvent(StrEnum):
    """The six CS transition events, in canonical dimension order.

    Each event flips exactly one CS dimension from its not-yet-happened value
    to its happened value.  Events are irreversible and occur at most once in
    a case history.
    """

    V = "V"
    """Vendor becomes aware."""
    F = "F"
    """Fix becomes ready."""
    D = "D"
    """Fix is deployed."""
    P = "P"
    """Public becomes aware."""
    X = "X"
    """Exploit is made public."""
    A = "A"
    """Attacks are observed."""


CS_EVENTS: tuple[CSEvent, ...] = tuple(CSEvent)
"""All six CS events in canonical (`VFDPXA`) order."""

VFD_EVENTS: frozenset[CSEvent] = frozenset({CSEvent.V, CSEvent.F, CSEvent.D})
"""The CS events belonging to the vendor fix path (VFD) dimension."""

PXA_EVENTS: frozenset[CSEvent] = frozenset({CSEvent.P, CSEvent.X, CSEvent.A})
"""The CS events belonging to the public/exploit/attack (PXA) dimension."""

CS_EVENT_TO_PXA_TRIGGER: dict[CSEvent, PXA_Trigger] = {
    CSEvent.P: PXA_Trigger.P,
    CSEvent.X: PXA_Trigger.X,
    CSEvent.A: PXA_Trigger.A,
}
"""Maps each PXA-dimension CS event to the `PxaDimension.transition()` trigger."""


def cs_dimensions(state: CS) -> tuple[CS_vf, CS_d, CS_pxa]:
    """Return the (VF, D, PXA) dimension states of a compound CS state.

    Examples::

        cs_dimensions(CS.vfdpxa)  # (CS_vf.vf, CS_d.d, CS_pxa.pxa)
        cs_dimensions(CS.VFdPXa)  # (CS_vf.VF, CS_d.d, CS_pxa.PXa)
    """
    compound = state.value
    return compound.vf_state, compound.d_state, compound.pxa_state


def cs_from_dimensions(
    vf_state: CS_vf, d_state: CS_d, pxa_state: CS_pxa
) -> CS:
    """Return the compound `CS` member for a (VF, D, PXA) dimension triple.

    Every one of the 3 x 2 x 8 = 48 combinations is not necessarily valid;
    only the 32 structurally possible members of `CS` can be returned.

    Examples::

        cs_from_dimensions(CS_vf.VF, CS_d.d, CS_pxa.Pxa)  # CS.VFdPxa
    """
    return CS[f"{vf_state.name}{d_state.name}{pxa_state.name}"]
