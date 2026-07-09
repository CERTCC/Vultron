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
"""Report prioritization fuzzer nodes for the Vultron demo layer.

This module provides probabilistic stub ``py_trees`` behaviour nodes for the
Report Management prioritization workflow (``RMPrioritizeBt``).  Each node
represents an external-dependency touchpoint — a human decision,
environmental check, or system integration hook — that will eventually be
replaced by production logic.

Nodes are built on the probabilistic base types in
``vultron.demo.fuzzer.base`` and satisfy BT-16-003 (named integration-point
nodes with semantic docstrings) and BT-16-005 (automation-potential
categorization).

References
----------
- Source: ``vultron/bt/report_management/fuzzer/prioritize_report.py``
- Spec: ``specs/behavior-tree-integration.yaml`` BT-16-003, BT-16-004, BT-16-005
- Notes: ``notes/bt-fuzzer-nodes-report-management.md``
"""

from __future__ import annotations

from vultron.demo.fuzzer.base import (
    AlmostAlwaysSucceed,
    AlwaysSucceed,
    ProbablySucceed,
    UsuallySucceed,
)
from vultron.demo.fuzzer.call_out_point import ActuatorCallOutPoint


class NoNewPrioritizationInfo(ProbablySucceed):
    """Check whether new information has arrived that should trigger
    re-prioritization of the report.

    Semantic function:
        Condition — check whether new information has arrived that
        should trigger re-prioritization of the report.  Succeeds more
        often than not to avoid redundant re-evaluation cycles.

    Input category: Environmental check / Human decision.

    Success probability: 0.67 (``ProbablySucceed``).

    Automation potential: **High** — metadata timestamp or case-update
    event check; fully automatable.
    """


class EnoughPrioritizationInfo(UsuallySucceed):
    """Determine whether sufficient context exists to make an accept/defer
    decision.

    Semantic function:
        Condition — determine whether there is enough context to make an
        accept/defer decision.  Insufficient info triggers a gathering
        phase.

    Input category: Human decision / Environmental check.

    Success probability: 0.75 (``UsuallySucceed``).

    Automation potential: **Medium** — availability of SSVC decision-point
    data (e.g., CVSS score, exploitation status) is automatable; the
    sufficiency judgment for a final accept/defer decision usually
    involves human analyst review.
    """


class GatherPrioritizationInfo(AlmostAlwaysSucceed):
    """Collect additional context needed to support a prioritization decision.

    Semantic function:
        Action — collect additional context needed to support a
        prioritization decision (e.g., severity scores, asset inventory,
        threat landscape data).  Succeeds almost always in simulation to
        keep the workflow progressing.

    Input category: System integration / Human analyst research.

    Success probability: 0.90 (``AlmostAlwaysSucceed``).

    Automation potential: **Medium** — fetching CVSS scores, EPSS
    scores, NVD data, and asset inventory is fully automatable via APIs;
    analyst interpretation and gap-filling still requires human
    involvement.
    """


class OnAccept(ActuatorCallOutPoint, AlwaysSucceed):
    """Execute site-specific tasks when a report is accepted.

    Semantic function:
        Action integration hook — trigger notifications, initialize the
        case workflow, assign to a team, and update case status when the
        report is accepted.  Must be idempotent in production.

    Blackboard contract (BT-18-001):
      Input keys:  (none — trigger only; case context from construction time)
      Output keys: (none — side effect: notify stakeholders, initialize workflow)

    Input category: System integration.

    Success probability: 1.00 (``AlwaysSucceed``).

    Automation potential: **High** — stakeholder notifications, workflow
    initialization, and state updates are all automatable via
    integration APIs.
    """


class OnDefer(ActuatorCallOutPoint, AlwaysSucceed):
    """Execute site-specific tasks when a report is deferred.

    Semantic function:
        Action integration hook — notify stakeholders, schedule a
        follow-up, and update the case status when the report is
        deferred.  Must be idempotent in production.

    Blackboard contract (BT-18-001):
      Input keys:  (none — trigger only; case context from construction time)
      Output keys: (none — side effect: notify stakeholders, schedule follow-up)

    Input category: System integration.

    Success probability: 1.00 (``AlwaysSucceed``).

    Automation potential: **High** — stakeholder notifications, follow-up
    scheduling, and state updates are all automatable via integration
    APIs.
    """
