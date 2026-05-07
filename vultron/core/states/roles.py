#!/usr/bin/env python
#  Copyright (c) 2023-2026 Carnegie Mellon University and Contributors.
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
"""Provides CVD Role states."""

from enum import StrEnum, auto


class CVDRole(StrEnum):
    """Individual CVD role values (lowercase string enum).

    Each member represents a single, atomic CVD role. Participants may hold
    multiple roles simultaneously; use ``list[CVDRole]`` at call sites rather
    than bitmask arithmetic.

    Values are lowercase strings (e.g. ``CVDRole.FINDER == 'finder'``).

    Roles:
        FINDER: Entity that discovers the vulnerability.
        REPORTER: Entity that reports the vulnerability to others.
        VENDOR: Supplier of the affected product or service.
        DEPLOYER: Entity that deploys the fix.
        COORDINATOR: Entity that coordinates the CVD process.
        OTHER: Any other CVD role not captured above.
        CASE_OWNER: Actor who owns and manages a VulnerabilityCase (BTND-05-001).
        CASE_ACTOR: The ActivityStreams Service actor that performs ongoing case
            replica synchronisation on behalf of the case owner.  A CaseActor
            participant always also holds the COORDINATOR role (CBT-01-003).
    """

    FINDER = auto()
    REPORTER = auto()
    VENDOR = auto()
    DEPLOYER = auto()
    COORDINATOR = auto()
    OTHER = auto()
    CASE_OWNER = auto()
    CASE_ACTOR = auto()


def serialize_roles(roles: list[CVDRole]) -> list[str]:
    """Serialize a list of CVDRole members to a list of lowercase strings."""
    return [role.value for role in roles]


def validate_roles(value: object) -> list[CVDRole]:
    """Coerce a list of strings or CVDRole members to ``list[CVDRole]``.

    Accepts either a list of ``CVDRole`` enum members (pass-through) or a
    list of string values (e.g. from JSON deserialization).
    """
    if not isinstance(value, list):
        return []
    result: list[CVDRole] = []
    for item in value:
        if isinstance(item, CVDRole):
            result.append(item)
        elif isinstance(item, str):
            result.append(CVDRole(item.lower()))
    return result
