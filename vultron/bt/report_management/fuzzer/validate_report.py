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
This is a fuzzer for the validation process.
It provides stub implementations of the validation conditions and actions.
"""

from vultron.bt.base.factory import fuzzer
from vultron.bt.base.fuzzer import (
    AlmostAlwaysSucceed,
    ProbablySucceed,
    UsuallySucceed,
)

# ask a human or check if the report has been updated
NoNewValidationInfo = fuzzer(
    ProbablySucceed,
    "NoNewValidationInfo",
    """This condition is used to check if there is new validation information.
    In most cases, there will be no new validation information, so this condition will succeed.

    In an actual implementation, it might be possible to automate this node as a condition check
    based on whether or not new information has been added to the report.
    For example, if the report has been updated, then this condition could succeed. Otherwise, if the report has not been
    updated, then this condition could fail. Or it could be left to a human to decide.

    In this stub implementation, the condition succeeds with a probability of 2/3.
    """,
)


# ask a human
EvaluateReportCredibility = fuzzer(
    AlmostAlwaysSucceed,
    "EvaluateReportCredibility",
    """This condition is used to evaluate the credibility of the report.
    Suggestions for evaluating report credibility are provided in the SSVC documentation.

    In actual implementation, it is likely that this condition would be implemented as a human decision.

    In this stub implementation, the condition almost always succeeds with a probability of 0.9.
    """,
)

# ask a human
EvaluateReportValidity = fuzzer(
    AlmostAlwaysSucceed,
    "EvaluateReportValidity",
    """This condition is used to evaluate the validity of the report.
    Report validity is contextual to the receiving organization.
    In order for a report to be valid, it must be credible, and it
    must meet the organization's criteria for validity.
    For example, a report may be credible, but it may not be valid
    if it is not in scope for the organization.
    Note that invalid reports are not necessarily invalid for all
    organizations, nor does an invalid report necessarily mean
    that the report is false or not credible.
    """,
)


# ask a human
EnoughValidationInfo = fuzzer(
    UsuallySucceed,
    "EnoughValidationInfo",
    """This condition is used to check if there is enough information to validate the report.
    In an actual implementation, this condition is likely to be implemented as a human decision.
    In our stub implementation, this condition succeeds with a probability of 3/4.
    """,
)


# ask a human to gather validation information
GatherValidationInfo = fuzzer(
    AlmostAlwaysSucceed,
    "GatherValidationInfo",
    """This node represents the process of gathering validation information.
    In an actual implementation, this node would likely be implemented as prompt for a human to gather validation information.
    In our stub implementation, this node almost always succeeds with a probability of 0.9.
    """,
)
