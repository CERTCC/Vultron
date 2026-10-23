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
from vultron.bt.base.fuzzer import (
    AlmostAlwaysFail,
    AlmostAlwaysSucceed,
    AlwaysSucceed,
    OftenSucceed,
    UsuallyFail,
    UsuallySucceed,
)

# ask a human or check if the report has been updated
NoNewDeploymentInfo = fuzzer(
    UsuallySucceed,
    "NoNewDeploymentInfo",
    """This condition is used to check if there is new deployment information.
    In most cases, there will be no new deployment information, so this condition will succeed.
    In an actual implementation, it might be possible to automate this node as a condition check
    based on whether or not new deployment information has been added to the report.
    For example, if the report has been updated, then this condition might fail.
    """,
)


# ask a human to prioritize the deployment
PrioritizeDeployment = fuzzer(
    AlmostAlwaysSucceed,
    "PrioritizeDeployment",
    """This node represents the process of prioritizing the deployment of a fix. In an actual implementation,
    this node would likely be implemented as prompt for a human to prioritize the deployment. In our stub
    implementation, this node almost always succeeds with a probability of 0.9 so that we can test the rest of the
    process.
    """,
)


# check the status of the mitigation deployment
MitigationDeployed = fuzzer(
    UsuallyFail,
    "MitigationDeployed",
    """This condition is used to check if a mitigation has been deployed. In an actual implementation,
    this condition could be a simple status check on the case.
    In our stub implementation, this condition fails with a probability of 3/4.
    """,
)


# check whether mitigations are available to deploy
MitigationAvailable = fuzzer(
    OftenSucceed,
    "MitigationAvailable",
    """This condition is used to check if a mitigation is available. In an actual implementation, this condition could
    be a simple status check on the case after mitigation options have been evaluated.
    """,
)


# prompt a human to deploy a mitigation
DeployMitigation = fuzzer(
    UsuallySucceed,
    "DeployMitigation",
    """This node represents the process of deploying a mitigation. In an actual implementation,
    this node would likely be implemented as a prompt for a human to deploy a mitigation. In our stub
    implementation, this node usually succeeds with a probability of 3/4.
    """,
)


# check whether monitoring is required
MonitoringRequirement = fuzzer(
    OftenSucceed,
    "MonitoringRequirement",
    """This condition is used to check whether it is necessary to monitor the deployment of a fix.
    This is typically a policy decision, so in an actual implementation, this condition would likely be implemented
    a policy check. In our stub implementation, this condition succeeds in 3 of 10 cases.
    """,
)


MonitorDeployment = fuzzer(
    AlwaysSucceed,
    "MonitorDeployment",
    """This node represents the process of monitoring the deployment of a fix. In an actual implementation,
    this node would likely be implemented as a prompt for a human to monitor the deployment.
    In our stub implementation, this node always succeeds.
    """,
)


DeployFix = fuzzer(
    AlmostAlwaysFail,
    "DeployFix",
    """This node represents the process of deploying a fix. In an actual implementation, this node would likely be
    implemented as a prompt for a human to deploy a fix. In our stub implementation, this node almost always fails
    with a probability of 0.9 so that we can test the rest of the process.
    """,
)
