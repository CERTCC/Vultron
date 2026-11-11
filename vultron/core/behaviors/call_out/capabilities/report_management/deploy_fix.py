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
"""Core capability declarations for ``report_management.deploy_fix``.

Each class declares one named capability's blackboard contract as typed
ports (BT-18-012).  Its simulation node, in
``vultron.demo.fuzzer.report_management.deploy_fix``,
subclasses the declaration rather than restating it (BT-18-021).
"""

from __future__ import annotations

from py_trees.ports import PortInformation

from vultron.core.behaviors.call_out.capability import (
    ActuatorCapability,
    EvaluatorCapability,
    RetrieverCapability,
)


class NoNewDeploymentInfoCapability(RetrieverCapability):
    """Check whether any new deployment information has arrived.

    Blackboard contract (BT-18-001):
      Input keys:  (none — queries deployment-relevant data sources)
      Output keys: (none — binary result only, per BT-18-006)
      Refusal keys: call_out_refusal_reason: str  (no only)

    Store-held answer (BT-18-039): **cannot** — whether new information
    reached the deployer's own systems since the last evaluation is not
    recorded in the case file or the actor's store.
    """


class PrioritizeDeploymentCapability(EvaluatorCapability):
    """Assign priority to deploying the available fix or mitigation.

    Blackboard contract (BT-18-001):
      Input keys:  (none — evaluates case context from caller's DataLayer)
      Output keys: deployment_priority_verdict: str  (yes only)
      Refusal keys: call_out_refusal_reason: str  (no only)
    """

    OUTPUT_PORTS = {
        "deployment_priority_verdict": PortInformation(
            data_type=str, required=True
        ),
    }


class MitigationDeployedCapability(RetrieverCapability):
    """Check whether a mitigation has already been deployed.

    Blackboard contract (BT-18-001):
      Input keys:  (none — queries a CMDB for mitigation status)
      Output keys: (none — binary result only, per BT-18-006)
      Refusal keys: call_out_refusal_reason: str  (no only)

    Store-held answer (BT-18-039): **cannot** — mitigation has no case state
    bit, so no read-first guard precedes it (see
    ``DeployMitigationCallOutBundle.mitigation_deployed_factory``).
    """


class MitigationAvailableCapability(RetrieverCapability):
    """Check whether a mitigation option is available to deploy.

    Blackboard contract (BT-18-001):
      Input keys:  (none — queries a mitigation catalogue)
      Output keys: (none — binary result only, per BT-18-006)
      Refusal keys: call_out_refusal_reason: str  (no only)

    Store-held answer (BT-18-039): **cannot** — the case file records no
    mitigation, so no read-first guard precedes it (see
    ``DeployMitigationCallOutBundle.mitigation_available_factory``).
    """


class DeployMitigationCapability(EvaluatorCapability):
    """Deploy the available mitigation for the vulnerability.

    Blackboard contract (BT-18-001):
      Input keys:  (none — evaluates mitigation context from caller's DataLayer)
      Output keys: deploy_mitigation_verdict: str  (yes only)
      Refusal keys: call_out_refusal_reason: str  (no only)
    """

    OUTPUT_PORTS = {
        "deploy_mitigation_verdict": PortInformation(
            data_type=str, required=True
        ),
    }


class MonitoringRequirementCapability(EvaluatorCapability):
    """Determine whether deployment monitoring is required by policy.

    Blackboard contract (BT-18-001):
      Input keys:  (none — evaluates case and policy context from caller's DataLayer)
      Output keys: monitoring_requirement_verdict: str  (yes only)
      Refusal keys: call_out_refusal_reason: str  (no only)
    """

    OUTPUT_PORTS = {
        "monitoring_requirement_verdict": PortInformation(
            data_type=str, required=True
        ),
    }


class MonitorDeploymentCapability(ActuatorCapability):
    """Monitor the ongoing deployment of the fix or mitigation.

    Blackboard contract (BT-18-001):
      Input keys:  (none — trigger only; deployment context from construction time)
      Output keys: (none — side effect: trigger monitoring hooks, alert on anomalies)
      Refusal keys: call_out_refusal_reason: str  (no only)
    """


class DeployFixCapability(EvaluatorCapability):
    """Deploy the vendor fix to the affected environment.

    Blackboard contract (BT-18-001):
      Input keys:  (none — evaluates deployment context from caller's DataLayer)
      Output keys: deploy_fix_verdict: str  (yes only)
      Refusal keys: call_out_refusal_reason: str  (no only)
    """

    OUTPUT_PORTS = {
        "deploy_fix_verdict": PortInformation(data_type=str, required=True),
    }


__all__ = [
    "DeployFixCapability",
    "DeployMitigationCapability",
    "MitigationAvailableCapability",
    "MitigationDeployedCapability",
    "MonitorDeploymentCapability",
    "MonitoringRequirementCapability",
    "NoNewDeploymentInfoCapability",
    "PrioritizeDeploymentCapability",
]
