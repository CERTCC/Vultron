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
"""Fix deployment behavior tree composition.

This module provides :func:`create_deploy_fix_tree`, which composes the full
fix-deployment workflow as a ``DeployFixBT`` Fallback:

.. code-block:: text

    DeployFixBT (Fallback)
    ├─ CSinStateFixDeployed                 # short-circuit: fix already deployed
    ├─ _ShouldStayInRmDeferred (Sequence)
    │  ├─ RMinStateDeferred
    │  └─ CheckNoNewDeploymentInfoNode
    ├─ _DeployFixIfReady (Sequence)
    │  ├─ CheckDeployerRoleNode
    │  ├─ CheckRMStateAccepted
    │  ├─ CheckCSFixNotYetDeployed
    │  ├─ <PrioritizeDeployment call-out>   # Evaluator, injected
    │  ├─ <DeployFix call-out>              # Evaluator, injected
    │  ├─ TransitionCStoFixDeployed
    │  └─ EmitCDActivity
    └─ _MonitorDeploymentIfDesired (Sequence)
       ├─ <MonitoringRequirement call-out>  # Evaluator, injected
       └─ <MonitorDeployment call-out>      # Actuator, injected

This replaces the Phase 1 stub (PR #1357) which exposed the call-out points in
a flat Sequence with no guard nodes (Concern #1813).

Call-out injection seams (ADR-0025 / BT-18-004)
-----------------------------------------------
Four factories on :class:`DeployFixCallOutBundle`:

- **PrioritizeDeployment** — ``prioritize_deployment_factory`` (Evaluator,
  p=0.90 → AlwaysSucceed)
- **DeployFix** — ``deploy_fix_factory`` (Evaluator, p=0.10 → AlwaysFail)
- **MonitoringRequirement** — ``monitoring_requirement_factory`` (Evaluator,
  p=0.70 → AlwaysSucceed)
- **MonitorDeployment** — ``monitor_deployment_factory`` (Actuator,
  p=1.0 → AlwaysSucceed)

References
----------
- Issue: #1825
- Source Idea: #1248
- Concern: #1813 (Phase 1 stub missing guard nodes)
- ADR-0025: ``docs/adr/0025-call-out-point-abstraction-layer.md``
- Spec: ``specs/behavior-tree-integration.yaml`` BT-06-001, BT-18-004
- Notes: ``notes/bt-fuzzer-rm-fix.md``
"""

import logging
from typing import TYPE_CHECKING

import py_trees

from vultron.core.behaviors.report.nodes.deploy_fix import (
    CheckCSFixNotYetDeployed,
    CheckNoNewDeploymentInfoNode,
    CSinStateFixDeployed,
    EmitCDActivity,
    RMinStateDeferred,
    TransitionCStoFixDeployed,
)
from vultron.core.behaviors.case.nodes.vfd_role_guards import (
    CheckDeployerRoleNode,
)
from vultron.core.behaviors.report.nodes.conditions import (
    CheckRMStateAccepted,
)

if TYPE_CHECKING:
    from vultron.core.behaviors.call_out.bundles.deploy_fix import (
        DeployFixCallOutBundle,
    )

logger = logging.getLogger(__name__)


def create_deploy_fix_tree(
    case_id: str,
    actor_id: str,
    call_out: "DeployFixCallOutBundle | None" = None,
) -> py_trees.behaviour.Behaviour:
    """Create behavior tree for the fix deployment workflow.

    Mirrors the legacy ``Deployment`` Fallback from
    ``vultron/bt/report_management/_behaviors/deploy_fix.py`` with all guards
    and protocol-action nodes implemented as production-layer ``py_trees``
    nodes.  Replaces the Phase 1 stub (PR #1357) that lacked guard nodes
    (Concern #1813).

    The tree short-circuits (returns SUCCESS) when the fix is already deployed
    or when a deferred deployer has no new deployment information.  Deployers
    whose RM state is ACCEPTED and whose fix is not yet deployed proceed
    through the ``_DeployFixIfReady`` Sequence.

    Call-out injection seams (ADR-0025 / BT-18-004):

    - ``PrioritizeDeployment`` — ``prioritize_deployment_factory``
    - ``DeployFix`` — ``deploy_fix_factory``
    - ``MonitoringRequirement`` — ``monitoring_requirement_factory``
    - ``MonitorDeployment`` — ``monitor_deployment_factory``

    Args:
        case_id: ID of VulnerabilityCase being processed.
        actor_id: ID of the actor running this tree.
        call_out: Bundle of call-out backend factories for this domain.
            Defaults to
            :data:`~vultron.core.behaviors.call_out.bundles.deploy_fix.DEPLOY_FIX_DETERMINISTIC`
            (BT-23-003, BT-23-005).

    Returns:
        Root node of the deploy-fix behavior tree (Fallback).
    """
    from vultron.core.behaviors.call_out.bundles.deploy_fix import (
        DEPLOY_FIX_DETERMINISTIC,
    )

    bundle = call_out if call_out is not None else DEPLOY_FIX_DETERMINISTIC

    result_out: dict = {}

    should_stay_deferred = py_trees.composites.Sequence(
        name="_ShouldStayInRmDeferred",
        memory=False,
        children=[
            RMinStateDeferred(case_id=case_id, actor_id=actor_id),
            CheckNoNewDeploymentInfoNode(),
        ],
    )

    deploy_fix_if_ready = py_trees.composites.Sequence(
        name="_DeployFixIfReady",
        memory=False,
        children=[
            CheckDeployerRoleNode(case_id=case_id, actor_id=actor_id),
            CheckRMStateAccepted(case_id=case_id, actor_id=actor_id),
            CheckCSFixNotYetDeployed(case_id=case_id, actor_id=actor_id),
            bundle.prioritize_deployment_factory("PrioritizeDeployment"),
            bundle.deploy_fix_factory("DeployFix"),
            TransitionCStoFixDeployed(
                case_id=case_id, actor_id=actor_id, result_out=result_out
            ),
            EmitCDActivity(
                case_id=case_id, actor_id=actor_id, result_out=result_out
            ),
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
        name="DeployFixBT",
        memory=False,
        children=[
            CSinStateFixDeployed(case_id=case_id, actor_id=actor_id),
            should_stay_deferred,
            deploy_fix_if_ready,
            monitor_deployment_if_desired,
        ],
    )

    logger.info("Created DeployFixBT for case=%s actor=%s", case_id, actor_id)
    return root
