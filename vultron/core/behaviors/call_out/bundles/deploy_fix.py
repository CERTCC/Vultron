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

Provides :class:`DeployFixCallOutBundle` and the pre-built core DETERMINISTIC
singleton :data:`DEPLOY_FIX_DETERMINISTIC`.  The matching STOCHASTIC singleton
lives in the simulation layer
(:data:`vultron.demo.fuzzer.bundles.deploy_fix.DEPLOY_FIX_STOCHASTIC`).

:class:`DeployFixCallOutBundle` inherits the three shared monitoring fields
from :class:`~vultron.core.behaviors.call_out.bundles.deploy_monitoring.DeploymentMonitoringBundle`
and adds ``deploy_fix_factory``.

Ceiling/floor mapping (BT-23-002):

- ``prioritize_deployment_factory``  — PrioritizeDeployment  (p=0.90) → AlwaysSucceed  (inherited)
- ``monitoring_requirement_factory`` — MonitoringRequirement (p=0.70) → AlwaysSucceed  (inherited)
- ``monitor_deployment_factory``     — MonitorDeployment     (p=1.0)  → AlwaysSucceed  (inherited)
- ``deploy_fix_factory``             — DeployFix             (p=0.10) → AlwaysFail

Mitigation deployment (``DeployMitigation``) is scoped OUT of this bundle
(#1248) — it belongs to the distinct ``DeployMitigationCallOutBundle`` peer.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import py_trees

from vultron.core.behaviors.call_out.bundles.deploy_monitoring import (
    DeploymentMonitoringBundle,
)
from vultron.core.behaviors.call_out.nodes import AlwaysFail
from vultron.core.behaviors.call_out.protocol import CallOutBackendFactory


def _always_fail(name: str) -> py_trees.behaviour.Behaviour:
    return AlwaysFail(name)


@dataclass(frozen=True)
class DeployFixCallOutBundle(DeploymentMonitoringBundle):
    """Call-out backend bundle for the fix deployment domain (BT-23-003).

    Inherits the three shared monitoring fields from
    :class:`~vultron.core.behaviors.call_out.bundles.deploy_monitoring.DeploymentMonitoringBundle`
    and adds ``deploy_fix_factory``.

    Fields map to the corresponding factory parameters on
    :func:`~vultron.core.behaviors.report.deploy_fix_tree.create_deploy_fix_tree`.
    """

    deploy_fix_factory: CallOutBackendFactory = field(
        default=_always_fail  # type: ignore[assignment]
    )


DEPLOY_FIX_DETERMINISTIC = DeployFixCallOutBundle()
"""Deterministic bundle: ceiling/floor of stochastic p (BT-23-001, BT-23-002)."""

__all__ = [
    "DeployFixCallOutBundle",
    "DEPLOY_FIX_DETERMINISTIC",
]
