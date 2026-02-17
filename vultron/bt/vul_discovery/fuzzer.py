#!/usr/bin/env python
"""This module provides behavior tree fuzzers."""

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

from vultron.bt.base.factory import fuzzer
from vultron.bt.base.fuzzer import AlwaysSucceed, ProbablySucceed

NoVulFound = fuzzer(
    AlwaysSucceed,
    "NoVulFound",
    "Placeholder for the case where no vulnerability is found."
    "Always succeeds to keep the workflow moving.",
)


HaveDiscoveryPriority = fuzzer(
    AlwaysSucceed,
    "HaveDiscoveryPriority",
    "Condition check to see if we have prioritized vulnerability discovery as a goal.",
)

DiscoverVulnerability = fuzzer(
    ProbablySucceed,
    "DiscoverVulnerability",
    "Placeholder for the process of discovering a vulnerability."
    "In our stub implementation, we need to succeed relatively often to keep the workflow moving.",
)
