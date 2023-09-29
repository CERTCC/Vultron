#!/usr/bin/env python
"""file: develop_fix
author: adh
created_at: 2/21/23 2:47 PM
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

from vultron.bt.base import fuzzer as btz


class CreateFix(btz.AlmostAlwaysSucceed):
    """This node represents the process of creating a fix for the vulnerability.
    In a real implementation, this would probably be a prompt for a human to create a fix, for example by
    initiating an internal development process (e.g., in a bug tracking system).
    In our stub implementation, this node succeeds in 9 out of 10 attempts, allowing us to exercise the rest of the workflow.
    """

    # prompt a human to create a fix
