#!/usr/bin/env python
"""file: cvd_role_conditions
author: adh
created_at: 4/26/22 10:23 AM
"""
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
#
#  See LICENSE for details

from vultron.bt.base.bt_node import ConditionCheck
from vultron.bt.base.decorators import Invert
from vultron.bt.roles.states import CVDRoles


class RoleIsVendor(ConditionCheck):
    def func(self):
        return self.bb.CVD_role & CVDRoles.VENDOR


class RoleIsDeployer(ConditionCheck):
    def func(self):
        return self.bb.CVD_role & CVDRoles.DEPLOYER


class RoleIsNotVendor(Invert):
    _children = (RoleIsVendor,)


class RoleIsNotDeployer(Invert):
    _children = (RoleIsDeployer,)


def main():
    pass


if __name__ == "__main__":
    main()
