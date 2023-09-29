#!/usr/bin/env python
"""file: deployment
author: adh
created_at: 6/23/22 2:29 PM
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


from vultron.bt.base.composites import FallbackNode, SequenceNode
from vultron.bt.case_state.conditions import (
    CSinStateFixDeployed,
    CSinStateNotDeployedButPublicAware,
    CSinStateVendorAwareFixReadyFixNotDeployed,
)
from vultron.bt.case_state.transitions import q_cs_to_D
from vultron.bt.messaging.outbound.behaviors import EmitCD, EmitRA, EmitRD
from vultron.bt.report_management.conditions import (
    RMinStateAccepted,
    RMinStateDeferred,
)
from vultron.bt.report_management.fuzzer.deploy_fix import (
    DeployFix,
    DeployMitigation,
    MitigationAvailable,
    MitigationDeployed,
    MonitorDeployment,
    MonitoringRequirement,
    NoNewDeploymentInfo,
    PrioritizeDeployment,
)
from vultron.bt.report_management.transitions import (
    q_rm_to_A,
    q_rm_to_D,
)
from vultron.bt.roles.conditions import RoleIsDeployer, RoleIsVendor


class ShouldStayInRmDeferred(SequenceNode):
    """This node represents the process of deciding whether to stay in the RMDeferred state.
    It starts with a check that the report is in the DEFERRED state.
    Then it checks if there is new deployment information.
    If there is new info, it may be appropriate to reevaluate the deployment priority.
    """

    _children = (RMinStateDeferred, NoNewDeploymentInfo)


class DecideToAcceptDeploymentTasking(SequenceNode):
    """This node represents the process of deciding whether to accept a deployment tasking.
    Steps:
    1. Determine the priority of the deployment tasking.
    2. Transition to the ACCEPTED state (from the deplyer's perspective).
    3. Emit a RA message indicating that the deployment tasking has been accepted.
    If all of these steps succeed, then the deployment tasking is accepted.
    If any of these steps fail, then the deployment tasking is not accepted.
    """

    _children = (PrioritizeDeployment, q_rm_to_A, EmitRA)


class DeferDeploymentTasking(SequenceNode):
    """This node represents the process of deferring a deployment tasking.
    Steps:
    1. Transition to the DEFERRED state (from the deplyer's perspective).
    2. Emit a RD message indicating that the deployment tasking has been deferred.
    If all of these steps succeed, then the deployment tasking is deferred.
    If any of these steps fail, then the deployment tasking is not deferred.
    """

    _children = (q_rm_to_D, EmitRD)


class DecideWhetherToDeploy(FallbackNode):
    """This node represents the process of deciding whether to deploy a fix.
    If the deployment task has already been prioritized, then the deployer's RM state
    will be either ACCEPTED or DEFERRED state and there is no need to reevaluate the deployment priority.
    If the deployment task has not been prioritized, then the deployer needs to decide the priority.
    If the deployment tasking is not explicitly accepted, then it is implicitly deferred.
    """

    _children = (
        RMinStateDeferred,
        RMinStateAccepted,
        DecideToAcceptDeploymentTasking,
        DeferDeploymentTasking,
    )


class DecideAbilityToDeploy(FallbackNode):
    """This node represents the process of deciding whether the deployer is able to deploy a fix.
    There are two possible success conditions:
    1. The deployer is the vendor and can deploy a fix as soon as it is ready.
    2. The deployer is not the vendor and can deploy a fix only after it has been made public.
    If neither of these conditions is met, then the deployer is not able to deploy a fix and the node fails.
    """

    _children = (RoleIsVendor, CSinStateNotDeployedButPublicAware)


class DeployFixWhenReady(SequenceNode):
    """This node represents the process of deploying a fix.
    Steps:
    1. Determine whether the deployer is able to deploy a fix.
    2. Determine whether there is a fix availble to deploy.
    3. Deploy the fix.
    4. Transition to the FixDeployed state.
    5. Emit a CD message indicating that the fix has been deployed.
    """

    _children = (
        DecideAbilityToDeploy,
        CSinStateVendorAwareFixReadyFixNotDeployed,
        DeployFix,
        q_cs_to_D,
        EmitCD,
    )


class DeployMitigationWhenReady(SequenceNode):
    """This node represents the process of deploying a mitigation.
    Note that a mitigation is not a fix and may not be a complete solution.
    However, it may be the best solution available at the time and may be deployed prior to a fix being available.
    Steps:
    1. Determine whether there is a mitigation availble to deploy.
    2. Deploy the mitigation.
    If all of these steps succeed, then the mitigation is deployed.
    If any of these steps fail, then the mitigation is not deployed.
    """

    _children = (MitigationAvailable, DeployMitigation)


class Deploy(FallbackNode):
    """This node represents the process of deploying a fix or mitigation.
    The process short-circuits if the deployer has deferred the deployment tasking.
    It also short-circuits if the deployer has already deployed a fix.
    Otherwise, the deployer will attempt to deploy a fix if one is available.
    If no fix is available, the deployer will attempt to deploy a mitigation if one is available.
    If neither a fix nor a mitigation is available, the node fails.
    """

    _children = (
        RMinStateDeferred,
        CSinStateFixDeployed,
        DeployFixWhenReady,
        MitigationDeployed,
        DeployMitigationWhenReady,
    )


class DeployIfDesired(SequenceNode):
    """This node represents the process of deciding whether to deploy a fix or mitigation.
    It starts by confirming that the actor has the role of deployer.
    Then it checks whether the deployment tasking has been accepted.
    If the deployment tasking has been accepted, then the deployer will attempt to deploy a fix or mitigation.
    """

    _children = (RoleIsDeployer, DecideWhetherToDeploy, Deploy)


class MonitorDeploymentIfDesired(SequenceNode):
    """This node represents the process of deciding whether to monitor a deployment and then monitoring it.
    It starts with a check that the deployment is supposed to be monitored.
    Then it performs the monitoring.
    """

    _children = (MonitoringRequirement, MonitorDeployment)


class Deployment(FallbackNode):
    """This bt represents the process of deploying a fix or mitigation and monitoring the deployment."""

    _children = (
        CSinStateFixDeployed,
        ShouldStayInRmDeferred,
        DeployIfDesired,
        MonitorDeploymentIfDesired,
    )
