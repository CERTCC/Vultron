#!/usr/bin/env python
#  Copyright (c) 2026 Carnegie Mellon University and Contributors.
#  - see Contributors.md for a full list of Contributors
#  - see ContributionInstructions.md for information on how you can Contribute to this project
#  Vultron Multiparty Coordinated Vulnerability Disclosure Protocol Prototype is
#  licensed under a MIT (SEI)-style license, please see LICENSE.md distributed
#  with this Software or contact permission@sei.cmu.edu for full terms.
#  Created, in part, with funding and support from the United States Government
#  (see Acknowledgments file). This program may include and/or can make use of
#  certain third party source code, object code, documentation and other files
#  ("Third Party Software"). See LICENSE.md for more details.
#  Carnegie Mellon®, CERT® and CERT Coordination Center® are registered in the
#  U.S. Patent and Trademark Office by Carnegie Mellon University
"""Mitigation deployment behavior tree composition.

This module provides :func:`create_deploy_mitigation_tree`, which composes the
full mitigation-deployment workflow as a ``DeployMitigationBT`` Fallback:

.. code-block:: text

    DeployMitigationBT (Fallback)
    ├─ <MitigationDeployed call-out>        # Retriever, injected
    ├─ _ShouldStayInRmDeferred (Sequence)
    │  ├─ RMinStateDeferred
    │  └─ CheckNoNewDeploymentInfoNode
    ├─ _DeployMitigationIfAvailable (Sequence)
    │  ├─ CheckDeployerRoleNode
    │  ├─ CheckRMStateAccepted
    │  ├─ <MitigationAvailable call-out>    # Retriever, injected
    │  ├─ <PrioritizeDeployment call-out>   # Evaluator, injected
    │  └─ <DeployMitigation call-out>       # Evaluator, injected
    └─ _MonitorDeploymentIfDesired (Sequence)
       ├─ <MonitoringRequirement call-out>  # Evaluator, injected
       └─ <MonitorDeployment call-out>      # Actuator, injected

Unlike the fix-deployment tree, there is no CS state bit for mitigation and no
dedicated protocol message type — so no ``TransitionCS`` or ``EmitActivity``
production nodes are needed.  All three mitigation-specific arms use call-out
injection seams only.

Call-out injection seams (ADR-0025 / BT-18-004)
-----------------------------------------------
Six factories on :class:`DeployMitigationCallOutBundle`:

- **MitigationDeployed** — ``mitigation_deployed_factory`` (Retriever,
  p=0.25 → AlwaysFail)
- **MitigationAvailable** — ``mitigation_available_factory`` (Retriever,
  p=0.70 → AlwaysSucceed)
- **PrioritizeDeployment** — ``prioritize_deployment_factory`` (Evaluator,
  p=0.90 → AlwaysSucceed)
- **DeployMitigation** — ``deploy_mitigation_factory`` (Evaluator,
  p=0.75 → AlwaysSucceed)
- **MonitoringRequirement** — ``monitoring_requirement_factory`` (Evaluator,
  p=0.70 → AlwaysSucceed)
- **MonitorDeployment** — ``monitor_deployment_factory`` (Actuator,
  p=1.0 → AlwaysSucceed)

References
----------
- Issue: #1954
- Spec: ``specs/behavior-tree-integration.yaml`` BT-20-005
- Notes: ``notes/bt-fuzzer-rm-fix.md``
- ADR-0025: ``docs/adr/0025-call-out-point-abstraction-layer.md``
"""

import logging
from typing import TYPE_CHECKING

import py_trees

from vultron.core.behaviors.case.nodes.vfd_role_guards import (
    CheckDeployerRoleNode,
)
from vultron.core.behaviors.report.nodes.deploy_fix import (
    CheckNoNewDeploymentInfoNode,
    RMinStateDeferred,
)
from vultron.core.behaviors.report.nodes.develop_fix import (
    CheckRMStateAccepted,
)

if TYPE_CHECKING:
    from vultron.core.behaviors.call_out.bundles.deploy_mitigation import (
        DeployMitigationCallOutBundle,
    )

logger = logging.getLogger(__name__)


def create_deploy_mitigation_tree(
    case_id: str,
    actor_id: str,
    call_out: "DeployMitigationCallOutBundle | None" = None,
) -> py_trees.behaviour.Behaviour:
    """Create behavior tree for the mitigation deployment workflow.

    The tree short-circuits (returns SUCCESS) when mitigation is already
    deployed or when a deferred deployer has no new deployment information.
    Deployers whose RM state is ACCEPTED proceed through the
    ``_DeployMitigationIfAvailable`` Sequence.

    No CS state transition or protocol message is emitted — mitigation has no
    CS state bit and no dedicated message type in the 29-message set (BT-20-005).

    Call-out injection seams (ADR-0025 / BT-18-004):

    - ``MitigationDeployed`` — ``mitigation_deployed_factory``
    - ``MitigationAvailable`` — ``mitigation_available_factory``
    - ``PrioritizeDeployment`` — ``prioritize_deployment_factory``
    - ``DeployMitigation`` — ``deploy_mitigation_factory``
    - ``MonitoringRequirement`` — ``monitoring_requirement_factory``
    - ``MonitorDeployment`` — ``monitor_deployment_factory``

    Args:
        case_id: ID of VulnerabilityCase being processed.
        actor_id: ID of the actor running this tree.
        call_out: Bundle of call-out backend factories for this domain.
            Defaults to
            :data:`~vultron.core.behaviors.call_out.bundles.deploy_mitigation.DEPLOY_MITIGATION_DETERMINISTIC`
            (BT-23-001, BT-23-002).

    Returns:
        Root node of the deploy-mitigation behavior tree (Fallback).
    """
    from vultron.core.behaviors.call_out.bundles.deploy_mitigation import (
        DEPLOY_MITIGATION_DETERMINISTIC,
    )

    bundle = (
        call_out if call_out is not None else DEPLOY_MITIGATION_DETERMINISTIC
    )

    should_stay_deferred = py_trees.composites.Sequence(
        name="_ShouldStayInRmDeferred",
        memory=False,
        children=[
            RMinStateDeferred(case_id=case_id, actor_id=actor_id),
            CheckNoNewDeploymentInfoNode(),
        ],
    )

    deploy_mitigation_if_available = py_trees.composites.Sequence(
        name="_DeployMitigationIfAvailable",
        memory=False,
        children=[
            CheckDeployerRoleNode(case_id=case_id, actor_id=actor_id),
            CheckRMStateAccepted(case_id=case_id, actor_id=actor_id),
            bundle.mitigation_available_factory("MitigationAvailable"),
            bundle.prioritize_deployment_factory("PrioritizeDeployment"),
            bundle.deploy_mitigation_factory("DeployMitigation"),
        ],
    )

    monitor_deployment_if_desired = py_trees.composites.Sequence(
        name="_MonitorDeploymentIfDesired",
        memory=False,
        children=[
            bundle.monitoring_requirement_factory("MonitoringRequirement"),
            bundle.monitor_deployment_factory("MonitorDeployment"),
        ],
    )

    root = py_trees.composites.Selector(
        name="DeployMitigationBT",
        memory=False,
        children=[
            bundle.mitigation_deployed_factory("MitigationDeployed"),
            should_stay_deferred,
            deploy_mitigation_if_available,
            monitor_deployment_if_desired,
        ],
    )

    logger.info(
        "Created DeployMitigationBT for case=%s actor=%s", case_id, actor_id
    )
    return root
