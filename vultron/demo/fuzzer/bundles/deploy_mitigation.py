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
"""STOCHASTIC call-out bundle for the mitigation deployment domain (BT-20-005, BT-23-003).

Provides the simulation-layer :data:`DEPLOY_MITIGATION_STOCHASTIC` singleton.
The bundle dataclass and DETERMINISTIC default are core concerns
(``vultron.core.behaviors.call_out.bundles.deploy_mitigation``) and are
re-exported here for backward-compatible import paths.

Ceiling/floor mapping for the DETERMINISTIC counterpart (BT-23-002):

- ``prioritize_deployment_factory``  — PrioritizeDeployment  (p=0.90) → AlwaysSucceed
- ``monitoring_requirement_factory`` — MonitoringRequirement (p=0.70) → AlwaysSucceed
- ``monitor_deployment_factory``     — MonitorDeployment     (p=1.00) → AlwaysSucceed
- ``mitigation_deployed_factory``    — MitigationDeployed    (p=0.25) → AlwaysFail
- ``mitigation_available_factory``   — MitigationAvailable   (p=0.70) → AlwaysSucceed
- ``deploy_mitigation_factory``      — DeployMitigation      (p=0.75) → AlwaysSucceed
"""

from __future__ import annotations

import py_trees

from vultron.core.behaviors.call_out.bundles.deploy_mitigation import (  # noqa: F401
    DEPLOY_MITIGATION_DETERMINISTIC,
    DeployMitigationCallOutBundle,
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


def _stochastic_monitor_deployment(name: str) -> py_trees.behaviour.Behaviour:
    from vultron.demo.fuzzer.report_management.deploy_fix import (
        MonitorDeployment,
    )

    return MonitorDeployment(name)


def _stochastic_mitigation_deployed(name: str) -> py_trees.behaviour.Behaviour:
    from vultron.demo.fuzzer.report_management.deploy_fix import (
        MitigationDeployed,
    )

    return MitigationDeployed(name)


def _stochastic_mitigation_available(
    name: str,
) -> py_trees.behaviour.Behaviour:
    from vultron.demo.fuzzer.report_management.deploy_fix import (
        MitigationAvailable,
    )

    return MitigationAvailable(name)


def _stochastic_deploy_mitigation(name: str) -> py_trees.behaviour.Behaviour:
    from vultron.demo.fuzzer.report_management.deploy_fix import (
        DeployMitigation,
    )

    return DeployMitigation(name)


DEPLOY_MITIGATION_STOCHASTIC = DeployMitigationCallOutBundle(
    prioritize_deployment_factory=_stochastic_prioritize_deployment,  # type: ignore[arg-type]
    monitoring_requirement_factory=_stochastic_monitoring_requirement,  # type: ignore[arg-type]
    monitor_deployment_factory=_stochastic_monitor_deployment,  # type: ignore[arg-type]
    mitigation_deployed_factory=_stochastic_mitigation_deployed,  # type: ignore[arg-type]
    mitigation_available_factory=_stochastic_mitigation_available,  # type: ignore[arg-type]
    deploy_mitigation_factory=_stochastic_deploy_mitigation,  # type: ignore[arg-type]
)
"""Stochastic bundle: all nodes use probabilistic fuzzer classes."""

__all__ = [
    "DeployMitigationCallOutBundle",
    "DEPLOY_MITIGATION_DETERMINISTIC",
    "DEPLOY_MITIGATION_STOCHASTIC",
]
