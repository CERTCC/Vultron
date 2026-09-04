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

"""Tests for vultron.core.predicates.roles."""

import pytest

from vultron.core.predicates.roles import (
    has_case_manager_role,
    has_case_owner_role,
    has_cna_role,
    has_deployer_role,
    has_vendor_role,
    is_sole_observer,
    vendor_vf_state_is_valid,
)
from vultron.core.states.cs import CS_vf
from vultron.enums.roles import CVDRole


class TestHasVendorRole:
    def test_vendor_only(self):
        assert has_vendor_role([CVDRole.VENDOR]) is True

    def test_vendor_plus_other(self):
        assert has_vendor_role([CVDRole.VENDOR, CVDRole.DEPLOYER]) is True

    def test_deployer_only(self):
        assert has_vendor_role([CVDRole.DEPLOYER]) is False

    def test_empty_list(self):
        assert has_vendor_role([]) is False

    def test_observer_only(self):
        assert has_vendor_role([CVDRole.OBSERVER]) is False

    def test_all_non_vendor(self):
        assert (
            has_vendor_role(
                [CVDRole.DEPLOYER, CVDRole.CASE_MANAGER, CVDRole.OBSERVER]
            )
            is False
        )


class TestHasDeployerRole:
    def test_deployer_only(self):
        assert has_deployer_role([CVDRole.DEPLOYER]) is True

    def test_deployer_plus_vendor(self):
        assert has_deployer_role([CVDRole.VENDOR, CVDRole.DEPLOYER]) is True

    def test_vendor_only(self):
        assert has_deployer_role([CVDRole.VENDOR]) is False

    def test_empty_list(self):
        assert has_deployer_role([]) is False

    def test_observer_only(self):
        assert has_deployer_role([CVDRole.OBSERVER]) is False


class TestHasCaseOwnerRole:
    def test_case_owner_only(self):
        assert has_case_owner_role([CVDRole.CASE_OWNER]) is True

    def test_case_owner_plus_vendor(self):
        assert (
            has_case_owner_role([CVDRole.CASE_OWNER, CVDRole.VENDOR]) is True
        )

    def test_vendor_only(self):
        assert has_case_owner_role([CVDRole.VENDOR]) is False

    def test_empty_list(self):
        assert has_case_owner_role([]) is False


class TestHasCaseManagerRole:
    def test_case_manager_only(self):
        assert has_case_manager_role([CVDRole.CASE_MANAGER]) is True

    def test_case_manager_plus_vendor(self):
        assert (
            has_case_manager_role([CVDRole.CASE_MANAGER, CVDRole.VENDOR])
            is True
        )

    def test_vendor_only(self):
        assert has_case_manager_role([CVDRole.VENDOR]) is False

    def test_empty_list(self):
        assert has_case_manager_role([]) is False


class TestHasCnaRole:
    def test_cna_only(self):
        assert has_cna_role([CVDRole.CVE_NUMBERING_AUTHORITY]) is True

    def test_cna_plus_vendor(self):
        assert (
            has_cna_role([CVDRole.CVE_NUMBERING_AUTHORITY, CVDRole.VENDOR])
            is True
        )

    def test_vendor_only(self):
        assert has_cna_role([CVDRole.VENDOR]) is False

    def test_empty_list(self):
        assert has_cna_role([]) is False


class TestIsSoleObserver:
    def test_observer_only_is_sole(self):
        assert is_sole_observer([CVDRole.OBSERVER]) is True

    def test_observer_plus_vendor_is_not_sole(self):
        assert is_sole_observer([CVDRole.OBSERVER, CVDRole.VENDOR]) is False

    def test_vendor_only_is_not_sole(self):
        assert is_sole_observer([CVDRole.VENDOR]) is False

    def test_empty_list_is_not_sole(self):
        assert is_sole_observer([]) is False

    def test_observer_plus_deployer_is_not_sole(self):
        assert is_sole_observer([CVDRole.OBSERVER, CVDRole.DEPLOYER]) is False

    def test_multiple_non_observer_roles(self):
        assert is_sole_observer([CVDRole.VENDOR, CVDRole.DEPLOYER]) is False


class TestVendorVfStateIsValid:
    def test_vendor_vf_aware_is_valid(self):
        """Vendor with CS_vf.Vf (aware, fix not ready) is valid."""
        assert vendor_vf_state_is_valid([CVDRole.VENDOR], CS_vf.Vf) is True

    def test_vendor_vf_fix_ready_is_valid(self):
        """Vendor with CS_vf.VF (aware, fix ready) is valid."""
        assert vendor_vf_state_is_valid([CVDRole.VENDOR], CS_vf.VF) is True

    def test_vendor_vf_unaware_is_invalid(self):
        """Vendor with CS_vf.vf (vendor-unaware) violates ADR-0084."""
        assert vendor_vf_state_is_valid([CVDRole.VENDOR], CS_vf.vf) is False

    def test_non_vendor_vf_unaware_is_valid(self):
        """Non-vendor actor with CS_vf.vf is fine — rule is Vendor-only."""
        assert vendor_vf_state_is_valid([CVDRole.DEPLOYER], CS_vf.vf) is True

    def test_empty_roles_any_vf_valid(self):
        """Empty role list: no VENDOR constraint."""
        assert vendor_vf_state_is_valid([], CS_vf.vf) is True
        assert vendor_vf_state_is_valid([], CS_vf.Vf) is True

    def test_vendor_none_vf_is_valid(self):
        """None vf means dimension absent — no constraint applies."""
        assert vendor_vf_state_is_valid([CVDRole.VENDOR], None) is True

    def test_non_vendor_none_vf_is_valid(self):
        assert vendor_vf_state_is_valid([CVDRole.DEPLOYER], None) is True

    @pytest.mark.parametrize("vf", list(CS_vf))
    def test_non_vendor_any_vf_state_valid(self, vf: CS_vf):
        """Non-vendor actors are never constrained by VF state."""
        assert vendor_vf_state_is_valid([CVDRole.DEPLOYER], vf) is True

    @pytest.mark.parametrize(
        "vf,expected",
        [
            (CS_vf.vf, False),
            (CS_vf.Vf, True),
            (CS_vf.VF, True),
        ],
    )
    def test_vendor_vf_state_validity(self, vf: CS_vf, expected: bool):
        """Parameterized check over every Vendor-legal and illegal VF state."""
        assert vendor_vf_state_is_valid([CVDRole.VENDOR], vf) is expected
