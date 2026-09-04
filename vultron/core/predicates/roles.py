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

"""Pure predicate functions over CVD role lists and role-gated state assertions.

These functions contain no I/O and no DataLayer dependencies, making them
independently testable with in-memory objects.  BT nodes and service methods
that need to enforce a role-membership rule MUST call one of these functions
rather than writing the check inline.

Import constraints
------------------
- This module MAY import from ``vultron.core.states`` (state-value types).
- This module MAY import from ``vultron.enums`` (bottom-of-stack enums).
- This module MUST NOT import from ``vultron.core.behaviors``,
  ``vultron.core.use_cases``, or ``vultron.core.services``.

Spec references: CSB-15-001, CSB-15-002, CM-25-005, ADR-0057, ADR-0075,
ADR-0084.
"""

from vultron.core.states.cs import CS_vf
from vultron.enums.roles import CVDRole

# ---------------------------------------------------------------------------
# Simple role-membership predicates (AC-1)
# ---------------------------------------------------------------------------


def has_vendor_role(roles: list[CVDRole]) -> bool:
    """Return ``True`` when ``CVDRole.VENDOR`` is present in *roles*.

    Gate for VF state assertions: only a Vendor-role actor may assert
    vendor-path state transitions (CSB-15-001, ADR-0075).

    Args:
        roles: The participant's current role list.

    Returns:
        ``True`` if ``CVDRole.VENDOR`` is in *roles*; ``False`` otherwise.

    Examples::

        has_vendor_role([CVDRole.VENDOR])           # True
        has_vendor_role([CVDRole.VENDOR, CVDRole.COORDINATOR])  # True
        has_vendor_role([CVDRole.DEPLOYER])         # False
        has_vendor_role([])                         # False
    """
    return CVDRole.VENDOR in roles


def has_deployer_role(roles: list[CVDRole]) -> bool:
    """Return ``True`` when ``CVDRole.DEPLOYER`` is present in *roles*.

    Gate for D-state assertions: only a Deployer-role actor may assert
    fix-deployment state transitions (CSB-15-002, ADR-0075).

    Args:
        roles: The participant's current role list.

    Returns:
        ``True`` if ``CVDRole.DEPLOYER`` is in *roles*; ``False`` otherwise.

    Examples::

        has_deployer_role([CVDRole.DEPLOYER])                   # True
        has_deployer_role([CVDRole.VENDOR, CVDRole.DEPLOYER])   # True
        has_deployer_role([CVDRole.VENDOR])                     # False
        has_deployer_role([])                                   # False
    """
    return CVDRole.DEPLOYER in roles


def has_case_owner_role(roles: list[CVDRole]) -> bool:
    """Return ``True`` when ``CVDRole.CASE_OWNER`` is present in *roles*.

    Used in ``StatusAdoptionGate`` to identify gospel senders whose status
    reports bypass the approval call-out (RSH-01-002).

    Args:
        roles: The participant's current role list.

    Returns:
        ``True`` if ``CVDRole.CASE_OWNER`` is in *roles*; ``False`` otherwise.
    """
    return CVDRole.CASE_OWNER in roles


def has_case_manager_role(roles: list[CVDRole]) -> bool:
    """Return ``True`` when ``CVDRole.CASE_MANAGER`` is present in *roles*.

    Args:
        roles: The participant's current role list.

    Returns:
        ``True`` if ``CVDRole.CASE_MANAGER`` is in *roles*; ``False`` otherwise.
    """
    return CVDRole.CASE_MANAGER in roles


def has_cna_role(roles: list[CVDRole]) -> bool:
    """Return ``True`` when ``CVDRole.CVE_NUMBERING_AUTHORITY`` is present.

    Gate for direct CVE-ID assignment: only a CNA-role actor may assign IDs
    without delegating to an external CNA service.

    Args:
        roles: The participant's current role list.

    Returns:
        ``True`` if ``CVDRole.CVE_NUMBERING_AUTHORITY`` is in *roles*;
        ``False`` otherwise.
    """
    return CVDRole.CVE_NUMBERING_AUTHORITY in roles


def is_sole_observer(roles: list[CVDRole]) -> bool:
    """Return ``True`` when the actor holds ONLY ``CVDRole.OBSERVER``.

    An actor whose *only* role is OBSERVER may not assert vendor-path (VFD)
    state transitions (CM-25-005, ADR-0057).  An actor holding OBSERVER
    alongside VENDOR or DEPLOYER retains VFD obligations from those roles
    (CM-26-001 union-of-permissions rule).

    This uses an equality test (``roles == [CVDRole.OBSERVER]``), NOT a
    membership test, per CM-25-005.

    Args:
        roles: The participant's current role list.

    Returns:
        ``True`` only when *roles* is exactly ``[CVDRole.OBSERVER]``.

    Examples::

        is_sole_observer([CVDRole.OBSERVER])                           # True
        is_sole_observer([CVDRole.OBSERVER, CVDRole.VENDOR])           # False
        is_sole_observer([CVDRole.VENDOR])                             # False
        is_sole_observer([])                                           # False
    """
    return roles == [CVDRole.OBSERVER]


# ---------------------------------------------------------------------------
# Role-gated state invariants (AC-3 / ADR-0084)
# ---------------------------------------------------------------------------


def vendor_vf_state_is_valid(roles: list[CVDRole], vf: CS_vf | None) -> bool:
    """Return ``True`` when *vf* is consistent with *roles* for a Vendor.

    A participant holding ``CVDRole.VENDOR`` is, by definition, already aware
    of the case; therefore a Vendor-role participant can never validly report
    ``CS_vf.vf`` (vendor-unaware).  Valid Vendor VF states are ``CS_vf.Vf``
    (aware, fix not ready) and ``CS_vf.VF`` (aware, fix ready).

    When the actor does not hold ``CVDRole.VENDOR`` or when *vf* is ``None``
    (dimension absent), no constraint applies and the function returns
    ``True``.

    This is always an error to violate and is enforced at every assertion site
    (ADR-0084).

    Args:
        roles: The participant's current role list.
        vf: The VF state being asserted, or ``None`` when absent.

    Returns:
        ``False`` only when ``CVDRole.VENDOR`` is in *roles* AND *vf* is
        ``CS_vf.vf`` (vendor-unaware); ``True`` in all other cases.

    Examples::

        vendor_vf_state_is_valid([CVDRole.VENDOR], CS_vf.Vf)   # True
        vendor_vf_state_is_valid([CVDRole.VENDOR], CS_vf.VF)   # True
        vendor_vf_state_is_valid([CVDRole.VENDOR], CS_vf.vf)   # False
        vendor_vf_state_is_valid([CVDRole.DEPLOYER], CS_vf.vf) # True (no VENDOR)
        vendor_vf_state_is_valid([], None)                     # True
    """
    if CVDRole.VENDOR not in roles:
        return True
    if vf is None:
        return True
    return vf != CS_vf.vf


__all__ = [
    "has_vendor_role",
    "has_deployer_role",
    "has_case_owner_role",
    "has_case_manager_role",
    "has_cna_role",
    "is_sole_observer",
    "vendor_vf_state_is_valid",
]
