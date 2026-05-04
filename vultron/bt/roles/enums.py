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
"""Legacy bitmask CVD role enum used by the vultron.bt simulator layer.

This module is intentionally isolated from ``vultron.core``. The simulator
(``vultron.bt``) uses bitmask arithmetic to represent combined roles on a
single blackboard field. New code in ``vultron.core`` and ``vultron.wire``
uses ``CVDRole`` (a ``StrEnum``) with ``list[CVDRole]`` instead.
"""

from enum import Flag, auto


class CVDRolesFlag(Flag):
    """Bitmask CVD role flags for the vultron.bt simulator.

    Use ``CVDRole`` (``vultron.core.states.roles``) for new code.
    This class exists solely to keep the legacy ``vultron.bt`` simulator
    working without modification.
    """

    NO_ROLE = 0
    FINDER = auto()
    REPORTER = auto()
    VENDOR = auto()
    DEPLOYER = auto()
    COORDINATOR = auto()
    OTHER = auto()
    CASE_OWNER = auto()

    # shorthand
    F = FINDER
    R = REPORTER
    V = VENDOR
    D = DEPLOYER
    C = COORDINATOR
    O = OTHER  # noqa: E741

    # frequent combinations
    FINDER_REPORTER = FINDER | REPORTER
    FINDER_VENDOR = FINDER | VENDOR
    FINDER_REPORTER_VENDOR = FINDER | REPORTER | VENDOR
    FINDER_REPORTER_VENDOR_DEPLOYER = FINDER | REPORTER | VENDOR | DEPLOYER
    FINDER_REPORTER_VENDOR_DEPLOYER_COORDINATOR = (
        FINDER | REPORTER | VENDOR | DEPLOYER | COORDINATOR
    )

    VENDOR_DEPLOYER = VENDOR | DEPLOYER
    VENDOR_COORDINATOR = VENDOR | COORDINATOR

    FINDER_COORDINATOR = FINDER | COORDINATOR
    FINDER_DEPLOYER = FINDER | DEPLOYER

    FR = FINDER_REPORTER
    FV = FINDER_VENDOR
    FRV = FINDER_REPORTER_VENDOR
    FRVD = FINDER_REPORTER_VENDOR_DEPLOYER
    FRVDC = FINDER_REPORTER_VENDOR_DEPLOYER_COORDINATOR


def add_role(old_role: CVDRolesFlag, new_role: CVDRolesFlag) -> CVDRolesFlag:
    """Return the bitwise OR of two CVDRolesFlag values."""
    return old_role | new_role
