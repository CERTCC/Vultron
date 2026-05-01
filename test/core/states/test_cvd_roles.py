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
"""
Unit tests for CVDRoles enum.

Spec coverage:
- BTND-05-001: CVDRoles MUST include a CASE_OWNER flag value.
"""

from vultron.core.states.roles import CVDRoles


def test_case_owner_exists():
    """CVDRoles.CASE_OWNER must exist (BTND-05-001)."""
    assert hasattr(CVDRoles, "CASE_OWNER")
    assert CVDRoles.CASE_OWNER in CVDRoles


def test_case_owner_is_distinct():
    """CVDRoles.CASE_OWNER must be distinct from all other role values."""
    other_roles = [
        CVDRoles.FINDER,
        CVDRoles.REPORTER,
        CVDRoles.VENDOR,
        CVDRoles.DEPLOYER,
        CVDRoles.COORDINATOR,
        CVDRoles.OTHER,
    ]
    for role in other_roles:
        assert CVDRoles.CASE_OWNER != role, f"CASE_OWNER must not equal {role}"


def test_case_owner_combinable_with_other_roles():
    """CVDRoles.CASE_OWNER can be combined with other roles via bitwise OR."""
    combined = CVDRoles.VENDOR | CVDRoles.CASE_OWNER
    assert CVDRoles.CASE_OWNER in combined
    assert CVDRoles.VENDOR in combined


def test_existing_roles_unchanged():
    """Adding CASE_OWNER must not change the values of existing roles."""
    assert CVDRoles.NO_ROLE.value == 0
    assert CVDRoles.FINDER.value == 1
    assert CVDRoles.REPORTER.value == 2
    assert CVDRoles.VENDOR.value == 4
    assert CVDRoles.DEPLOYER.value == 8
    assert CVDRoles.COORDINATOR.value == 16
    assert CVDRoles.OTHER.value == 32
