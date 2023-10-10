#!/usr/bin/env python
"""file: notify_others
author: adh
created_at: 2/21/23 2:03 PM

This module provides fuzzer leaf nodes in support of the process of notifying other parties of the report/case
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
from vultron.bt.base.fuzzer import AlmostAlwaysFail, AlwaysSucceed, UsuallyFail


class AllPartiesKnown(btz.UniformSucceedFail):
    """This condition is used to check if all parties that should be involved in the report have been identified.
    In an actual implementation, this condition would likely be implemented as a human decision.
    In our stub implementation, this condition succeeds with a probability of 0.5.
    """


class IdentifyVendors(btz.SuccessOrRunning):
    """This node represents the process of identifying vendors that should be involved in the report.
    In an actual implementation, this node would likely be implemented as prompt for a human to identify vendors.
    In our stub implementation, this node succeeds with a probability of 0.5.
    """

    # prompt for a human to identify vendors


class IdentifyCoordinators(btz.SuccessOrRunning):
    """This node represents the process of identifying coordinators that should be involved in the report.
    In an actual implementation, this node would likely be implemented as prompt for a human to identify coordinators.
    In our stub implementation, this node succeeds with a probability of 0.5.
    """

    # prompt for a human to identify coordinators


class IdentifyOthers(btz.AlwaysSucceed):
    """This node represents the process of identifying other parties that should be involved in the report.
    In an actual implementation, this node would likely be implemented as prompt for a human to identify other parties.
    In our stub implementation, this node always succeeds.
    """

    # prompt for a human to identify other parties


class NotificationsComplete(btz.UniformSucceedFail):
    """This condition is used to check if all notifications have been sent. In an actual implementation, this condition
    could be a simple check to see if all identified parties have been notified. In our stub implementation,
    this condition succeeds with a probability of 0.5.
    """

    # check if all identified parties have been notified


class ChooseRecipient(btz.AlwaysSucceed):
    """This node represents the process of choosing a recipient for the notification. In a real implementation,
    this could be fully automated by choosing a recipient to notify from a list of identified parties. In our stub
    implementation, this node always succeeds so that we can exercise the rest of the workflow.
    """

    # choose a recipient from a list of identified parties


class RemoveRecipient(btz.AlwaysSucceed):
    """This node represents the process of removing a recipient from the list of identified parties. In a real
    implementation, this could be fully automated by removing a recipient from the list of identified parties based
    on some criteria. In our stub implementation, this node always succeeds so that we can exercise the rest of the
    workflow.
    """

    # remove a recipient from the list of identified parties


class RecipientEffortExceeded(btz.AlmostCertainlyFail):
    """This condition is used to check if the effort expended to notify a recipient has exceeded some threshold. In a
    real implementation, this could be a simple check to see if the effort expended to notify a recipient has
    exceeded some threshold. For example, an organization might have a policy that no more than 3 attempts should be
    made to notify a recipient. Alternatively, an organization might have a policy that no more than 1 hour of effort
    should be expended to notify a recipient. It may also be left up to the discretion of the analyst to determine if
    the effort expended to notify a recipient has exceeded some threshold. In our stub implementation, this condition
    only succeeds in 7 out of 100 attempts.
    """

    # check effort against some threshold or ask a human


class PolicyCompatible(btz.ProbablySucceed):
    """This node represents the process to see if the potential recipient's embargo policy is compatible with the
    expectations set out in the case. In a real implementation, this might be automated as a comparison between the
    intended recipient's embargo policy and the policy associated with the case. Alternatively, this might be a
    prompt for a human to determine if the potential recipient's embargo policy is compatible with the case. In our
    stub implementation, this node succeeds with a probability of 2/3.
    """

    # compare the intended recipient's embargo policy with the policy associated with the case or ask a human


class FindContact(btz.UsuallySucceed):
    """This node represents the process of finding contact info for the potential recipient. In a real implementation,
    this might be automated as a lookup in a database of contacts, or a prompt for a human to find contact info. In
    our stub implementation, this node succeeds with a probability of 3/4.
    """

    # lookup contact info in a database or ask a human


class RcptNotInQrmS(btz.AlmostAlwaysSucceed):
    """This condition is used to check if the potential recipient is in the RM.START state, indicating that they have
    not been notified yet. In a real implementation, this might be a simple check to see if the potential recipient
    is in the RM.START state. In our stub implementation, this condition only fails in 1 out of 10 attempts.
    """

    # check if the potential recipient is in the RM.START state


class SetRcptQrmR(btz.AlwaysSucceed):
    """This node represents the process of setting the potential recipient's state to RM.RECEIVED.
    In a real implementation, this might be automated as a simple state transition from RM.START to RM.RECEIVED.
    In our stub implementation, this node always succeeds.
    """

    # set the potential recipient's state to RM.RECEIVED


class TotalEffortLimitMet(btz.AlmostAlwaysFail):
    """This condition is used to check if the total effort expended to notify all recipients has exceeded some
    threshold. In a real implementation, this could be a simple check to see if the total effort expended to notify
    all recipients has exceeded some threshold. For example, an organization might have a policy that no more than 20
    hours of effort should be expended to notify all recipients. It may also be left up to the discretion of the
    analyst to determine if the total effort expended to notify all recipients has exceeded some threshold. In our
    stub implementation, this condition fails in 9 out of 10 attempts.
    """

    # check effort against some threshold or ask a human


class HaveReportToOthersCapability(btz.UsuallySucceed):
    """
    This node represents the ability to report to others. In a real implementation, it would be replaced
    with a capability check.
    """


class InjectParticipant(AlwaysSucceed):
    pass


class MoreVendors(UsuallyFail):
    pass


class MoreCoordinators(AlmostAlwaysFail):
    pass


class MoreOthers(AlmostAlwaysFail):
    pass


class InjectVendor(InjectParticipant):
    participant_type = "Vendor"


class InjectCoordinator(InjectParticipant):
    participant_type = "Coordinator"


class InjectOther(InjectParticipant):
    participant_type = "Participant"
