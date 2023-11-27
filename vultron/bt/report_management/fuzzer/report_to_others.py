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
This module provides fuzzer leaf nodes in support of the process of notifying other parties of the report/case
"""
from vultron.bt.base.factory import fuzzer


from vultron.bt.base.fuzzer import (
    AlmostAlwaysFail,
    AlmostAlwaysSucceed,
    AlmostCertainlyFail,
    AlwaysSucceed,
    ProbablySucceed,
    SuccessOrRunning,
    UniformSucceedFail,
    UsuallyFail,
    UsuallySucceed,
)


AllPartiesKnown = fuzzer(
    UniformSucceedFail,
    "AllPartiesKnown",
    """This condition is used to check if all parties that should be involved in the report have been identified.
    In an actual implementation, this condition would likely be implemented as a human decision.
    In our stub implementation, this condition succeeds with a probability of 0.5.
    """,
)


# prompt for a human to identify vendors
IdentifyVendors = fuzzer(
    SuccessOrRunning,
    "IdentifyVendors",
    """This node represents the process of identifying vendors that should be involved in the report.
    In an actual implementation, this node would likely be implemented as prompt for a human to identify vendors.
    In our stub implementation, this node succeeds with a probability of 0.5.
    """,
)


# prompt for a human to identify coordinators
IdentifyCoordinators = fuzzer(
    SuccessOrRunning,
    "IdentifyCoordinators",
    """This node represents the process of identifying coordinators that should be involved in the report.
    In an actual implementation, this node would likely be implemented as prompt for a human to identify coordinators.
    In our stub implementation, this node succeeds with a probability of 0.5.
    """,
)


# prompt for a human to identify other parties
IdentifyOthers = fuzzer(
    AlwaysSucceed,
    "IdentifyOthers",
    """This node represents the process of identifying other parties that should be involved in the report.
    In an actual implementation, this node would likely be implemented as prompt for a human to identify other parties.
    In our stub implementation, this node always succeeds.
    """,
)


# check if all identified parties have been notified
NotificationsComplete = fuzzer(
    UniformSucceedFail,
    "NotificationsComplete",
    """This condition is used to check if all notifications have been sent. In an actual implementation, this condition
    could be a simple check to see if all identified parties have been notified. In our stub implementation,
    this condition succeeds with a probability of 0.5.
    """,
)


# choose a recipient from a list of identified parties
ChooseRecipient = fuzzer(
    AlwaysSucceed,
    "ChooseRecipient",
    """This node represents the process of choosing a recipient for the notification. In a real implementation,
    this could be fully automated by choosing a recipient to notify from a list of identified parties. In our stub
    implementation, this node always succeeds so that we can exercise the rest of the workflow.
    """,
)


# remove a recipient from the list of identified parties
RemoveRecipient = fuzzer(
    AlwaysSucceed,
    "RemoveRecipient",
    """This node represents the process of removing a recipient from the list of identified parties. In a real
    implementation, this could be fully automated by removing a recipient from the list of identified parties based
    on some criteria. In our stub implementation, this node always succeeds so that we can exercise the rest of the
    workflow.
    """,
)


# check effort against some threshold or ask a human
RecipientEffortExceeded = fuzzer(
    AlmostCertainlyFail,
    "RecipientEffortExceeded",
    """This condition is used to check if the effort expended to notify a recipient has exceeded some threshold. In a
    real implementation, this could be a simple check to see if the effort expended to notify a recipient has
    exceeded some threshold. For example, an organization might have a policy that no more than 3 attempts should be
    made to notify a recipient. Alternatively, an organization might have a policy that no more than 1 hour of effort
    should be expended to notify a recipient. It may also be left up to the discretion of the analyst to determine if
    the effort expended to notify a recipient has exceeded some threshold. In our stub implementation, this condition
    only succeeds in 7 out of 100 attempts.
    """,
)


# compare the intended recipient's embargo policy with the policy associated with the case or ask a human
PolicyCompatible = fuzzer(
    ProbablySucceed,
    "PolicyCompatible",
    """This node represents the process to see if the potential recipient's embargo policy is compatible with the
    expectations set out in the case. In a real implementation, this might be automated as a comparison between the
    intended recipient's embargo policy and the policy associated with the case. Alternatively, this might be a
    prompt for a human to determine if the potential recipient's embargo policy is compatible with the case. In our
    stub implementation, this node succeeds with a probability of 2/3.
    """,
)


# lookup contact info in a database or ask a human
FindContact = fuzzer(
    UsuallySucceed,
    "FindContact",
    """This node represents the process of finding contact info for the potential recipient. In a real implementation,
    this might be automated as a lookup in a database of contacts, or a prompt for a human to find contact info. In
    our stub implementation, this node succeeds with a probability of 3/4.
    """,
)


# check if the potential recipient is in the RM.START state
RcptNotInQrmS = fuzzer(
    AlmostAlwaysSucceed,
    "RcptNotInQrmS",
    """This condition is used to check if the potential recipient is in the RM.START state, indicating that they have
    not been notified yet. In a real implementation, this might be a simple check to see if the potential recipient
    is in the RM.START state. In our stub implementation, this condition only fails in 1 out of 10 attempts.
    """,
)


# set the potential recipient's state to RM.RECEIVED
SetRcptQrmR = fuzzer(
    AlwaysSucceed,
    "SetRcptQrmR",
    """This node represents the process of setting the potential recipient's state to RM.RECEIVED.
    In a real implementation, this might be automated as a simple state transition from RM.START to RM.RECEIVED.
    In our stub implementation, this node always succeeds.
    """,
)


# check effort against some threshold or ask a human
TotalEffortLimitMet = fuzzer(
    AlmostAlwaysFail,
    "TotalEffortLimitMet",
    """This condition is used to check if the total effort expended to notify all recipients has exceeded some
    threshold. In a real implementation, this could be a simple check to see if the total effort expended to notify
    all recipients has exceeded some threshold. For example, an organization might have a policy that no more than 20
    hours of effort should be expended to notify all recipients. It may also be left up to the discretion of the
    analyst to determine if the total effort expended to notify all recipients has exceeded some threshold. In our
    stub implementation, this condition fails in 9 out of 10 attempts.
    """,
)


HaveReportToOthersCapability = fuzzer(
    UsuallySucceed,
    "HaveReportToOthersCapability",
    """
    This node represents the ability to report to others. In a real implementation, it would be replaced
    with a capability check.
    """,
)


MoreVendors = fuzzer(
    UsuallyFail,
    "MoreVendors",
    """
    This condition is used to check if there are more vendors to notify. In a real implementation, this could be a
    query to a database of vendors. In our stub implementation, this condition fails stochastically.
    """,
)


MoreCoordinators = fuzzer(
    AlmostAlwaysFail,
    "MoreCoordinators",
    """
        This condition is used to check if there are more coordinators to notify. In a real implementation, this could be a
        query to a database of coordinators. In our stub implementation, this condition fails stochastically.
        """,
)


MoreOthers = fuzzer(
    AlmostAlwaysFail,
    "MoreOthers",
    """
    This condition is used to check if there are more other parties to notify. In a real implementation, this could be a
    query to a database of other parties. In our stub implementation, this condition fails stochastically.
    """,
)

InjectParticipant = fuzzer(
    AlwaysSucceed,
    "InjectParticipant",
    """
    Inject a participant into a case.
    """,
)

InjectVendor = fuzzer(
    InjectParticipant,
    "InjectVendor",
    InjectParticipant.__doc__,
)

InjectCoordinator = fuzzer(
    InjectParticipant,
    "InjectCoordinator",
    InjectParticipant.__doc__,
)

InjectOther = fuzzer(
    InjectParticipant,
    "InjectOther",
    InjectParticipant.__doc__,
)
