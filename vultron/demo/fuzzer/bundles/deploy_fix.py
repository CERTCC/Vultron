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
"""STOCHASTIC call-out bundle for the fix deployment domain (BT-23-003, BT-23-005).

Provides the simulation-layer :data:`DEPLOY_FIX_STOCHASTIC` singleton.  The
bundle dataclass and DETERMINISTIC default are core concerns
(``vultron.core.behaviors.call_out.bundles.deploy_fix``) and are re-exported
here for backward-compatible import paths.

Ceiling/floor mapping for the DETERMINISTIC counterpart (BT-23-002):

- ``prioritize_deployment_factory``  — PrioritizeDeployment  (p=0.90) → AlwaysSucceed
- ``deploy_fix_factory``             — DeployFix             (p=0.10) → AlwaysFail
- ``monitoring_requirement_factory`` — MonitoringRequirement (p=0.70) → AlwaysSucceed
- ``monitor_deployment_factory``     — MonitorDeployment     (p=1.0) → AlwaysSucceed
"""

from __future__ import annotations

import py_trees

from vultron.core.behaviors.call_out.bundles.deploy_fix import (  # noqa: F401
    DEPLOY_FIX_DETERMINISTIC,
    DeployFixCallOutBundle,
)


def _stochastic_prioritize_deployment(
    name: str,
) -> py_trees.behaviour.Behaviour:
    from vultron.demo.fuzzer.report_management.deploy_fix import (
        PrioritizeDeployment,
    )

    return PrioritizeDeployment(name)


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


DEPLOY_FIX_STOCHASTIC = DeployFixCallOutBundle(
    prioritize_deployment_factory=_stochastic_prioritize_deployment,  # type: ignore[arg-type]
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
