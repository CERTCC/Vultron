#!/usr/bin/env python
#  Copyright (c) 2023-2025 Carnegie Mellon University and Contributors.
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
"""Fix deployment fuzzer nodes for the Vultron demo layer.

This module provides probabilistic stub ``py_trees`` behaviour nodes for the
fix deployment sub-workflow within Report Management (``DeployFixBt``).  Each
node represents an external-dependency touchpoint — a human decision,
environmental check, or system integration hook — that will eventually be
replaced by production logic.

Nodes are built on the probabilistic base types in
``vultron.demo.fuzzer.base`` and satisfy BT-16-003 (named integration-point
nodes with semantic docstrings) and BT-16-005 (automation-potential
categorization).

References
----------
- Source: ``vultron/bt/report_management/fuzzer/deploy_fix.py``
- Spec: ``specs/behavior-tree-integration.yaml`` BT-16-003, BT-16-004, BT-16-005
- Notes: ``notes/bt-fuzzer-nodes-report-management.md``
"""

from __future__ import annotations

from vultron.demo.fuzzer.base import (
    AlmostAlwaysFail,
    AlmostAlwaysSucceed,
    AlwaysSucceed,
    OftenSucceed,
    UsuallyFail,
    UsuallySucceed,
)
from vultron.demo.fuzzer.call_out_point import EvaluatorCallOutPoint


class NoNewDeploymentInfo(UsuallySucceed):
    """Check whether any new deployment information has arrived.

    Semantic function:
        Condition — check whether any new information about the deployment
        state of a fix or mitigation has arrived since the last evaluation.
        In most cases there will be no new information, so this condition
        succeeds, avoiding unnecessary re-evaluation.  In production this
        could be implemented as an event subscription or a case-metadata
        timestamp comparison.

    Input category: Environmental check / Human decision.

    Success probability: 0.75 (``UsuallySucceed``).

    Automation potential: **High** — event subscription on the case record
    or metadata timestamp comparison; fully automatable without human
    involvement.
    """


class PrioritizeDeployment(EvaluatorCallOutPoint, AlmostAlwaysSucceed):
    """Assign priority to deploying the available fix or mitigation.

    Semantic function:
        Action — prompt a human or invoke a policy engine to assign a
        deployment priority for the available fix or mitigation.  In
        production this would typically involve a change-management system
        or SSVC-based prioritization workflow.  The fuzzer models the
        overwhelmingly common case where prioritization succeeds.

    Blackboard contract (BT-18-001):
      Input keys:  (none — evaluates case context from caller's DataLayer)
      Output keys: deployment_priority_verdict: str  (SUCCESS only)

    Input category: Human decision.

    Success probability: 0.90 (``AlmostAlwaysSucceed``).

    Automation potential: **Medium** — SSVC deployment status and
    environmental scoring can drive an automated priority recommendation;
    final approval for high-impact changes typically requires human sign-off.
    """

    output_keys = {"deployment_priority_verdict": str}


class MitigationDeployed(UsuallyFail):
    """Check whether a mitigation has already been deployed.

    Semantic function:
        Condition — check whether an interim mitigation (workaround, network
        control, configuration change) is currently active for the
        vulnerability.  In production this is typically a status query against
        the case record or a configuration-management database.  Fails most
        of the time to reflect that mitigations are not yet deployed in the
        typical workflow step.

    Input category: Environmental check.

    Success probability: 0.25 (``UsuallyFail``).

    Automation potential: **High** — configuration-management database (CMDB)
    or asset-inventory API queries can confirm mitigation status without
    human involvement.
    """


class MitigationAvailable(OftenSucceed):
    """Check whether a mitigation option is available to deploy.

    Semantic function:
        Condition — check whether an interim mitigation (e.g., a workaround,
        firewall rule, or configuration change) has been identified and is
        ready to be applied.  Succeeds more often than not to reflect that
        mitigations are typically available when this node is reached.

    Input category: Environmental check.

    Success probability: 0.70 (``OftenSucceed``).

    Automation potential: **Medium** — known workarounds and mitigations can
    be catalogued in the case record and queried automatically; evaluating
    applicability to a specific environment may require human judgment.
    """


