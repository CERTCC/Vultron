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
"""
Provides fuzzer leaf nodes for the report management workflow.
"""

from vultron.bt.base.factory import fuzzer
from vultron.bt.base.fuzzer import AlwaysSucceed, UsuallyFail

# ask a human
OtherCloseCriteriaMet = fuzzer(
    UsuallyFail,
    "OtherCloseCriteriaMet",
    """This condition is used to check if other criteria have been met that would allow the report to be closed.
    In an actual implementation, this condition would likely be implemented as a human decision, or perhaps
    as a check of the case status versus a set of site-specific criteria or policies.
    In our stub implementation, this condition fails with a probability of 3/4.
    """,
)


# perform a pre-close action or actions
PreCloseAction = fuzzer(
    AlwaysSucceed,
    "PreCloseAction",
    """This node represents the process of performing a pre-close action. An actual implementation of this node could
    automate some activity that must be performed before a report can be closed. For example, a quality assurance
    process might be triggered at this point.
    In our stub implementation, this node always succeeds.
    """,
)
