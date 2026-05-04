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
Unit tests for CVDRolesFlag — the legacy bitmask Flag enum used by the
vultron.bt simulator layer.
"""

from vultron.bt.roles.enums import CVDRolesFlag, add_role


def test_no_role_is_zero():
    """CVDRolesFlag.NO_ROLE must be 0."""
    assert CVDRolesFlag.NO_ROLE.value == 0


def test_atomic_role_values_unchanged():
    """Atomic role values must match the original CVDRoles values."""
    assert CVDRolesFlag.FINDER.value == 1
    assert CVDRolesFlag.REPORTER.value == 2
    assert CVDRolesFlag.VENDOR.value == 4
    assert CVDRolesFlag.DEPLOYER.value == 8
    assert CVDRolesFlag.COORDINATOR.value == 16
    assert CVDRolesFlag.OTHER.value == 32


def test_case_owner_exists():
    """CVDRolesFlag.CASE_OWNER must exist."""
    assert hasattr(CVDRolesFlag, "CASE_OWNER")


def test_case_owner_is_distinct():
    """CVDRolesFlag.CASE_OWNER must be distinct from other atomic roles."""
    other_roles = [
        CVDRolesFlag.FINDER,
        CVDRolesFlag.REPORTER,
        CVDRolesFlag.VENDOR,
        CVDRolesFlag.DEPLOYER,
        CVDRolesFlag.COORDINATOR,
        CVDRolesFlag.OTHER,
    ]
    for role in other_roles:
        assert CVDRolesFlag.CASE_OWNER != role


def test_bitmask_combination():
    """Combination aliases use bitmask OR and membership works via &."""
    combined = CVDRolesFlag.FINDER_REPORTER
    assert bool(combined & CVDRolesFlag.FINDER)
    assert bool(combined & CVDRolesFlag.REPORTER)
    assert not bool(combined & CVDRolesFlag.VENDOR)


def test_add_role():
    """add_role returns the bitwise OR of two CVDRolesFlag values."""
    result = add_role(CVDRolesFlag.VENDOR, CVDRolesFlag.DEPLOYER)
    assert bool(result & CVDRolesFlag.VENDOR)
    assert bool(result & CVDRolesFlag.DEPLOYER)


def test_frvdc_combination():
    """FINDER_REPORTER_VENDOR_DEPLOYER_COORDINATOR combines all five roles."""
    combo = CVDRolesFlag.FINDER_REPORTER_VENDOR_DEPLOYER_COORDINATOR
    for role in (
        CVDRolesFlag.FINDER,
        CVDRolesFlag.REPORTER,
        CVDRolesFlag.VENDOR,
        CVDRolesFlag.DEPLOYER,
        CVDRolesFlag.COORDINATOR,
    ):
        assert bool(combo & role), f"{role} should be in FRVDC"
