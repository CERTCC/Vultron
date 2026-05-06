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
Unit tests for CVDRole StrEnum.

Spec coverage:
- BTND-05-001: CVDRoles MUST include a CASE_OWNER flag value.
"""

from enum import StrEnum

import pytest

from vultron.core.states.roles import CVDRole, serialize_roles, validate_roles


def test_cvdrole_is_str_enum():
    """CVDRole must be a StrEnum."""
    assert issubclass(CVDRole, StrEnum)


def test_atomic_roles_exist():
    """All expected atomic roles must exist."""
    expected = {
        "FINDER",
        "REPORTER",
        "VENDOR",
        "DEPLOYER",
        "COORDINATOR",
        "OTHER",
        "CASE_OWNER",
        "CASE_ACTOR",
    }
    actual = {m.name for m in CVDRole}
    assert expected == actual


def test_case_owner_exists():
    """CVDRole.CASE_OWNER must exist (BTND-05-001)."""
    assert hasattr(CVDRole, "CASE_OWNER")
    assert CVDRole.CASE_OWNER in CVDRole


def test_values_are_lowercase():
    """All CVDRole values must be lowercase strings."""
    for role in CVDRole:
        assert (
            role.value == role.value.lower()
        ), f"{role.name}.value should be lowercase, got {role.value!r}"


def test_name_value_relationship():
    """Each member's name is the uppercase version of its value."""
    for role in CVDRole:
        assert (
            role.name == role.value.upper()
        ), f"{role.name}: name={role.name!r} value={role.value!r}"


def test_string_equality():
    """CVDRole members compare equal to their string values."""
    assert CVDRole.FINDER == "finder"
    assert CVDRole.VENDOR == "vendor"
    assert CVDRole.CASE_OWNER == "case_owner"


def test_lookup_by_value():
    """CVDRole can be looked up by lowercase string value."""
    assert CVDRole("finder") is CVDRole.FINDER
    assert CVDRole("vendor") is CVDRole.VENDOR
    assert CVDRole("case_owner") is CVDRole.CASE_OWNER


def test_lookup_by_name():
    """CVDRole can be looked up by name."""
    assert CVDRole["FINDER"] is CVDRole.FINDER
    assert CVDRole["VENDOR"] is CVDRole.VENDOR


def test_no_combination_aliases():
    """CVDRole must not have combination aliases like FINDER_REPORTER."""
    assert not hasattr(CVDRole, "FINDER_REPORTER")
    assert not hasattr(CVDRole, "FINDER_REPORTER_VENDOR_DEPLOYER_COORDINATOR")


def test_no_no_role():
    """CVDRole must not have a NO_ROLE member (empty list represents no role)."""
    assert not hasattr(CVDRole, "NO_ROLE")


def test_list_membership():
    """list[CVDRole] membership check works correctly."""
    roles = [CVDRole.FINDER, CVDRole.VENDOR]
    assert CVDRole.FINDER in roles
    assert CVDRole.VENDOR in roles
    assert CVDRole.COORDINATOR not in roles


# --- serialize_roles ---


def test_serialize_roles_empty():
    """serialize_roles([]) returns an empty list."""
    assert serialize_roles([]) == []


def test_serialize_roles_single():
    """serialize_roles emits lowercase string values."""
    assert serialize_roles([CVDRole.VENDOR]) == ["vendor"]


def test_serialize_roles_multiple():
    """serialize_roles emits all role values in order."""
    roles = [CVDRole.FINDER, CVDRole.COORDINATOR]
    assert serialize_roles(roles) == ["finder", "coordinator"]


# --- validate_roles ---


def test_validate_roles_from_enum_members():
    """validate_roles passes CVDRole members through unchanged."""
    roles = [CVDRole.FINDER, CVDRole.VENDOR]
    assert validate_roles(roles) == [CVDRole.FINDER, CVDRole.VENDOR]


def test_validate_roles_from_strings():
    """validate_roles coerces lowercase string values to CVDRole."""
    result = validate_roles(["finder", "vendor"])
    assert result == [CVDRole.FINDER, CVDRole.VENDOR]


def test_validate_roles_empty():
    """validate_roles([]) returns an empty list."""
    assert validate_roles([]) == []


def test_validate_roles_non_list():
    """validate_roles returns [] for non-list input."""
    assert validate_roles(None) == []  # type: ignore[arg-type]
    assert validate_roles("finder") == []  # type: ignore[arg-type]


def test_validate_roles_invalid_value():
    """validate_roles raises ValueError for unknown string values."""
    with pytest.raises(ValueError):
        validate_roles(["no_role"])


def test_roundtrip():
    """serialize_roles -> validate_roles roundtrip preserves roles."""
    original = [CVDRole.FINDER, CVDRole.COORDINATOR, CVDRole.CASE_OWNER]
    serialized = serialize_roles(original)
    assert validate_roles(serialized) == original
