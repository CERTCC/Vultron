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
"""Fix deployment behavior tree composition (Phase 1 stub).

This module provides :func:`create_deploy_fix_tree`, which hosts five
fix-deployment call-out points wired per ADR-0025 / BT-18-004:

Evaluator nodes:
- ``PrioritizeDeployment``
- ``DeployMitigation``
- ``MonitoringRequirement``
- ``DeployFix``

Actuator node:
- ``MonitorDeployment``

Phase 1 contains only the injectable call-out points as a stub Sequence.
The full deployment workflow (no-new-info early exit, mitigation arm,
monitoring arm, fix deployment arm) is deferred to a future issue.

References
----------
- ADR-0025: ``docs/adr/0025-call-out-point-abstraction-layer.md``
- Spec: ``specs/behavior-tree-integration.yaml`` BT-18-004
"""

import logging
from typing import TYPE_CHECKING

import py_trees

if TYPE_CHECKING:
    from vultron.demo.fuzzer.bundles.deploy_fix import DeployFixCallOutBundle

logger = logging.getLogger(__name__)


def create_deploy_fix_tree(
    case_id: str,
    call_out: "DeployFixCallOutBundle | None" = None,
) -> py_trees.behaviour.Behaviour:
    """Create behavior tree for the fix deployment workflow (Phase 1 stub).

    Phase 1 exposes the four Evaluator call-out points and the MonitorDeployment
    Actuator as a stub Sequence.  The full workflow (no-new-info early exit,
    mitigation arm, monitoring arm, fix deployment arm) is deferred to a
    future issue.

    Args:
        case_id: ID of VulnerabilityCase being processed.
        call_out: Bundle of call-out backend factories for this domain.
            Defaults to :data:`~vultron.demo.fuzzer.bundles.deploy_fix.DEPLOY_FIX_DETERMINISTIC`
            (BT-23-003, BT-23-005).

    Returns:
        Root node of the deploy-fix behavior tree (Phase 1 stub Sequence).
    """
    from vultron.demo.fuzzer.bundles.deploy_fix import DEPLOY_FIX_DETERMINISTIC

    bundle = call_out if call_out is not None else DEPLOY_FIX_DETERMINISTIC
    root = py_trees.composites.Sequence(
        name="DeployFixBT",
        memory=False,
        children=[
            bundle.prioritize_deployment_factory("PrioritizeDeployment"),
            bundle.deploy_mitigation_factory("DeployMitigation"),
            bundle.monitoring_requirement_factory("MonitoringRequirement"),
            bundle.deploy_fix_factory("DeployFix"),
            bundle.monitor_deployment_factory("MonitorDeployment"),
        ],
    )
    logger.info(f"Created DeployFixBT (Phase 1 stub) for case={case_id}")
    return root
