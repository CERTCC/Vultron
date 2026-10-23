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
    """True when rejecting *embargo_id* must also end the embargo (EMB-04-002).

    The case is in ``REVISE`` (an embargo is in force and *embargo_id* is
    its last open revision, EP-08-001) and CS is public, exploited or
    attacked.  Rejecting the revision returns the case to the prior terms,
    which no act may end in then: the CASE_MANAGER records the ``REJECT``
    step and then terminates the embargo in the same act (MSM-07-009).  The
    CASE_MANAGER reads this before the rejection, among the guards that
    trial-apply both steps; replicas never read it, they copy both entries
    (CM-23-016).
    """
    return case.proposed_embargo_ids == [embargo_id] and _in_force_disclosed(
        case
    )


def embargo_outlives_disclosure(case: "VulnerabilityCase") -> bool:
    """True when the prior terms stand after CS went public (EMB-04-002).

    An embargo is in force, no proposal is open, and CS is public, exploited
    or attacked.  This is the case the owner's rejection of the last
    revision leaves when :func:`rejection_ends_embargo` held before it: the
    CASE_MANAGER's rejection trees read it after the ``REJECT`` step and
    terminate the embargo in the same act (MSM-07-009).
    """
    return not case.proposed_embargo_ids and _in_force_disclosed(case)


def _in_force_disclosed(case: "VulnerabilityCase") -> bool:
    """An embargo is in force and CS is public, exploited or attacked."""
    return case.active_embargo_id is not None and not pxa_is_embargo_eligible(
        case.current_status.pxa.state
    )


__all__ = [
    "embargo_outlives_disclosure",
    "pxa_is_embargo_eligible",
    "rejection_ends_embargo",
]
