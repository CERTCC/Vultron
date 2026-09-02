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

Spec references: EMB-01-002, EMB-02-002.
"""

from vultron.core.states.cs import CS_pxa


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


__all__ = ["pxa_is_embargo_eligible"]
