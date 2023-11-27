#!/usr/bin/env python
#  Copyright (c) 2023 Carnegie Mellon University and Contributors.
#  - see Contributors.md for a full list of Contributors
#  - see ContributionInstructions.md for information on how you can Contribute to this project
#  Vultron Multiparty Coordinated Vulnerability Disclosure Protocol Prototype is
#  licensed under a MIT (SEI)-style license, please see LICENSE.md distributed
#  with this Software or contact permission@sei.cmu.edu for full terms.
#  Created, in part, with funding and support from the United States Government
#  (see Acknowledgments file). This program may include and/or can make use of
#  certain third party source code, object code, documentation and other files
#  (“Third Party Software”). See LICENSE.md for more details.
#  Carnegie Mellon®, CERT® and CERT Coordination Center® are registered in the
#  U.S. Patent and Trademark Office by Carnegie Mellon University
"""Provides CVD Role states
"""


from enum import Flag, auto


class CVDRoles(Flag):
    """Coordinated Vulnerability Disclosure Roles as a Flag (bitwise)

    NO_ROLE: No role is assigned
    FINDER: CVD Finder (entity that finds the vulnerability)
    REPORTER: CVD Reporter (often the same as the finder)
    VENDOR: CVD Vendor (supplier of the affected product or service, usually provider of the fix)
    DEPLOYER: CVD Deployer (entity that deploys the fix, sometimes the same as the vendor)
    COORDINATOR: CVD Coordinator (entity that coordinates the CVD process)
    OTHER: Other role
    """

    NO_ROLE = 0
    FINDER = auto()
    REPORTER = auto()
    VENDOR = auto()
    DEPLOYER = auto()
    COORDINATOR = auto()
    OTHER = auto()

    # shorthand
    F = FINDER
    R = REPORTER
    V = VENDOR
    D = DEPLOYER
    C = COORDINATOR
    O = OTHER

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


def add_role(old_role, new_role):
    return old_role | new_role


def main():
    for x in CVDRoles.__members__:
        print("\t".join([x, str(CVDRoles[x]), str(CVDRoles[x].value)]))


if __name__ == "__main__":
    main()
