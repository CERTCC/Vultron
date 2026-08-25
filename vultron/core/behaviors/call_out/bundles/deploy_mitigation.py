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
"""Call-out bundle for the mitigation deployment domain (BT-20-005, BT-23-003).

Provides :class:`DeployMitigationCallOutBundle` and the pre-built core
DETERMINISTIC singleton :data:`DEPLOY_MITIGATION_DETERMINISTIC`.  The matching
STOCHASTIC singleton lives in the simulation layer
(:data:`vultron.demo.fuzzer.bundles.deploy_mitigation.DEPLOY_MITIGATION_STOCHASTIC`).

:class:`DeployMitigationCallOutBundle` inherits the three shared monitoring
fields from
:class:`~vultron.core.behaviors.call_out.bundles.deploy_monitoring.DeploymentMonitoringBundle`
and adds three mitigation-specific fields.

Ceiling/floor mapping (BT-23-002):

- ``prioritize_deployment_factory``  — PrioritizeDeployment  (p=0.90) → AlwaysSucceed  (inherited)
- ``monitoring_requirement_factory`` — MonitoringRequirement (p=0.70) → AlwaysSucceed  (inherited)
- ``monitor_deployment_factory``     — MonitorDeployment     (p=1.00) → AlwaysSucceed  (inherited)
- ``mitigation_deployed_factory``    — MitigationDeployed    (p=0.25) → AlwaysFail
- ``mitigation_available_factory``   — MitigationAvailable   (p=0.70) → AlwaysSucceed
- ``deploy_mitigation_factory``      — DeployMitigation      (p=0.75) → AlwaysSucceed
"""

from __future__ import annotations

from dataclasses import dataclass, field

import py_trees

from vultron.core.behaviors.call_out.bundles.deploy_monitoring import (
    DeploymentMonitoringBundle,
)
from vultron.core.behaviors.call_out.nodes import AlwaysFail, AlwaysSucceed
from vultron.core.behaviors.call_out.protocol import CallOutBackendFactory


def _always_fail(name: str) -> py_trees.behaviour.Behaviour:
    return AlwaysFail(name)


def _always_succeed(name: str) -> py_trees.behaviour.Behaviour:
    return AlwaysSucceed(name)


@dataclass(frozen=True)
class DeployMitigationCallOutBundle(DeploymentMonitoringBundle):
    """Call-out backend bundle for the mitigation deployment domain (BT-20-005).

    Inherits the three shared monitoring fields from
    :class:`~vultron.core.behaviors.call_out.bundles.deploy_monitoring.DeploymentMonitoringBundle`
    and adds three mitigation-specific fields.

    Fields map to the corresponding factory parameters on
    ``create_deploy_mitigation_tree``.
    """

    mitigation_deployed_factory: CallOutBackendFactory = field(
        default=_always_fail  # type: ignore[assignment]
    )
    mitigation_available_factory: CallOutBackendFactory = field(
        default=_always_succeed  # type: ignore[assignment]
    )
    deploy_mitigation_factory: CallOutBackendFactory = field(
        default=_always_succeed  # type: ignore[assignment]
    )


DEPLOY_MITIGATION_DETERMINISTIC = DeployMitigationCallOutBundle()
"""Deterministic bundle: ceiling/floor of stochastic p (BT-23-001, BT-23-002)."""

__all__ = [
    "DeployMitigationCallOutBundle",
    "DEPLOY_MITIGATION_DETERMINISTIC",
]
