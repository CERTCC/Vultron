#!/usr/bin/env python
"""This module provides condition check behavior tree nodes"""

#  Copyright (c) 2023-2025 Carnegie Mellon University and Contributors.
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


from vultron.bt.base.bt_node import BtNode
from vultron.bt.base.factory import condition_check, invert
from vultron.bt.roles.states import CVDRoles


def role_is_vendor(obj: BtNode) -> bool:
    """True if the CVD role is vendor"""
    return bool(obj.bb.CVD_role & CVDRoles.VENDOR)


RoleIsVendor = condition_check("RoleIsVendor", role_is_vendor)


def role_is_deployer(obj: BtNode) -> bool:
    """True if the CVD role is deployer"""
    return bool(obj.bb.CVD_role & CVDRoles.DEPLOYER)


RoleIsDeployer = condition_check("RoleIsDeployer", role_is_deployer)


def role_is_coordinator(obj: BtNode) -> bool:
    """True if the CVD role is coordinator"""
    return bool(obj.bb.CVD_role & CVDRoles.COORDINATOR)


RoleIsCoordinator = condition_check("RoleIsCoordinator", role_is_coordinator)


RoleIsNotVendor = invert(
    "RoleIsNotVendor", "SUCCEED if CVD role is not Vendor", RoleIsVendor
)

RoleIsNotDeployer = invert(
    "RoleIsNotDeployer", "SUCCEED if CVD role is not Deployer", RoleIsDeployer
)

RoleIsNotCoordinator = invert(
    "RoleIsNotCoordinator",
    "SUCCEED if CVD role is not Coordinator",
    RoleIsCoordinator,
)


def main():
    pass


if __name__ == "__main__":
    main()
