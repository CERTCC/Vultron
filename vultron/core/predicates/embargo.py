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

"""Pure predicate functions for embargo eligibility.

These functions contain no I/O and no DataLayer dependencies, making them
independently testable with in-memory objects.  Service methods that enforce
embargo eligibility MUST call these functions rather than embedding the rule
inline.

Import constraints
------------------
- This module MAY import from ``vultron.core.states`` (state-value types).
- This module MUST NOT import from ``vultron.core.behaviors``,
  ``vultron.core.use_cases``, or ``vultron.core.services``.

Spec references: EMB-01-002, EMB-02-002, EMB-04-002.
"""

from typing import TYPE_CHECKING

from vultron.core.states.cs import CS_pxa

if TYPE_CHECKING:
    from vultron.core.models.case import VulnerabilityCase


def pxa_is_embargo_eligible(pxa_state: CS_pxa) -> bool:
    """Return ``True`` when the case is still eligible for embargo operations.

    Per EMB-01-002 and EMB-02-002: once any of P (public aware), X (exploit
    public), or A (attacks observed) is set on the case — i.e. when
    ``pxa_state != CS_pxa.pxa`` — no new embargo may be proposed or accepted
    in STRICT mode.

    A ``True`` result means "the operation is permitted by the PXA state";
    a ``False`` result means "public awareness, exploit publication, or
    attack observation has been set and the embargo-creation window is closed".

    Args:
        pxa_state: The current PXA case state dimension.

    Returns:
        ``True`` when *pxa_state* is ``CS_pxa.pxa`` (all bits clear);
        ``False`` otherwise.

    Examples::

        pxa_is_embargo_eligible(CS_pxa.pxa)  # True  — no public info
        pxa_is_embargo_eligible(CS_pxa.Pxa)  # False — public aware
        pxa_is_embargo_eligible(CS_pxa.pXa)  # False — exploit public
        pxa_is_embargo_eligible(CS_pxa.pxA)  # False — attacks observed
    """
    return pxa_state == CS_pxa.pxa


def rejection_ends_embargo(case: "VulnerabilityCase", embargo_id: str) -> bool:
    """True when rejecting *embargo_id* must end the embargo instead (EMB-04-002).

    The case is in ``REVISE`` (an embargo is in force and *embargo_id* is
    its last open revision, EP-08-001) and CS is public, exploited or
    attacked.  Rejecting the revision would return the case to the prior
    terms, which is not allowed then: the rejection is answered with ET,
    whose ``TERMINATE`` step cancels the revision (EP-08-004).  The one
    condition the CASE_MANAGER's decision, its lifecycle refusal and the
    replica slot all read (MSM-07-009).
    """
    return (
        case.proposed_embargo_ids == [embargo_id]
        and case.active_embargo_id is not None
        and not pxa_is_embargo_eligible(case.current_status.pxa.state)
    )


__all__ = ["pxa_is_embargo_eligible", "rejection_ends_embargo"]