class DeployMitigation(EvaluatorCallOutPoint, UsuallySucceed):
    """Deploy the available mitigation for the vulnerability.

    Semantic function:
        Action — apply the identified mitigation to the affected system or
        environment.  In production this would typically be a prompt for
        a system administrator or an automated remediation workflow
        (e.g., applying a firewall rule via an API).  Succeeds most of
        the time to model the common case where mitigation deployment
        proceeds without issues.

    Blackboard contract (BT-18-001):
      Input keys:  (none — evaluates mitigation context from caller's DataLayer)
      Output keys: deploy_mitigation_verdict: str  (SUCCESS only)

    Input category: System integration / Human decision.

    Success probability: 0.75 (``UsuallySucceed``).

    Automation potential: **Medium** — standard mitigations with
        well-defined procedures (e.g., network-level controls) can be
        automated via infrastructure APIs; complex environment-specific
        mitigations typically require human coordination.
    """

    output_keys = {"deploy_mitigation_verdict": str}


class MonitoringRequirement(EvaluatorCallOutPoint, OftenSucceed):
    """Determine whether deployment monitoring is required by policy.

    Semantic function:
        Condition — evaluate whether it is necessary to actively monitor
        the deployment of the fix or mitigation according to organizational
        policy.  In production this is typically a policy lookup or a
        configuration check.  Succeeds about 70 % of the time to reflect
        that monitoring is commonly required but not universal.

    Blackboard contract (BT-18-001):
      Input keys:  (none — evaluates case and policy context from caller's DataLayer)
      Output keys: monitoring_requirement_verdict: str  (SUCCESS only)

    Input category: Environmental check / Policy.

    Success probability: 0.70 (``OftenSucceed``).

    Automation potential: **High** — policy-driven checks (e.g., "monitor
    all critical-severity deployments") are fully automatable; rule-based
    policy engines can evaluate this condition without human input.
    """

    output_keys = {"monitoring_requirement_verdict": str}


class MonitorDeployment(AlwaysSucceed):
    """Monitor the ongoing deployment of the fix or mitigation.

    Semantic function:
        Action — perform active monitoring of the deployment process to
        ensure the fix or mitigation is being applied correctly and
        completely.  In production this would typically be a prompt for a
        human operator or an automated monitoring hook (e.g., a deployment
        pipeline status poll).  Always succeeds in simulation to model the
        assumption that monitoring itself does not fail.

    Input category: System integration.

    Success probability: 1.00 (``AlwaysSucceed``).

    Automation potential: **High** — deployment-pipeline APIs and
    configuration-management tools provide fully automatable monitoring
    hooks; human involvement is only required when anomalies are detected.
    """


class DeployFix(EvaluatorCallOutPoint, AlmostAlwaysFail):
    """Deploy the vendor fix to the affected environment.

    Semantic function:
        Action — apply the vendor-provided fix (patch, updated package, or
        firmware) to the affected system.  Fails almost always to model the
        realistic scenario where a definitive fix is not yet deployed at
        the point this node is evaluated — the workflow must fall back to
        mitigation or monitoring paths.  Infrequent successes allow the
        rest of the post-deployment workflow to be exercised.

    Blackboard contract (BT-18-001):
      Input keys:  (none — evaluates deployment context from caller's DataLayer)
      Output keys: deploy_fix_verdict: str  (SUCCESS only)

    Input category: System integration / Human decision.

    Success probability: 0.10 (``AlmostAlwaysFail``).

    Automation potential: **Medium** — patch-management systems and software
    distribution platforms can automate fix deployment for many asset
    types; complex or high-risk changes in regulated environments typically
    require human approval and change-management controls.
    """

    output_keys = {"deploy_fix_verdict": str}
