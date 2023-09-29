#!/usr/bin/env python
"""file: prioritization_fuzzer
author: adh
created_at: 2/21/23 1:58 PM

This module provides a fuzzer for the report/case prioritization process.
It contains stub implementations of prioritization nodes and conditions.
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


class EnoughPrioritizationInfo(btz.UsuallySucceed):
    """This condition is used to check if there is enough information to prioritize the report.
    In an actual implementation, this condition is likely to be implemented as a human decision.
    In our stub implementation, this condition succeeds with a probability of 3/4.
    """

    # ask a human


class GatherPrioritizationInfo(btz.AlmostAlwaysSucceed):
    """This node represents the process of gathering prioritization information. In an actual implementation,
    this node would likely be implemented as prompt for a human to gather prioritization information. In our stub
    implementation, this node almost always succeeds with a probability of 0.9.
    """

    # ask a human to gather prioritization information


class NoNewPrioritizationInfo(btz.ProbablySucceed):
    """This condition is used to check if there is new prioritization information.
    In most cases, there will be no new prioritization information, so this condition will succeed.
    In an actual implementation, it might be possible to automate this node as a condition check
    based on whether or not new information has been added to the report.
    For example, if the report has been updated, then this condition might fail.

    In this stub implementation, the condition succeeds with a probability of 2/3.
    """

    # ask a human or check if the report has been updated


class OnDefer(btz.AlwaysSucceed):
    """This is a stub for now.
    It serves as a placeholder for site-specific logic that should be executed when a report is deferred.

    In an actual implementation, this would probably be a call out to a function that
    does whatever is necessary when a report is deferred.
    E.g., it might trigger some automated process to notify internal stakeholders that the report has been deferred,
    or schedule a follow-up task to check on the report at a later date.
    """

    # implement site-specific logic


class OnAccept(btz.AlwaysSucceed):
    """This is a stub for now.
    It serves as a placeholder for site-specific logic that should be executed when a report is accepted.

    In an actual implementation, this would probably be a call out to a function that
    does whatever is necessary when a report is accepted.
    E.g., it might trigger some automated process to notify internal stakeholders that the report has been accepted,
    or set up a series of standard tasks to be completed once the report is accepted.
    """

    # implement site-specific logic
