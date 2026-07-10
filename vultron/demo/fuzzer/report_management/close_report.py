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
"""Report closure fuzzer nodes for the Vultron demo layer.

This module provides probabilistic stub ``py_trees`` behaviour nodes for the
report closure sub-workflow within Report Management.  Each node represents an
external-dependency touchpoint — a human decision, policy check, or system
integration hook — that will eventually be replaced by production logic.

Nodes are built on the probabilistic base types in
``vultron.demo.fuzzer.base`` and satisfy BT-16-003 (named integration-point
nodes with semantic docstrings) and BT-16-005 (automation-potential
categorization).

References
----------
- Source: ``vultron/bt/report_management/fuzzer/close_report.py``
- Spec: ``specs/behavior-tree-integration.yaml`` BT-16-003, BT-16-004, BT-16-005
- Notes: ``notes/bt-fuzzer-nodes-report-management.md``
"""

from __future__ import annotations

from vultron.demo.fuzzer.base import AlwaysSucceed, UsuallyFail
from vultron.demo.fuzzer.call_out_point import EvaluatorCallOutPoint


class OtherCloseCriteriaMet(EvaluatorCallOutPoint, UsuallyFail):
    """Check whether site-specific closure criteria have been satisfied.

    Semantic function:
        Condition — evaluate whether organizational or case-specific criteria
        beyond the standard CVD workflow conditions have been met, allowing the
        report to be closed.  In production this is typically a human decision
        or a check of case state against a configurable set of site-specific
        policies (e.g., all stakeholders notified, public advisory published,
        or internal QA completed).  The fuzzer models the uncommon case where
        additional criteria are satisfied, reflecting that extra criteria are
        not routinely met.

    Blackboard contract (BT-18-001):
      Input keys:  (none — evaluates case-specific criteria from caller's DataLayer)
      Output keys: other_close_criteria_met_verdict: str  (SUCCESS only)

    Input category: Human decision / policy.

    Success probability: 0.25 (``UsuallyFail``).

    Automation potential: **Low** — closure criteria are highly
    organization-specific and often context-dependent; encoding all
    possible criteria as a general policy rule is impractical, and the
    final closure decision usually benefits from human confirmation.
    """

    output_keys = {"other_close_criteria_met_verdict": str}


class PreCloseAction(AlwaysSucceed):
    """Perform required actions immediately before closing the report.

    Semantic function:
        Action integration hook — execute any mandatory pre-closure tasks such
        as quality-assurance checks, notification dispatches, or bookkeeping
        updates that must be completed before the report transitions to the
        Closed state.  Must be idempotent in production to support safe retries.

    Input category: System integration.

    Success probability: 1.00 (``AlwaysSucceed``).

    Automation potential: **High** — standard pre-close actions (e.g., marking
    tasks complete, archiving related artifacts, sending closure notifications)
    are fully automatable via API integrations; no human involvement is
    required once the pre-close checklist is defined.
    """
