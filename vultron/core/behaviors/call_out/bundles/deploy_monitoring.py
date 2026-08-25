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
"""Shared base call-out bundle for deployment-monitoring domains (BT-23-002).

Provides :class:`DeploymentMonitoringBundle`, a frozen ``@dataclass`` base
with the three call-out factory fields shared between fix deployment
(:class:`~vultron.core.behaviors.call_out.bundles.deploy_fix.DeployFixCallOutBundle`)
and mitigation deployment
(:class:`~vultron.core.behaviors.call_out.bundles.deploy_mitigation.DeployMitigationCallOutBundle`):

- ``prioritize_deployment_factory``  — PrioritizeDeployment  (p=0.90) → AlwaysSucceed
- ``monitoring_requirement_factory`` — MonitoringRequirement (p=0.70) → AlwaysSucceed
- ``monitor_deployment_factory``     — MonitorDeployment     (p=1.00) → AlwaysSucceed
"""

from __future__ import annotations

from dataclasses import dataclass, field

import py_trees

from vultron.core.behaviors.call_out.nodes import AlwaysSucceed
from vultron.core.behaviors.call_out.protocol import CallOutBackendFactory


def _always_succeed(name: str) -> py_trees.behaviour.Behaviour:
    return AlwaysSucceed(name)


@dataclass(frozen=True)
class DeploymentMonitoringBundle:
    """Shared call-out fields for deployment-monitoring domains (BT-23-002).

    Base for :class:`~vultron.core.behaviors.call_out.bundles.deploy_fix.DeployFixCallOutBundle`
    and
    :class:`~vultron.core.behaviors.call_out.bundles.deploy_mitigation.DeployMitigationCallOutBundle`.
    """

    prioritize_deployment_factory: CallOutBackendFactory = field(
        default=_always_succeed  # type: ignore[assignment]
    )
    monitoring_requirement_factory: CallOutBackendFactory = field(
        default=_always_succeed  # type: ignore[assignment]
    )
    monitor_deployment_factory: CallOutBackendFactory = field(
        default=_always_succeed  # type: ignore[assignment]
    )


__all__ = [
    "DeploymentMonitoringBundle",
]
