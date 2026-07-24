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
"""Call-out bundle for the fix deployment domain (BT-23-003, BT-23-005).

Provides :class:`DeployFixCallOutBundle` plus the pre-built singletons
:data:`DEPLOY_FIX_DETERMINISTIC` and :data:`DEPLOY_FIX_STOCHASTIC`.

Ceiling/floor mapping (BT-23-002):

- ``prioritize_deployment_factory``  — PrioritizeDeployment  (p=0.90) → AlwaysSucceed
- ``deploy_mitigation_factory``      — DeployMitigation      (p=0.75) → AlwaysSucceed
- ``monitoring_requirement_factory`` — MonitoringRequirement (p=0.70) → AlwaysSucceed
- ``deploy_fix_factory``             — DeployFix             (p=0.10) → AlwaysFail
- ``monitor_deployment_factory``     — MonitorDeployment     (p=1.0) → AlwaysSucceed
"""

from __future__ import annotations

from dataclasses import dataclass, field

import py_trees

from vultron.core.behaviors.call_out_point import CallOutBackendFactory


def _always_succeed(name: str) -> py_trees.behaviour.Behaviour:
    from vultron.demo.fuzzer.base import AlwaysSucceed

    return AlwaysSucceed(name)


def _always_fail(name: str) -> py_trees.behaviour.Behaviour:
    from vultron.demo.fuzzer.base import AlwaysFail

    return AlwaysFail(name)


def _stochastic_prioritize_deployment(
    name: str,
) -> py_trees.behaviour.Behaviour:
    from vultron.demo.fuzzer.report_management.deploy_fix import (
        PrioritizeDeployment,
    )

    return PrioritizeDeployment(name)


def _stochastic_deploy_mitigation(name: str) -> py_trees.behaviour.Behaviour:
    from vultron.demo.fuzzer.report_management.deploy_fix import (
        DeployMitigation,
    )

    return DeployMitigation(name)


def _stochastic_monitoring_requirement(
    name: str,
) -> py_trees.behaviour.Behaviour:
    from vultron.demo.fuzzer.report_management.deploy_fix import (
        MonitoringRequirement,
    )

    return MonitoringRequirement(name)


def _stochastic_deploy_fix(name: str) -> py_trees.behaviour.Behaviour:
    from vultron.demo.fuzzer.report_management.deploy_fix import DeployFix

    return DeployFix(name)


def _stochastic_monitor_deployment(name: str) -> py_trees.behaviour.Behaviour:
    from vultron.demo.fuzzer.report_management.deploy_fix import (
        MonitorDeployment,
    )

    return MonitorDeployment(name)


@dataclass(frozen=True)
class DeployFixCallOutBundle:
    """Call-out backend bundle for the fix deployment domain (BT-23-003).

    Fields map to the corresponding factory parameters on
    :func:`~vultron.core.behaviors.report.deploy_fix_tree.create_deploy_fix_tree`.
    """

    prioritize_deployment_factory: CallOutBackendFactory = field(
        default=_always_succeed  # type: ignore[assignment]
    )
    deploy_mitigation_factory: CallOutBackendFactory = field(
        default=_always_succeed  # type: ignore[assignment]
    )
    monitoring_requirement_factory: CallOutBackendFactory = field(
        default=_always_succeed  # type: ignore[assignment]
    )
    deploy_fix_factory: CallOutBackendFactory = field(
        default=_always_fail  # type: ignore[assignment]
    )
    monitor_deployment_factory: CallOutBackendFactory = field(
        default=_always_succeed  # type: ignore[assignment]
    )


DEPLOY_FIX_DETERMINISTIC = DeployFixCallOutBundle()
"""Deterministic bundle: ceiling/floor of stochastic p (BT-23-001, BT-23-002)."""

DEPLOY_FIX_STOCHASTIC = DeployFixCallOutBundle(
    prioritize_deployment_factory=_stochastic_prioritize_deployment,  # type: ignore[arg-type]
    deploy_mitigation_factory=_stochastic_deploy_mitigation,  # type: ignore[arg-type]
    monitoring_requirement_factory=_stochastic_monitoring_requirement,  # type: ignore[arg-type]
    deploy_fix_factory=_stochastic_deploy_fix,  # type: ignore[arg-type]
    monitor_deployment_factory=_stochastic_monitor_deployment,  # type: ignore[arg-type]
)
"""Stochastic bundle: all nodes use probabilistic fuzzer classes."""

__all__ = [
    "DeployFixCallOutBundle",
    "DEPLOY_FIX_DETERMINISTIC",
    "DEPLOY_FIX_STOCHASTIC",
]
