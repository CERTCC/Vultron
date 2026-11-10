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
``vultron.demo.fuzzer.base`` and satisfy BT-16-003 and BT-16-007 (named
integration-point nodes with semantic docstrings) and BT-16-005 (automation-potential
categorization).

References
----------
- Source: ``vultron/bt/report_management/fuzzer/prioritize_report.py``
- Spec: ``specs/behavior-tree-integration.yaml`` BT-16-003, BT-16-004, BT-16-005
- Catalog: ``docs/developer/reference/bt-fuzzer/rm-prioritization.md``
"""

from __future__ import annotations

from typing import ClassVar

from vultron.core.behaviors.call_out.answer import (
    CallOutContract,
)
from vultron.demo.fuzzer.base import (
    AlmostAlwaysSucceed,
    AlwaysSucceed,
    ProbablySucceed,
    UsuallySucceed,
)
from vultron.demo.fuzzer.call_out_point import (
    ActuatorCallOutPoint,
    EvaluatorCallOutPoint,
    RetrieverCallOutPoint,
)


class NoNewPrioritizationInfo(RetrieverCallOutPoint, ProbablySucceed):
    """Check whether new information has arrived that should trigger
    re-prioritization of the report.

    Semantic function:
        Condition — ask the sources of prioritization-relevant information
        (SSVC scoring data, CVSS score updates, threat intelligence) whether
        anything new has arrived that should trigger re-prioritization of the
        report.  Succeeds more often than not to avoid redundant re-evaluation
        cycles.  A binary Retriever: the tree asks on its own tick, so this is
        a call-out, not a Sentinel (BT-18-006, BT-18-013).

    Store-held answer (BT-18-039): **cannot** — whether new information
    reached the outside sources since the last evaluation is not recorded
    in the case file or the actor's store.

    Blackboard contract (BT-18-001):
      Input keys:  (none — queries prioritization-relevant information sources)
      Output keys: (none — binary result only, per BT-18-006)

    Input category: Environmental check.

    Success probability: 0.67 (``ProbablySucceed``).

    Automation potential: **High** — metadata timestamp or case-update
    event check; fully automatable.
    """


class EnoughPrioritizationInfo(EvaluatorCallOutPoint, UsuallySucceed):
    """Determine whether sufficient context exists to make an accept/defer
    decision.

    Semantic function:
        Condition — determine whether there is enough context to make an
        accept/defer decision.  Insufficient info triggers a gathering
        phase.

    Blackboard contract (BT-18-001):
      Input keys:  (none — evaluates available context from caller's DataLayer)
      Output keys: enough_prioritization_info_verdict: str  (yes only)

    Input category: Human decision / Environmental check.

    Success probability: 0.75 (``UsuallySucceed``).

    Automation potential: **Medium** — availability of SSVC decision-point
    data (e.g., CVSS score, exploitation status) is automatable; the
    sufficiency judgment for a final accept/defer decision usually
    involves human analyst review.
    """

    contract: ClassVar[CallOutContract] = CallOutContract(
        outputs={"enough_prioritization_info_verdict": str}
    )


class GatherPrioritizationInfo(RetrieverCallOutPoint, AlmostAlwaysSucceed):
    """Collect additional context needed to support a prioritization decision.

    Semantic function:
        Action — collect additional context needed to support a
        prioritization decision (e.g., severity scores, asset inventory,
        threat landscape data).  Succeeds almost always in simulation to
        keep the workflow progressing.

    Store-held answer (BT-18-039): **cannot** — it collects outside
    context, such as scores and threat data, that the case file does not
    record.

    Blackboard contract (BT-18-001):
      Input keys:  (none — queries external sources directly)
      Output keys: prioritization_info_gathered: str  (yes only)

    Input category: System integration / Human analyst research.

    Success probability: 0.90 (``AlmostAlwaysSucceed``).

    Automation potential: **Medium** — fetching CVSS scores, EPSS
    scores, NVD data, and asset inventory is fully automatable via APIs;
    analyst interpretation and gap-filling still requires human
    involvement.
    """

    contract: ClassVar[CallOutContract] = CallOutContract(
        outputs={"prioritization_info_gathered": str}
    )


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


class EvaluateCasePriority(EvaluatorCallOutPoint, AlwaysSucceed):
    """Evaluate whether to engage or defer a case using prioritization policy.

    Semantic function:
        Decision — evaluate case priority to determine whether the local
        actor should engage (accept) or defer the case.  This is the SSVC
        integration seam: a production backend replaces this stub with a
        real priority evaluator.

    Blackboard contract (BT-18-001):
      Input keys:  (none — evaluates case context from construction time)
      Output keys: evaluate_case_priority_verdict: str  (yes only)

    Input category: Human decision / Policy engine.

    Success probability: 1.00 (``AlwaysSucceed``): always engage in the
    stochastic simulation (SSVC deferred — PROTO-05-001).

    Automation potential: **High** — SSVC scoring, asset inventory lookups,
    and policy-based engage/defer decisions are fully automatable.
    """

    contract: ClassVar[CallOutContract] = CallOutContract(
        outputs={"evaluate_case_priority_verdict": str}
    )


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
