#!/usr/bin/env python
"""file: fuzzer
author: adh
created_at: 6/23/22 12:11 PM
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


from vultron.bt.base import fuzzer as btz


class NoVulFound(btz.AlwaysSucceed):
    """Placeholder for the case where no vulnerability is found.
    Always succeeds to keep the workflow moving.
    """


class HaveDiscoveryPriority(btz.AlwaysSucceed):
    """Condition check to see if we have prioritized vulnerability discovery as a goal."""


class DiscoverVulnerability(btz.ProbablySucceed):
    """Placeholder for the process of discovering a vulnerability.
    In our stub implementation, we need to succeed relatively often to keep the workflow moving.
    """
