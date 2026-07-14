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

import py_trees

from vultron.core.behaviors.call_out_point import CallOutBackendFactory

logger = logging.getLogger(__name__)


def _default_prioritize_deployment_factory(
    name: str,
) -> py_trees.behaviour.Behaviour:
    from vultron.demo.fuzzer.report_management.deploy_fix import (
        PrioritizeDeployment,
    )

    return PrioritizeDeployment(name)


def _default_deploy_mitigation_factory(
    name: str,
) -> py_trees.behaviour.Behaviour:
    from vultron.demo.fuzzer.report_management.deploy_fix import (
        DeployMitigation,
    )

    return DeployMitigation(name)


def _default_monitoring_requirement_factory(
    name: str,
) -> py_trees.behaviour.Behaviour:
    from vultron.demo.fuzzer.report_management.deploy_fix import (
        MonitoringRequirement,
    )

    return MonitoringRequirement(name)


def _default_deploy_fix_factory(name: str) -> py_trees.behaviour.Behaviour:
    from vultron.demo.fuzzer.report_management.deploy_fix import DeployFix

    return DeployFix(name)


def _default_monitor_deployment_factory(
    name: str,
) -> py_trees.behaviour.Behaviour:
    from vultron.demo.fuzzer.report_management.deploy_fix import (
        MonitorDeployment,
    )

    return MonitorDeployment(name)


def create_deploy_fix_tree(
    case_id: str,
    prioritize_deployment_factory: CallOutBackendFactory = _default_prioritize_deployment_factory,
    deploy_mitigation_factory: CallOutBackendFactory = _default_deploy_mitigation_factory,
    monitoring_requirement_factory: CallOutBackendFactory = _default_monitoring_requirement_factory,
    deploy_fix_factory: CallOutBackendFactory = _default_deploy_fix_factory,
    monitor_deployment_factory: CallOutBackendFactory = _default_monitor_deployment_factory,
) -> py_trees.behaviour.Behaviour:
    """Create behavior tree for the fix deployment workflow (Phase 1 stub).

    Phase 1 exposes the four Evaluator call-out points and the MonitorDeployment
    Actuator as a stub Sequence.  The full workflow (no-new-info early exit,
    mitigation arm, monitoring arm, fix deployment arm) is deferred to a
    future issue.

    Args:
        case_id: ID of VulnerabilityCase being processed.
        prioritize_deployment_factory: Factory for the Evaluator call-out point
            that assigns deployment priority.  Defaults to the fuzzer backend
            (BT-18-004).
        deploy_mitigation_factory: Factory for the Evaluator call-out point
            that deploys an interim mitigation.  Defaults to the fuzzer backend
            (BT-18-004).
        monitoring_requirement_factory: Factory for the Evaluator call-out
            point that checks whether deployment monitoring is required by
            policy.  Defaults to the fuzzer backend (BT-18-004).
        deploy_fix_factory: Factory for the Evaluator call-out point that
            applies the vendor-provided fix.  Defaults to the fuzzer backend
            (BT-18-004).
        monitor_deployment_factory: Factory for the Actuator call-out point
            that performs active deployment monitoring.  Defaults to the fuzzer
            backend (BT-18-004).

    Returns:
        Root node of the deploy-fix behavior tree (Phase 1 stub Sequence).
    """
    root = py_trees.composites.Sequence(
        name="DeployFixBT",
        memory=False,
        children=[
            prioritize_deployment_factory("PrioritizeDeployment"),
            deploy_mitigation_factory("DeployMitigation"),
            monitoring_requirement_factory("MonitoringRequirement"),
            deploy_fix_factory("DeployFix"),
            monitor_deployment_factory("MonitorDeployment"),
        ],
    )
    logger.info(f"Created DeployFixBT (Phase 1 stub) for case={case_id}")
    return root
