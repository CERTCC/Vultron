#!/usr/bin/env python
"""This module defines the Embargo Management states for the Vultron protocol.

EM has no transition table of its own: a case's EM state is derived from its
embargo register (ADR-0122,
:func:`vultron.core.states.embargo_register.derive_em`).
"""

#  Copyright (c) 2023-2025 Carnegie Mellon University and Contributors.
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

from enum import StrEnum


class EM(StrEnum):
    """Embargo Management States

    NONE: No embargo is in effect
    PROPOSED: Embargo is proposed but not yet active
    ACTIVE: Embargo is active
    REVISE: Embargo is active and a revision is proposed
    EXITED: Embargo had been active but has been exited
    """

    NONE = "NONE"
    PROPOSED = "PROPOSED"
    ACTIVE = "ACTIVE"
    REVISE = "REVISE"
    EXITED = "EXITED"

    # convenience aliases
    EMBARGO_MANAGEMENT_NONE = NONE
    EMBARGO_MANAGEMENT_PROPOSED = PROPOSED
    EMBARGO_MANAGEMENT_ACTIVE = ACTIVE
    EMBARGO_MANAGEMENT_REVISE = REVISE
    EMBARGO_MANAGEMENT_EXITED = EXITED

    N = NONE
    P = PROPOSED
    A = ACTIVE
    R = REVISE
    X = EXITED


# Named EM state subsets (SM-07-001 style convenience constants)
# Example: EM_NEGOTIATING groups states where embargo negotiation is ongoing
EM_NEGOTIATING = (EM.PROPOSED, EM.REVISE)

# States where an embargo is currently in force.
# Once an entry is ACTIVE the register never returns EM to NONE/PROPOSED.
EM_EMBARGO_ACTIVE = (EM.ACTIVE, EM.REVISE)


def is_em_embargo_active(state: EM) -> bool:
    """Return True if an embargo is currently in force (ACTIVE or REVISE).

    The REVISE state retains the active embargo while a revision is negotiated;
    the embargo remains in force until EXITED.

    Examples::

        is_em_embargo_active(EM.ACTIVE)   # True
        is_em_embargo_active(EM.REVISE)   # True
        is_em_embargo_active(EM.PROPOSED) # False
        is_em_embargo_active(EM.EXITED)   # False
    """
    return state in EM_EMBARGO_ACTIVE


def is_em_exited(state: EM) -> bool:
    """Return True if the embargo has been exited (terminated).

    Examples::

        is_em_exited(EM.EXITED)   # True
        is_em_exited(EM.ACTIVE)   # False
        is_em_exited(EM.PROPOSED) # False
    """
    return state == EM.EXITED
